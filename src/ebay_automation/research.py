"""Measure real demand per niche from eBay's live marketplace.

eBay's official sold-item feeds are closed to us: the Marketplace Insights
API is a limited release not open to new applicants, and the Finding API's
findCompletedItems was decommissioned in February 2025. What remains — and
what this module uses — is the free Browse API's getItem call, which
reports `estimatedSoldQuantity` per listing. Combined with
`itemCreationDate` that yields a real sales-rate signal:

    units sold / days listed  ->  units per listing per month

That is the number that decides whether a niche is worth listing into.
Active-listing counts alone measure competition, not demand, and ranking
on them (as this module used to) is why the first batch of listings went
into niches where comparable listings had sat unsold for years.

Known bias: listings that sell out drop out of the active index, so a
fast-moving niche is under-counted here. Treat every figure as a
conservative floor.
"""
from __future__ import annotations

import datetime
import logging
import statistics
import urllib.parse
from dataclasses import dataclass, field

import requests

from .config import Config
from .ebay_auth import get_app_access_token

log = logging.getLogger(__name__)

_BROWSE_BASE = "https://api.ebay.com/buy/browse/v1"

# eBay's final value fee on most categories, plus the per-order fixed fee.
EBAY_FEE_RATE = 0.1325
EBAY_FEE_FIXED_CENTS = 40


@dataclass
class NicheDemand:
    """Live demand measurement for one search phrase."""

    keyword: str
    active_listings: int
    sampled: int
    listings_with_sales: int
    units_sold: int
    units_per_listing_per_month: float
    median_price_selling_cents: int | None
    median_price_all_cents: int | None
    expected_monthly_profit_cents: int = 0
    unit_profit_cents: int = 0

    @property
    def sell_through_rate(self) -> float:
        return self.listings_with_sales / self.sampled if self.sampled else 0.0


@dataclass
class DemandReport:
    """Ranked demand measurements plus the ones that failed the profit floor."""

    ranked: list[NicheDemand] = field(default_factory=list)
    rejected: list[NicheDemand] = field(default_factory=list)


def _browse_get(path: str, config: Config, params: dict | None = None) -> dict:
    resp = requests.get(
        f"{_BROWSE_BASE}{path}",
        headers={
            "Authorization": f"Bearer {get_app_access_token(config)}",
            "X-EBAY-C-MARKETPLACE-ID": config.ebay_marketplace_id,
        },
        params=params,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def _listing_age_days(created: str | None) -> int:
    if not created:
        return 1
    stamp = datetime.datetime.fromisoformat(created.replace("Z", "+00:00"))
    return max(1, (datetime.datetime.now(datetime.timezone.utc) - stamp).days)


def measure_niche(keyword: str, config: Config, sample_size: int = 12) -> NicheDemand | None:
    """Sample live listings for `keyword` and measure how fast they actually sell."""
    search = _browse_get(
        "/item_summary/search",
        config,
        {"q": keyword, "limit": sample_size, "filter": "buyingOptions:{FIXED_PRICE}"},
    )

    prices_all: list[float] = []
    prices_selling: list[float] = []
    units_sold = 0
    monthly_rates: list[float] = []

    for summary in search.get("itemSummaries", []) or []:
        item_id = urllib.parse.quote(summary["itemId"], safe="")
        try:
            item = _browse_get(f"/item/{item_id}", config)
        except requests.HTTPError:
            log.warning("Could not fetch item %s while measuring %r", summary["itemId"], keyword)
            continue

        availability = (item.get("estimatedAvailabilities") or [{}])[0]
        sold = availability.get("estimatedSoldQuantity")
        if sold is None:
            continue

        price = float(item.get("price", {}).get("value", 0) or 0)
        if price <= 0:
            continue

        prices_all.append(price)
        units_sold += sold
        monthly_rates.append(sold / _listing_age_days(item.get("itemCreationDate")) * 30)
        if sold > 0:
            prices_selling.append(price)

    if not prices_all:
        log.warning("No usable sold-quantity data for %r", keyword)
        return None

    return NicheDemand(
        keyword=keyword,
        active_listings=int(search.get("total", 0)),
        sampled=len(prices_all),
        listings_with_sales=len(prices_selling),
        units_sold=units_sold,
        units_per_listing_per_month=round(statistics.mean(monthly_rates), 3),
        median_price_selling_cents=round(statistics.median(prices_selling) * 100) if prices_selling else None,
        median_price_all_cents=round(statistics.median(prices_all) * 100),
    )


def target_price_cents(demand: NicheDemand) -> int | None:
    """The price buyers in this niche actually pay, not a markup on our cost.

    Listings that have sold tell us what converts; listings that never sold
    tell us nothing except what sellers hoped for. Fall back to the overall
    median only when nothing in the sample has sold.
    """
    return demand.median_price_selling_cents or demand.median_price_all_cents


def unit_profit_cents(price_cents: int, product_cost_cents: int) -> int:
    """Net per unit after eBay's cut, given what the item costs us landed."""
    fees = round(price_cents * EBAY_FEE_RATE) + EBAY_FEE_FIXED_CENTS
    return price_cents - fees - product_cost_cents


def rank_niches(
    keywords: list[str],
    config: Config,
    product_cost_cents: int,
    min_unit_profit_cents: int = 100,
    sample_size: int = 12,
) -> DemandReport:
    """Measure every keyword and order them by expected profit per listing per month.

    A niche is rejected outright when a unit sold at the going market price
    would not clear `min_unit_profit_cents` — volume cannot rescue a product
    that loses money on every sale.
    """
    report = DemandReport()

    for keyword in keywords:
        try:
            demand = measure_niche(keyword, config, sample_size=sample_size)
        except requests.HTTPError:
            log.exception("Demand measurement failed for %r; skipping.", keyword)
            continue
        if demand is None:
            continue

        price = target_price_cents(demand)
        if price is None:
            continue

        demand.unit_profit_cents = unit_profit_cents(price, product_cost_cents)
        demand.expected_monthly_profit_cents = round(
            demand.unit_profit_cents * demand.units_per_listing_per_month
        )

        if demand.unit_profit_cents < min_unit_profit_cents:
            report.rejected.append(demand)
        else:
            report.ranked.append(demand)

    report.ranked.sort(key=lambda d: d.expected_monthly_profit_cents, reverse=True)
    return report
