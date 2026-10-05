#!/usr/bin/env python3
"""Write a Pinterest bulk-create CSV for every live eBay listing.

Pinterest's API only publishes publicly visible Pins after a Standard
access review, so until then the free route is Settings -> Bulk create
Pins with this file. Each Pin is scheduled one day apart so the board gets
fresh content daily instead of 14 Pins at once.

Usage:
    python scripts/pinterest_bulk_csv.py [YYYY-MM-DDTHH:MM (UTC, first Pin)]
"""
from __future__ import annotations

import csv
import datetime
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOARD = "Funny Coffee Mugs"
KEYWORDS = "funny coffee mug, sarcastic mug, office gift, coworker gift, coffee lover gift"


def _sentence(headline: str) -> str:
    text = headline.capitalize()
    text = re.sub(r"\bi('m|'ve|'d)?\b", lambda m: "I" + (m.group(1) or ""), text)
    return re.sub(r"([.!?] )([a-z])", lambda m: m.group(1) + m.group(2).upper(), text)


def _title(headline: str) -> str:
    words = re.sub(r"\b(\w)", lambda m: m.group(1).upper(), headline.lower())
    words = re.sub(r"'([A-Z])", lambda m: "'" + m.group(1).lower(), words)
    return f"{words} – Funny Sarcastic Coffee Mug"[:100]


def rows(listings: dict, start: datetime.datetime) -> list[list[str]]:
    live = [v for v in listings.values() if v.get("status") == "published" and v.get("listing_url")]
    out = []
    for i, v in enumerate(live):
        desc = (
            f'"{_sentence(v["headline"])}" — an 11oz ceramic coffee mug for anyone who runs on coffee '
            "and sarcasm. Funny office gift for coworkers, bosses and friends. Dishwasher and microwave "
            "safe. #funnymug #coffeemug #officegift #sarcasticgifts #giftsforcoworkers"
        )[:500]
        when = (start + datetime.timedelta(days=i)).strftime("%Y-%m-%dT%H:%M:%S")
        out.append([
            _title(v["headline"]), v["image_url"].split("?")[0], BOARD, "",
            desc, v["listing_url"], when, KEYWORDS,
        ])
    return out


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
