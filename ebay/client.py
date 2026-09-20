"""Thin wrapper around eBay's REST APIs (Sell Inventory/Account, Commerce
Taxonomy, Identity OAuth2). See https://developer.ebay.com/api-docs.

eBay has two separate OAuth grants in play here:

- Client Credentials grant (app token): no seller involved, used for public
  read-only data like the Taxonomy API's category suggestions.
- Authorization Code grant (user token): requires the seller to log into
  eBay in a browser once and approve access; yields a refresh_token (valid
  ~18 months) that this client uses to mint short-lived access tokens for
  the Sell APIs (Inventory, Account, Fulfillment). See oauth_consent.py and
  exchange_code.py for that one-time step.
"""
from __future__ import annotations

import base64
import time

import requests

PRODUCTION_API_BASE = "https://api.ebay.com"
SANDBOX_API_BASE = "https://api.sandbox.ebay.com"
PRODUCTION_AUTH_BASE = "https://auth.ebay.com"
SANDBOX_AUTH_BASE = "https://auth.sandbox.ebay.com"

APPLICATION_SCOPE = "https://api.ebay.com/oauth/api_scope"
SELL_SCOPES = " ".join(
    [
        "https://api.ebay.com/oauth/api_scope/sell.inventory",
        "https://api.ebay.com/oauth/api_scope/sell.account",
        "https://api.ebay.com/oauth/api_scope/sell.fulfillment",
    ]
)


class EbayClient:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        ru_name: str | None = None,
        refresh_token: str | None = None,
        sandbox: bool = False,
        content_language: str = "en-US",
    ):
        if not client_id or not client_secret:
            raise ValueError("eBay client id/secret are required (EBAY_CLIENT_ID / EBAY_CLIENT_SECRET).")
        self.client_id = client_id
        self.client_secret = client_secret
        self.ru_name = ru_name
        self.refresh_token = refresh_token
        self.sandbox = sandbox
        # Required by the Sell Inventory API on every write (item/group/offer);
        # the Account and Taxonomy APIs don't need it.
        self.content_language = content_language
        self.api_base = SANDBOX_API_BASE if sandbox else PRODUCTION_API_BASE
        self.auth_base = SANDBOX_AUTH_BASE if sandbox else PRODUCTION_AUTH_BASE
        self.token_url = f"{self.api_base}/identity/v1/oauth2/token"

        self._session = requests.Session()
        self._app_token: str | None = None
        self._app_token_expiry = 0.0
        self._user_token: str | None = None
        self._user_token_expiry = 0.0

    def _basic_auth_header(self) -> str:
        creds = f"{self.client_id}:{self.client_secret}".encode()
        return "Basic " + base64.b64encode(creds).decode()

    def _token_request(self, data: dict) -> dict:
        response = self._session.post(
            self.token_url,
            headers={
                "Authorization": self._basic_auth_header(),
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data=data,
        )
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            raise requests.HTTPError(f"{exc} -- {response.text}") from exc
        return response.json()

    # -- OAuth --------------------------------------------------------------
    def get_application_token(self) -> str:
        """Client Credentials grant - no seller consent needed."""
        if self._app_token and time.time() < self._app_token_expiry - 60:
            return self._app_token
        result = self._token_request({"grant_type": "client_credentials", "scope": APPLICATION_SCOPE})
        self._app_token = result["access_token"]
        self._app_token_expiry = time.time() + result["expires_in"]
        return self._app_token

    def get_user_token(self) -> str:
        """Refresh Token grant - requires a refresh_token from the one-time
        browser consent flow (see oauth_consent.py / exchange_code.py)."""
        if not self.refresh_token:
            raise ValueError(
                "No EBAY_REFRESH_TOKEN configured. Run oauth_consent.py to get a "
                "consent URL, approve it in a browser, then exchange_code.py to "
                "turn the resulting code into a refresh token."
            )
        if self._user_token and time.time() < self._user_token_expiry - 60:
            return self._user_token
        result = self._token_request(
            {"grant_type": "refresh_token", "refresh_token": self.refresh_token, "scope": SELL_SCOPES}
        )
        self._user_token = result["access_token"]
        self._user_token_expiry = time.time() + result["expires_in"]
        return self._user_token

    def exchange_authorization_code(self, code: str) -> dict:
        """One-time: turn a browser-consent authorization code into an
        access_token + refresh_token. Returns the raw token response so the
        caller can persist refresh_token."""
        if not self.ru_name:
            raise ValueError("EBAY_RU_NAME is required to exchange an authorization code.")
        return self._token_request(
            {"grant_type": "authorization_code", "code": code, "redirect_uri": self.ru_name}
        )

    def consent_url(self, scopes: str = SELL_SCOPES) -> str:
        if not self.ru_name:
            raise ValueError("EBAY_RU_NAME is required to build a consent URL.")
        from urllib.parse import quote

        return (
            f"{self.auth_base}/oauth2/authorize"
            f"?client_id={quote(self.client_id)}"
            f"&redirect_uri={quote(self.ru_name)}"
            f"&response_type=code"
            f"&scope={quote(scopes)}"
        )

    # -- generic request ------------------------------------------------
    def _request(self, method: str, path: str, *, token: str, **kwargs) -> dict | None:
        url = f"{self.api_base}{path}"
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {token}"
        headers.setdefault("Content-Type", "application/json")
        response = self._session.request(method, url, headers=headers, **kwargs)
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            try:
                detail = response.json()
            except ValueError:
                detail = response.text
            raise requests.HTTPError(f"{exc} -- {detail}") from exc
        if response.content:
            return response.json()
        return None

    def _app_request(self, method: str, path: str, **kwargs) -> dict | None:
        return self._request(method, path, token=self.get_application_token(), **kwargs)

    def _user_request(self, method: str, path: str, **kwargs) -> dict | None:
        return self._request(method, path, token=self.get_user_token(), **kwargs)

    # -- Commerce Taxonomy API (app token) -------------------------------
    def get_default_category_tree_id(self, marketplace_id: str = "EBAY_US") -> str:
        result = self._app_request(
            "GET", "/commerce/taxonomy/v1/get_default_category_tree_id", params={"marketplace_id": marketplace_id}
        )
        return result["categoryTreeId"]

    def get_category_suggestions(self, category_tree_id: str, query: str) -> list[dict]:
        result = self._app_request(
            "GET",
            f"/commerce/taxonomy/v1/category_tree/{category_tree_id}/get_category_suggestions",
            params={"q": query},
        )
        return result.get("categorySuggestions", [])

    def get_item_aspects_for_category(self, category_tree_id: str, category_id: str) -> dict:
        return self._app_request(
            "GET",
            f"/commerce/taxonomy/v1/category_tree/{category_tree_id}/get_item_aspects_for_category",
            params={"category_id": category_id},
        )

    # -- Sell Account API (user token) -----------------------------------
    def list_fulfillment_policies(self, marketplace_id: str = "EBAY_US") -> list[dict]:
        result = self._user_request(
            "GET", "/sell/account/v1/fulfillment_policy", params={"marketplace_id": marketplace_id}
        )
        return result.get("fulfillmentPolicies", [])

    def list_payment_policies(self, marketplace_id: str = "EBAY_US") -> list[dict]:
        result = self._user_request(
            "GET", "/sell/account/v1/payment_policy", params={"marketplace_id": marketplace_id}
        )
        return result.get("paymentPolicies", [])

    def list_return_policies(self, marketplace_id: str = "EBAY_US") -> list[dict]:
        result = self._user_request(
            "GET", "/sell/account/v1/return_policy", params={"marketplace_id": marketplace_id}
        )
        return result.get("returnPolicies", [])

    def list_inventory_locations(self) -> list[dict]:
        result = self._user_request("GET", "/sell/inventory/v1/location")
        return result.get("locations", []) if result else []

    def create_inventory_location(self, merchant_location_key: str, payload: dict) -> None:
        self._user_request("POST", f"/sell/inventory/v1/location/{merchant_location_key}", json=payload)

    def create_fulfillment_policy(self, payload: dict) -> dict:
        return self._user_request("POST", "/sell/account/v1/fulfillment_policy", json=payload)

    def create_payment_policy(self, payload: dict) -> dict:
        return self._user_request("POST", "/sell/account/v1/payment_policy", json=payload)

    def create_return_policy(self, payload: dict) -> dict:
        return self._user_request("POST", "/sell/account/v1/return_policy", json=payload)

    # -- Sell Inventory API (user token) ---------------------------------
    def _content_language_headers(self) -> dict:
        return {"Content-Language": self.content_language}

    def create_or_replace_inventory_item(self, sku: str, payload: dict) -> None:
        self._user_request(
            "PUT", f"/sell/inventory/v1/inventory_item/{sku}", json=payload, headers=self._content_language_headers()
        )

    def get_inventory_item(self, sku: str) -> dict:
        return self._user_request("GET", f"/sell/inventory/v1/inventory_item/{sku}")

    def create_or_replace_inventory_item_group(self, group_key: str, payload: dict) -> None:
        self._user_request(
            "PUT",
            f"/sell/inventory/v1/inventory_item_group/{group_key}",
            json=payload,
            headers=self._content_language_headers(),
        )

    def get_inventory_item_group(self, group_key: str) -> dict:
        return self._user_request("GET", f"/sell/inventory/v1/inventory_item_group/{group_key}")

    def publish_offer_by_inventory_item_group(self, group_key: str, marketplace_id: str) -> dict:
        return self._user_request(
            "POST",
            "/sell/inventory/v1/offer/publish_by_inventory_item_group",
            json={"inventoryItemGroupKey": group_key, "marketplaceId": marketplace_id},
            headers=self._content_language_headers(),
        )

    def create_offer(self, payload: dict) -> dict:
        return self._user_request(
            "POST", "/sell/inventory/v1/offer", json=payload, headers=self._content_language_headers()
        )

    def update_offer(self, offer_id: str, payload: dict) -> None:
        self._user_request(
            "PUT", f"/sell/inventory/v1/offer/{offer_id}", json=payload, headers=self._content_language_headers()
        )

    def get_offers_for_sku(self, sku: str) -> list[dict]:
        # eBay 404s (errorId 25713, "This Offer is not available") instead
        # of returning an empty list when a SKU has no offers yet.
        try:
            result = self._user_request("GET", "/sell/inventory/v1/offer", params={"sku": sku})
        except requests.HTTPError as exc:
            if "25713" in str(exc):
                return []
            raise
        return result.get("offers", []) if result else []

    def publish_offer(self, offer_id: str) -> dict:
        return self._user_request("POST", f"/sell/inventory/v1/offer/{offer_id}/publish")

    def withdraw_offer(self, offer_id: str) -> dict:
        return self._user_request("POST", f"/sell/inventory/v1/offer/{offer_id}/withdraw")
