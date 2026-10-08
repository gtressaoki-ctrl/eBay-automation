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
    computed = export_research.profit_jpy(
        price, "USD", offer.price_jpy, offer.free_shipping, config.export_listing_size, config
    )
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


def create_draft(config: Config, ebay: EbayClient, candidate: Candidate, product: dict) -> dict:
    sku = export_state.sku_for(candidate.jan)
    title = product.get("title", "")[:80]
    images = _images(product)
    if not images:
        raise ValueError(f"catalog product {product.get('epid')} has no stock photo")
    body = description(title, config)
    ebay.create_or_replace_inventory_item(
        sku,
        {
            "availability": {"shipToLocationAvailability": {"quantity": 1}},
            "condition": "NEW",
            "product": {
                "title": title,
                "description": body,
                "epid": product.get("epid"),
                "imageUrls": images,
                "aspects": _aspects(product),
            },
        },
    )
    offer_id = ebay.create_offer(
        {
            "sku": sku,
            "marketplaceId": config.ebay_marketplace_id,
            "format": "FIXED_PRICE",
            "availableQuantity": 1,
            "categoryId": candidate.category_id,
            "listingDescription": body,
            "pricingSummary": {"price": {"value": f"{candidate.price:.2f}", "currency": "USD"}},
            "merchantLocationKey": config.export_merchant_location_key,
            "listingPolicies": {
                "fulfillmentPolicyId": config.export_fulfillment_policy_id,
                "paymentPolicyId": config.ebay_payment_policy_id,
                "returnPolicyId": config.ebay_return_policy_id,
            },
        }
    )
    return {
        "sku": sku,
        "jan": candidate.jan,
        "epid": product.get("epid"),
        "title": title,
        "status": "pending_approval",
        "ebay_offer_id": offer_id,
        "price_usd": candidate.price,
        "competitor_price_usd": candidate.competitor_price,
        "units_per_month": candidate.units_per_month,
        "source_price_jpy": candidate.domestic.price_jpy,
        "source_url": candidate.domestic.url,
        "source_name": candidate.domestic.name,
        "expected_profit_jpy": candidate.profit_jpy,
        "margin": candidate.margin,
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
    }


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


def _write_summary(found: int, rows: list[str]) -> None:
    report = "\n".join(
        [
            "## 輸出出品の候補（DRY RUN・下書きは作っていません）",
            "",
            f"利益ラインを超えた候補: {found} 件（うちカタログ写真があり、今日の上限内のもの: {len(rows)} 件）",
            "",
            "| 商品（eBayカタログ） | 販売価格 | 今の仕入れ値 | 利益/個 | 月販/出品 |",
            "|---|---|---|---|---|",
            *rows,
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
    active = {e["jan"] for e in listings.values() if e.get("status") in ("pending_approval", "published")}
    candidates = find_candidates(config, active)
    log.info("%d export candidates clear the profit floor", len(candidates))

    ebay = EbayClient(config)
    github = None if config.dry_run else GithubClient(config)
    created = 0
    dry_rows: list[str] = []
    for candidate in candidates:
        if created >= config.export_daily_listing_quota:
            break
        try:
            product = ebay.find_catalog_product(candidate.jan)
        except EbayApiError:
            log.exception("Catalog lookup failed for %s", candidate.jan)
            continue
        if product is None:
            log.info("No single catalog product for JAN %s; skipping.", candidate.jan)
            continue
        if config.dry_run:
            dry_rows.append(
                f"| {product.get('title', '')[:60]} | ${candidate.price:.2f} (競合 ${candidate.competitor_price:.2f}) "
                f"| [¥{candidate.domestic.price_jpy:,}]({candidate.domestic.url}) | ¥{candidate.profit_jpy:,} "
                f"| {candidate.units_per_month:.1f} |"
            )
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
        _write_summary(len(candidates), dry_rows)
    log.info("Created %d export drafts.", created)
    return created


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run()
