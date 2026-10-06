"""Report eBay Seller Hub traffic (impressions, views, click-through rate)
per EQUINOX listing, using the Sell Analytics API's Traffic Report.

Requires the sell.analytics.readonly scope - if EBAY_REFRESH_TOKEN predates
that scope being added to SELL_SCOPES (see client.py), re-run the OAuth
consent flow (ebay/oauth_consent.py + ebay/exchange_code.py) first.

Usage:
    python -m ebay.traffic_report [--days 30] [--sku-prefix EQX-]
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import sys

from dotenv import load_dotenv

from .client import EbayClient


def our_listing_ids(ebay: EbayClient, sku_prefix: str) -> dict[str, str]:
    """Returns {listing_id: sku} for our published offers, deduplicated by
    listing (a multi-variation listing has one listingId shared by all its
    variant offers, so we only need to query it once)."""
    listings: dict[str, str] = {}
    for item in ebay.list_inventory_items():
        sku = item.get("sku", "")
        if not sku.startswith(sku_prefix):
            continue
        for offer in ebay.get_offers_for_sku(sku):
            listing_id = offer.get("listing", {}).get("listingId")
            if listing_id and listing_id not in listings:
                listings[listing_id] = sku
    return listings


def main(argv: list[str] | None = None) -> int:
    load_dotenv()

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--days", type=int, default=30, help="How many trailing days to report (max ~90).")
    parser.add_argument("--sku-prefix", default="EQX-", help="Only report listings whose SKU starts with this.")
    parser.add_argument("--marketplace-id", default=os.environ.get("EBAY_MARKETPLACE_ID", "EBAY_US"))
    args = parser.parse_args(argv)

    ebay = EbayClient(
        client_id=os.environ["EBAY_CLIENT_ID"],
        client_secret=os.environ["EBAY_CLIENT_SECRET"],
        ru_name=os.environ.get("EBAY_RU_NAME"),
        refresh_token=os.environ["EBAY_REFRESH_TOKEN"],
        sandbox=os.environ.get("EBAY_SANDBOX") == "true",
    )

    listings = our_listing_ids(ebay, args.sku_prefix)
    if not listings:
        print(f"No published listings found with SKU prefix '{args.sku_prefix}'.", file=sys.stderr)
        return 0

    end = dt.date.today()
    start = end - dt.timedelta(days=args.days)
    report = ebay.get_traffic_report(
        start_date=start.isoformat(),
        end_date=end.isoformat(),
        marketplace_ids=args.marketplace_id,
        listing_ids=list(listings.keys()),
    )

    rows = {r["listingId"]: r for r in report.get("records", [])}

    print(f"Traffic report {start} to {end} ({args.marketplace_id}):\n")
    header = f"{'SKU':<28} {'Listing ID':<14} {'Impressions':>11} {'Views':>7} {'CTR':>7}"
    print(header)
    print("-" * len(header))
    for listing_id, sku in sorted(listings.items(), key=lambda kv: kv[1]):
        record = rows.get(listing_id, {})
        metrics = {m["metricKey"]: m["value"] for m in record.get("metrics", [])}
        impressions = metrics.get("LISTING_IMPRESSION_TOTAL", "0")
        views = metrics.get("LISTING_VIEWS_TOTAL", "0")
        ctr = metrics.get("CLICK_THROUGH_RATE", "0")
        print(f"{sku:<28} {listing_id:<14} {impressions:>11} {views:>7} {ctr:>7}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
