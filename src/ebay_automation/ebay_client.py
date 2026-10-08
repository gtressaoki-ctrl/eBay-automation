"""Thin wrapper around eBay's Sell Inventory, Fulfillment and Marketing APIs.

Reference:
- Inventory API: https://developer.ebay.com/api-docs/sell/inventory/resources/methods
- Fulfillment API: https://developer.ebay.com/api-docs/sell/fulfillment/resources/methods
- Marketing API (Promoted Listings): https://developer.ebay.com/api-docs/sell/marketing/resources/methods

Only the subset of calls this pipeline needs is implemented. Every call
uses a fresh user access token (see ebay_auth.py) — eBay access tokens
expire in ~2h so we do not cache HTTP sessions across long-running jobs.
"""
from __future__ import annotations

import datetime
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

    @property
    def is_selling_limit(self) -> bool:
        # eBay reports the account-wide monthly selling limit under the
        # generic errorId 25002, so the message is the only distinguishing
        # signal. Once hit, every further publish this month fails the same
        # way — callers use this to stop instead of burning more products.
        # eBay words it differently depending on whether this listing would
        # cross the limit ("would cause you to exceed the number of items")
        # or it is already reached ("you've reached the number of items").
        return "number of items" in (self.body or "")


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

    def get_inventory_item(self, sku: str) -> dict[str, Any]:
        return self._request("GET", f"/sell/inventory/v1/inventory_item/{sku}").json()

    def create_or_replace_inventory_item(self, sku: str, item: dict[str, Any]) -> None:
        self._request("PUT", f"/sell/inventory/v1/inventory_item/{sku}", json=item)

    def create_offer(self, offer: dict[str, Any]) -> str:
        resp = self._request("POST", "/sell/inventory/v1/offer", json=offer)
        return resp.json()["offerId"]

    def get_offer(self, offer_id: str) -> dict[str, Any]:
        return self._request("GET", f"/sell/inventory/v1/offer/{offer_id}").json()

    def update_offer(self, offer_id: str, offer: dict[str, Any]) -> None:
        self._request("PUT", f"/sell/inventory/v1/offer/{offer_id}", json=offer)

    def set_available_quantity(self, sku: str, offer_id: str, quantity: int) -> None:
        self._request(
            "POST",
            "/sell/inventory/v1/bulk_update_price_quantity",
            json={
                "requests": [
                    {
                        "sku": sku,
                        "shipToLocationAvailability": {"quantity": quantity},
                        "offers": [{"offerId": offer_id, "availableQuantity": quantity}],
                    }
                ]
            },
        )

    def publish_offer(self, offer_id: str) -> str:
        resp = self._request("POST", f"/sell/inventory/v1/offer/{offer_id}/publish")
        return resp.json()["listingId"]

    def withdraw_offer(self, offer_id: str) -> None:
        self._request("POST", f"/sell/inventory/v1/offer/{offer_id}/withdraw")

    def delete_inventory_item(self, sku: str) -> None:
        self._request("DELETE", f"/sell/inventory/v1/inventory_item/{sku}")

    # ---- Catalog API -------------------------------------------------------

    def find_catalog_product(self, gtin: str) -> dict[str, Any] | None:
        """The single eBay catalog product for this GTIN, or None.

        Catalog products carry eBay's own stock photos and item specifics,
        which is what export listings use instead of copying another
        seller's photos. Ambiguous GTINs (several products) return None:
        the Inventory API would not pick up product details for them either.
        """
        resp = self._request(
            "GET",
            "/commerce/catalog/v1_beta/product_summary/search",
            params={"gtin": gtin, "limit": 2},
            extra_headers={"X-EBAY-C-MARKETPLACE-ID": self.config.ebay_marketplace_id},
        )
        if resp.status_code == 204:
            return None
        products = resp.json().get("productSummaries") or []
        return products[0] if len(products) == 1 else None

    # ---- Media API ---------------------------------------------------------

    def upload_image(self, data: bytes, filename: str) -> str:
        """Upload a photo to eBay Picture Services and return its EPS URL.

        EPS URLs are what listings should point at: eBay serves them itself,
        so nothing outside eBay has to stay online for the listing to work.
        """
        url = f"{self.base_url}/commerce/media/v1_beta/image/create_image_from_file"
        headers = {"Authorization": f"Bearer {get_user_access_token(self.config)}"}
        resp = requests.post(url, headers=headers, files={"image": (filename, data)}, timeout=60)
        if not resp.ok:
            raise EbayApiError("POST", url, resp.status_code, resp.text)
        image_id = resp.headers.get("Location", "").rstrip("/").rsplit("/", 1)[-1]
        return self._request("GET", f"/commerce/media/v1_beta/image/{image_id}").json()["imageUrl"]

    # ---- Account API (business policies) --------------------------------------

    def get_fulfillment_policy(self, policy_id: str) -> dict[str, Any]:
        return self._request("GET", f"/sell/account/v1/fulfillment_policy/{policy_id}").json()

    def update_fulfillment_policy(self, policy_id: str, policy: dict[str, Any]) -> dict[str, Any]:
        return self._request("PUT", f"/sell/account/v1/fulfillment_policy/{policy_id}", json=policy).json()

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

    # ---- Analytics API ----------------------------------------------------

    TRAFFIC_METRICS = ("LISTING_IMPRESSION_TOTAL", "LISTING_VIEWS_TOTAL", "TRANSACTION")

    def get_traffic_report(self, listing_ids: list[str], days: int = 30) -> dict[str, dict[str, int]]:
        """Impressions / page views / sales per listing over the last `days`.

        Tells *why* a listing isn't selling: never shown in search, shown
        but not clicked, or clicked but not bought each call for a
        different fix."""
        # eBay evaluates dates in US Pacific time, so "today" in UTC is often
        # still tomorrow there and gets rejected as a future date (50018).
        today = datetime.date.today() - datetime.timedelta(days=1)
        start = today - datetime.timedelta(days=days)
        report: dict[str, dict[str, int]] = {}
        for i in range(0, len(listing_ids), 200):
            chunk = listing_ids[i : i + 200]
            resp = self._request(
                "GET",
                "/sell/analytics/v1/traffic_report",
                params={
                    "dimension": "LISTING",
                    "metric": ",".join(self.TRAFFIC_METRICS),
                    "filter": (
                        f"marketplace_ids:{{{self.config.ebay_marketplace_id}}},"
                        f"date_range:[{start:%Y%m%d}..{today:%Y%m%d}],"
                        f"listing_ids:{{{'|'.join(chunk)}}}"
                    ),
                },
            )
            body = resp.json()
            keys = [m["key"] for m in body.get("header", {}).get("metrics", [])]
            for record in body.get("records", []):
                listing_id = record["dimensionValues"][0]["value"]
                values = [mv.get("value") or 0 for mv in record.get("metricValues", [])]
                report[listing_id] = {k: int(v) for k, v in zip(keys, values)}
        return report

    # ---- Marketing API (Promoted Listings, cost-per-sale) --------------------
    #
    # A brand-new seller with no feedback is ranked far down eBay's own search
    # (Cassini) regardless of how good the listing is — that's the actual
    # bottleneck, not the automation. Cost-per-sale Promoted Listings is the
    # one lever that fits a near-zero-effort, near-zero-idle-cost pipeline:
    # eBay only takes its cut of the sale price when an ad click leads to an
    # actual sale, nothing if it doesn't sell, so turning it on never spends
    # money the pipeline hasn't already earned.

    def find_campaign(self, campaign_name: str) -> str | None:
        """An existing, still-active campaign with this name, if any."""
        resp = self._request(
            "GET", "/sell/marketing/v1/ad_campaign", params={"campaign_name": campaign_name, "limit": 10}
        )
        for campaign in resp.json().get("campaigns", []):
            if campaign.get("campaignStatus") in ("RUNNING", "SCHEDULED", "PAUSED"):
                return campaign["campaignId"]
        return None

    def create_cost_per_sale_campaign(self, campaign_name: str, bid_percentage: float) -> str:
        resp = self._request(
            "POST",
            "/sell/marketing/v1/ad_campaign",
            json={
                "marketplaceId": self.config.ebay_marketplace_id,
                "campaignName": campaign_name,
                "fundingStrategy": {
                    "fundingModel": "COST_PER_SALE",
                    "bidPercentage": f"{bid_percentage:.1f}",
                },
                "startDate": datetime.datetime.now(datetime.timezone.utc)
                .isoformat(timespec="seconds")
                .replace("+00:00", "Z"),
            },
        )
        location = resp.headers.get("Location", "")
        return location.rstrip("/").rsplit("/", 1)[-1]

    def get_or_create_cost_per_sale_campaign(self, campaign_name: str, bid_percentage: float) -> str:
        """One long-running campaign is reused across runs rather than
        creating a fresh one every day."""
        return self.find_campaign(campaign_name) or self.create_cost_per_sale_campaign(
            campaign_name, bid_percentage
        )

    def promote_listing(self, campaign_id: str, sku: str, bid_percentage: float) -> None:
        """Add one SKU to a cost-per-sale campaign. bidPercentage must be 2.0-100.0."""
        self._request(
            "POST",
            f"/sell/marketing/v1/ad_campaign/{campaign_id}/create_ads_by_inventory_reference",
            json={
                "bidPercentage": f"{bid_percentage:.1f}",
                "inventoryReferenceId": sku,
                "inventoryReferenceType": "INVENTORY_ITEM",
            },
        )
