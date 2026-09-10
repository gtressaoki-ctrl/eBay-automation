#!/usr/bin/env python3
"""One-off helper: run this locally after setting PRINTIFY_API_KEY to find
the blueprint_id / print_provider_id / variant_ids for the blank product
you want to sell (e.g. a specific t-shirt). Copy the IDs you want into
your GitHub repository variables (PRINTIFY_BLUEPRINT_ID,
PRINTIFY_PRINT_PROVIDER_ID, PRINTIFY_VARIANT_IDS).

Usage:
    PRINTIFY_API_KEY=... python scripts/list_printify_catalog.py
    PRINTIFY_API_KEY=... python scripts/list_printify_catalog.py --blueprint 384
"""
from __future__ import annotations

import argparse
import os
import sys

import requests

_BASE = "https://api.printify.com/v1"


def _headers() -> dict:
    api_key = os.environ.get("PRINTIFY_API_KEY")
    if not api_key:
        print("Set PRINTIFY_API_KEY first.", file=sys.stderr)
        sys.exit(1)
    return {"Authorization": f"Bearer {api_key}"}


def list_blueprints() -> None:
    resp = requests.get(f"{_BASE}/catalog/blueprints.json", headers=_headers(), timeout=30)
    resp.raise_for_status()
    for bp in resp.json():
        print(f"{bp['id']:>6}  {bp['title']} ({bp.get('brand', '')})")


def list_providers_and_variants(blueprint_id: int) -> None:
    resp = requests.get(
        f"{_BASE}/catalog/blueprints/{blueprint_id}/print_providers.json", headers=_headers(), timeout=30
    )
    resp.raise_for_status()
    providers = resp.json()
    for p in providers:
        print(f"print_provider_id={p['id']}  {p['title']}")
        vresp = requests.get(
            f"{_BASE}/catalog/blueprints/{blueprint_id}/print_providers/{p['id']}/variants.json",
            headers=_headers(),
            timeout=30,
        )
        vresp.raise_for_status()
        for v in vresp.json().get("variants", [])[:10]:
            print(f"    variant_id={v['id']}  {v.get('title')}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--blueprint", type=int, default=None, help="Blueprint ID to inspect print providers/variants for")
    args = parser.parse_args()

    if args.blueprint:
        list_providers_and_variants(args.blueprint)
    else:
        list_blueprints()
