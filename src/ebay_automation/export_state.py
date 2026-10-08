"""State for export (buy-after-sale) listings and orders, kept apart from
the print-on-demand files in ledger.py so neither pipeline can trip over
the other's records.

- state/export_listings.json: keyed by SKU (always "JX-<JAN>").
- state/export_orders.json: keyed by eBay order ID.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_STATE_DIR = Path(__file__).resolve().parent.parent.parent / "state"
LISTINGS_PATH = _STATE_DIR / "export_listings.json"
ORDERS_PATH = _STATE_DIR / "export_orders.json"

SKU_PREFIX = "JX-"


def sku_for(jan: str) -> str:
    return f"{SKU_PREFIX}{jan}"


def is_export_sku(sku: str | None) -> bool:
    return bool(sku) and sku.startswith(SKU_PREFIX)


def _read(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def _write(path: Path, data: dict) -> None:
    _STATE_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def load_listings() -> dict[str, dict[str, Any]]:
    return _read(LISTINGS_PATH)


def save_listing(sku: str, entry: dict[str, Any]) -> None:
    data = load_listings()
    data[sku] = entry
    _write(LISTINGS_PATH, data)


def load_orders() -> dict[str, dict[str, Any]]:
    return _read(ORDERS_PATH)


def save_order(order_id: str, record: dict[str, Any]) -> None:
    data = load_orders()
    data[order_id] = record
    _write(ORDERS_PATH, data)
