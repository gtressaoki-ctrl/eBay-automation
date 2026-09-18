"""Thin wrapper around the Printify REST API (https://developers.printify.com).

Only the endpoints needed to upload artwork and create/publish products are
implemented. Every method raises ``requests.HTTPError`` on a non-2xx
response so callers get the real Printify error message instead of a silent
failure.
"""
from __future__ import annotations

import base64
import time
from pathlib import Path
from typing import Any

import requests

API_BASE = "https://api.printify.com/v1"


class PrintifyClient:
    def __init__(self, api_token: str, user_agent: str = "eBay-automation/printify-brand-setup"):
        if not api_token:
            raise ValueError("Printify API token is required (set PRINTIFY_API_TOKEN).")
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {api_token}",
                "User-Agent": user_agent,
                "Content-Type": "application/json",
            }
        )

    def _request(self, method: str, path: str, retries: int = 3, **kwargs) -> Any:
        url = f"{API_BASE}{path}"
        last_exc: Exception | None = None
        for attempt in range(1, retries + 1):
            response = self._session.request(method, url, **kwargs)
            if response.status_code == 429 and attempt < retries:
                time.sleep(2 * attempt)
                continue
            try:
                response.raise_for_status()
            except requests.HTTPError as exc:
                last_exc = exc
                if response.status_code >= 500 and attempt < retries:
                    time.sleep(2 * attempt)
                    continue
                try:
                    detail = response.json()
                except ValueError:
                    detail = response.text
                raise requests.HTTPError(f"{exc} -- {detail}") from exc
            if response.content:
                return response.json()
            return None
        raise last_exc  # pragma: no cover - only reached if retries exhausted on 429

    # -- shops -----------------------------------------------------------
    def list_shops(self) -> list[dict]:
        return self._request("GET", "/shops.json")

    # -- catalog -----------------------------------------------------------
    def list_blueprints(self) -> list[dict]:
        return self._request("GET", "/catalog/blueprints.json")

    def find_blueprints(self, keyword: str) -> list[dict]:
        keyword = keyword.lower()
        return [b for b in self.list_blueprints() if keyword in b["title"].lower()]

    def list_print_providers(self, blueprint_id: int) -> list[dict]:
        return self._request("GET", f"/catalog/blueprints/{blueprint_id}/print_providers.json")

    def list_variants(self, blueprint_id: int, print_provider_id: int) -> dict:
        return self._request(
            "GET",
            f"/catalog/blueprints/{blueprint_id}/print_providers/{print_provider_id}/variants.json",
        )

    # -- images -----------------------------------------------------------
    def upload_image(self, file_path: str | Path, file_name: str | None = None) -> dict:
        path = Path(file_path)
        file_name = file_name or path.name
        contents = base64.b64encode(path.read_bytes()).decode("ascii")
        return self._request(
            "POST",
            "/uploads/images.json",
            json={"file_name": file_name, "contents": contents},
        )

    # -- products -----------------------------------------------------------
    def create_product(self, shop_id: str, payload: dict) -> dict:
        return self._request("POST", f"/shops/{shop_id}/products.json", json=payload)

    def get_product(self, shop_id: str, product_id: str) -> dict:
        return self._request("GET", f"/shops/{shop_id}/products/{product_id}.json")

    def publish_product(self, shop_id: str, product_id: str, publish_payload: dict | None = None) -> None:
        payload = publish_payload or {
            "title": True,
            "description": True,
            "images": True,
            "variants": True,
            "tags": True,
            "keyFeatures": True,
            "shipping_template": True,
        }
        self._request("POST", f"/shops/{shop_id}/products/{product_id}/publish.json", json=payload)

    def mark_publish_succeeded(self, shop_id: str, product_id: str, external_id: str, handle: str) -> None:
        """Required for manual/API-only shops: tells Printify the publish step
        finished so the product leaves the "publishing" state."""
        self._request(
            "POST",
            f"/shops/{shop_id}/products/{product_id}/publishing_succeeded.json",
            json={"external": {"id": external_id, "handle": handle}},
        )
