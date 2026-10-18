#!/usr/bin/env python3
"""Cut the EQUINOX (EQX-) test listings down to the minimum, freeing the
monthly selling limit for export listings that have a measured margin.

What stays, decided from the last 30 days of eBay traffic:
- every EQUINOX listing that sold something;
- otherwise the best T-shirt listing and the best sticker listing
  (most views, then most impressions), so the design test keeps running;
- in what stays, a T-shirt keeps at most 3 variants (sizes M, L, XL first)
  and a sticker keeps 1. The other variants go to quantity 0.
Every other EQUINOX listing is ended (withdrawn).

With END_ALL=true every EQUINOX listing is ended instead.

Without APPLY=true it only prints the plan.

Usage (also the "Trim EQUINOX Listings" workflow):
    PYTHONPATH=src python scripts/trim_equinox.py            # plan
    APPLY=true PYTHONPATH=src python scripts/trim_equinox.py # do it
"""
from __future__ import annotations

import os
from collections import defaultdict

from ebay_automation.config import load_config
from ebay_automation.ebay_client import EbayApiError, EbayClient

PREFIX = "EQX-"
SHIRT_VARIANTS = 3
STICKER_VARIANTS = 1
PREFERRED_SIZES = ["M", "L", "XL", "S", "2XL"]


def equinox_variants(ebay: EbayClient) -> list[dict]:
    rows, offset = [], 0
    while True:
        page = ebay._request(
            "GET", "/sell/inventory/v1/inventory_item", params={"limit": 100, "offset": offset}
        ).json()
        for item in page.get("inventoryItems", []):
            if not item["sku"].startswith(PREFIX):
                continue
            offers = ebay._request("GET", "/sell/inventory/v1/offer", params={"sku": item["sku"]}).json()
            for offer in offers.get("offers", []):
                if offer.get("status") != "PUBLISHED":
                    continue
                aspects = item.get("product", {}).get("aspects", {}) or {}
                rows.append(
                    {
                        "sku": item["sku"],
                        "title": item.get("product", {}).get("title", ""),
                        "size": (aspects.get("Size") or [""])[0],
                        "group": (item.get("groupIds") or [""])[0],
                        "offer_id": offer["offerId"],
                        "listing_id": offer.get("listing", {}).get("listingId", ""),
                        "price": float(offer.get("pricingSummary", {}).get("price", {}).get("value") or 0),
                        "quantity": int(offer.get("availableQuantity") or 0),
                    }
                )
        offset += 100
        if offset >= int(page.get("total", 0)):
            return rows


def plan(
    variants: list[dict], traffic: dict[str, dict[str, int]], end_all: bool = False
) -> tuple[dict[str, list[dict]], list[dict], list[list[dict]]]:
    """Variants kept per listing, variants set to quantity 0, and the listings to end."""
    listings: dict[str, list[dict]] = defaultdict(list)
    for v in variants:
        listings[v["listing_id"]].append(v)
    if end_all:
        return {}, [], list(listings.values())

    def kind(listing_id: str) -> str:
        return "shirt" if "shirt" in listings[listing_id][0]["title"].lower() else "sticker"

    def score(listing_id: str) -> tuple[int, int, int]:
        t = traffic.get(listing_id, {})
        return (t.get("TRANSACTION", 0), t.get("LISTING_VIEWS_TOTAL", 0), t.get("LISTING_IMPRESSION_TOTAL", 0))

    keep = {lid for lid in listings if score(lid)[0] > 0}
    for k in ("shirt", "sticker"):
        same = [lid for lid in listings if kind(lid) == k]
        if same and not keep & set(same):
            keep.add(max(same, key=score))

    kept, zeroed = {}, []
    for lid in keep:
        limit = SHIRT_VARIANTS if kind(lid) == "shirt" else STICKER_VARIANTS
        ranked = sorted(
            listings[lid],
            key=lambda v: PREFERRED_SIZES.index(v["size"]) if v["size"] in PREFERRED_SIZES else len(PREFERRED_SIZES),
        )
        kept[lid] = ranked[:limit]
        zeroed += [v for v in ranked[limit:] if v["quantity"] > 0]
    ended = [listings[lid] for lid in listings if lid not in keep]
    return kept, zeroed, ended


def main() -> None:
    apply = os.environ.get("APPLY", "").lower() == "true"
    end_all = os.environ.get("END_ALL", "").lower() == "true"
    ebay = EbayClient(load_config())
    variants = equinox_variants(ebay)
    listing_ids = sorted({v["listing_id"] for v in variants if v["listing_id"]})
    try:
        traffic = ebay.get_traffic_report(listing_ids, 30) if listing_ids else {}
    except EbayApiError as exc:
        print(f"Traffic report unavailable ({exc.body[:200]}); deciding without it.")
        traffic = {}
    kept, zeroed, ended = plan(variants, traffic, end_all)

    before = sum(v["price"] * v["quantity"] for v in variants)
    after = sum(v["price"] * v["quantity"] for vs in kept.values() for v in vs)
    lines = [
        f"## EQUINOX trim ({'applied' if apply else 'plan only'})",
        "",
        f"- Listed now: {len(listing_ids)} listings, {sum(v['quantity'] for v in variants)} units, ${before:,.2f}",
        f"- After: {len(kept)} listings, {sum(len(vs) for vs in kept.values())} units, ${after:,.2f} "
        f"(frees ${before - after:,.2f} of the monthly limit)",
        "",
        "| listing | title | 30d impressions / views / sales | action |",
        "|---|---|---|---|",
    ]
    for lid in listing_ids:
        title = next(v["title"] for v in variants if v["listing_id"] == lid)[:50]
        t = traffic.get(lid, {})
        stats = f"{t.get('LISTING_IMPRESSION_TOTAL', 0)} / {t.get('LISTING_VIEWS_TOTAL', 0)} / {t.get('TRANSACTION', 0)}"
        if lid in kept:
            action = "keep: " + ", ".join(v["sku"] + (f" ({v['size']})" if v["size"] else "") for v in kept[lid])
        else:
            action = "end"
        lines.append(f"| {lid} | {title} | {stats} | {action} |")

    errors = []
    if apply:
        for v in zeroed:
            try:
                ebay.set_available_quantity(v["sku"], v["offer_id"], 0)
            except EbayApiError as exc:
                errors.append(f"{v['sku']} -> 0: {exc.body[:200]}")
        for group in ended:
            key = group[0]["group"]
            try:
                if key:
                    ebay._request(
                        "POST",
                        "/sell/inventory/v1/offer/withdraw_by_inventory_item_group",
                        json={"inventoryItemGroupKey": key, "marketplaceId": ebay.config.ebay_marketplace_id},
                    )
                else:
                    for v in group:
                        ebay.withdraw_offer(v["offer_id"])
            except EbayApiError as exc:
                errors.append(f"end {group[0]['listing_id']}: {exc.body[:200]}")
    if errors:
        lines += ["", "Errors:"] + [f"- {e}" for e in errors]

    report = "\n".join(lines) + "\n"
    print(report)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(report)


if __name__ == "__main__":
    main()
