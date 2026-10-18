import datetime

import pytest

from ebay_automation import export_review, export_state
from ebay_automation.config import Config

NOW = datetime.datetime(2026, 11, 1, tzinfo=datetime.timezone.utc)


def _e(days_ago, **kw):
    stamp = (NOW - datetime.timedelta(days=days_ago)).isoformat()
    return {"title_changed_at": stamp, **kw}


@pytest.mark.parametrize(
    "stats, expected",
    [
        ({"LISTING_IMPRESSION_TOTAL": 10}, "表示されていない"),
        ({"LISTING_IMPRESSION_TOTAL": 500, "LISTING_VIEWS_TOTAL": 1}, "開かれない"),
        ({"LISTING_IMPRESSION_TOTAL": 500, "LISTING_VIEWS_TOTAL": 30}, "売れない"),
        ({"LISTING_IMPRESSION_TOTAL": 500, "TRANSACTION": 1}, "売れている"),
    ],
)
def test_verdict_after_the_title_settled(stats, expected):
    assert expected in export_review.verdict(_e(20), stats, NOW)


def test_recent_title_change_is_left_alone():
    assert "様子見" in export_review.verdict(_e(5), {"LISTING_IMPRESSION_TOTAL": 0}, NOW)


def test_report_reads_each_site_traffic(monkeypatch, tmp_path):
    monkeypatch.setattr(export_state, "LISTINGS_PATH", tmp_path / "l.json")
    monkeypatch.setattr(export_state, "_STATE_DIR", tmp_path)
    export_state.save_listing("JXGB-1", _e(20, sku="JXGB-1", status="published", title="Stadium", price=57.91,
                                           currency="GBP", ebay_listing_id="9", listing_url="https://www.ebay.co.uk/itm/9"))

    class Ebay:
        def get_traffic_report(self, ids, days):
            assert ids == ["9"]
            return {"9": {"LISTING_IMPRESSION_TOTAL": 300, "LISTING_VIEWS_TOTAL": 12, "TRANSACTION": 0}}

    body = export_review.report(Config(), {"GB": Ebay(), "US": Ebay()}, NOW)
    assert "£57.91" in body and "300 / 12 / 0" in body and "売れない" in body
