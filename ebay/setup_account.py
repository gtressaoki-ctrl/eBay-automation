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
import re
import sys

import requests
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

    # eBay's fulfillment policy schema requires a DOMESTIC shipping option to
    # be present even when the seller never actually ships domestically
    # (e.g. a Japan-based seller listing on EBAY_US) - omitting it fails
    # validation with SHIPELIG_ERROR_CODE_NAME=DOMESTIC_SHIPPING_REQUIRED.
    # The codes below are real eBay ShippingService enum values pulled from
    # the Trading API's GeteBayDetails(ShippingServiceDetails) reference,
    # not guessed - eBay silently rejects unlisted codes
    # (UNKNOWN_SHIPPING_SERVICE_CODE) with no live lookup in the REST APIs.
    shipping_options = [
        {
            "optionType": "DOMESTIC",
            "costType": "FLAT_RATE",
            "shippingServices": [
                {
                    "sortOrder": 1,
                    "shippingCarrierCode": os.environ.get("EBAY_DOMESTIC_SHIPPING_CARRIER", "USPS"),
                    "shippingServiceCode": os.environ.get("EBAY_DOMESTIC_SHIPPING_SERVICE", "USPSParcel"),
                    "shippingCost": {"value": os.environ.get("EBAY_DOMESTIC_SHIPPING_COST", "0.00"), "currency": "USD"},
                    "freeShipping": os.environ.get("EBAY_DOMESTIC_SHIPPING_COST", "0.00") == "0.00",
                }
            ],
        }
    ]

    if os.environ.get("EBAY_INCLUDE_INTERNATIONAL_SHIPPING", "true") == "true":
        ship_to_region = os.environ.get("EBAY_SHIP_TO_REGION", "US")
        shipping_options.append(
            {
                "optionType": "INTERNATIONAL",
                "costType": "FLAT_RATE",
                "shippingServices": [
                    {
                        "sortOrder": 1,
                        # "StandardInternational" is carrier-agnostic in eBay's
                        # schema (it auto-assigns shippingCarrierCode=GENERIC);
                        # the actual carrier used to fulfill (e.g. Japan Post)
                        # doesn't need to be declared here.
                        "shippingServiceCode": os.environ.get("EBAY_INTERNATIONAL_SHIPPING_SERVICE", "StandardInternational"),
                        "shippingCost": {"value": os.environ.get("EBAY_SHIPPING_COST", "25.00"), "currency": "USD"},
                        "freeShipping": False,
                        "shipToLocations": {"regionIncluded": [{"regionName": ship_to_region}]},
                    }
                ],
            }
        )

    payload = {
        "name": name,
        "marketplaceId": marketplace_id,
        "categoryTypes": [{"name": "ALL_EXCLUDING_MOTORS_VEHICLES"}],
        "handlingTime": {"value": handling_days, "unit": "DAY"},
        "shippingOptions": shipping_options,
    }
    result = ebay.create_fulfillment_policy(payload)
    print(f"   created fulfillment policy '{name}'.", file=sys.stderr)
    return result["fulfillmentPolicyId"]


def _duplicate_policy_id(exc: requests.HTTPError) -> str | None:
    """eBay refuses a second policy with the same categoryTypes/marketplace
    ('Duplicate Policy') - most accounts already have a default payment/
    return policy from signup, so extract and reuse it instead of failing."""
    match = re.search(r"'duplicatePolicyId', 'value': '(\d+)'", str(exc))
    return match.group(1) if match else None


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
    try:
        result = ebay.create_payment_policy(payload)
    except requests.HTTPError as exc:
        duplicate_id = _duplicate_policy_id(exc)
        if not duplicate_id:
            raise
        print(f"   reusing existing payment policy {duplicate_id} (account already has one for this category/marketplace).", file=sys.stderr)
        return duplicate_id
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
    try:
        result = ebay.create_return_policy(payload)
    except requests.HTTPError as exc:
        duplicate_id = _duplicate_policy_id(exc)
        if not duplicate_id:
            raise
        print(f"   reusing existing return policy {duplicate_id} (account already has one for this category/marketplace).", file=sys.stderr)
        return duplicate_id
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
