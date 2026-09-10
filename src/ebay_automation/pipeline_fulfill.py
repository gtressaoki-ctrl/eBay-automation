"""Recurring entrypoint: pull new eBay orders, place the matching Printify
production order (this is the actual "ship the product" step — Printify
prints and ships directly to the buyer), then once Printify reports a
tracking number, mark the eBay order as shipped.

Two-phase per order (state tracked in state/order_fulfillment.json)
because production/shipping is not instant:
  1. "submitted"  — order handed to Printify, tracking not yet available
  2. "shipped"    — tracking number received and pushed back to eBay

Run via: python -m ebay_automation.pipeline_fulfill
Triggered on a schedule by .github/workflows/fulfill_orders.yml.
"""
from __future__ import annotations

import logging

from . import ledger
from .config import load_config
from .ebay_client import EbayClient
from .printify_client import PrintifyClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

_CARRIER_MAP = {
    "usps": "USPS",
    "ups": "UPS",
    "fedex": "FedEx",
    "dhl": "DHL",
}


def _map_carrier(name: str) -> str:
    return _CARRIER_MAP.get((name or "").strip().lower(), "Other")


def _split_name(full_name: str) -> tuple[str, str]:
    parts = (full_name or "Buyer").split(" ", 1)
    return (parts[0], parts[1] if len(parts) > 1 else "")


def _to_printify_address(ship_to: dict) -> dict:
    addr = ship_to.get("contactAddress", {})
    first, last = _split_name(ship_to.get("fullName", ""))
    return {
        "first_name": first,
        "last_name": last,
        "email": ship_to.get("email", "buyer@example.com"),
        "phone": (ship_to.get("primaryPhone") or {}).get("phoneNumber", ""),
        "country": addr.get("countryCode", "US"),
        "region": addr.get("stateOrProvince", ""),
        "address1": addr.get("addressLine1", ""),
        "address2": addr.get("addressLine2", ""),
        "city": addr.get("city", ""),
        "zip": addr.get("postalCode", ""),
    }


def _submit_to_printify(config, printify: PrintifyClient, ebay_order: dict) -> dict | None:
    order_id = ebay_order["orderId"]
    line_items = ebay_order.get("lineItems", [])
    ship_to = ebay_order["fulfillmentStartInstructions"][0]["shippingStep"]["shipTo"]

    printify_line_items = []
    ebay_line_items = []
    skus = []
    for li in line_items:
        sku = li["sku"]
        pending = ledger.get_pending_listing(sku)
        if pending is None:
            log.warning("Order %s references unknown SKU %s (not ours?) skipping line item.", order_id, sku)
            continue
        quantity = int(li["quantity"])
        printify_line_items.append(
            {
                "product_id": pending["printify_product_id"],
                "variant_id": pending["printify_variant_id"],
                "quantity": quantity,
            }
        )
        ebay_line_items.append({"lineItemId": li["lineItemId"], "quantity": quantity})
        skus.append({"sku": sku, "quantity": quantity, "unit_price_cents": pending["price_cents"], "unit_cost_cents": pending["cost_cents"]})

    if not printify_line_items:
        log.warning("Order %s had no recognized line items; skipping.", order_id)
        return None

    printify_order = printify.submit_order(
        external_id=order_id,
        line_items=printify_line_items,
        shipping_address=_to_printify_address(ship_to),
    )
    record = {
        "status": "submitted",
        "printify_order_id": printify_order["id"],
        "ebay_line_items": ebay_line_items,
        "skus": skus,
    }
    ledger.set_order_record(order_id, record)
    log.info("Submitted order %s to Printify as %s", order_id, printify_order["id"])
    return record


def _check_and_sync_shipment(config, ebay: EbayClient, printify: PrintifyClient, order_id: str, record: dict) -> None:
    printify_order = printify.get_order(record["printify_order_id"])
    shipments = printify_order.get("shipments") or []
    if not shipments:
        log.info("Order %s not shipped by Printify yet.", order_id)
        return

    shipment = shipments[0]
    tracking_number = shipment.get("number") or shipment.get("tracking_number", "")
    carrier = _map_carrier(shipment.get("carrier", ""))

    ebay.create_shipping_fulfillment(
        order_id=order_id,
        line_items=record["ebay_line_items"],
        tracking_number=tracking_number,
        shipping_carrier_code=carrier,
    )

    revenue_cents = sum(s["unit_price_cents"] * s["quantity"] for s in record["skus"])
    cost_cents = sum(s["unit_cost_cents"] * s["quantity"] for s in record["skus"])
    primary_sku = record["skus"][0]["sku"] if record["skus"] else "unknown"
    ledger.record_order_fulfilled(order_id, primary_sku, revenue_cents, cost_cents, tracking_number)

    record["status"] = "shipped"
    record["tracking_number"] = tracking_number
    ledger.set_order_record(order_id, record)
    log.info("Order %s marked shipped on eBay (tracking %s)", order_id, tracking_number)


def run() -> None:
    config = load_config()
    ebay = EbayClient(config)
    printify = PrintifyClient(config)

    orders = ebay.get_orders()
    log.info("Fetched %d open eBay orders", len(orders))

    for order in orders:
        order_id = order["orderId"]
        try:
            record = ledger.get_order_record(order_id)
            if record is None:
                _submit_to_printify(config, printify, order)
            elif record["status"] == "submitted":
                _check_and_sync_shipment(config, ebay, printify, order_id, record)
            else:
                log.info("Order %s already %s; nothing to do.", order_id, record["status"])
        except Exception:
            log.exception("Error processing order %s; will retry next run.", order_id)


if __name__ == "__main__":
    run()
