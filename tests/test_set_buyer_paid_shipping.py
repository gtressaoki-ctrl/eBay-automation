import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "set_buyer_paid_shipping", Path(__file__).resolve().parent.parent / "scripts" / "set_buyer_paid_shipping.py"
)
script = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(script)


def test_domestic_free_shipping_becomes_a_flat_buyer_paid_rate():
    policy = {
        "fulfillmentPolicyId": "264302633024",
        "name": "Default",
        "handlingTime": {"value": 3, "unit": "DAY"},
        "shippingOptions": [
            {
                "optionType": "DOMESTIC",
                "costType": "FLAT_RATE",
                "shippingServices": [{"shippingServiceCode": "USPSGroundAdvantage", "freeShipping": True}],
            },
            {
                "optionType": "INTERNATIONAL",
                "costType": "FLAT_RATE",
                "shippingServices": [{"shippingServiceCode": "X", "freeShipping": True}],
            },
        ],
    }

    updated = script.buyer_paid(policy, "5.79")

    assert "fulfillmentPolicyId" not in updated
    domestic, international = updated["shippingOptions"]
    assert domestic["shippingServices"][0]["freeShipping"] is False
    assert domestic["shippingServices"][0]["shippingCost"] == {"value": "5.79", "currency": "USD"}
    # Only the domestic rate is changed; international stays as configured.
    assert international["shippingServices"][0]["freeShipping"] is True
