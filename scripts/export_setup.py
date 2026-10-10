#!/usr/bin/env python3
"""One-time setup for export listings, nothing to configure by hand:

1. the Japan ship-from location (EXPORT_MERCHANT_LOCATION_KEY, "jp-home");
2. the shipping policy for parcels from Japan (EXPORT_FULFILLMENT_POLICY_NAME,
   "Japan export"): free economy shipping to US buyers, handling time
   EXPORT_HANDLING_DAYS. Prices already include shipping (see
   export_research.profit_jpy), which is why it is free to the buyer.

Both are left alone when they already exist. The location takes only
city and prefecture — what eBay shows buyers as "Located in" anyway.

Usage (also the "Japan Export Setup" workflow):
    EXPORT_LOCATION_CITY=Yokohama EXPORT_LOCATION_PREFECTURE=Kanagawa \\
    PYTHONPATH=src python scripts/export_setup.py
"""
from __future__ import annotations

import os
import sys

from ebay_automation.config import load_config
from ebay_automation.ebay_client import EbayApiError, EbayClient

# eBay.com services for parcels sent from outside the US, cheapest first.
# Which ones an account may use depends on where it is registered, so each
# is tried until eBay accepts one.
SHIPPING_SERVICES = ["EconomyShippingFromOutsideUS", "StandardShippingFromOutsideUS"]


def policy_body(name: str, marketplace: str, handling_days: int, service: str) -> dict:
    return {
        "name": name,
        "marketplaceId": marketplace,
        "categoryTypes": [{"name": "ALL_EXCLUDING_MOTORS_VEHICLES"}],
        "handlingTime": {"value": handling_days, "unit": "DAY"},
        "shippingOptions": [
            {
                "optionType": "DOMESTIC",
                "costType": "FLAT_RATE",
                "shippingServices": [
                    {
                        "sortOrder": 1,
                        "shippingServiceCode": service,
                        "freeShipping": True,
                        "shippingCost": {"value": "0.0", "currency": "USD"},
                    }
                ],
            }
        ],
    }


def main() -> None:
    config = load_config()
    ebay = EbayClient(config)
    lines = ["## Japan export setup", ""]
    ok = True

    key = config.export_merchant_location_key
    if ebay.get_location(key):
        lines.append(f"- ✅ Ship-from location `{key}` already exists.")
    else:
        city = os.environ.get("EXPORT_LOCATION_CITY", "").strip()
        prefecture = os.environ.get("EXPORT_LOCATION_PREFECTURE", "").strip()
        if not (city and prefecture):
            lines.append("- ❌ Location missing: run again with the city and prefecture inputs filled in.")
            ok = False
        else:
            try:
                ebay.create_location(
                    key,
                    {
                        "location": {"address": {"city": city, "stateOrProvince": prefecture, "country": "JP"}},
                        "locationTypes": ["WAREHOUSE"],
                        "name": "Japan (export)",
                    },
                )
                lines.append(f"- ✅ Created ship-from location `{key}` ({city}, {prefecture}, Japan).")
            except EbayApiError as exc:
                lines.append(f"- ❌ Creating the location failed: {exc.body[:500]}")
                ok = False

    name = config.export_fulfillment_policy_name
    existing = ebay.find_fulfillment_policy_id(name)
    if existing:
        lines.append(f"- ✅ Shipping policy `{name}` already exists (ID {existing}).")
    else:
        errors = []
        for service in SHIPPING_SERVICES:
            try:
                policy_id = ebay.create_fulfillment_policy(
                    policy_body(name, config.ebay_marketplace_id, config.export_handling_days, service)
                )
                lines.append(
                    f"- ✅ Created shipping policy `{name}` (ID {policy_id}): {service}, free to the buyer, "
                    f"handling {config.export_handling_days} business days."
                )
                break
            except EbayApiError as exc:
                errors.append(f"{service}: {exc.body[:400]}")
        else:
            lines.append("- ❌ Creating the shipping policy failed:")
            lines += [f"  - {e}" for e in errors]
            ok = False

    for attr, label in (("ebay_payment_policy_id", "payment"), ("ebay_return_policy_id", "return")):
        if not getattr(config, attr):
            lines.append(f"- ❌ No {label} policy configured (EBAY_{label.upper()}_POLICY_ID).")
            ok = False

    lines += ["", "Ready: the next Japan Export Listing run creates real drafts." if ok else "Not ready yet."]
    report = "\n".join(lines) + "\n"
    print(report)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(report)
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
