#!/usr/bin/env python3
"""Read-only account check: selling limit, what live listings use of it,
and how much of today's Browse API allowance research has left.

Usage (also the "Account Status" workflow):
    PYTHONPATH=src python scripts/account_status.py
"""
from __future__ import annotations

import os

import requests

from ebay_automation.config import load_config
from ebay_automation.ebay_auth import get_app_access_token
from ebay_automation.ebay_client import EbayApiError, EbayClient


def live_listings(ebay: EbayClient) -> list[dict]:
    """Published offers created through the Inventory API (mugs and exports)."""
    rows, offset = [], 0
    while True:
        page = ebay._request(
            "GET", "/sell/inventory/v1/inventory_item", params={"limit": 100, "offset": offset}
        ).json()
        for item in page.get("inventoryItems", []):
            try:
                offers = ebay._request("GET", "/sell/inventory/v1/offer", params={"sku": item["sku"]}).json()
            except EbayApiError:
                continue
            for offer in offers.get("offers", []):
                if offer.get("status") != "PUBLISHED":
                    continue
                price = float(offer.get("pricingSummary", {}).get("price", {}).get("value") or 0)
                rows.append(
                    {
                        "sku": item["sku"],
                        "title": item.get("product", {}).get("title", "")[:50],
                        "price": price,
                        "quantity": int(offer.get("availableQuantity") or 0),
                        "listing_id": offer.get("listing", {}).get("listingId", ""),
                    }
                )
        offset += 100
        if offset >= int(page.get("total", 0)):
            return rows


def browse_allowance(config) -> str:
    resp = requests.get(
        "https://api.ebay.com/developer/analytics/v1_beta/rate_limit/",
        headers={"Authorization": f"Bearer {get_app_access_token(config)}"},
        params={"api_name": "Browse"},
        timeout=30,
    )
    if not resp.ok:
        return f"unavailable ({resp.status_code})"
    for api in resp.json().get("rateLimits", []):
        for res in api.get("resources", []):
            for rate in res.get("rates", []):
                if rate.get("timeWindow") == 86400:
                    return f"{rate.get('remaining')} / {rate.get('limit')} left today (resets {rate.get('reset')})"
    return "not reported"


def main() -> None:
    config = load_config()
    ebay = EbayClient(config)
    privilege = ebay._request("GET", "/sell/account/v1/privilege").json()
    limit = privilege.get("sellingLimit", {})
    amount = limit.get("amount", {})
    rows = live_listings(ebay)
    used = sum(r["price"] * r["quantity"] for r in rows)

    lines = [
        "## Account status",
        "",
        f"- Monthly selling limit: **{amount.get('value', '?')} {amount.get('currency', '')}**, "
        f"**{limit.get('quantity', '?')} items**",
        f"- Live listings (Inventory API): **{len(rows)}**, worth **${used:,.2f}** at current price x quantity",
        "  (eBay also counts what sold or was listed earlier this month, so the real headroom can be lower)",
        f"- Browse API (research): {browse_allowance(config)}",
        "",
        "| SKU | title | price | qty | listing |",
        "|---|---|---|---|---|",
    ]
    lines += [
        f"| {r['sku']} | {r['title']} | ${r['price']:.2f} | {r['quantity']} | {r['listing_id']} |" for r in rows
    ]
    report = "\n".join(lines) + "\n"
    print(report)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(report)


if __name__ == "__main__":
    main()
