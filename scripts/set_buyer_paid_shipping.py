#!/usr/bin/env python3
"""Switch the configured eBay shipping (fulfillment) policy from free
shipping to a flat, buyer-paid domestic rate.

Printify bills us the same shipping either way; charging the buyer for it
is what turns a ~$0.68 unit margin into ~$5.70. The policy is shared by
every listing that uses it, so this changes all of them at once.

Usage (or run the "Set buyer-paid shipping" workflow):
    PYTHONPATH=src python scripts/set_buyer_paid_shipping.py 5.79
"""
from __future__ import annotations

import json
import sys

from ebay_automation.config import load_config
from ebay_automation.ebay_client import EbayClient


def buyer_paid(policy: dict, cost: str) -> dict:
    policy = {k: v for k, v in policy.items() if k not in ("fulfillmentPolicyId", "warnings")}
    for option in policy.get("shippingOptions", []):
        if option.get("optionType") != "DOMESTIC":
            continue
        option["costType"] = "FLAT_RATE"
        for service in option.get("shippingServices", []):
            service["freeShipping"] = False
            service["shippingCost"] = {"value": cost, "currency": "USD"}
    return policy


def _summary(policy: dict) -> str:
    lines = [f"name={policy.get('name')!r} handlingTime={policy.get('handlingTime')}"]
    for option in policy.get("shippingOptions", []):
        for service in option.get("shippingServices", []):
            lines.append(
                f"  {option.get('optionType')} {option.get('costType')} "
                f"{service.get('shippingServiceCode')} free={service.get('freeShipping')} "
                f"cost={json.dumps(service.get('shippingCost'))}"
            )
    return "\n".join(lines)


def main() -> None:
    cost = sys.argv[1] if len(sys.argv) > 1 else "5.79"
    config = load_config()
    config.require("ebay_fulfillment_policy_id")
    ebay = EbayClient(config)
    policy_id = config.ebay_fulfillment_policy_id

    before = ebay.get_fulfillment_policy(policy_id)
    print("BEFORE\n" + _summary(before))
    ebay.update_fulfillment_policy(policy_id, buyer_paid(before, cost))
    print("AFTER\n" + _summary(ebay.get_fulfillment_policy(policy_id)))


if __name__ == "__main__":
    main()
