"""Currency conversion to JPY for export profit math.

Rates come from frankfurter.dev (ECB reference rates, free, no key). If it
is unreachable, USD falls back to Config.export_fx_fallback_usd_jpy so a
research run still completes; other currencies are then skipped by the
caller rather than guessed.
"""
from __future__ import annotations

import logging

import requests

from .config import Config

log = logging.getLogger(__name__)

_URL = "https://api.frankfurter.dev/v1/latest"

_cache: dict[str, float] = {}


def rate_to_jpy(currency: str, config: Config) -> float | None:
    """Mid-market JPY per one unit of `currency`, before any payout haircut."""
    currency = currency.upper()
    if currency == "JPY":
        return 1.0
    if currency in _cache:
        return _cache[currency]
    try:
        resp = requests.get(_URL, params={"from": currency, "to": "JPY"}, timeout=15)
        resp.raise_for_status()
        rate = float(resp.json()["rates"]["JPY"])
    except (requests.RequestException, KeyError, ValueError):
        log.warning("FX lookup for %s failed", currency)
        if currency != "USD":
            return None
        rate = config.export_fx_fallback_usd_jpy
    _cache[currency] = rate
    return rate
