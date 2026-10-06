"""Pinterest API v5: OAuth tokens, boards and Pins for our own account.

Reference: https://developers.pinterest.com/docs/api/v5/

Pinterest rotates the refresh token on every refresh — the one sent is
spent, and the response carries its replacement — so the token pair can't
live in a GitHub secret (Actions can't write secrets back). It is kept in
state/pinterest_token.enc instead, Fernet-encrypted with the
PINTEREST_TOKEN_KEY secret, and committed with the rest of the state. The
repository is public; without that key the file is opaque.
"""
from __future__ import annotations

import json
import time
import urllib.parse
from pathlib import Path
from typing import Any

import requests
from cryptography.fernet import Fernet

from .config import Config

TOKEN_PATH = Path(__file__).resolve().parent.parent.parent / "state" / "pinterest_token.enc"
SCOPES = ("boards:read", "boards:write", "pins:read", "pins:write", "user_accounts:read")
# Access tokens last 30 days. Refreshing only when this close to expiry
# keeps rotations — and the commits that persist them — to about one a month.
_REFRESH_MARGIN_SECONDS = 3 * 24 * 3600


class PinterestApiError(RuntimeError):
    def __init__(self, method: str, url: str, status: int, body: str):
        super().__init__(f"{method} {url} -> {status}: {body}")
        self.status = status
        self.body = body


def authorize_url(config: Config, state: str = "pin") -> str:
    """The consent page the account owner opens once to grant access."""
    query = urllib.parse.urlencode(
        {
            "client_id": config.pinterest_app_id,
            "redirect_uri": config.pinterest_redirect_uri,
            "response_type": "code",
            "scope": ",".join(SCOPES),
            "state": state,
        }
    )
    return f"https://www.pinterest.com/oauth/?{query}"


# ---- encrypted token store ------------------------------------------------


def load_tokens(config: Config, path: Path = TOKEN_PATH) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(Fernet(config.pinterest_token_key.encode()).decrypt(path.read_bytes()))


def save_tokens(config: Config, tokens: dict[str, Any], path: Path = TOKEN_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(Fernet(config.pinterest_token_key.encode()).encrypt(json.dumps(tokens).encode()))


def _tokens_from_response(body: dict[str, Any], now: float) -> dict[str, Any]:
    return {
        "access_token": body["access_token"],
        "access_expires_at": int(now + body.get("expires_in", 0)),
        "refresh_token": body["refresh_token"],
        "refresh_expires_at": int(now + body.get("refresh_token_expires_in", 0)),
    }


class PinterestClient:
    def __init__(self, config: Config, token_path: Path = TOKEN_PATH):
        self.config = config
        self.token_path = token_path
        self._tokens: dict[str, Any] | None = None

    @property
    def base_url(self) -> str:
        return self.config.pinterest_api_base.rstrip("/")

    # ---- OAuth -------------------------------------------------------------

    def _token_request(self, form: dict[str, str]) -> dict[str, Any]:
        url = f"{self.base_url}/v5/oauth/token"
        resp = requests.post(
            url,
            data=form,
            auth=(self.config.pinterest_app_id, self.config.pinterest_app_secret),
            timeout=30,
        )
        if not resp.ok:
            raise PinterestApiError("POST", url, resp.status_code, resp.text)
        return resp.json()

    def exchange_code(self, code: str) -> dict[str, Any]:
        """One-time: turn the consent page's code into a stored token pair."""
        body = self._token_request(
            {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self.config.pinterest_redirect_uri,
            }
        )
        self._tokens = _tokens_from_response(body, time.time())
        save_tokens(self.config, self._tokens, self.token_path)
        return self._tokens

    def access_token(self) -> str:
        if self._tokens is None:
            self._tokens = load_tokens(self.config, self.token_path)
        if self._tokens is None:
            raise RuntimeError(
                "No Pinterest token stored yet — run the 'Pinterest authorize' workflow first."
            )
        if self._tokens["access_expires_at"] - time.time() < _REFRESH_MARGIN_SECONDS:
            body = self._token_request(
                {"grant_type": "refresh_token", "refresh_token": self._tokens["refresh_token"]}
            )
            # The old refresh token is now spent: persist the new pair before
            # anything else can fail, or the next run is locked out.
            self._tokens = _tokens_from_response(body, time.time())
            save_tokens(self.config, self._tokens, self.token_path)
        return self._tokens["access_token"]

    # ---- API ---------------------------------------------------------------

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        url = f"{self.base_url}{path}"
        resp = requests.request(
            method,
            url,
            headers={"Authorization": f"Bearer {self.access_token()}"},
            timeout=30,
            **kwargs,
        )
        if not resp.ok:
            raise PinterestApiError(method, url, resp.status_code, resp.text)
        return resp

    def list_boards(self) -> list[dict[str, Any]]:
        boards: list[dict[str, Any]] = []
        bookmark = None
        while True:
            params = {"page_size": 100, **({"bookmark": bookmark} if bookmark else {})}
            body = self._request("GET", "/v5/boards", params=params).json()
            boards.extend(body.get("items", []))
            bookmark = body.get("bookmark")
            if not bookmark:
                return boards

    def get_or_create_board(self, name: str, description: str = "") -> str:
        for board in self.list_boards():
            if board.get("name", "").strip().lower() == name.strip().lower():
                return board["id"]
        body = self._request(
            "POST", "/v5/boards", json={"name": name, "description": description, "privacy": "PUBLIC"}
        ).json()
        return body["id"]

    def create_pin(
        self, board_id: str, title: str, description: str, link: str, image_url: str, alt_text: str = ""
    ) -> str:
        body = self._request(
            "POST",
            "/v5/pins",
            json={
                "board_id": board_id,
                "title": title[:100],
                "description": description[:800],
                "link": link,
                "alt_text": (alt_text or title)[:500],
                "media_source": {"source_type": "image_url", "url": image_url},
            },
        ).json()
        return body["id"]
