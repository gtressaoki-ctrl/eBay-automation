import pytest

from ebay_automation import ledger


@pytest.fixture(autouse=True)
def isolated_state(tmp_path, monkeypatch):
    monkeypatch.setattr(ledger, "_STATE_DIR", tmp_path)
    monkeypatch.setattr(ledger, "_PENDING_PATH", tmp_path / "pending_listings.json")
    monkeypatch.setattr(ledger, "_LEDGER_PATH", tmp_path / "ledger.json")
    monkeypatch.setattr(ledger, "_ORDER_STATE_PATH", tmp_path / "order_fulfillment.json")
    yield


def test_add_and_update_pending_listing():
    ledger.add_pending_listing("SKU1", {"status": "pending_approval", "issue_number": 42})
    assert ledger.get_pending_listing("SKU1")["status"] == "pending_approval"

    ledger.update_listing_status("SKU1", "published", ebay_listing_id="123")
    entry = ledger.get_pending_listing("SKU1")
    assert entry["status"] == "published"
    assert entry["ebay_listing_id"] == "123"


def test_update_unknown_sku_raises():
    with pytest.raises(KeyError):
        ledger.update_listing_status("MISSING", "published")


def test_record_order_fulfilled_updates_totals():
    ledger.record_order_fulfilled("ORDER1", "SKU1", revenue_cents=2500, cost_cents=1300, tracking_number="TRK1")
    data = ledger.load_ledger()
    assert data["totals"]["orders_fulfilled"] == 1
    assert data["totals"]["revenue_cents"] == 2500
    assert data["totals"]["cost_cents"] == 1300
    assert data["totals"]["profit_cents"] == 1200
    assert data["orders"][0]["tracking_number"] == "TRK1"


def test_adjust_daily_quota_increases_when_profitable():
    ledger.record_order_fulfilled("ORDER1", "SKU1", revenue_cents=2500, cost_cents=1300, tracking_number="TRK1")
    starting_quota = ledger.load_ledger()["daily_listing_quota"]
    new_quota = ledger.adjust_daily_quota(max_quota=10)
    assert new_quota == starting_quota + 1


def test_adjust_daily_quota_holds_steady_with_no_orders():
    starting_quota = ledger.load_ledger()["daily_listing_quota"]
    new_quota = ledger.adjust_daily_quota()
    assert new_quota == starting_quota


def test_pause_forces_quota_to_zero():
    ledger.pause("policy warning received")
    assert ledger.adjust_daily_quota() == 0
    assert ledger.load_ledger()["pause_reason"] == "policy warning received"


def test_order_state_roundtrip():
    assert ledger.get_order_record("ORDER1") is None
    ledger.set_order_record("ORDER1", {"status": "submitted"})
    assert ledger.get_order_record("ORDER1") == {"status": "submitted"}
