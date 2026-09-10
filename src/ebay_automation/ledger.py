"""Persistence for pipeline state, stored as JSON files committed back to
the repo by the GitHub Actions workflows (no external database needed).

- state/pending_listings.json: draft offers awaiting human approval, and
  a running record of published/rejected ones (keyed by SKU).
- state/ledger.json: revenue/cost/profit totals and per-order history,
  used to decide whether to raise or lower the daily listing quota.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_STATE_DIR = Path(__file__).resolve().parent.parent.parent / "state"
_PENDING_PATH = _STATE_DIR / "pending_listings.json"
_LEDGER_PATH = _STATE_DIR / "ledger.json"
_ORDER_STATE_PATH = _STATE_DIR / "order_fulfillment.json"

_EMPTY_LEDGER = {
    "daily_listing_quota": 3,
    "totals": {
        "listings_created": 0,
        "listings_published": 0,
        "orders_fulfilled": 0,
        "revenue_cents": 0,
        "cost_cents": 0,
        "profit_cents": 0,
    },
    "orders": [],
    "paused": False,
    "pause_reason": None,
}


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return json.loads(json.dumps(default))  # deep copy
    return json.loads(path.read_text())


def _write_json(path: Path, data: Any) -> None:
    _STATE_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def load_pending_listings() -> dict:
    return _read_json(_PENDING_PATH, {})


def save_pending_listings(data: dict) -> None:
    _write_json(_PENDING_PATH, data)


def add_pending_listing(sku: str, entry: dict) -> None:
    data = load_pending_listings()
    data[sku] = entry
    save_pending_listings(data)


def get_pending_listing(sku: str) -> dict | None:
    return load_pending_listings().get(sku)


def update_listing_status(sku: str, status: str, **extra: Any) -> None:
    data = load_pending_listings()
    if sku not in data:
        raise KeyError(f"Unknown SKU in pending_listings.json: {sku}")
    data[sku]["status"] = status
    data[sku].update(extra)
    save_pending_listings(data)


def load_ledger() -> dict:
    return _read_json(_LEDGER_PATH, _EMPTY_LEDGER)


def save_ledger(data: dict) -> None:
    _write_json(_LEDGER_PATH, data)


def record_listing_created(quantity: int = 1) -> None:
    ledger = load_ledger()
    ledger["totals"]["listings_created"] += quantity
    save_ledger(ledger)


def record_listing_published() -> None:
    ledger = load_ledger()
    ledger["totals"]["listings_published"] += 1
    save_ledger(ledger)


def record_order_fulfilled(order_id: str, sku: str, revenue_cents: int, cost_cents: int, tracking_number: str) -> None:
    ledger = load_ledger()
    ledger["orders"].append(
        {
            "order_id": order_id,
            "sku": sku,
            "revenue_cents": revenue_cents,
            "cost_cents": cost_cents,
            "profit_cents": revenue_cents - cost_cents,
            "tracking_number": tracking_number,
        }
    )
    totals = ledger["totals"]
    totals["orders_fulfilled"] += 1
    totals["revenue_cents"] += revenue_cents
    totals["cost_cents"] += cost_cents
    totals["profit_cents"] += revenue_cents - cost_cents
    save_ledger(ledger)


def adjust_daily_quota(max_quota: int = 15, min_quota: int = 1) -> int:
    """Simple rule-based reinvestment: profitable so far -> nudge quota up.

    No orders yet -> hold steady (still building initial listings).
    Explicitly paused (e.g. a policy warning was recorded) -> quota 0.
    """
    ledger = load_ledger()
    if ledger.get("paused"):
        ledger["daily_listing_quota"] = 0
        save_ledger(ledger)
        return 0

    totals = ledger["totals"]
    quota = ledger.get("daily_listing_quota", 3)
    if totals["orders_fulfilled"] > 0 and totals["profit_cents"] > 0:
        quota = min(quota + 1, max_quota)
    quota = max(quota, min_quota)
    ledger["daily_listing_quota"] = quota
    save_ledger(ledger)
    return quota


def load_order_state() -> dict:
    return _read_json(_ORDER_STATE_PATH, {})


def save_order_state(data: dict) -> None:
    _write_json(_ORDER_STATE_PATH, data)


def get_order_record(order_id: str) -> dict | None:
    return load_order_state().get(order_id)


def set_order_record(order_id: str, record: dict) -> None:
    data = load_order_state()
    data[order_id] = record
    save_order_state(data)


def pause(reason: str) -> None:
    ledger = load_ledger()
    ledger["paused"] = True
    ledger["pause_reason"] = reason
    save_ledger(ledger)
