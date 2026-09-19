"""One-time eBay seller account setup: a shipping-from location, and
fulfillment/payment/return business policies. These are prerequisites the
Inventory API's offers point to (merchantLocationKey / *PolicyId).

If a location/policy with the given key/name already exists, it's reused
instead of creating a duplicate. Business address and policy terms are real
business decisions, so this never invents them - point it at values you
set in .env (see .env.example's EBAY_* block).

Usage:
    python -m ebay.setup_account
"""
from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

from .client import EbayClient


def ensure_location(ebay: EbayClient) -> str:
    key = os.environ["EBAY_MERCHANT_LOCATION_KEY"]
    existing = {loc["merchantLocationKey"] for loc in ebay.list_inventory_locations()}
    if key in existing:
        print(f"   location '{key}' already exists.", file=sys.stderr)
        return key

    payload = {
        "location": {
            "address": {
                "addressLine1": os.environ["EBAY_LOCATION_ADDRESS_LINE1"],
                "city": os.environ["EBAY_LOCATION_CITY"],
                "stateOrProvince": os.environ["EBAY_LOCATION_STATE"],
                "postalCode": os.environ["EBAY_LOCATION_POSTAL_CODE"],
                "country": os.environ.get("EBAY_LOCATION_COUNTRY", "US"),
            }
        },
        "locationTypes": ["WAREHOUSE"],
        "name": os.environ.get("EBAY_LOCATION_NAME", key),
        "merchantLocationStatus": "ENABLED",
    }
    ebay.create_inventory_location(key, payload)
    print(f"   created location '{key}'.", file=sys.stderr)
    return key


def ensure_fulfillment_policy(ebay: EbayClient, marketplace_id: str) -> str:
    name = os.environ.get("EBAY_FULFILLMENT_POLICY_NAME", "EQUINOX standard shipping")
    for policy in ebay.list_fulfillment_policies(marketplace_id):
        if policy["name"] == name:
            print(f"   fulfillment policy '{name}' already exists.", file=sys.stderr)
            return policy["fulfillmentPolicyId"]

    handling_days = int(os.environ.get("EBAY_HANDLING_DAYS", "3"))
    payload = {
        "name": name,
        "marketplaceId": marketplace_id,
        "categoryTypes": [{"name": "ALL_EXCLUDING_MOTORS_VEHICLES"}],
        "handlingTime": {"value": handling_days, "unit": "DAY"},
        "shippingOptions": [
            {
                "optionType": "DOMESTIC",
                "costType": "FLAT_RATE",
                "shippingServices": [
                    {
                        "sortOrder": 1,
                        "shippingCarrierCode": os.environ.get("EBAY_SHIPPING_CARRIER", "USPS"),
                        "shippingServiceCode": os.environ.get("EBAY_SHIPPING_SERVICE", "USPSGroundAdvantage"),
                        "shippingCost": {"value": os.environ.get("EBAY_SHIPPING_COST", "0.00"), "currency": "USD"},
                        "freeShipping": os.environ.get("EBAY_SHIPPING_COST", "0.00") == "0.00",
                    }
                ],
            }
        ],
    }
    result = ebay.create_fulfillment_policy(payload)
    print(f"   created fulfillment policy '{name}'.", file=sys.stderr)
    return result["fulfillmentPolicyId"]


def ensure_payment_policy(ebay: EbayClient, marketplace_id: str) -> str:
    name = os.environ.get("EBAY_PAYMENT_POLICY_NAME", "EQUINOX managed payments")
    for policy in ebay.list_payment_policies(marketplace_id):
        if policy["name"] == name:
            print(f"   payment policy '{name}' already exists.", file=sys.stderr)
            return policy["paymentPolicyId"]

    payload = {
        "name": name,
        "marketplaceId": marketplace_id,
        "categoryTypes": [{"name": "ALL_EXCLUDING_MOTORS_VEHICLES"}],
        "immediatePay": False,
    }
    result = ebay.create_payment_policy(payload)
    print(f"   created payment policy '{name}'.", file=sys.stderr)
    return result["paymentPolicyId"]


def ensure_return_policy(ebay: EbayClient, marketplace_id: str) -> str:
    name = os.environ.get("EBAY_RETURN_POLICY_NAME", "EQUINOX 30-day returns")
    for policy in ebay.list_return_policies(marketplace_id):
        if policy["name"] == name:
            print(f"   return policy '{name}' already exists.", file=sys.stderr)
            return policy["returnPolicyId"]

    return_days = int(os.environ.get("EBAY_RETURN_DAYS", "30"))
    payload = {
        "name": name,
        "marketplaceId": marketplace_id,
        "returnsAccepted": True,
        "returnPeriod": {"value": return_days, "unit": "DAY"},
        "returnShippingCostPayer": os.environ.get("EBAY_RETURN_SHIPPING_PAYER", "BUYER"),
        "refundMethod": "MONEY_BACK",
    }
    result = ebay.create_return_policy(payload)
    print(f"   created return policy '{name}'.", file=sys.stderr)
    return result["returnPolicyId"]


def main(argv: list[str] | None = None) -> int:
    load_dotenv()

    marketplace_id = os.environ.get("EBAY_MARKETPLACE_ID", "EBAY_US")
    ebay = EbayClient(
        client_id=os.environ.get("EBAY_CLIENT_ID", ""),
        client_secret=os.environ.get("EBAY_CLIENT_SECRET", ""),
        ru_name=os.environ.get("EBAY_RU_NAME"),
        refresh_token=os.environ.get("EBAY_REFRESH_TOKEN"),
        sandbox=os.environ.get("EBAY_SANDBOX") == "true",
    )

    print("Ensuring inventory location...", file=sys.stderr)
    location_key = ensure_location(ebay)
    print("Ensuring fulfillment policy...", file=sys.stderr)
    fulfillment_id = ensure_fulfillment_policy(ebay, marketplace_id)
    print("Ensuring payment policy...", file=sys.stderr)
    payment_id = ensure_payment_policy(ebay, marketplace_id)
    print("Ensuring return policy...", file=sys.stderr)
    return_id = ensure_return_policy(ebay, marketplace_id)

    print("\nSave these to .env:\n", file=sys.stderr)
    print(f"EBAY_MERCHANT_LOCATION_KEY={location_key}")
    print(f"EBAY_FULFILLMENT_POLICY_ID={fulfillment_id}")
    print(f"EBAY_PAYMENT_POLICY_ID={payment_id}")
    print(f"EBAY_RETURN_POLICY_ID={return_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
