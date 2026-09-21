import datetime

import pytest

from ebay_automation import research as research_module
from ebay_automation.config import Config
from ebay_automation.research import (
    NicheDemand,
    measure_niche,
    rank_niches,
    target_price_cents,
    unit_profit_cents,
)


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


def _days_ago(days: int) -> str:
    stamp = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
    return stamp.isoformat().replace("+00:00", "Z")


def _browse_stub(items_by_keyword: dict[str, list[dict]]):
    """Serve item_summary/search and item/<id> out of a per-keyword fixture."""
    by_id = {
        item["itemId"]: item for items in items_by_keyword.values() for item in items
    }

    def fake_get(url, headers=None, params=None, timeout=None):
        if "/item_summary/search" in url:
            items = items_by_keyword[params["q"]]
            return FakeResponse(
                {"total": len(items) * 100, "itemSummaries": [{"itemId": i["itemId"]} for i in items]}
            )
        item_id = url.rsplit("/", 1)[-1].replace("%7C", "|")
        return FakeResponse(by_id[item_id])

    return fake_get


def _item(item_id: str, price: str, sold: int, age_days: int) -> dict:
    return {
        "itemId": item_id,
        "price": {"value": price, "currency": "USD"},
        "estimatedAvailabilities": [{"estimatedSoldQuantity": sold}],
        "itemCreationDate": _days_ago(age_days),
    }


def test_measure_niche_counts_units_and_sales_rate(monkeypatch):
    items = [
        _item("v1|1", "18.00", 30, 30),  # 30 units in a month
        _item("v1|2", "22.00", 0, 365),  # never sold
    ]
    monkeypatch.setattr(research_module.requests, "get", _browse_stub({"kanji mug": items}))

    demand = measure_niche("kanji mug", Config())

    assert demand is not None
    assert demand.sampled == 2
    assert demand.listings_with_sales == 1
    assert demand.units_sold == 30
    assert demand.sell_through_rate == 0.5
    # 30/30*30 = 30 for the first, ~0 for the second -> mean ~15
    assert 14 < demand.units_per_listing_per_month < 16


def test_measure_niche_prices_off_listings_that_actually_sold(monkeypatch):
    items = [
        _item("v1|1", "19.00", 4, 60),
        _item("v1|2", "99.00", 0, 60),  # wishful pricing, never sold
    ]
    monkeypatch.setattr(research_module.requests, "get", _browse_stub({"mug": items}))

    demand = measure_niche("mug", Config())

    assert demand.median_price_selling_cents == 1900
    assert target_price_cents(demand) == 1900


def test_target_price_falls_back_to_all_listings_when_nothing_sold(monkeypatch):
    items = [_item("v1|1", "12.00", 0, 100), _item("v1|2", "16.00", 0, 100)]
    monkeypatch.setattr(research_module.requests, "get", _browse_stub({"mug": items}))

    demand = measure_niche("mug", Config())

    assert demand.median_price_selling_cents is None
    assert target_price_cents(demand) == 1400


def test_measure_niche_returns_none_without_sold_quantity_data(monkeypatch):
    items = [{"itemId": "v1|1", "price": {"value": "20.00"}, "estimatedAvailabilities": [{}]}]
    monkeypatch.setattr(research_module.requests, "get", _browse_stub({"mug": items}))

    assert measure_niche("mug", Config()) is None


def test_unit_profit_subtracts_ebay_fees_and_landed_cost():
    # $18.00 sale, 13.25% + $0.40 fees, $11.79 landed cost
    assert unit_profit_cents(1800, 1179) == 1800 - (round(1800 * 0.1325) + 40) - 1179


def test_unit_profit_can_go_negative():
    assert unit_profit_cents(900, 1179) < 0


def test_rank_niches_orders_by_expected_monthly_profit(monkeypatch):
    fixture = {
        # Lower price, but sells constantly.
        "fast": [_item("v1|1", "20.00", 60, 30), _item("v1|2", "20.00", 30, 30)],
        # Same price, barely moves.
        "slow": [_item("v1|3", "20.00", 1, 300), _item("v1|4", "20.00", 0, 300)],
    }
    monkeypatch.setattr(research_module.requests, "get", _browse_stub(fixture))

    report = rank_niches(["slow", "fast"], Config(), product_cost_cents=1179)

    assert [d.keyword for d in report.ranked] == ["fast", "slow"]
    assert not report.rejected


def test_rank_niches_rejects_a_niche_that_cannot_clear_the_profit_floor(monkeypatch):
    fixture = {"cheap": [_item("v1|1", "9.00", 50, 30)]}
    monkeypatch.setattr(research_module.requests, "get", _browse_stub(fixture))

    report = rank_niches(["cheap"], Config(), product_cost_cents=1179, min_unit_profit_cents=100)

    assert not report.ranked
    assert [d.keyword for d in report.rejected] == ["cheap"]


def test_sell_through_rate_is_zero_when_nothing_sampled():
    demand = NicheDemand(
        keyword="x",
        active_listings=0,
        sampled=0,
        listings_with_sales=0,
        units_sold=0,
        units_per_listing_per_month=0.0,
        median_price_selling_cents=None,
        median_price_all_cents=None,
    )
    assert demand.sell_through_rate == 0.0
