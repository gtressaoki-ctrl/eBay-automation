import json
from unittest.mock import MagicMock

import pytest

from ebay_automation import ledger, pipeline_approve
from ebay_automation.config import Config


@pytest.fixture(autouse=True)
def isolated_state(tmp_path, monkeypatch):
    monkeypatch.setattr(ledger, "_STATE_DIR", tmp_path)
    monkeypatch.setattr(ledger, "_PENDING_PATH", tmp_path / "pending_listings.json")
    monkeypatch.setattr(ledger, "_LEDGER_PATH", tmp_path / "ledger.json")
    monkeypatch.setattr(ledger, "_ORDER_STATE_PATH", tmp_path / "order_fulfillment.json")


def _event(issue_number=42, comment_body="/approve", labels=("pending-approval",), association="OWNER"):
    return {
        "comment": {"body": comment_body, "author_association": association},
        "issue": {"number": issue_number, "labels": [{"name": label} for label in labels]},
    }


@pytest.fixture
def event_file(tmp_path, monkeypatch):
    def write(event: dict) -> None:
        path = tmp_path / "event.json"
        path.write_text(json.dumps(event))
        monkeypatch.setenv("GITHUB_EVENT_PATH", str(path))

    return write


@pytest.fixture
def github(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(pipeline_approve, "GithubClient", lambda config: client)
    return client


@pytest.fixture
def ebay(monkeypatch):
    client = MagicMock()
    client.publish_offer.return_value = "listing-1"
    monkeypatch.setattr(pipeline_approve, "EbayClient", lambda config: client)
    return client


def _use_config(monkeypatch, **overrides) -> Config:
    cfg = Config(**overrides)
    monkeypatch.setattr(pipeline_approve, "load_config", lambda: cfg)
    return cfg


def _pending_listing(sku: str = "SKU-1", issue_number: int = 42) -> str:
    ledger.add_pending_listing(
        sku,
        {"issue_number": issue_number, "status": "pending_approval", "ebay_offer_id": "offer-1"},
    )
    return sku


def test_approve_publishes_without_touching_ads_when_disabled(event_file, github, ebay, monkeypatch):
    _use_config(monkeypatch, promoted_listings_enabled=False)
    event_file(_event())
    sku = _pending_listing()

    pipeline_approve.run()

    ebay.publish_offer.assert_called_once_with("offer-1")
    ebay.get_or_create_cost_per_sale_campaign.assert_not_called()
    comment = github.comment_issue.call_args[0][1]
    assert "広告" not in comment
    assert ledger.load_pending_listings()[sku]["status"] == "published"


def test_approve_promotes_the_listing_when_enabled(event_file, github, ebay, monkeypatch):
    _use_config(
        monkeypatch,
        promoted_listings_enabled=True,
        promoted_listings_bid_percentage=12.0,
        promoted_listings_campaign_name="test-camp",
    )
    ebay.get_or_create_cost_per_sale_campaign.return_value = "camp-1"
    event_file(_event())
    sku = _pending_listing()

    pipeline_approve.run()

    ebay.get_or_create_cost_per_sale_campaign.assert_called_once_with("test-camp", 12.0)
    ebay.promote_listing.assert_called_once_with("camp-1", sku, 12.0)
    comment = github.comment_issue.call_args[0][1]
    assert "広告" in comment


def test_approve_stays_published_even_when_promoted_listings_fails(event_file, github, ebay, monkeypatch):
    _use_config(monkeypatch, promoted_listings_enabled=True)
    ebay.get_or_create_cost_per_sale_campaign.side_effect = RuntimeError("missing sell.marketing scope")
    event_file(_event())
    sku = _pending_listing()

    pipeline_approve.run()

    github.close_issue.assert_called_once()
    comment = github.comment_issue.call_args[0][1]
    assert "失敗" in comment
    assert ledger.load_pending_listings()[sku]["status"] == "published"


def test_reject_never_touches_promoted_listings(event_file, github, ebay, monkeypatch):
    _use_config(monkeypatch, promoted_listings_enabled=True)
    monkeypatch.setattr(pipeline_approve, "PrintifyClient", lambda config: MagicMock())
    event_file(_event(comment_body="/reject"))
    sku = _pending_listing()

    pipeline_approve.run()

    ebay.publish_offer.assert_not_called()
    ebay.get_or_create_cost_per_sale_campaign.assert_not_called()
    assert ledger.load_pending_listings()[sku]["status"] == "rejected"
