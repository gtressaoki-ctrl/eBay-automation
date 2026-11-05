import importlib.util
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ebay_automation import export_state

_spec = importlib.util.spec_from_file_location(
    "retire_export_listings", Path(__file__).resolve().parent.parent / "scripts" / "retire_export_listings.py"
)
retire_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(retire_mod)


@pytest.fixture(autouse=True)
def state(tmp_path, monkeypatch):
    monkeypatch.setattr(export_state, "_STATE_DIR", tmp_path)
    monkeypatch.setattr(export_state, "LISTINGS_PATH", tmp_path / "export_listings.json")
    export_state.save_listing("JX-a", {"status": "published", "ebay_offer_id": "o-a", "ebay_listing_id": "1"})
    export_state.save_listing("JX-b", {"status": "published", "ebay_offer_id": "o-b", "ebay_listing_id": "2"})
    export_state.save_listing("JX-c", {"status": "pending_approval", "ebay_offer_id": "o-c"})


def test_ends_only_the_named_live_listings():
    ebay = MagicMock()
    assert retire_mod.retire(ebay, ["JX-a", "JX-c", "JX-zz"], "why") == ["JX-a"]
    saved = export_state.load_listings()
    assert saved["JX-a"]["status"] == "withdrawn"
    assert saved["JX-a"]["paused_reason"] == "why"
    assert saved["JX-b"]["status"] == "published"
    assert saved["JX-c"]["status"] == "pending_approval"
    ebay.withdraw_offer.assert_called_once_with("o-a")


def test_a_failed_withdrawal_leaves_the_listing_live():
    ebay = MagicMock()
    ebay.withdraw_offer.side_effect = [RuntimeError("500"), None]
    assert retire_mod.retire(ebay, ["JX-a", "JX-b"], "why") == ["JX-b"]
    assert export_state.load_listings()["JX-a"]["status"] == "published"
