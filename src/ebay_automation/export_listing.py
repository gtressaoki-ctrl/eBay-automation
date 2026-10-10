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
from .pipeline_research import listing_url
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


# Another seller's title often carries their own sales wording; a pre-order
# label in particular would promise a release-date listing we don't run.
_SELLER_WORDS = re.compile(
    r"\b(pre-?sale|pre-?order|in stock|ships? (fast|today|now)|fast shipping|free shipping|brand new|new|"
    r"from japan|japan seller|authentic|genuine|limited stock|hot)\b[!.,:]*",
    re.I,
)


def clean_title(title: str) -> str:
    """A competitor's title reduced to the product itself, for photo listings."""
    cleaned = re.sub(r"\s{2,}", " ", _SELLER_WORDS.sub(" ", title or "")).strip(" -|/")
    return f"{cleaned} Japan"[:80] if "japan" not in cleaned.lower() else cleaned[:80]


# Sweep categories whose typical item does not fit a small parcel. Titles
# rarely say how big a rice cooker or a guitar is, so the category sets a
# floor under whatever size_for() reads from the title.
_CATEGORY_SIZE_FLOOR = {
    "293": "medium", "625": "medium", "11700": "medium", "58058": "medium", "870": "medium",
    "11450": "medium", "550": "medium", "20081": "medium", "888": "medium",
    "619": "large",
}
_SIZES = ["small", "medium", "large"]


def larger(a: str, b: str) -> str:
    return max(a, b, key=_SIZES.index)


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
    searches = [{"q": q, "limit": 50} for q in config.export_listing_queries] + [
        {"category_ids": c, "limit": config.export_sweep_per_category} for c in config.export_sweep_categories
    ]
    for params in searches:
        floor = _CATEGORY_SIZE_FLOOR.get(params.get("category_ids", ""), "small")
        try:
            search = _browse_get("/item_summary/search", config, {**params, "filter": _JP_NEW})
        except requests.HTTPError:
            log.warning("Search %s failed; skipping.", params)
            continue
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
                found[jan] = {
                    "rate": rate,
                    "category_id": item.get("categoryId", ""),
                    "title": item.get("title", ""),
                    "size_floor": floor,
                }
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
    size = larger(size_for(info["title"], config), info.get("size_floor", "small"))
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


_policy_cache: dict[str, str] = {}


def export_policy_id(config: Config, ebay: EbayClient) -> str | None:
    """The Japan shipping policy: as configured, or found by name (created by export_setup.py)."""
    if config.export_fulfillment_policy_id:
        return config.export_fulfillment_policy_id
    name = config.export_fulfillment_policy_name
    if name not in _policy_cache:
        found = ebay.find_fulfillment_policy_id(name)
        if not found:
            return None
        _policy_cache[name] = found
    return _policy_cache[name]


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
                "fulfillmentPolicyId": export_policy_id(config, ebay),
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
        "size": larger(candidate.size, size_for(title, config)),
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


def publish_draft(config: Config, ebay: EbayClient, entry: dict) -> str | None:
    """Re-check the source, then publish; returns why not, or None once live."""
    from .export_sync import source_check  # export_sync builds on this module's helpers

    offer, profit, blocked = source_check(entry, config)
    if blocked:
        return blocked
    try:
        listing_id = ebay.publish_offer(entry["ebay_offer_id"])
    except EbayApiError as exc:
        return "今月の販売上限（出品数・金額）に達しています" if exc.is_selling_limit else f"eBayエラー: {exc.body[:400]}"
    entry.update(
        status="published",
        quantity=1,
        ebay_listing_id=listing_id,
        listing_url=listing_url(listing_id),
        expected_profit_jpy=profit,
        source_price_jpy=offer.price_jpy,
        source_url=offer.url,
        published_at=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
    )
    export_state.save_listing(entry["sku"], entry)
    return None


def published_note(entry: dict) -> str:
    return (
        f"公開しました: {entry['listing_url']}\n\n今の仕入れ値 ¥{entry['source_price_jpy']:,}、"
        f"想定利益 ¥{entry['expected_profit_jpy']:,}/個。仕入れ先の在庫は2時間ごとに確認し、"
        "在庫切れや採算割れのときは自動で購入不可にします。\n\n"
        "**売れたら「[仕入れ]」Issueが届きます。** 買って、自分の住所で受け取り、発送して `/shipped` してください。"
    )


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


def setup_missing(config: Config, ebay: EbayClient) -> list[str]:
    """What export listing still lacks before it can create real drafts."""
    missing = [n for n in ("ebay_payment_policy_id", "ebay_return_policy_id") if not getattr(config, n)]
    if not ebay.get_location(config.export_merchant_location_key):
        missing.append(f"location '{config.export_merchant_location_key}' (run Japan Export Setup)")
    if not export_policy_id(config, ebay):
        missing.append(f"shipping policy '{config.export_fulfillment_policy_name}' (run Japan Export Setup)")
    return missing


def run(config: Config | None = None) -> int:
    config = config or load_config()
    config.require("ebay_app_id", "ebay_cert_id", "ebay_refresh_token", "yahoo_app_id")
    ebay = EbayClient(config)
    missing = [] if config.dry_run else setup_missing(config, ebay)
    if missing:
        # Not set up yet (docs/SETUP.md §7): a scheduled run should not go
        # red every day until then, so fall back to showing candidates.
        log.warning("Export listing not set up (%s); running as a dry run.", "; ".join(missing))
        config = dataclasses.replace(config, dry_run=True)
    listings = export_state.load_listings()
    # Rejected products stay skipped, so a /reject is not undone the next morning.
    active = {
        e["jan"] for e in listings.values()
        if e.get("status") in ("pending_approval", "published", "needs_photos", "rejected")
    }
    candidates = find_candidates(config, active)
    log.info("%d export candidates clear the profit floor", len(candidates))

    github = None if config.dry_run else GithubClient(config)
    created = 0
    stop_reason = ""
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
            # A photo request means buying a unit up front; one that sells
            # once in ten months (as the first live run proposed) just ties
            # up the money.
            if candidate.units_per_month < config.export_photo_min_units_per_month:
                continue
            photo_requests += 1
            entry = candidate_entry(candidate, clean_title(candidate.title), "needs_photos", config)
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
        export_state.save_listing(entry["sku"], entry)
        failure = publish_draft(config, ebay, entry) if config.export_auto_publish else "approval"
        if failure and failure != "approval" and "販売上限" in failure:
            stop_reason = failure
        issue = github.create_issue(
            title=(
                f"[輸出・出品済み] {entry['title'][:60]} ({entry['sku']})"
                if not failure
                else f"[輸出・承認待ち] {entry['title'][:60]} ({entry['sku']})"
            ),
            body=issue_body(entry, (_images(product) or [None])[0])
            + ("" if failure in (None, "approval") else f"\n自動公開できませんでした: {failure}\n"),
            labels=["export-approval", "ebay-automation"],
        )
        entry["issue_number"] = issue["number"]
        export_state.save_listing(entry["sku"], entry)
        if not failure:
            github.comment_issue(issue["number"], published_note(entry))
            github.close_issue(issue["number"], "completed")
        created += 1
        log.info("Export %s: %s (#%s)", entry["sku"], failure or "published", issue["number"])
        if stop_reason:
            log.warning("Stopping for today: %s", stop_reason)
            break
    if config.dry_run:
        _write_summary(len(candidates), dry_rows, photo_rows)
    log.info("Created %d export drafts.", created)
    return created


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run()
