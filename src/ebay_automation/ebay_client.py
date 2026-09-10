"""Thin wrapper around eBay's Sell Inventory API and Sell Fulfillment API.

Reference:
- Inventory API: https://developer.ebay.com/api-docs/sell/inventory/resources/methods
- Fulfillment API: https://developer.ebay.com/api-docs/sell/fulfillment/resources/methods

Only the subset of calls this pipeline needs is implemented. Every call
uses a fresh user access token (see ebay_auth.py) — eBay access tokens
expire in ~2h so we do not cache HTTP sessions across long-running jobs.
"""
from __future__ import annotations

from typing import Any

import requests

from .config import Config
from .ebay_auth import get_user_access_token

_PROD_BASE = "https://api.ebay.com"
_SANDBOX_BASE = "https://api.sandbox.ebay.com"


class EbayApiError(RuntimeError):
    def __init__(self, method: str, url: str, status: int, body: str):
        super().__init__(f"{method} {url} -> {status}: {body}")
        self.status = status
        self.body = body


class EbayClient:
    def __init__(self, config: Config):
        self.config = config

    @property
    def base_url(self) -> str:
        return _SANDBOX_BASE if self.config.ebay_env.upper() == "SANDBOX" else _PROD_BASE

    def _headers(self, extra: dict | None = None) -> dict:
        headers = {
            "Authorization": f"Bearer {get_user_access_token(self.config)}",
            "Content-Type": "application/json",
            "Content-Language": "en-US",
            "Accept-Language": "en-US",
        }
        if extra:
            headers.update(extra)
        return headers

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        url = f"{self.base_url}{path}"
        resp = requests.request(method, url, headers=self._headers(kwargs.pop("extra_headers", None)), timeout=30, **kwargs)
        if not resp.ok:
            raise EbayApiError(method, url, resp.status_code, resp.text)
        return resp

    # ---- Inventory API ----------------------------------------------------

    def create_or_replace_inventory_item(self, sku: str, item: dict[str, Any]) -> None:
        self._request("PUT", f"/sell/inventory/v1/inventory_item/{sku}", json=item)

    def create_offer(self, offer: dict[str, Any]) -> str:
        resp = self._request("POST", "/sell/inventory/v1/offer", json=offer)
        return resp.json()["offerId"]

    def update_offer(self, offer_id: str, offer: dict[str, Any]) -> None:
        self._request("PUT", f"/sell/inventory/v1/offer/{offer_id}", json=offer)

    def publish_offer(self, offer_id: str) -> str:
        resp = self._request("POST", f"/sell/inventory/v1/offer/{offer_id}/publish")
        return resp.json()["listingId"]

    def withdraw_offer(self, offer_id: str) -> None:
        self._request("POST", f"/sell/inventory/v1/offer/{offer_id}/withdraw")

    def delete_inventory_item(self, sku: str) -> None:
        self._request("DELETE", f"/sell/inventory/v1/inventory_item/{sku}")

    # ---- Fulfillment API ----------------------------------------------------

    def get_orders(self, filter_str: str = "orderfulfillmentstatus:{NOT_STARTED|IN_PROGRESS}", limit: int = 50) -> list[dict]:
        resp = self._request(
            "GET",
            "/sell/fulfillment/v1/order",
            params={"filter": filter_str, "limit": limit},
        )
        return resp.json().get("orders", [])

    def create_shipping_fulfillment(
        self,
        order_id: str,
        line_items: list[dict[str, Any]],
        tracking_number: str,
        shipping_carrier_code: str,
    ) -> str:
        payload = {
            "lineItems": line_items,
            "shippedDate": None,
            "shippingCarrierCode": shipping_carrier_code,
            "trackingNumber": tracking_number,
        }
        payload = {k: v for k, v in payload.items() if v is not None}
        resp = self._request(
            "POST",
            f"/sell/fulfillment/v1/order/{order_id}/shipping_fulfillment",
            json=payload,
        )
        location = resp.headers.get("Location", "")
        return location.rstrip("/").rsplit("/", 1)[-1] if location else ""
