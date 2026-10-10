#!/usr/bin/env python3
"""End live print-on-demand mug listings to free eBay selling-limit room.

The monthly selling limit is shared with the Japan export listings, which
actually sell. Offers are withdrawn (not deleted), and the Printify product
and eBay inventory item are kept, so any design can be republished later.
Retired entries stay in state/pending_listings.json so research never lists
the same design twice, and --pause stops the daily research run from
filling the freed room with new mugs.

Usage (or run the "Retire mug listings" workflow):
    PYTHONPATH=src python scripts/retire_mug_listings.py --keep 318929527170 --pause
"""
from __future__ import annotations

import argparse
import datetime

from ebay_automation import ledger
from ebay_automation.config import load_config
from ebay_automation.ebay_client import EbayClient


def retire(ebay, keep: set[str], reason: str) -> list[str]:
    retired = []
    now = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    for sku, entry in ledger.load_pending_listings().items():
        # Only print-on-demand mugs; export listings live in their own file
        # but are never touched here even if one ever lands in this one.
        if not sku.startswith("POD-") or entry.get("status") != "published":
            continue
        if entry.get("ebay_listing_id") in keep or sku in keep:
            continue
        try:
            ebay.withdraw_offer(entry["ebay_offer_id"])
        except Exception as exc:  # one failure must not stop the rest
            print(f"Failed to withdraw {sku}: {exc}")
            continue
        ledger.update_listing_status(sku, "retired", retired_at=now, retired_reason=reason)
        retired.append(sku)
        print(f"Retired {sku} (listing {entry.get('ebay_listing_id')})")
    return retired


def pause(reason: str) -> None:
    data = ledger.load_ledger()
    data["paused"] = True
    data["pause_reason"] = reason
    ledger.save_ledger(data)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--keep", default="", help="comma-separated listing IDs or SKUs to leave live")
    parser.add_argument("--pause", action="store_true", help="stop the daily research run from listing new mugs")
    parser.add_argument("--reason", default="selling limit reallocated to Japan export listings")
    args = parser.parse_args()

    keep = {k.strip() for k in args.keep.split(",") if k.strip()}
    retired = retire(EbayClient(load_config()), keep, args.reason)
    print(f"Retired {len(retired)} listing(s); kept {sorted(keep) or 'none'}.")
    if args.pause:
        pause(args.reason)
        print("Research pipeline paused.")


if __name__ == "__main__":
    main()
