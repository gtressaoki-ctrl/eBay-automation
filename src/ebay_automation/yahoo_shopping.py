"""Yahoo!ショッピング 商品検索API (v3): the domestic purchase price.

Used only to look up what a product costs new and in stock in Japan, by
its JAN code — an exact product match, unlike keyword search. Buying is
always done by a person after an eBay sale; nothing here places orders.

The API allows roughly one request per second per Client ID and answers
429 beyond that, so calls are spaced out here.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import requests

from .config import Config

log = logging.getLogger(__name__)

_URL = "https://shopping.yahooapis.jp/ShoppingWebService/V3/itemSearch"
_MIN_INTERVAL_S = 1.1
# hit["shipping"]["code"]: 2 = 送料無料. Anything else may charge us
# domestic shipping, so Config.export_domestic_shipping_jpy is added.
_FREE_SHIPPING_CODE = 2

_last_call = 0.0


@dataclass
class DomesticOffer:
    jan: str
    name: str
    price_jpy: int
    free_shipping: bool
    url: str
    seller: str


def _throttle() -> None:
    global _last_call
    wait = _last_call + _MIN_INTERVAL_S - time.monotonic()
    if wait > 0:
        time.sleep(wait)
    _last_call = time.monotonic()


def cheapest_new_offer(jan: str, config: Config) -> DomesticOffer | None:
    """Cheapest new, in-stock listing for this JAN, or None if nobody stocks it."""
    config.require("yahoo_app_id")
    for attempt in range(3):
        _throttle()
        resp = requests.get(
            _URL,
            params={
                "appid": config.yahoo_app_id,
                "jan_code": jan,
                "in_stock": "true",
                "condition": "new",
                "sort": "+price",
                "results": 10,
            },
            timeout=20,
        )
        if resp.status_code == 429 and attempt < 2:
            time.sleep(5 * (attempt + 1))
            continue
        resp.raise_for_status()
        break

    for hit in resp.json().get("hits", []) or []:
        price = hit.get("price")
        if not price or hit.get("inStock") is False or hit.get("condition") == "used":
            continue
        return DomesticOffer(
            jan=jan,
            name=hit.get("name", ""),
            price_jpy=int(price),
            free_shipping=(hit.get("shipping") or {}).get("code") == _FREE_SHIPPING_CODE,
            url=hit.get("url", ""),
            seller=(hit.get("seller") or {}).get("name", ""),
        )
    return None
