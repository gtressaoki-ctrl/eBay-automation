import importlib.util
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ebay_automation.ebay_client import EbayApiError

_spec = importlib.util.spec_from_file_location(
    "list_owned_item", Path(__file__).resolve().parent.parent / "scripts" / "list_owned_item.py"
)
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)


@pytest.fixture
def spec(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "STATE_PATH", tmp_path / "owned_listings.json")
    monkeypatch.setattr(mod, "policy_ids", lambda config, ebay: {"fulfillmentPolicyId": "f"})
    (tmp_path / "cam").mkdir()
    (tmp_path / "cam" / "1.jpg").write_bytes(b"img")
    path = tmp_path / "cam.json"
    path.write_text(json.dumps({
        "sku": "OWN-CAM", "title": "Cam", "price": 69.99, "category_id": "11724",
        "condition": "USED_EXCELLENT", "condition_description": "ok", "aspects": {"Brand": ["X"]},
        "description_html": "<p>d</p>", "photos": ["1.jpg"],
    }))
    return path


def _ebay():
    ebay = MagicMock()
    ebay.upload_image.return_value = "https://i.ebayimg.com/1"
    ebay.create_offer.return_value = "off1"
    ebay.publish_offer.return_value = "123"
    return ebay


def test_publishes_with_uploaded_photos_and_records_the_url(spec):
    ebay = _ebay()
    entry = mod.list_item(MagicMock(export_merchant_location_key="loc"), ebay, spec)
    assert entry["listing_url"] == "https://www.ebay.com/itm/123"
    item = ebay.create_or_replace_inventory_item.call_args[0][1]
    assert item["product"]["imageUrls"] == ["https://i.ebayimg.com/1"]
    assert item["condition"] == "USED_EXCELLENT"
    assert ebay.create_offer.call_args[0][0]["pricingSummary"]["price"]["value"] == "69.99"
    assert json.loads(mod.STATE_PATH.read_text())["OWN-CAM"]["status"] == "published"


def test_selling_limit_keeps_the_draft_and_a_rerun_reuses_it(spec):
    ebay = _ebay()
    ebay.publish_offer.side_effect = EbayApiError("POST", "u", 400, "amount you can list")
    assert mod.list_item(MagicMock(), ebay, spec)["status"] == "waiting_for_limit"
    ebay = _ebay()
    assert mod.list_item(MagicMock(), ebay, spec)["status"] == "published"
    ebay.upload_image.assert_not_called()
    ebay.create_offer.assert_not_called()
    ebay.publish_offer.assert_called_once_with("off1")


def test_existing_offer_id_is_taken_from_the_error(spec):
    ebay = _ebay()
    ebay.create_offer.side_effect = EbayApiError(
        "POST", "u", 400, '{"parameters":[{"name":"offerId","value":"777"}]}'
    )
    mod.list_item(MagicMock(), ebay, spec)
    ebay.publish_offer.assert_called_once_with("777")


def test_upload_image_uses_the_media_api_host(monkeypatch):
    from ebay_automation import ebay_client

    calls = []

    class Resp:
        def __init__(self, headers=None, body=None):
            self.ok, self.status_code, self.text = True, 200, ""
            self.headers, self._body = headers or {}, body

        def json(self):
            return self._body

    def post(url, **kw):
        calls.append(url)
        return Resp(headers={"Location": "https://apim.ebay.com/commerce/media/v1_beta/image/IMG1"})

    def get(url, **kw):
        calls.append(url)
        return Resp(body={"imageUrl": "https://i.ebayimg.com/x.jpg"})

    monkeypatch.setattr(ebay_client.requests, "post", post)
    monkeypatch.setattr(ebay_client.requests, "get", get)
    monkeypatch.setattr(ebay_client, "get_user_access_token", lambda config: "t")
    client = ebay_client.EbayClient(MagicMock(ebay_env="PRODUCTION"))
    assert client.upload_image(b"x", "a.jpg") == "https://i.ebayimg.com/x.jpg"
    assert calls == [
        "https://apim.ebay.com/commerce/media/v1_beta/image/create_image_from_file",
        "https://apim.ebay.com/commerce/media/v1_beta/image/IMG1",
    ]
