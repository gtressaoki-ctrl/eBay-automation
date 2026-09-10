"""Thin wrapper around the Printify API (v1) — our print-on-demand
manufacturing/fulfillment partner.

Printify acts as the "wholesale supplier who ships directly to the buyer"
in eBay's dropshipping policy terms, which is why this model is compliant
(see docs/SETUP.md for the policy citation). We deliberately do NOT use
Printify's built-in eBay sales-channel connector (that requires the
$99.99/mo Empire plan) — instead we create a free "Manual order platform /
API" shop in the Printify dashboard and drive everything through this
client, paying Printify only the per-order production + shipping cost.

Reference: https://developers.printify.com/
Field names are current as of this project's creation; verify against the
live docs if Printify returns unexpected 4xx errors, since third-party
APIs evolve.
"""
from __future__ import annotations

from typing import Any

import requests

from .config import Config

_BASE_URL = "https://api.printify.com/v1"


class PrintifyApiError(RuntimeError):
    def __init__(self, method: str, url: str, status: int, body: str):
        super().__init__(f"{method} {url} -> {status}: {body}")
        self.status = status
        self.body = body


class PrintifyClient:
    def __init__(self, config: Config):
        self.config = config
        config.require("printify_api_key")

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.config.printify_api_key}",
            "Content-Type": "application/json",
            "User-Agent": "ebay-automation/1.0",
        }

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        url = f"{_BASE_URL}{path}"
        resp = requests.request(method, url, headers=self._headers(), timeout=60, **kwargs)
        if not resp.ok:
            raise PrintifyApiError(method, url, resp.status_code, resp.text)
        return resp

    # ---- Shop / catalog ----------------------------------------------------

    def list_shops(self) -> list[dict]:
        return self._request("GET", "/shops.json").json()

    def get_blueprint_variants(self, blueprint_id: int, print_provider_id: int) -> dict:
        return self._request(
            "GET", f"/catalog/blueprints/{blueprint_id}/print_providers/{print_provider_id}/variants.json"
        ).json()

    # ---- Images / products ----------------------------------------------------

    def upload_image_from_url(self, file_name: str, url: str) -> str:
        resp = self._request("POST", "/uploads/images.json", json={"file_name": file_name, "url": url})
        return resp.json()["id"]

    def upload_image_base64(self, file_name: str, contents_b64: str) -> str:
        resp = self._request(
            "POST", "/uploads/images.json", json={"file_name": file_name, "contents": contents_b64}
        )
        return resp.json()["id"]

    def create_product(
        self,
        title: str,
        description: str,
        blueprint_id: int,
        print_provider_id: int,
        variant_ids: list[int],
        image_id: str,
        base_price_cents: dict[int, int] | None = None,
    ) -> dict:
        shop_id = self.config.printify_shop_id
        self.config.require("printify_shop_id")
        variants = [
            {"id": vid, "price": (base_price_cents or {}).get(vid, 1999), "is_enabled": True}
            for vid in variant_ids
        ]
        payload = {
            "title": title,
            "description": description,
            "blueprint_id": blueprint_id,
            "print_provider_id": print_provider_id,
            "variants": variants,
            "print_areas": [
                {
                    "variant_ids": variant_ids,
                    "placeholders": [
                        {
                            "position": "front",
                            "images": [
                                {
                                    "id": image_id,
                                    "x": 0.5,
                                    "y": 0.5,
                                    "scale": 1,
                                    "angle": 0,
                                }
                            ],
                        }
                    ],
                }
            ],
        }
        resp = self._request("POST", f"/shops/{shop_id}/products.json", json=payload)
        return resp.json()

    def get_product(self, product_id: str) -> dict:
        shop_id = self.config.printify_shop_id
        return self._request("GET", f"/shops/{shop_id}/products/{product_id}.json").json()

    def delete_product(self, product_id: str) -> None:
        shop_id = self.config.printify_shop_id
        self._request("DELETE", f"/shops/{shop_id}/products/{product_id}.json")

    # ---- Orders (fulfillment) ----------------------------------------------------

    def submit_order(
        self,
        external_id: str,
        line_items: list[dict[str, Any]],
        shipping_address: dict[str, Any],
        shipping_method: int = 1,
    ) -> dict:
        shop_id = self.config.printify_shop_id
        self.config.require("printify_shop_id")
        payload = {
            "external_id": external_id,
            "line_items": line_items,
            "shipping_method": shipping_method,
            "send_shipping_notification": False,
            "address_to": shipping_address,
        }
        resp = self._request("POST", f"/shops/{shop_id}/orders.json", json=payload)
        return resp.json()

    def get_order(self, order_id: str) -> dict:
        shop_id = self.config.printify_shop_id
        return self._request("GET", f"/shops/{shop_id}/orders/{order_id}.json").json()
