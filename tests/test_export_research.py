import datetime

import pytest

from ebay_automation import export_research, fx, research, yahoo_shopping
from ebay_automation.config import Config
from ebay_automation.export_genres import ExportGenre
from ebay_automation.yahoo_shopping import DomesticOffer


class FakeResponse:
    def __init__(self, json_data):
        self._json = json_data

    def raise_for_status(self):
        pass

    def json(self):
        return self._json


@pytest.fixture(autouse=True)
def fixed_fx(monkeypatch):
    monkeypatch.setenv("EXPORT_SELLER_DUTY_RATE", "0")
    monkeypatch.setattr(research, "get_app_access_token", lambda config: "fake-app-token")
    monkeypatch.setattr(fx, "rate_to_jpy", lambda currency, config: {"USD": 150.0, "JPY": 1.0}.get(currency))


def _days_ago(days: int) -> str:
    stamp = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
    return stamp.isoformat().replace("+00:00", "Z")


def _item(item_id, price, sold, age_days, gtin=None, title="Gundam HG kit"):
    item = {
        "itemId": item_id,
        "title": title,
        "itemWebUrl": f"https://www.ebay.com/itm/{item_id}",
        "price": {"value": price, "currency": "USD"},
        "shippingOptions": [{"shippingCost": {"value": "0.00", "currency": "USD"}}],
        "estimatedAvailabilities": [{"estimatedSoldQuantity": sold}],
        "itemCreationDate": _days_ago(age_days),
    }
    if gtin:
        item["gtin"] = gtin
    return item


def _browse(items):
    by_id = {i["itemId"]: i for i in items}

    def fake_get(url, headers=None, params=None, timeout=None):
        if "/item_summary/search" in url:
            assert "itemLocationCountry:JP" in params["filter"]
            return FakeResponse({"total": 500, "itemSummaries": [{"itemId": i} for i in by_id]})
        return FakeResponse(by_id[url.rsplit("/", 1)[-1].replace("%7C", "|")])

    return fake_get


def test_valid_jan_checks_digit_and_pads_upc():
    assert export_research.valid_jan("4573102616098") == "4573102616098"
    assert export_research.valid_jan("4573102616091") is None
    assert export_research.valid_jan("036000291452") == "0036000291452"
    assert export_research.valid_jan(None) is None
    assert export_research.valid_jan("Does not apply") is None


def test_profit_counts_fees_fx_and_shipping():
    config = Config(export_fx_haircut=0.0, export_fee_rate=0.15, export_fee_fixed_usd_cents=0)
    # $40 -> 6000 yen; fees 900; purchase 2000; small shipping 2200; free domestic
    profit, margin = export_research.profit_jpy(40.0, "USD", 2000, True, "small", config)
    assert profit == 6000 - 900 - 2000 - 2200
    assert margin == pytest.approx(900 / 6000)


def test_tax_refund_and_domestic_shipping():
    base = Config(export_fx_haircut=0.0, export_fee_rate=0.0, export_fee_fixed_usd_cents=0)
    refunded = Config(export_fx_haircut=0.0, export_fee_rate=0.0, export_fee_fixed_usd_cents=0, export_tax_refund=True)
    p_free, _ = export_research.profit_jpy(40.0, "USD", 1100, True, "small", base)
    p_paid, _ = export_research.profit_jpy(40.0, "USD", 1100, False, "small", base)
    p_refund, _ = export_research.profit_jpy(40.0, "USD", 1100, True, "small", refunded)
    assert p_free - p_paid == base.export_domestic_shipping_jpy
    assert p_refund - p_free == 100


def test_measure_genre_prices_matched_products(monkeypatch):
    items = [
        _item("v1|1", "80.00", 30, 30, gtin="4573102616098"),  # 30/month, profitable
        _item("v1|2", "20.00", 10, 30, gtin="4549660000006"),  # sells but loses money
        _item("v1|3", "50.00", 0, 365, gtin="4902370000009"),  # never sold: not priced
        _item("v1|4", "45.00", 5, 30),  # no JAN
    ]
    monkeypatch.setattr(research.requests, "get", _browse(items))
    offers = {"4573102616098": 3000, "4549660000006": 2500}
    looked_up = []

    def fake_offer(jan, config):
        looked_up.append(jan)
        return DomesticOffer(jan, "x", offers[jan], True, f"https://store/{jan}", "shop")

    monkeypatch.setattr(yahoo_shopping, "cheapest_new_offer", fake_offer)
    config = Config(yahoo_app_id="yid", export_min_profit_jpy=1500)
    genre = ExportGenre("gunpla", "ガンプラ", "gunpla", "medium")

    result = export_research.measure_genre(genre, config)

    assert result.sampled == 4
    assert result.listings_with_sales == 3
    assert result.with_jan == 2
    assert sorted(looked_up) == ["4549660000006", "4573102616098"]
    assert result.matched == 2
    assert result.profitable == 1
    best = result.products[0]
    assert best.jan == "4573102616098"
    assert best.profit_jpy >= 1500
    assert result.expected_monthly_profit_jpy == round(best.profit_jpy * best.units_per_month)


def test_bundle_listings_are_not_scored(monkeypatch):
    items = [_item("v1|1", "200.00", 30, 30, gtin="4573102616098", title="Lot of 5 Gundam kits")]
    monkeypatch.setattr(research.requests, "get", _browse(items))
    monkeypatch.setattr(
        yahoo_shopping, "cheapest_new_offer", lambda jan, config: DomesticOffer(jan, "x", 3000, True, "u", "s")
    )
    result = export_research.measure_genre(
        ExportGenre("g", "g", "q", "medium"), Config(yahoo_app_id="yid")
    )
    assert result.matched == 1
    assert result.products[0].bundle_suspect
    assert result.profitable == 0


def test_without_yahoo_key_ranks_by_demand_only(monkeypatch):
    items = [_item("v1|1", "60.00", 30, 30, gtin="4573102616098")]
    monkeypatch.setattr(research.requests, "get", _browse(items))

    def boom(jan, config):
        raise AssertionError("should not look up prices without a key")

    monkeypatch.setattr(yahoo_shopping, "cheapest_new_offer", boom)
    config = Config(yahoo_app_id="")
    result = export_research.measure_genre(ExportGenre("g", "g", "q", "small"), config)

    assert result.matched == 0
    report = export_research.render_report([result], False, config, "2026-10-07T00:00:00+00:00")
    assert "YAHOO_APP_ID が未設定" in report


def test_rank_prefers_expected_profit():
    a = export_research.GenreResult("a", "A", "", expected_monthly_profit_jpy=1000)
    b = export_research.GenreResult("b", "B", "", expected_monthly_profit_jpy=5000)
    assert [r.key for r in export_research.rank([a, b], True)] == ["b", "a"]


def test_yahoo_cheapest_skips_out_of_stock(monkeypatch):
    hits = [
        {"price": 900, "inStock": False, "condition": "new", "url": "a"},
        {"price": 1200, "inStock": True, "condition": "new", "url": "b", "shipping": {"code": 2},
         "seller": {"name": "shop"}, "name": "item"},
    ]
    monkeypatch.setattr(yahoo_shopping, "_MIN_INTERVAL_S", 0)

    class Resp(FakeResponse):
        status_code = 200

    monkeypatch.setattr(yahoo_shopping.requests, "get", lambda *a, **k: Resp({"hits": hits}))
    offer = yahoo_shopping.cheapest_new_offer("4573102616098", Config(yahoo_app_id="yid"))
    assert offer.price_jpy == 1200
    assert offer.free_shipping
    assert offer.url == "b"


def _priced(monkeypatch, title, price, domestic_price, domestic_name="商品"):
    items = [_item("v1|1", price, 30, 30, gtin="4573102616098", title=title)]
    monkeypatch.setattr(research.requests, "get", _browse(items))
    monkeypatch.setattr(
        yahoo_shopping,
        "cheapest_new_offer",
        lambda jan, config: DomesticOffer(jan, domestic_name, domestic_price, True, "u", "s"),
    )
    return export_research.measure_genre(ExportGenre("g", "g", "q", "small"), Config(yahoo_app_id="yid"))


def test_box_listing_matched_to_single_pack_is_not_scored(monkeypatch):
    result = _priced(monkeypatch, "Pokemon Card Booster Box Sealed", "124.00", 990, "拡張パック 1パック")
    assert result.products[0].mismatch
    assert result.profitable == 0


def test_box_listing_matched_to_box_is_scored(monkeypatch):
    result = _priced(monkeypatch, "Pokemon Card Booster Box Sealed", "124.00", 7000, "拡張パック BOX")
    assert result.products[0].mismatch == ""
    assert result.profitable == 1


def test_implausibly_cheap_source_is_not_scored(monkeypatch):
    # $110 sale (~16,000 yen) against a 752 yen purchase: a different size
    result = _priced(monkeypatch, "Anessa Perfect UV Sunscreen", "110.00", 752)
    assert "未満" in result.products[0].mismatch
    assert result.profitable == 0


@pytest.mark.parametrize(
    "title, bundle",
    [("UV Essence Gel 90g x3", True), ("3x Tomica", True), ("Beyblade X BX-52 Starter", False), ("Beyblade X 01", False)],
)
def test_bundle_regex(title, bundle):
    assert bool(export_research._BUNDLE_RE.search(title)) is bundle


def test_new_in_box_is_not_a_box_of_packs(monkeypatch):
    result = _priced(monkeypatch, "RICOH DW-5 Wide Conversion Lens New in Box", "124.00", 9591, "リコー ワイドコンバージョンレンズ")
    assert result.products[0].mismatch == ""


def test_seller_paid_duty_is_charged_on_item_value():
    no_duty = Config(export_fx_haircut=0.03, export_seller_duty_rate=0.0)
    duty = Config(export_fx_haircut=0.03, export_seller_duty_rate=0.15, export_duty_fee_jpy=300)
    p0, _ = export_research.profit_jpy(54.48, "USD", 2640, True, "small", no_duty)
    p1, _ = export_research.profit_jpy(54.48, "USD", 2640, True, "small", duty)
    # 15% of $54.48 at the mid rate (150), plus the prepayment fee.
    assert p0 - p1 == round(54.48 * 150 * 0.15 + 300)
