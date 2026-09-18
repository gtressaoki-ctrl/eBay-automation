"""eBay OAuth token handling (authorization code / refresh-token flow).

All Sell APIs (Inventory, Fulfillment, Account) operate on a specific
seller's account, so every call in this project uses a **user access
token** obtained by refreshing the long-lived refresh token that is
generated once during the manual 3-legged OAuth consent flow described
in docs/SETUP.md. Access tokens are short-lived (~2h) and are refreshed
on demand; the refresh token itself lasts ~18 months and must be
re-generated manually when it expires.
"""
from __future__ import annotations

import base64
import time
from dataclasses import dataclass

import requests

from .config import Config

_PROD_TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"
_SANDBOX_TOKEN_URL = "https://api.sandbox.ebay.com/identity/v1/oauth2/token"

SCOPES = " ".join(
    [
        "https://api.ebay.com/oauth/api_scope/sell.inventory",
        "https://api.ebay.com/oauth/api_scope/sell.fulfillment",
        "https://api.ebay.com/oauth/api_scope/sell.account",
    ]
)


@dataclass
class _CachedToken:
    access_token: str
    expires_at: float


_cache: dict[str, _CachedToken] = {}


def token_url(config: Config) -> str:
    return _SANDBOX_TOKEN_URL if config.ebay_env.upper() == "SANDBOX" else _PROD_TOKEN_URL


def _basic_auth_header(config: Config) -> str:
    config.require("ebay_app_id", "ebay_cert_id")
    raw = f"{config.ebay_app_id}:{config.ebay_cert_id}".encode("utf-8")
    return base64.b64encode(raw).decode("ascii")


def get_user_access_token(config: Config, force_refresh: bool = False) -> str:
    """Return a valid user access token, refreshing it if needed."""
    cache_key = f"{config.ebay_env}:{config.ebay_refresh_token}"
    cached = _cache.get(cache_key)
    if cached and not force_refresh and cached.expires_at - 60 > time.time():
        return cached.access_token

    config.require("ebay_refresh_token")
    resp = requests.post(
        token_url(config),
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Basic {_basic_auth_header(config)}",
        },
        data={
            "grant_type": "refresh_token",
            "refresh_token": config.ebay_refresh_token,
            "scope": SCOPES,
        },
        timeout=30,
    )
    if not resp.ok:
        raise RuntimeError(f"eBay token refresh failed ({resp.status_code}): {resp.text}")
    payload = resp.json()
    token = payload["access_token"]
    expires_in = payload.get("expires_in", 7200)
    _cache[cache_key] = _CachedToken(access_token=token, expires_at=time.time() + expires_in)
    return token


def get_app_access_token(config: Config, force_refresh: bool = False) -> str:
    """Return an application (client-credentials) access token.

    Used only for the public, read-only Buy Browse API (market research).
    All Sell API calls must use get_user_access_token instead.
    """
    cache_key = f"app:{config.ebay_env}:{config.ebay_app_id}"
    cached = _cache.get(cache_key)
    if cached and not force_refresh and cached.expires_at - 60 > time.time():
        return cached.access_token

    resp = requests.post(
        token_url(config),
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Basic {_basic_auth_header(config)}",
        },
        data={
            "grant_type": "client_credentials",
            "scope": "https://api.ebay.com/oauth/api_scope",
        },
        timeout=30,
    )
    if not resp.ok:
        raise RuntimeError(f"eBay app token request failed ({resp.status_code}): {resp.text}")
    payload = resp.json()
    token = payload["access_token"]
    expires_in = payload.get("expires_in", 7200)
    _cache[cache_key] = _CachedToken(access_token=token, expires_at=time.time() + expires_in)
    return token
