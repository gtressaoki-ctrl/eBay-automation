import importlib.util
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ebay_automation import ledger

_spec = importlib.util.spec_from_file_location(
    "retire_mug_listings", Path(__file__).resolve().parent.parent / "scripts" / "retire_mug_listings.py"
)
retire_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(retire_mod)


@pytest.fixture
def state(tmp_path, monkeypatch):
    monkeypatch.setattr(ledger, "_STATE_DIR", tmp_path)
    monkeypatch.setattr(ledger, "_PENDING_PATH", tmp_path / "pending_listings.json")
    monkeypatch.setattr(ledger, "_LEDGER_PATH", tmp_path / "ledger.json")
    ledger.save_pending_listings(
        {
            "POD-a": {"status": "published", "ebay_offer_id": "o-a", "ebay_listing_id": "1"},
            "POD-b": {"status": "published", "ebay_offer_id": "o-b", "ebay_listing_id": "2"},
            "POD-c": {"status": "published", "ebay_offer_id": "o-c", "ebay_listing_id": "3"},
            "old": {"status": "rejected", "ebay_offer_id": "o-old"},
            "JX-1": {"status": "published", "ebay_offer_id": "o-jx", "ebay_listing_id": "9"},
        }
    )


def test_retires_live_listings_except_the_kept_ones(state):
    ebay = MagicMock()
    assert retire_mod.retire(ebay, {"2"}, "why") == ["POD-a", "POD-c"]
    saved = ledger.load_pending_listings()
    assert [saved["POD-" + k]["status"] for k in "abc"] == ["retired", "published", "retired"]
    assert saved["JX-1"]["status"] == "published"
    assert saved["POD-a"]["retired_reason"] == "why"
    assert sorted(c.args[0] for c in ebay.withdraw_offer.call_args_list) == ["o-a", "o-c"]


def test_a_failed_withdrawal_leaves_that_listing_published(state):
    ebay = MagicMock()
    ebay.withdraw_offer.side_effect = [RuntimeError("500"), None, None]
    retire_mod.retire(ebay, set(), "why")
    assert ledger.load_pending_listings()["POD-a"]["status"] == "published"


def test_pause_stops_the_research_run(state):
    retire_mod.pause("why")
    assert ledger.load_ledger()["paused"] is True
