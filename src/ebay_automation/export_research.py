"""Which Japanese goods are worth exporting: demand on eBay vs. cost in Japan.

For each candidate genre (export_genres.py) this samples new, fixed-price
listings that ship from Japan, and measures — exactly as research.py does
for print-on-demand — how many units each listing actually sells per
month (`estimatedSoldQuantity` over listing age).

Listings that carry a JAN code are then matched, exactly, to the cheapest
new in-stock offer on Yahoo!ショッピング, and the profit per unit is
worked out in yen after eBay's fees, payout FX spread, domestic and
international shipping:

    profit = sale price × FX − fees − purchase − domestic − international (+ tax refund)

A genre's score is the expected monthly profit of the matched products
that clear EXPORT_MIN_PROFIT_JPY: Σ(profit × units/listing/month). Without
a Yahoo Client ID the run still ranks genres by demand alone.

Sourcing model (see docs/SETUP.md §0): the seller buys after the sale,
receives and inspects the item, and ships it. Japanese shops are never
asked to ship to the eBay buyer directly — that is the dropshipping eBay
prohibits.

Run via: python -m ebay_automation.export_research
"""
from __future__ import annotations

import datetime
import json
import logging
import os
import re
import statistics
import urllib.parse
from dataclasses import asdict, dataclass, field
from pathlib import Path

import requests

from . import fx, yahoo_shopping
from .config import Config, load_config
from .export_genres import GENRES, ExportGenre
from .research import _browse_get, _listing_age_days

log = logging.getLogger(__name__)

STATE_PATH = Path("state/export_research.json")
REPORT_PATH = Path("reports/export_research.md")

# Listings whose GTIN describes one unit but which sell several — the
# per-unit profit would be overstated, so they are matched but not scored.
_BUNDLE_RE = re.compile(
    r"\b(lot|set of|bundle|\d+\s*(pcs|pieces|packs|boxes)|x\s?[2-9]\d*|[2-9]\d*\s?x)\b", re.I
)
# A sealed box listed on eBay is often tagged with the JAN of the single
# pack inside it, so the "match" is one pack. The domestic listing must
# then say it is a box too.
_BOX_RE = re.compile(r"\bbox\b", re.I)
_DOMESTIC_BOX_RE = re.compile(r"box|ボックス|カートン", re.I)


@dataclass
class ProductOpportunity:
    title: str
    ebay_url: str
    jan: str
    sale_price: float
    currency: str
    units_per_month: float
    domestic_price_jpy: int | None = None
    domestic_url: str = ""
    domestic_name: str = ""
    profit_jpy: int | None = None
    margin: float | None = None
    bundle_suspect: bool = False
    # Why the JAN match is not trusted (e.g. box vs. single pack); such
    # products are reported but never scored.
    mismatch: str = ""

    @property
    def scoreable(self) -> bool:
        return not self.bundle_suspect and not self.mismatch


@dataclass
class GenreResult:
    key: str
    label: str
    caution: str
    active_listings: int = 0
    sampled: int = 0
    listings_with_sales: int = 0
    units_per_listing_per_month: float = 0.0
    median_price_selling_usd: float | None = None
    with_jan: int = 0
    matched: int = 0
    profitable: int = 0
    expected_monthly_profit_jpy: int = 0
    products: list[ProductOpportunity] = field(default_factory=list)

    @property
    def sell_through_rate(self) -> float:
        return self.listings_with_sales / self.sampled if self.sampled else 0.0

    @property
    def demand_score(self) -> float:
        """Monthly sales per listing × going price — ranks genres when unpriced."""
        return self.units_per_listing_per_month * (self.median_price_selling_usd or 0)


def valid_jan(code: str | None) -> str | None:
    """Normalize an eBay GTIN to a 13-digit JAN/EAN with a valid check digit."""
    if not code:
        return None
    digits = re.sub(r"\D", "", code)
    if len(digits) == 12:  # UPC-A is an EAN-13 with a leading zero
        digits = "0" + digits
    if len(digits) != 13:
        return None
    total = sum(int(d) * (3 if i % 2 else 1) for i, d in enumerate(digits[:12]))
    return digits if (10 - total % 10) % 10 == int(digits[12]) else None


def profit_jpy(
    sale_total: float,
    currency: str,
    purchase_jpy: int,
    free_domestic_shipping: bool,
    size: str,
    config: Config,
) -> tuple[int, float] | None:
    """Per-unit profit in yen and its margin on revenue, or None if FX is unknown."""
    rate = fx.rate_to_jpy(currency, config)
    usd_rate = fx.rate_to_jpy("USD", config)
    if rate is None or usd_rate is None:
        return None
    payout = 1 - config.export_fx_haircut
    revenue = sale_total * rate * payout
    fees = revenue * config.export_fee_rate + config.export_fee_fixed_usd_cents / 100 * usd_rate * payout
    domestic = 0 if free_domestic_shipping else config.export_domestic_shipping_jpy
    refund = purchase_jpy * 10 / 110 if config.export_tax_refund else 0
    profit = revenue - fees - purchase_jpy - domestic - config.export_shipping_jpy(size) + refund
    return round(profit), (profit / revenue if revenue else 0.0)


def _sale_total(item: dict) -> tuple[float, str]:
    price = item.get("price") or {}
    total = float(price.get("value") or 0)
    currency = price.get("currency") or "USD"
    ship = ((item.get("shippingOptions") or [{}])[0].get("shippingCost") or {})
    if ship.get("currency") == currency:
        total += float(ship.get("value") or 0)
    return total, currency


def measure_genre(genre: ExportGenre, config: Config) -> GenreResult:
    result = GenreResult(key=genre.key, label=genre.label, caution=genre.caution)
    search = _browse_get(
        "/item_summary/search",
        config,
        {
            "q": genre.query,
            "limit": config.export_sample_size,
            "filter": "itemLocationCountry:JP,buyingOptions:{FIXED_PRICE},conditionIds:{1000}",
        },
    )
    result.active_listings = int(search.get("total", 0))

    rates: list[float] = []
    selling_prices: list[float] = []
    for summary in search.get("itemSummaries", []) or []:
        item_id = urllib.parse.quote(summary["itemId"], safe="")
        try:
            item = _browse_get(f"/item/{item_id}", config)
        except requests.HTTPError:
            log.warning("Could not fetch item %s in %s", summary["itemId"], genre.key)
            continue
        sold = ((item.get("estimatedAvailabilities") or [{}])[0]).get("estimatedSoldQuantity")
        total, currency = _sale_total(item)
        if sold is None or total <= 0:
            continue

        rate = sold / _listing_age_days(item.get("itemCreationDate")) * 30
        rates.append(rate)
        if sold > 0:
            result.listings_with_sales += 1
            if currency == "USD":
                selling_prices.append(total)

        jan = valid_jan(item.get("gtin"))
        if jan and sold > 0:
            result.products.append(
                ProductOpportunity(
                    title=item.get("title", ""),
                    ebay_url=item.get("itemWebUrl", ""),
                    jan=jan,
                    sale_price=round(total, 2),
                    currency=currency,
                    units_per_month=round(rate, 2),
                    bundle_suspect=bool(_BUNDLE_RE.search(item.get("title", ""))),
                )
            )

    result.sampled = len(rates)
    result.with_jan = len(result.products)
    if rates:
        result.units_per_listing_per_month = round(statistics.mean(rates), 3)
    if selling_prices:
        result.median_price_selling_usd = round(statistics.median(selling_prices), 2)

    if config.yahoo_app_id:
        _price_products(result, genre, config)
    return result


def _price_products(result: GenreResult, genre: ExportGenre, config: Config) -> None:
    seen: set[str] = set()
    for product in result.products:
        if product.jan in seen:
            continue
        seen.add(product.jan)
        try:
            offer = yahoo_shopping.cheapest_new_offer(product.jan, config)
        except requests.HTTPError:
            log.warning("Yahoo lookup failed for JAN %s", product.jan)
            continue
        if offer is None:
            continue
        computed = profit_jpy(
            product.sale_price, product.currency, offer.price_jpy, offer.free_shipping, genre.size, config
        )
        if computed is None:
            continue
        product.domestic_price_jpy = offer.price_jpy
        product.domestic_url = offer.url
        product.domestic_name = offer.name
        product.mismatch = _mismatch_reason(product, offer, config)
        product.profit_jpy, margin = computed
        product.margin = round(margin, 3)
        result.matched += 1
        if product.profit_jpy >= config.export_min_profit_jpy and product.scoreable:
            result.profitable += 1
            result.expected_monthly_profit_jpy += round(product.profit_jpy * product.units_per_month)

    result.products.sort(key=lambda p: (p.profit_jpy is not None, p.profit_jpy or 0), reverse=True)


def _mismatch_reason(product: ProductOpportunity, offer, config: Config) -> str:
    """Why this JAN match probably isn't the same thing the eBay buyer gets."""
    if _BOX_RE.search(product.title) and not _DOMESTIC_BOX_RE.search(offer.name):
        return "eBayはBOX、国内はBOX表記なし（1パックの可能性）"
    rate = fx.rate_to_jpy(product.currency, config)
    if rate and offer.price_jpy < product.sale_price * rate * config.export_min_cost_ratio:
        return f"仕入れ値がeBay売価の{config.export_min_cost_ratio:.0%}未満（入数・容量違いの可能性）"
    return ""


def rank(results: list[GenreResult], priced: bool) -> list[GenreResult]:
    if priced:
        return sorted(results, key=lambda r: (r.expected_monthly_profit_jpy, r.demand_score), reverse=True)
    return sorted(results, key=lambda r: r.demand_score, reverse=True)


def render_report(results: list[GenreResult], priced: bool, config: Config, run_at: str) -> str:
    usd = fx.rate_to_jpy("USD", config) or config.export_fx_fallback_usd_jpy
    lines = [
        f"# 輸出ジャンル候補リサーチ（{run_at[:10]}）",
        "",
        "日本から発送されている新品・即決のeBay出品を各ジャンルでサンプリングし、"
        "「1出品が月に何個売れているか」を実測しています。",
    ]
    if priced:
        lines += [
            "JANコードが付いた売れ筋は、Yahoo!ショッピングの最安在庫（新品）と完全一致で照合し、"
            "手数料・為替スプレッド・国内送料・国際送料を引いた**1個あたりの利益**を出しています。",
            "",
            f"前提: 1 USD = {usd:.1f}円（受取時に{config.export_fx_haircut:.0%}目減り）、"
            f"eBay手数料 {config.export_fee_rate:.2%} + ${config.export_fee_fixed_usd_cents / 100:.2f}、"
            f"国際送料（梱包込みの概算） 小{config.export_shipping_small_jpy}円 / "
            f"中{config.export_shipping_medium_jpy}円 / 大{config.export_shipping_large_jpy}円、"
            f"消費税還付 {'あり' if config.export_tax_refund else 'なし'}、"
            f"採用ラインは利益{config.export_min_profit_jpy}円以上。",
            "",
            "| 順位 | ジャンル | 想定月利益 | 利益が出る商品 / 照合 / JANあり | 月販/出品 | 売れた率 | 売れ筋中央値 |",
            "|---|---|---|---|---|---|---|",
        ]
        for i, r in enumerate(results, 1):
            lines.append(
                f"| {i} | {r.label} | ¥{r.expected_monthly_profit_jpy:,} | {r.profitable} / {r.matched} / {r.with_jan} "
                f"| {r.units_per_listing_per_month:.2f} | {r.sell_through_rate:.0%} | {_usd(r.median_price_selling_usd)} |"
            )
    else:
        lines += [
            "",
            "**YAHOO_APP_ID が未設定のため、仕入れ価格は照合していません。** 需要（月販×価格）だけで並べています。",
            "",
            "| 順位 | ジャンル | 月販/出品 | 売れた率 | 売れ筋中央値 | 出品数（日本発） |",
            "|---|---|---|---|---|---|",
        ]
        for i, r in enumerate(results, 1):
            lines.append(
                f"| {i} | {r.label} | {r.units_per_listing_per_month:.2f} | {r.sell_through_rate:.0%} "
                f"| {_usd(r.median_price_selling_usd)} | {r.active_listings:,} |"
            )

    cautions = [r for r in results if r.caution]
    if cautions:
        lines += ["", "## ジャンル別の注意点", ""]
        lines += [f"- **{r.label}**: {r.caution}" for r in cautions]

    if priced:
        lines += ["", "## 利益が出る商品（上位）", ""]
        top = sorted(
            (
                (r, p)
                for r in results
                for p in r.products
                if p.profit_jpy is not None and p.profit_jpy >= config.export_min_profit_jpy and p.scoreable
            ),
            key=lambda rp: rp[1].profit_jpy * rp[1].units_per_month,
            reverse=True,
        )[:25]
        if not top:
            lines.append("今回のサンプルでは採用ラインを超える商品はありませんでした。")
        else:
            lines += [
                "| ジャンル | 商品 | eBay売価 | 仕入れ | 利益/個 | 利益率 | 月販 |",
                "|---|---|---|---|---|---|---|",
            ]
            for r, p in top:
                title = p.title.replace("|", "/")[:60]
                lines.append(
                    f"| {r.label} | [{title}]({p.ebay_url}) | {p.sale_price:.2f} {p.currency} "
                    f"| [¥{p.domestic_price_jpy:,}]({p.domestic_url}) | ¥{p.profit_jpy:,} | {p.margin:.0%} "
                    f"| {p.units_per_month:.2f} |"
                )

        excluded = [(r, p) for r in results for p in r.products if p.profit_jpy is not None and not p.scoreable]
        if excluded:
            lines += [
                "",
                "## 照合が怪しいため集計から外した商品",
                "",
                "同じJANでも、入数・容量・まとめ売りが違うと利益が過大に出ます。目で確認して、本物なら手動で検討してください。",
                "",
                "| ジャンル | 商品 | eBay売価 | 国内の照合先 | 理由 |",
                "|---|---|---|---|---|",
            ]
            for r, p in excluded[:25]:
                title = p.title.replace("|", "/")[:60]
                reason = p.mismatch or "まとめ売りの疑い"
                lines.append(
                    f"| {r.label} | [{title}]({p.ebay_url}) | {p.sale_price:.2f} {p.currency} "
                    f"| [¥{p.domestic_price_jpy:,}]({p.domestic_url}) | {reason} |"
                )

    lines += [
        "",
        "## 読み方",
        "",
        "- 売り切れた出品は検索結果から消えるため、よく売れるジャンルほど過小評価されます。数字は控えめな下限です。",
        "- 2025年8月から米国では少額輸入の免税がなくなり、日本製品には原則15%の関税がかかります。"
        "eBay経由なら関税は購入者が支払いますが、その分だけ需要が下がる可能性があります。",
        "- 国際送料は概算です。実際に契約した配送サービスの料金に `EXPORT_SHIPPING_*_JPY` を合わせてください。",
        "- 仕入れは売れた後に人が行い、**必ず自分で受け取ってから発送**します（仕入れ先から購入者への直送はeBay規約違反）。",
    ]
    return "\n".join(lines) + "\n"


def _usd(value: float | None) -> str:
    return f"${value:.2f}" if value is not None else "-"


def run(config: Config | None = None) -> list[GenreResult]:
    config = config or load_config()
    config.require("ebay_app_id", "ebay_cert_id")
    priced = bool(config.yahoo_app_id)
    if not priced:
        log.warning("YAHOO_APP_ID not set: ranking by demand only.")

    results = []
    for genre in GENRES:
        try:
            results.append(measure_genre(genre, config))
        except requests.HTTPError:
            log.exception("Measuring %s failed; skipping.", genre.key)
    results = rank(results, priced)

    run_at = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    report = render_report(results, priced, config, run_at)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")
    STATE_PATH.write_text(
        json.dumps(
            {"run_at": run_at, "priced": priced, "genres": [asdict(r) for r in results]},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(report)
    log.info("Wrote %s and %s", REPORT_PATH, STATE_PATH)
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run()
