from unittest.mock import MagicMock

import pytest

from ebay_automation import pipeline_fulfill
from ebay_automation.config import Config

ORDER = {
    "orderId": "ord-1",
    "lineItems": [{"sku": "POD-a", "quantity": 1, "lineItemId": "li-1"}],
    "fulfillmentStartInstructions": [
        {"shippingStep": {"shipTo": {"fullName": "Ada Lovelace", "contactAddress": {"countryCode": "US"}}}}
    ],
}


@pytest.fixture
def state(monkeypatch):
    records = {}
    pending = {
        "POD-a": {
            "printify_product_id": "prod-a",
            "printify_variant_id": 65216,
            "price_cents": 1499,
            "cost_cents": 1192,
            "ebay_offer_id": "offer-a",
        }
    }
    monkeypatch.setattr(pipeline_fulfill.ledger, "get_pending_listing", lambda sku: pending.get(sku))
    monkeypatch.setattr(pipeline_fulfill.ledger, "set_order_record", lambda oid, rec: records.__setitem__(oid, dict(rec)))
    return records


def test_new_order_is_sent_to_production_and_the_listing_restocked(state):
    printify = MagicMock()
    printify.submit_order.return_value = {"id": "pf-1"}
    ebay = MagicMock()

    pipeline_fulfill._submit_to_printify(Config(listing_quantity=1), printify, ebay, ORDER)

    # Without this call Printify leaves API-created orders on hold and the
    # buyer's mug is never printed.
    printify.send_to_production.assert_called_once_with("pf-1")
    assert state["ord-1"]["sent_to_production"] is True
    # Listings carry quantity 1, so a sale leaves them at 0 until restocked.
    ebay.set_available_quantity.assert_called_once_with("POD-a", "offer-a", 1)


def test_failed_send_to_production_is_retried_on_the_next_sync(state):
    printify = MagicMock()
    printify.submit_order.return_value = {"id": "pf-1"}
    printify.send_to_production.side_effect = RuntimeError("503")
    ebay = MagicMock()

    record = pipeline_fulfill._submit_to_printify(Config(), printify, ebay, ORDER)
    assert state["ord-1"]["sent_to_production"] is False

    printify.send_to_production.side_effect = None
    printify.get_order.return_value = {"shipments": []}
    pipeline_fulfill._check_and_sync_shipment(Config(), ebay, printify, "ord-1", record)

    assert printify.send_to_production.call_count == 2
    assert state["ord-1"]["sent_to_production"] is True
    # Retrying the send must never create a second Printify order.
    printify.submit_order.assert_called_once()
