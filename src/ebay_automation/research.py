"""Niche/keyword research for print-on-demand products.

Since we hold no inventory and generate designs on demand, "research"
here means: which niche phrases have healthy buyer search activity on
eBay without being oversaturated, and what price ceiling the market
supports. We use the public Buy Browse API (item_summary/search) to get
a live signal, scored with a simple heuristic. This is intentionally
simple for v1 — swap in eBay Marketplace Insights (sold-item data,
requires separate application approval) or a paid trend tool later for
a stronger signal.
"""
from __future__ import annotations

from dataclasses import dataclass

import requests

from .config import Config
from .ebay_auth import get_app_access_token

_BROWSE_SEARCH_URL_TMPL = "https://api.ebay.com/buy/browse/v1/item_summary/search"

# Curated, safe starter niches for text/graphic-based POD designs
# (t-shirts, mugs, hoodies). Extend this list over time based on
# state/ledger.json performance data. Deliberately generic/hobby-based
# to avoid trademark or IP risk in the generated designs.
SEED_NICHES: list[str] = [
    "cat mom shirt",
    "dog dad shirt",
    "nurse life shirt",
    "teacher appreciation shirt",
    "plant lady shirt",
    "coffee lover mug",
    "retired and loving it shirt",
    "gym motivation shirt",
    "dinosaur lover shirt",
    "camping life shirt",
    "yoga instructor shirt",
    "software engineer funny shirt",
    "gardening grandma shirt",
    "running mom shirt",
    "birdwatching gift shirt",
]


@dataclass
class NicheScore:
    keyword: str
    total_listings: int
    avg_price: float
    score: float


def _search_summary(keyword: str, config: Config, limit: int = 20) -> dict:
    token = get_app_access_token(config)
    resp = requests.get(
        _BROWSE_SEARCH_URL_TMPL,
        headers={
            "Authorization": f"Bearer {token}",
            "X-EBAY-C-MARKETPLACE-ID": config.ebay_marketplace_id,
        },
        params={"q": keyword, "limit": limit},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def _score(total_listings: int, avg_price: float) -> float:
    # No price signal at all means we can't confirm the niche is
    # profitable, regardless of how much demand-side activity there is.
    if total_listings <= 0 or avg_price <= 0:
        return 0.0

    import math

    # Peaks around ~3000 listings, decays for both very low and very high counts.
    demand_score = math.exp(-((math.log10(total_listings) - math.log10(3000)) ** 2) / 2)
    # Sweet spot: price in a POD-friendly $15-$35 range.
    price_score = max(0.0, 1 - abs(avg_price - 24) / 24)

    return round(demand_score * 0.6 + price_score * 0.4, 4)


def score_niche(keyword: str, config: Config) -> NicheScore:
    data = _search_summary(keyword, config)
    total = int(data.get("total", 0))
    items = data.get("itemSummaries", []) or []
    prices = [
        float(i["price"]["value"])
        for i in items
        if i.get("price") and i["price"].get("currency") == "USD"
    ]
    avg_price = sum(prices) / len(prices) if prices else 0.0
    return NicheScore(keyword=keyword, total_listings=total, avg_price=round(avg_price, 2), score=_score(total, avg_price))


def rank_niches(config: Config, keywords: list[str] | None = None) -> list[NicheScore]:
    keywords = keywords or SEED_NICHES
    scored = [score_niche(k, config) for k in keywords]
    return sorted(scored, key=lambda s: s.score, reverse=True)


def pick_candidates(config: Config, count: int, keywords: list[str] | None = None) -> list[NicheScore]:
    return rank_niches(config, keywords)[:count]
