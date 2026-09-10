import pytest

from ebay_automation import research as research_module
from ebay_automation.config import Config
from ebay_automation.research import _score, rank_niches, score_niche


def test_score_peaks_near_sweet_spot():
    sweet_spot = _score(total_listings=3000, avg_price=24)
    low_demand = _score(total_listings=5, avg_price=24)
    oversaturated = _score(total_listings=2_000_000, avg_price=24)
    off_price = _score(total_listings=3000, avg_price=90)

    assert sweet_spot > low_demand
    assert sweet_spot > oversaturated
    assert sweet_spot > off_price


def test_score_zero_listings_or_price_is_low():
    assert _score(0, 24) < 0.5
    assert _score(3000, 0) < 0.5


class FakeResponse:
    def __init__(self, json_data):
        self._json = json_data

    def raise_for_status(self):
        pass

    def json(self):
        return self._json


@pytest.fixture(autouse=True)
def fake_app_token(monkeypatch):
    monkeypatch.setattr(research_module, "get_app_access_token", lambda config: "fake-app-token")


def test_score_niche_uses_browse_api(monkeypatch):
    def fake_get(url, headers=None, params=None, timeout=None):
        assert params["q"] == "cat mom shirt"
        return FakeResponse(
            {
                "total": 3200,
                "itemSummaries": [
                    {"price": {"value": "22.00", "currency": "USD"}},
                    {"price": {"value": "26.00", "currency": "USD"}},
                ],
            }
        )

    monkeypatch.setattr(research_module.requests, "get", fake_get)

    result = score_niche("cat mom shirt", Config())

    assert result.total_listings == 3200
    assert result.avg_price == 24.0
    assert result.score > 0


def test_rank_niches_orders_by_score_desc(monkeypatch):
    responses_by_keyword = {
        "good": {"total": 3000, "itemSummaries": [{"price": {"value": "24.00", "currency": "USD"}}]},
        "bad": {"total": 5, "itemSummaries": [{"price": {"value": "1.00", "currency": "USD"}}]},
    }

    def fake_get(url, headers=None, params=None, timeout=None):
        return FakeResponse(responses_by_keyword[params["q"]])

    monkeypatch.setattr(research_module.requests, "get", fake_get)

    ranked = rank_niches(Config(), keywords=["bad", "good"])

    assert [n.keyword for n in ranked] == ["good", "bad"]
