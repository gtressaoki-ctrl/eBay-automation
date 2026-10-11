"""The eBay sites export listings go on, and what differs between them.

Each site gets its own listing (and SKU) priced in its own currency,
because a native ebay.com.au or ebay.co.uk listing ranks above an
ebay.com listing shown to the same buyer, and because what the seller
pays on arrival differs:

- US: duty is prepaid by the seller (Japan Post, since April 2026), so
  EXPORT_SELLER_DUTY_RATE applies.
- AU: eBay collects 10% GST at checkout on items up to A$1,000 and there
  is no duty under that threshold, so nothing is paid by the seller.
- GB: eBay collects 20% VAT at checkout on consignments up to £135 and
  customs duty is not charged on them. Above £135 the buyer pays VAT and
  duty on delivery, which they refuse, so listings stay at or under it.

Everything that looks a site up by marketplace (Browse, catalog, business
policies, campaigns) is pointed at the right site through market_config().
"""
from __future__ import annotations

import dataclasses
import logging
from dataclasses import dataclass

import requests

from . import fx
from .config import Config

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Market:
    key: str
    marketplace_id: str
    currency: str
    sku_prefix: str
    domain: str
    language: str
    category_tree_id: str
    # Seller-paid duty as a share of the item value; None keeps the configured rate.
    duty_rate: float | None
    # Highest price (local currency) that stays inside the buyer's no-surprise import regime.
    max_price: float | None
    symbol: str


MARKETS: dict[str, Market] = {
    "US": Market("US", "EBAY_US", "USD", "JX-", "www.ebay.com", "en-US", "0", None, None, "$"),
    "AU": Market("AU", "EBAY_AU", "AUD", "JXAU-", "www.ebay.com.au", "en-AU", "15", 0.0, 1000.0, "A$"),
    "GB": Market("GB", "EBAY_GB", "GBP", "JXGB-", "www.ebay.co.uk", "en-GB", "3", 0.0, 135.0, "£"),
}
US = MARKETS["US"]


def enabled(config: Config) -> list[Market]:
    return [MARKETS[k] for k in config.export_markets if k in MARKETS]


def for_sku(sku: str | None) -> Market | None:
    """The site a SKU was listed on; longest prefix first, since "JX-" is US."""
    for market in sorted(MARKETS.values(), key=lambda m: -len(m.sku_prefix)):
        if sku and sku.startswith(market.sku_prefix):
            return market
    return None


def of(entry: dict) -> Market:
    return MARKETS.get(entry.get("market", "")) or for_sku(entry.get("sku")) or US


def sku_for(jan: str, market: Market) -> str:
    return f"{market.sku_prefix}{jan}"


def price_of(entry: dict) -> tuple[float, str]:
    """(price, currency) of a listing or order line; entries from before AU/GB only had price_usd."""
    if "price" in entry:
        return float(entry["price"]), entry.get("currency", "USD")
    return float(entry["price_usd"]), "USD"


def money(value: float, currency: str) -> str:
    symbol = next((m.symbol for m in MARKETS.values() if m.currency == currency), currency + " ")
    return f"{symbol}{value:,.2f}"


def market_config(config: Config, market: Market) -> Config:
    """The config as seen from one site: its marketplace, duty and policies."""
    if market.key == "US":
        return config
    return dataclasses.replace(
        config,
        ebay_marketplace_id=market.marketplace_id,
        export_seller_duty_rate=market.duty_rate if market.duty_rate is not None else config.export_seller_duty_rate,
        # The configured IDs are the ebay.com policies; other sites' are found by name.
        export_fulfillment_policy_id="",
        ebay_payment_policy_id="",
        ebay_return_policy_id="",
        export_promote_campaign=f"{config.export_promote_campaign}-{market.key.lower()}",
    )


def convert(value: float, from_currency: str, to_currency: str, config: Config) -> float | None:
    if from_currency == to_currency:
        return value
    a, b = fx.rate_to_jpy(from_currency, config), fx.rate_to_jpy(to_currency, config)
    if not a or not b:
        return None
    return value * a / b


_TAXONOMY = "https://api.ebay.com/commerce/taxonomy/v1/category_tree"


def suggest_category(title: str, market: Market, config: Config) -> str | None:
    """The leaf category eBay suggests for this title on that site.

    Category IDs differ between sites, so the ebay.com category of the
    product cannot be reused on ebay.com.au or ebay.co.uk.
    """
    from .research import get_app_access_token

    resp = requests.get(
        f"{_TAXONOMY}/{market.category_tree_id}/get_category_suggestions",
        headers={"Authorization": f"Bearer {get_app_access_token(config)}"},
        params={"q": title[:350]},
        timeout=30,
    )
    if resp.status_code == 204:
        return None
    resp.raise_for_status()
    suggestions = resp.json().get("categorySuggestions") or []
    return suggestions[0]["category"]["categoryId"] if suggestions else None
