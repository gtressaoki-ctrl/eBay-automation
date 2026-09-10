import pytest

from ebay_automation import printify_client as printify_client_module
from ebay_automation.config import Config
from ebay_automation.printify_client import PrintifyApiError, PrintifyClient


class FakeResponse:
    def __init__(self, status_code=200, json_data=None, text=""):
        self.status_code = status_code
        self.ok = 200 <= status_code < 300
        self._json = json_data or {}
        self.text = text or str(self._json)

    def json(self):
        return self._json


@pytest.fixture
def client():
    return PrintifyClient(Config(printify_api_key="key", printify_shop_id="shop1"))


def test_missing_api_key_raises():
    with pytest.raises(RuntimeError, match="printify_api_key"):
        PrintifyClient(Config(printify_api_key=""))


def test_upload_image_base64_returns_id(monkeypatch, client):
    captured = {}

    def fake_request(method, url, headers=None, timeout=None, **kwargs):
        captured["json"] = kwargs.get("json")
        return FakeResponse(200, {"id": "img-1"})

    monkeypatch.setattr(printify_client_module.requests, "request", fake_request)
    image_id = client.upload_image_base64("design.png", "base64data")

    assert image_id == "img-1"
    assert captured["json"] == {"file_name": "design.png", "contents": "base64data"}


def test_create_product_builds_variants_and_print_areas(monkeypatch, client):
    captured = {}

    def fake_request(method, url, headers=None, timeout=None, **kwargs):
        captured["url"] = url
        captured["json"] = kwargs.get("json")
        return FakeResponse(200, {"id": "prod-1", "variants": [{"id": 1, "cost": 1250}]})

    monkeypatch.setattr(printify_client_module.requests, "request", fake_request)

    product = client.create_product(
        title="CAT MOM Tee",
        description="desc",
        blueprint_id=5,
        print_provider_id=10,
        variant_ids=[1, 2],
        image_id="img-1",
    )

    assert product["id"] == "prod-1"
    assert captured["url"].endswith("/shops/shop1/products.json")
    body = captured["json"]
    assert body["blueprint_id"] == 5
    assert body["print_provider_id"] == 10
    assert [v["id"] for v in body["variants"]] == [1, 2]
    assert body["print_areas"][0]["variant_ids"] == [1, 2]
    assert body["print_areas"][0]["placeholders"][0]["images"][0]["id"] == "img-1"


def test_submit_order_sends_expected_payload(monkeypatch, client):
    captured = {}

    def fake_request(method, url, headers=None, timeout=None, **kwargs):
        captured["url"] = url
        captured["json"] = kwargs.get("json")
        return FakeResponse(200, {"id": "order-1"})

    monkeypatch.setattr(printify_client_module.requests, "request", fake_request)

    result = client.submit_order(
        external_id="ebay-order-1",
        line_items=[{"product_id": "prod-1", "variant_id": 1, "quantity": 2}],
        shipping_address={"first_name": "Jane", "country": "US"},
    )

    assert result["id"] == "order-1"
    assert captured["url"].endswith("/shops/shop1/orders.json")
    assert captured["json"]["external_id"] == "ebay-order-1"
    assert captured["json"]["address_to"]["first_name"] == "Jane"


def test_error_response_raises_printify_api_error(monkeypatch, client):
    monkeypatch.setattr(
        printify_client_module.requests, "request", lambda *a, **k: FakeResponse(422, {}, text="bad payload")
    )
    with pytest.raises(PrintifyApiError):
        client.upload_image_base64("design.png", "data")
