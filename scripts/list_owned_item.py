#!/usr/bin/env python3
"""List one item the seller already owns (used goods, own photos) on ebay.com.

The item is described by state/owned_items/<name>.json with its photos in
state/owned_items/<name>/. Photos are uploaded to eBay Picture Services,
then the inventory item and offer are created with the export shipping,
payment and return policies (ships from Japan) and published.

Re-running is safe: an existing offer is reused, and a publish refused for
the monthly selling limit leaves the offer as a draft to retry next month.
The SKU (OWN-...) is neither a print-on-demand nor an export SKU, so the
order pipelines leave its orders alone; eBay notifies the seller directly.

Usage (or run the "List owned item" workflow):
    PYTHONPATH=src python scripts/list_owned_item.py state/owned_items/gopro_hero_session.json
"""
from __future__ import annotations

import argparse
import datetime
import json
import re
from pathlib import Path

from ebay_automation.config import load_config
from ebay_automation.ebay_client import EbayApiError, EbayClient
from ebay_automation.export_listing import policy_ids

STATE_PATH = Path(__file__).resolve().parent.parent / "state" / "owned_listings.json"


def _load() -> dict:
    return json.loads(STATE_PATH.read_text()) if STATE_PATH.exists() else {}


def _save(data: dict) -> None:
    STATE_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def list_item(config, ebay, spec_path: Path) -> dict:
    spec = json.loads(spec_path.read_text())
    sku = spec["sku"]
    state = _load()
    entry = state.get(sku, {})
    if entry.get("status") == "published":
        print(f"{sku} is already live: {entry.get('listing_url')}")
        return entry

    if not entry.get("image_urls"):
        photo_dir = spec_path.with_suffix("")
        entry["image_urls"] = [
            ebay.upload_image((photo_dir / name).read_bytes(), name) for name in spec["photos"]
        ]
    ebay.create_or_replace_inventory_item(
        sku,
        {
            "availability": {"shipToLocationAvailability": {"quantity": 1}},
            "condition": spec["condition"],
            "conditionDescription": spec["condition_description"],
            "product": {
                "title": spec["title"],
                "description": spec["description_html"],
                "aspects": spec["aspects"],
                "imageUrls": entry["image_urls"],
            },
        },
    )
    if not entry.get("offer_id"):
        try:
            entry["offer_id"] = ebay.create_offer(
                {
                    "sku": sku,
                    "marketplaceId": "EBAY_US",
                    "format": "FIXED_PRICE",
                    "availableQuantity": 1,
                    "categoryId": spec["category_id"],
                    "listingDescription": spec["description_html"],
                    "pricingSummary": {"price": {"value": f"{spec['price']:.2f}", "currency": "USD"}},
                    "merchantLocationKey": config.export_merchant_location_key,
                    "listingPolicies": policy_ids(config, ebay),
                }
            )
        except EbayApiError as exc:
            found = re.search(r'"offerId","value":"(\d+)"', exc.body or "")
            if not found:
                raise
            entry["offer_id"] = found.group(1)
    entry.update(title=spec["title"], price=spec["price"], currency="USD")
    try:
        listing_id = ebay.publish_offer(entry["offer_id"])
    except EbayApiError as exc:
        if not exc.is_selling_limit:
            state[sku] = entry
            _save(state)
            raise
        entry["status"] = "waiting_for_limit"
        print(f"{sku}: selling limit reached; the draft is kept, run again next month.")
    else:
        entry.update(
            status="published",
            listing_id=listing_id,
            listing_url=f"https://www.ebay.com/itm/{listing_id}",
            published_at=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        )
        print(f"{sku} is live: {entry['listing_url']}")
    state[sku] = entry
    _save(state)
    return entry


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("spec", type=Path)
    args = parser.parse_args()
    list_item(load_config(), EbayClient(load_config()), args.spec)


if __name__ == "__main__":
    main()
