#!/usr/bin/env python3
"""One-time setup for export listings, nothing to configure by hand:

1. the Japan ship-from location (EXPORT_MERCHANT_LOCATION_KEY, "jp-home");
2. the shipping policy for parcels from Japan (EXPORT_FULFILLMENT_POLICY_NAME,
   "Japan export"): free economy shipping to US buyers, handling time
   EXPORT_HANDLING_DAYS. Prices already include shipping (see
   export_research.profit_jpy), which is why it is free to the buyer.

3. for each other site in EXPORT_MARKETS (ebay.com.au, ebay.co.uk): the
   same shipping policy plus a payment and a return policy of the same
   name, since ebay.com's policies cannot be used on another site.

All are left alone when they already exist. The location takes only
city and prefecture — what eBay shows buyers as "Located in" anyway.

Usage (also the "Japan Export Setup" workflow):
    EXPORT_LOCATION_CITY=Yokohama EXPORT_LOCATION_PREFECTURE=Kanagawa \\
    PYTHONPATH=src python scripts/export_setup.py
"""
from __future__ import annotations

import os
import sys

from ebay_automation import export_markets
from ebay_automation.config import load_config
from ebay_automation.ebay_client import EbayApiError, EbayClient

# Each site's services for parcels sent from abroad, cheapest first. Which
# ones an account may use depends on where it is registered, so each is
# tried until eBay accepts one.
SHIPPING_SERVICES = {
    "EBAY_US": ["EconomyShippingFromOutsideUS", "StandardShippingFromOutsideUS"],
    "EBAY_AU": ["AU_EconomyDeliveryFromOutsideAU", "AU_StandardDeliveryFromOutsideAU"],
    "EBAY_GB": ["UK_EconomyShippingFromOutside", "UK_StandardShippingFromOutside"],
}


def payment_body(name: str, marketplace: str) -> dict:
    return {
        "name": name,
        "marketplaceId": marketplace,
        "categoryTypes": [{"name": "ALL_EXCLUDING_MOTORS_VEHICLES"}],
        "immediatePay": True,
    }


def return_body(name: str, marketplace: str) -> dict:
    # 30 days, buyer pays return postage: what a Japan seller on ebay.com
    # typically offers, and above the 14 days UK distance selling requires.
    return {
        "name": name,
        "marketplaceId": marketplace,
        "categoryTypes": [{"name": "ALL_EXCLUDING_MOTORS_VEHICLES"}],
        "returnsAccepted": True,
        "returnPeriod": {"value": 30, "unit": "DAY"},
        "returnShippingCostPayer": "BUYER",
    }


def policy_body(name: str, marketplace: str, handling_days: int, service: str, currency: str = "USD") -> dict:
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
                        "shippingCost": {"value": "0.0", "currency": currency},
                    }
                ],
            }
        ],
    }


def setup_market(ebay: EbayClient, config, market, name: str, lines: list[str]) -> bool:
    """Create the site's missing policies named `name`; False if one could not be made."""
    site = market.domain
    ok = True
    existing = ebay.find_policy_id("fulfillment", name, market.marketplace_id)
    if existing:
        lines.append(f"- ✅ {site}: shipping policy `{name}` already exists (ID {existing}).")
    else:
        errors = []
        for service in SHIPPING_SERVICES[market.marketplace_id]:
            try:
                policy_id = ebay.create_policy(
                    "fulfillment",
                    policy_body(name, market.marketplace_id, config.export_handling_days, service, market.currency),
                )
                lines.append(
                    f"- ✅ {site}: created shipping policy `{name}` (ID {policy_id}): {service}, free to the buyer, "
                    f"handling {config.export_handling_days} business days."
                )
                break
            except EbayApiError as exc:
                errors.append(f"{service}: {exc.body[:400]}")
        else:
            lines.append(f"- ❌ {site}: creating the shipping policy failed:")
            lines += [f"  - {e}" for e in errors]
            ok = False
    if market.key == "US":
        return ok  # ebay.com's payment and return policies are configured by ID
    for kind, body in (("payment", payment_body), ("return", return_body)):
        existing = ebay.find_policy_id(kind, name, market.marketplace_id)
        if existing:
            lines.append(f"- ✅ {site}: {kind} policy `{name}` already exists (ID {existing}).")
            continue
        try:
            policy_id = ebay.create_policy(kind, body(name, market.marketplace_id))
            lines.append(f"- ✅ {site}: created {kind} policy `{name}` (ID {policy_id}).")
        except EbayApiError as exc:
            lines.append(f"- ❌ {site}: creating the {kind} policy failed: {exc.body[:400]}")
            ok = False
    return ok


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
    for market in export_markets.enabled(config):
        ok = setup_market(ebay, config, market, name, lines) and ok

    for attr, label in (("ebay_payment_policy_id", "payment"), ("ebay_return_policy_id", "return")):
        if not getattr(config, attr):
            lines.append(f"- ❌ No ebay.com {label} policy configured (EBAY_{label.upper()}_POLICY_ID).")
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
