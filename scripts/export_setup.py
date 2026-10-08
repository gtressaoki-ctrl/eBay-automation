#!/usr/bin/env python3
"""One-time setup for export listings: create the Japan ship-from location
and list the account's shipping policies so the export one can be picked.

Reads EXPORT_LOCATION_CITY / EXPORT_LOCATION_PREFECTURE (repository
variables, not workflow inputs, so they are not printed in public logs).
Only city level is sent: it is what buyers see as "Located in", and a
street address is never needed for a ship-from location.

Usage (also the "Japan Export Setup" workflow):
    PYTHONPATH=src python scripts/export_setup.py
"""
from __future__ import annotations

import os
import sys

from ebay_automation.config import load_config
from ebay_automation.ebay_client import EbayApiError, EbayClient


def main() -> None:
    config = load_config()
    ebay = EbayClient(config)
    key = config.export_merchant_location_key or "jp-home"
    city = os.environ.get("EXPORT_LOCATION_CITY", "").strip()
    prefecture = os.environ.get("EXPORT_LOCATION_PREFECTURE", "").strip()

    lines = ["## Japan export setup", ""]
    if city and prefecture:
        try:
            ebay._request(
                "POST",
                f"/sell/inventory/v1/location/{key}",
                json={
                    "location": {"address": {"city": city, "stateOrProvince": prefecture, "country": "JP"}},
                    "locationTypes": ["WAREHOUSE"],
                    "name": "Japan (export)",
                },
            )
            lines.append(f"- Created ship-from location `{key}` ({city}, {prefecture}, JP).")
        except EbayApiError as exc:
            if "already exists" in exc.body or exc.status == 409:
                lines.append(f"- Location `{key}` already exists; left as is.")
            else:
                sys.exit(f"Creating location failed: {exc}")
        lines.append(f"- Set repository variable `EXPORT_MERCHANT_LOCATION_KEY` = `{key}`.")
    else:
        lines.append("- Skipped location: set `EXPORT_LOCATION_CITY` and `EXPORT_LOCATION_PREFECTURE` variables first.")

    resp = ebay._request(
        "GET", "/sell/account/v1/fulfillment_policy", params={"marketplace_id": config.ebay_marketplace_id}
    ).json()
    lines += ["", "| policy ID | name | handling days | international |", "|---|---|---|---|"]
    for p in resp.get("fulfillmentPolicies", []):
        intl = any(o.get("optionType") == "INTERNATIONAL" for o in p.get("shippingOptions", []))
        lines.append(
            f"| {p['fulfillmentPolicyId']} | {p.get('name', '')} | {(p.get('handlingTime') or {}).get('value', '-')} "
            f"| {'yes' if intl else 'no'} |"
        )
    lines += ["", "Set `EXPORT_FULFILLMENT_POLICY_ID` to the policy you created for shipping from Japan."]
    report = "\n".join(lines) + "\n"
    print(report)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(report)


if __name__ == "__main__":
    main()
