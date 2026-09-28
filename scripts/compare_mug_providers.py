#!/usr/bin/env python3
"""Find the cheapest landed cost (production + US shipping) for an 11oz mug
across every Printify blueprint/print provider.

Landed cost is the whole margin problem: at blueprint 478 / provider 99 it
is ~$11.92 against a ~$13-15 market price. The catalog API exposes shipping
but not production cost, so each candidate gets a throwaway product (free,
deleted immediately) just to read what Printify would bill for it.

Usage (also runnable from the "Compare mug providers" workflow):
    PRINTIFY_API_KEY=... PRINTIFY_SHOP_ID=... python scripts/compare_mug_providers.py
"""
from __future__ import annotations

import os
import sys

import requests

_BASE = "https://api.printify.com/v1"
# 1x1 white PNG — enough for Printify to price a product.
_PIXEL = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
)


def _session() -> requests.Session:
    key = os.environ.get("PRINTIFY_API_KEY")
    if not key:
        sys.exit("Set PRINTIFY_API_KEY first.")
    s = requests.Session()
    s.headers["Authorization"] = f"Bearer {key}"
    return s


def _us_first_item_shipping(s, bp: int, pp: int) -> int | None:
    resp = s.get(f"{_BASE}/catalog/blueprints/{bp}/print_providers/{pp}/shipping.json", timeout=30)
    if not resp.ok:
        return None
    costs = [
        p["first_item"]["cost"]
        for p in resp.json().get("profiles", [])
        if "US" in p.get("countries", [])
    ]
    return min(costs) if costs else None


def _production_cost(s, shop: str, image_id: str, bp: int, pp: int, variant: dict) -> int | None:
    placeholders = variant.get("placeholders") or [{"position": "front"}]
    payload = {
        "title": "cost probe (auto-deleted)",
        "description": "probe",
        "blueprint_id": bp,
        "print_provider_id": pp,
        "variants": [{"id": variant["id"], "price": 2000, "is_enabled": True}],
        "print_areas": [
            {
                "variant_ids": [variant["id"]],
                "placeholders": [
                    {
                        "position": placeholders[0]["position"],
                        "images": [{"id": image_id, "x": 0.5, "y": 0.5, "scale": 1, "angle": 0}],
                    }
                ],
            }
        ],
    }
    resp = s.post(f"{_BASE}/shops/{shop}/products.json", json=payload, timeout=60)
    if not resp.ok:
        return None
    product = resp.json()
    try:
        costs = [v.get("cost") for v in product.get("variants", []) if v.get("id") == variant["id"]]
        return costs[0] if costs else None
    finally:
        s.delete(f"{_BASE}/shops/{shop}/products/{product['id']}.json", timeout=30)


def main() -> None:
    s = _session()
    shop = os.environ.get("PRINTIFY_SHOP_ID") or sys.exit("Set PRINTIFY_SHOP_ID first.")
    image_id = s.post(
        f"{_BASE}/uploads/images.json", json={"file_name": "probe.png", "contents": _PIXEL}, timeout=60
    ).json()["id"]

    blueprints = s.get(f"{_BASE}/catalog/blueprints.json", timeout=30).json()
    mugs = [bp for bp in blueprints if "mug" in bp["title"].lower()]
    rows = []
    for bp in mugs:
        providers = s.get(f"{_BASE}/catalog/blueprints/{bp['id']}/print_providers.json", timeout=30).json()
        for pp in providers:
            variants = s.get(
                f"{_BASE}/catalog/blueprints/{bp['id']}/print_providers/{pp['id']}/variants.json", timeout=30
            ).json().get("variants", [])
            eleven = [v for v in variants if "11" in (v.get("title") or "")]
            if not eleven:
                continue
            variant = eleven[0]
            shipping = _us_first_item_shipping(s, bp["id"], pp["id"])
            cost = _production_cost(s, shop, image_id, bp["id"], pp["id"], variant)
            if shipping is None or cost is None:
                continue
            rows.append((cost + shipping, cost, shipping, bp["id"], pp["id"], variant["id"], bp["title"], pp["title"]))

    rows.sort()
    lines = [
        "| landed | production | US shipping | blueprint | provider | variant | product | provider name |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for landed, cost, ship, bp, pp, vid, bt, pt in rows:
        lines.append(f"| ${landed/100:.2f} | ${cost/100:.2f} | ${ship/100:.2f} | {bp} | {pp} | {vid} | {bt} | {pt} |")
    report = "\n".join(lines)
    print(report)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write("## 11oz mug landed cost by Printify provider (cheapest first)\n\n" + report + "\n")


if __name__ == "__main__":
    main()
