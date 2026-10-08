"""Daily entrypoint: draft export listings for Japanese goods bought after sale.

For every product that Japan-located sellers are actually selling (search
phrases in Config.export_listing_queries, Beyblade X by default):

1. the price is set just under the cheapest new, Japan-shipped competitor
   for the exact same JAN;
2. the cheapest new, in-stock offer on Yahoo!ショッピング for that JAN must
   leave at least EXPORT_MIN_PROFIT_JPY at that price, with the same
   pack-size checks the weekly research applies;
3. the listing is built from the eBay catalog product for that JAN — its
   title, item specifics and eBay's own stock photos — never from another
   seller's photos. Products without a single catalog match are skipped.

Each draft opens a GitHub issue; `/approve` publishes it (export_commands.py).

Nothing is bought here. The seller buys after an eBay sale, receives and
inspects the item, and ships it — see export_sync.py and docs/SETUP.md §7.

Run via: python -m ebay_automation.export_listing
"""
from __future__ import annotations

import dataclasses
import datetime
import logging
import re
import os
import urllib.parse
from dataclasses import dataclass

import requests

from . import export_research, export_state, yahoo_shopping
from .config import Config, load_config
from .ebay_client import EbayApiError, EbayClient
from .export_research import ProductOpportunity
from .github_client import GithubClient
from .research import _browse_get, _listing_age_days

log = logging.getLogger(__name__)

_JP_NEW = "itemLocationCountry:JP,conditionIds:{1000},buyingOptions:{FIXED_PRICE}"

# Toys whose box is far bigger than a booster or a single car: a Beyblade
# stadium or a Plarail starter set ships as "large", not at the small-parcel
# rate the first dry run priced the BX-10 stadium at.
_SIZE_RULES = [
    (re.compile(r"stadium|playset|play set|garage|station|plarail|track set|rail set|starter set|bundle|deluxe", re.I), "large"),
    (re.compile(r"\bset\b|launcher|kit|tamagotchi|\bbox\b", re.I), "medium"),
]


def size_for(title: str, config: Config) -> str:
    """Shipping size class from the product title; the configured default otherwise."""
    for pattern, size in _SIZE_RULES:
        if pattern.search(title or ""):
            return size
    return config.export_listing_size


@dataclass
class Candidate:
    jan: str
    category_id: str
    units_per_month: float
    competitor_price: float
    price: float
    domestic: yahoo_shopping.DomesticOffer
    profit_jpy: int
    margin: float
    size: str = "small"
    title: str = ""

    @property
    def expected_monthly_profit_jpy(self) -> int:
        return round(self.profit_jpy * self.units_per_month)


def _total_usd(summary: dict) -> float | None:
    price = summary.get("price") or {}
    if price.get("currency") != "USD":
        return None
    total = float(price.get("value") or 0)
    ship = ((summary.get("shippingOptions") or [{}])[0].get("shippingCost") or {})
    if ship.get("currency") == "USD":
        total += float(ship.get("value") or 0)
    return total or None


def _selling_jans(config: Config) -> dict[str, dict]:
    """JAN -> fastest sales rate and category among Japan-shipped listings."""
    found: dict[str, dict] = {}
    seen: set[str] = set()
    for query in config.export_listing_queries:
        search = _browse_get("/item_summary/search", config, {"q": query, "limit": 50, "filter": _JP_NEW})
        for summary in search.get("itemSummaries", []) or []:
            if summary["itemId"] in seen:
                continue
            seen.add(summary["itemId"])
            try:
                item = _browse_get(f"/item/{urllib.parse.quote(summary['itemId'], safe='')}", config)
            except requests.HTTPError:
                continue
            jan = export_research.valid_jan(item.get("gtin"))
            sold = ((item.get("estimatedAvailabilities") or [{}])[0]).get("estimatedSoldQuantity") or 0
            if not jan or sold <= 0 or export_research._BUNDLE_RE.search(item.get("title", "")):
                continue
            rate = sold / _listing_age_days(item.get("itemCreationDate")) * 30
            best = found.get(jan)
            if best is None or rate > best["rate"]:
                found[jan] = {"rate": rate, "category_id": item.get("categoryId", ""), "title": item.get("title", "")}
    return found


def _cheapest_competitor(jan: str, config: Config) -> float | None:
    search = _browse_get("/item_summary/search", config, {"gtin": jan, "limit": 20, "filter": _JP_NEW})
    prices = [p for p in (_total_usd(s) for s in search.get("itemSummaries", []) or []) if p]
    return min(prices) if prices else None


def evaluate(jan: str, info: dict, config: Config) -> Candidate | None:
    competitor = _cheapest_competitor(jan, config)
    if competitor is None:
        return None
    price = round(competitor - config.export_undercut_usd_cents / 100, 2)
    offer = yahoo_shopping.cheapest_new_offer(jan, config)
    if offer is None:
        return None
    size = size_for(info["title"], config)
    computed = export_research.profit_jpy(price, "USD", offer.price_jpy, offer.free_shipping, size, config)
    if computed is None:
        return None
    profit, margin = computed
    probe = ProductOpportunity(
        title=info["title"], ebay_url="", jan=jan, sale_price=price, currency="USD", units_per_month=info["rate"]
    )
    if profit < config.export_min_profit_jpy or export_research._mismatch_reason(probe, offer, config):
        return None
    return Candidate(
        jan=jan,
        category_id=info["category_id"],
        units_per_month=round(info["rate"], 2),
        competitor_price=competitor,
        price=price,
        domestic=offer,
        profit_jpy=profit,
        margin=round(margin, 3),
        size=size,
        title=info["title"],
    )


def find_candidates(config: Config, skip_jans: set[str]) -> list[Candidate]:
    candidates = []
    for jan, info in _selling_jans(config).items():
        if jan in skip_jans:
            continue
        try:
            candidate = evaluate(jan, info, config)
        except requests.HTTPError:
            log.exception("Evaluating JAN %s failed; skipping.", jan)
            continue
        if candidate:
            candidates.append(candidate)
    candidates.sort(key=lambda c: c.expected_monthly_profit_jpy, reverse=True)
    return candidates


def _aspects(product: dict) -> dict[str, list[str]]:
    return {
        a["localizedName"]: a.get("localizedValues", [])[:1]
        for a in product.get("aspects", []) or []
        if a.get("localizedName") and a.get("localizedValues")
    }


def _images(product: dict) -> list[str]:
    urls = [(product.get("image") or {}).get("imageUrl")]
    urls += [img.get("imageUrl") for img in product.get("additionalImages", []) or []]
    return [u for u in urls if u and u.startswith("https://")][:12]


def description(title: str, config: Config) -> str:
    return (
        f"<p><b>{title}</b></p>"
        "<p>Brand new and genuine, bought from an authorised retailer in Japan (Japanese domestic version). "
        "Every item is inspected and packed by hand before it leaves us.</p>"
        f"<p>Ships from Japan with tracking within {config.export_handling_days} business days. "
        "Import duties and taxes for your country may be collected by eBay at checkout.</p>"
    )


def put_listing(
    config: Config, ebay: EbayClient, sku: str, product: dict, category_id: str, price: float
) -> str:
    """Create the inventory item and its unpublished offer; returns the offer ID."""
    body = description(product["title"], config)
    ebay.create_or_replace_inventory_item(
        sku,
        {
            "availability": {"shipToLocationAvailability": {"quantity": 1}},
            "condition": "NEW",
            "product": {**product, "description": body},
        },
    )
    return ebay.create_offer(
        {
            "sku": sku,
            "marketplaceId": config.ebay_marketplace_id,
            "format": "FIXED_PRICE",
            "availableQuantity": 1,
            "categoryId": category_id,
            "listingDescription": body,
            "pricingSummary": {"price": {"value": f"{price:.2f}", "currency": "USD"}},
            "merchantLocationKey": config.export_merchant_location_key,
            "listingPolicies": {
                "fulfillmentPolicyId": config.export_fulfillment_policy_id,
                "paymentPolicyId": config.ebay_payment_policy_id,
                "returnPolicyId": config.ebay_return_policy_id,
            },
        }
    )


def candidate_entry(candidate: Candidate, title: str, status: str, config: Config) -> dict:
    return {
        "sku": export_state.sku_for(candidate.jan),
        "jan": candidate.jan,
        "title": title,
        "status": status,
        "category_id": candidate.category_id,
        "price_usd": candidate.price,
        "competitor_price_usd": candidate.competitor_price,
        "units_per_month": candidate.units_per_month,
        "source_price_jpy": candidate.domestic.price_jpy,
        "source_url": candidate.domestic.url,
        "source_name": candidate.domestic.name,
        "expected_profit_jpy": candidate.profit_jpy,
        "margin": candidate.margin,
        # The larger of what the competitor's title and the catalog title imply.
        "size": max(candidate.size, size_for(title, config), key=["small", "medium", "large"].index),
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
    }


def create_draft(config: Config, ebay: EbayClient, candidate: Candidate, product: dict) -> dict:
    title = product.get("title", "")[:80]
    images = _images(product)
    if not images:
        raise ValueError(f"catalog product {product.get('epid')} has no stock photo")
    entry = candidate_entry(candidate, title, "pending_approval", config)
    entry["epid"] = product.get("epid")
    entry["ebay_offer_id"] = put_listing(
        config,
        ebay,
        entry["sku"],
        {"title": title, "epid": product.get("epid"), "imageUrls": images, "aspects": _aspects(product)},
        candidate.category_id,
        candidate.price,
    )
    return entry


def photo_request_body(entry: dict) -> str:
    lines = [
        f"## {entry['title']}",
        "",
        "利益が出る商品ですが、eBayカタログに公式写真がないため、**自分で撮った写真**で出品します。",
        "",
        "| 項目 | 値 |",
        "|---|---|",
        f"| 販売価格 | ${entry['price_usd']:.2f}（日本発送の最安 ${entry['competitor_price_usd']:.2f} より少し下） |",
        f"| 今の仕入れ値 | [¥{entry['source_price_jpy']:,}]({entry['source_url']})（Yahoo!ショッピング最安・新品・在庫あり） |",
        f"| 想定利益 / 個 | ¥{entry['expected_profit_jpy']:,}（利益率 {entry['margin']:.0%}・送料は{entry['size']}サイズで計算） |",
        f"| 同じ商品の売れ行き | 月 {entry['units_per_month']:.1f} 個（日本発送の出品1件あたり） |",
        f"| JAN | {entry['jan']} |",
        "",
        "### やること",
        "1. 上の仕入れ先で **1個だけ** 買う（これが最初の在庫になります）",
        "2. 届いたら3〜8枚撮る: 箱の正面・背面・側面、JAN/型番が見える面。白っぽい背景・明るい場所で",
        "3. このIssueに写真をドラッグ＆ドロップして、同じコメントに `/photos` と書いて送信",
        "",
        "→ その写真でeBayに出品します（タイトルは上のものを使用。変えたい場合は `/photos` の次の行に `title: 新しいタイトル`）。",
        "手元の1個が売れた後は、同じ写真のまま受注後仕入れで販売を続けます。",
        "",
        "見送る場合は `/reject`。他の出品者やメーカーの写真は使いません（eBay規約・著作権のため）。",
    ]
    return "\n".join(lines) + "\n"


def issue_body(entry: dict, image_url: str | None) -> str:
    lines = [
        f"## {entry['title']}",
        "",
        f"![product]({image_url})" if image_url else "",
        "",
        "| 項目 | 値 |",
        "|---|---|",
        f"| 販売価格 | ${entry['price_usd']:.2f}（日本発送の最安 ${entry['competitor_price_usd']:.2f} より少し下） |",
        f"| 現在の仕入れ値 | [¥{entry['source_price_jpy']:,}]({entry['source_url']})（Yahoo!ショッピング最安・新品・在庫あり） |",
        f"| 想定利益 / 個 | ¥{entry['expected_profit_jpy']:,}（利益率 {entry['margin']:.0%}） |",
        f"| 同じ商品の売れ行き | 月 {entry['units_per_month']:.1f} 個（日本発送の出品1件あたり） |",
        f"| JAN / ePID | {entry['jan']} / {entry['epid']} |",
        "",
        "写真と商品情報は eBay カタログ（eBay の公式ストック写真）から取っています。",
        "",
        "- `/approve` … eBay に公開します",
        "- `/reject` … 下書きを削除します",
        "",
        "公開後は仕入れ先の在庫を2時間ごとに確認し、在庫切れや利益割れのときは自動で在庫0（購入不可）にします。",
    ]
    return "\n".join(lines) + "\n"


def _row(entry: dict) -> str:
    return (
        f"| {entry['title'][:60]} | ${entry['price_usd']:.2f} (競合 ${entry['competitor_price_usd']:.2f}) "
        f"| [¥{entry['source_price_jpy']:,}]({entry['source_url']}) | ¥{entry['expected_profit_jpy']:,} "
        f"| {entry['size']} | {entry['units_per_month']:.1f} |"
    )


def _write_summary(found: int, rows: list[str], photo_rows: list[str]) -> None:
    header = ["| 商品 | 販売価格 | 今の仕入れ値 | 利益/個 | 送料サイズ | 月販/出品 |", "|---|---|---|---|---|---|"]
    report = "\n".join(
        [
            "## 輸出出品の候補（DRY RUN・下書きもIssueも作っていません）",
            "",
            f"利益ラインを超えた候補: {found} 件",
            "",
            f"### eBayカタログ写真で出品できるもの（{len(rows)} 件）",
            "",
            *(header + rows if rows else ["なし"]),
            "",
            f"### 自分で撮った写真が必要なもの（{len(photo_rows)} 件・本番では[輸出・写真待ち]Issueになります）",
            "",
            *(header + photo_rows if photo_rows else ["なし"]),
        ]
    ) + "\n"
    print(report)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(report)


def run(config: Config | None = None) -> int:
    config = config or load_config()
    config.require("ebay_app_id", "ebay_cert_id", "ebay_refresh_token", "yahoo_app_id")
    missing = [
        n for n in ("export_merchant_location_key", "export_fulfillment_policy_id",
                    "ebay_payment_policy_id", "ebay_return_policy_id")
        if not getattr(config, n)
    ]
    if missing and not config.dry_run:
        # Not set up yet (docs/SETUP.md §7): a scheduled run should not go
        # red every day until then, so fall back to showing candidates.
        log.warning("Export listing not configured (%s); running as a dry run.", ", ".join(missing))
        config = dataclasses.replace(config, dry_run=True)
    listings = export_state.load_listings()
    # Rejected products stay skipped, so a /reject is not undone the next morning.
    active = {
        e["jan"] for e in listings.values()
        if e.get("status") in ("pending_approval", "published", "needs_photos", "rejected")
    }
    candidates = find_candidates(config, active)
    log.info("%d export candidates clear the profit floor", len(candidates))

    ebay = EbayClient(config)
    github = None if config.dry_run else GithubClient(config)
    created = 0
    photo_requests = 0
    dry_rows: list[str] = []
    photo_rows: list[str] = []
    for candidate in candidates:
        if created >= config.export_daily_listing_quota and photo_requests >= config.export_daily_photo_requests:
            break
        try:
            product = ebay.find_catalog_product(candidate.jan)
        except EbayApiError:
            log.exception("Catalog lookup failed for %s", candidate.jan)
            continue
        if product is None:
            if photo_requests >= config.export_daily_photo_requests:
                continue
            photo_requests += 1
            entry = candidate_entry(candidate, candidate.title[:80], "needs_photos", config)
            if config.dry_run:
                photo_rows.append(_row(entry))
                continue
            issue = github.create_issue(
                title=f"[輸出・写真待ち] {entry['title'][:60]} ({entry['sku']})",
                body=photo_request_body(entry),
                labels=["export-photos", "ebay-automation"],
            )
            entry["issue_number"] = issue["number"]
            export_state.save_listing(entry["sku"], entry)
            log.info("Opened photo request #%s for %s", issue["number"], entry["sku"])
            continue
        if created >= config.export_daily_listing_quota:
            continue
        if config.dry_run:
            dry_rows.append(_row(candidate_entry(candidate, product.get("title", "")[:80], "", config)))
            created += 1
            continue
        try:
            entry = create_draft(config, ebay, candidate, product)
        except (EbayApiError, ValueError):
            log.exception("Drafting JAN %s failed; skipping.", candidate.jan)
            continue
        issue = github.create_issue(
            title=f"[輸出・承認待ち] {entry['title'][:60]} ({entry['sku']})",
            body=issue_body(entry, (_images(product) or [None])[0]),
            labels=["export-approval", "ebay-automation"],
        )
        entry["issue_number"] = issue["number"]
        export_state.save_listing(entry["sku"], entry)
        created += 1
        log.info("Opened export approval issue #%s for %s", issue["number"], entry["sku"])
    if config.dry_run:
        _write_summary(len(candidates), dry_rows, photo_rows)
    log.info("Created %d export drafts.", created)
    return created


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run()
