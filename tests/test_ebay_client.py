import pytest

from ebay_automation import ebay_client as ebay_client_module
from ebay_automation.config import Config
from ebay_automation.ebay_client import EbayApiError, EbayClient


class FakeResponse:
    def __init__(self, status_code=200, json_data=None, headers=None, text=""):
        self.status_code = status_code
        self.ok = 200 <= status_code < 300
        self._json = json_data or {}
        self.headers = headers or {}
        self.text = text or str(self._json)

    def json(self):
        return self._json


@pytest.fixture(autouse=True)
def fake_token(monkeypatch):
    monkeypatch.setattr(ebay_client_module, "get_user_access_token", lambda config: "fake-token")


@pytest.fixture
def client():
    return EbayClient(Config(ebay_env="SANDBOX"))


def test_create_offer_returns_offer_id(monkeypatch, client):
    captured = {}

    def fake_request(method, url, headers=None, timeout=None, **kwargs):
        captured["method"] = method
        captured["url"] = url
        captured["json"] = kwargs.get("json")
        return FakeResponse(200, {"offerId": "off-123"})

    monkeypatch.setattr(ebay_client_module.requests, "request", fake_request)

    offer_id = client.create_offer({"sku": "SKU1", "marketplaceId": "EBAY_US"})

    assert offer_id == "off-123"
    assert captured["method"] == "POST"
    assert captured["url"].endswith("/sell/inventory/v1/offer")
    assert captured["json"]["sku"] == "SKU1"


def test_publish_offer_returns_listing_id(monkeypatch, client):
    monkeypatch.setattr(
        ebay_client_module.requests, "request", lambda *a, **k: FakeResponse(200, {"listingId": "999"})
    )
    assert client.publish_offer("off-123") == "999"


def test_get_orders_returns_list(monkeypatch, client):
    monkeypatch.setattr(
        ebay_client_module.requests,
        "request",
        lambda *a, **k: FakeResponse(200, {"orders": [{"orderId": "o1"}, {"orderId": "o2"}]}),
    )
    orders = client.get_orders()
    assert [o["orderId"] for o in orders] == ["o1", "o2"]


def test_create_shipping_fulfillment_parses_location_header(monkeypatch, client):
    monkeypatch.setattr(
        ebay_client_module.requests,
        "request",
        lambda *a, **k: FakeResponse(
            201, {}, headers={"Location": "https://api.ebay.com/.../shipping_fulfillment/abc123"}
        ),
    )
    fulfillment_id = client.create_shipping_fulfillment("order1", [{"lineItemId": "li1", "quantity": 1}], "TRK1", "USPS")
    assert fulfillment_id == "abc123"


def test_error_response_raises_ebay_api_error(monkeypatch, client):
    monkeypatch.setattr(
        ebay_client_module.requests, "request", lambda *a, **k: FakeResponse(400, {}, text="bad request")
    )
    with pytest.raises(EbayApiError):
        client.create_offer({"sku": "SKU1"})
