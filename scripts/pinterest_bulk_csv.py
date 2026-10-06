#!/usr/bin/env python3
"""Write a Pinterest bulk-create CSV for every live eBay listing.

Pinterest's API only publishes publicly visible Pins after a Standard
access review, so until then the free route is Settings -> Bulk create
Pins with this file. Each Pin is scheduled one day apart so the board gets
fresh content daily instead of 14 Pins at once.

Usage:
    PYTHONPATH=src python scripts/pinterest_bulk_csv.py [YYYY-MM-DDTHH:MM (UTC, first Pin)]
"""
from __future__ import annotations

import csv
import datetime
import json
import sys
from pathlib import Path

from ebay_automation import pinterest_content as pc

ROOT = Path(__file__).resolve().parent.parent
BOARD = "Funny Coffee Mugs"


def rows(listings: dict, start: datetime.datetime) -> list[list[str]]:
    live = [v for v in listings.values() if pc.pinnable(v)]
    return [
        [
            pc.title(v["headline"]), pc.image_url(v), BOARD, "", pc.description(v["headline"]),
            v["listing_url"], (start + datetime.timedelta(days=i)).strftime("%Y-%m-%dT%H:%M:%S"), pc.KEYWORDS,
        ]
        for i, v in enumerate(live)
    ]


def main() -> None:
    start = datetime.datetime.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else (
        datetime.datetime.utcnow().replace(hour=20, minute=0, second=0, microsecond=0)
        + datetime.timedelta(days=1)
    )
    listings = json.loads((ROOT / "state" / "pending_listings.json").read_text())
    path = ROOT / "exports" / "pinterest_bulk_pins.csv"
    path.parent.mkdir(exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Title", "Media URL", "Pinterest board", "Thumbnail", "Description", "Link", "Publish date", "Keywords"])
        w.writerows(rows(listings, start))
    print(path)


if __name__ == "__main__":
    main()
