#!/usr/bin/env python3
"""End chosen live export listings to free eBay selling-limit room.

The account's selling limit (amount) is full, so better-paying drafts wait
in pending_approval. Ending a near-zero-profit listing frees its amount
for one of them. The offer is withdrawn, not deleted, and the entry is
marked withdrawn so the stock sync leaves it alone; the draft can be
published again later.

Usage (or push state/export_retire_request.json):
    PYTHONPATH=src python scripts/retire_export_listings.py JXAU-0193905352807 ...
"""
from __future__ import annotations

import argparse
import datetime

from ebay_automation import export_state
from ebay_automation.config import load_config
from ebay_automation.ebay_client import EbayClient


def retire(ebay, skus: list[str], reason: str) -> list[str]:
    now = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    listings = export_state.load_listings()
    ended = []
    for sku in skus:
        entry = listings.get(sku)
        if not entry or entry.get("status") != "published":
            print(f"Skipped {sku}: not a live export listing")
            continue
        try:
            ebay.withdraw_offer(entry["ebay_offer_id"])
        except Exception as exc:  # one failure must not stop the rest
            print(f"Failed to withdraw {sku}: {exc}")
            continue
        entry.update(status="withdrawn", paused_reason=reason, withdrawn_at=now)
        export_state.save_listing(sku, entry)
        ended.append(sku)
        print(f"Ended {sku} (listing {entry.get('ebay_listing_id')})")
    return ended


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("skus", nargs="+")
    parser.add_argument("--reason", default="ended to free selling-limit room for higher-profit drafts")
    args = parser.parse_args()
    ended = retire(EbayClient(load_config()), args.skus, args.reason)
    print(f"Ended {len(ended)} listing(s).")


if __name__ == "__main__":
    main()
