import json
import time
from unittest.mock import MagicMock

import pytest
from cryptography.fernet import Fernet

from ebay_automation import ledger, pinterest_client, pipeline_pinterest
from ebay_automation.config import Config
from ebay_automation.pinterest_client import PinterestApiError, PinterestClient, load_tokens, save_tokens

KEY = Fernet.generate_key().decode()
BASE = "https://api.pinterest.com"


def _config(**overrides) -> Config:
    values = dict(
        pinterest_app_id="app",
        pinterest_app_secret="secret",
        pinterest_token_key=KEY,
        pinterest_api_base=BASE,
        pinterest_pins_per_run=2,
    )
    values.update(overrides)
    return Config(**values)


def _entry(n: int, **overrides) -> dict:
    entry = {
        "status": "published",
        "headline": "TECHNICALLY I'M AWAKE",
        "listing_url": f"https://www.ebay.com/itm/{n}",
        "image_url": f"https://images-api.printify.com/mockup/{n}.jpg?camera_label=front",
    }
    entry.update(overrides)
    return entry


@pytest.fixture
def pending(tmp_path, monkeypatch):
    monkeypatch.setattr(ledger, "_STATE_DIR", tmp_path)
    monkeypatch.setattr(ledger, "_PENDING_PATH", tmp_path / "pending_listings.json")
    data = {
        "a": _entry(1),
        "b": _entry(2),
        "c": _entry(3),
        "retired": _entry(4, status="retired"),
        "done": _entry(5, pinterest_pin_id="p-5"),
    }
    ledger.save_pending_listings(data)
    return data


def test_pins_only_live_unpinned_listings_up_to_the_per_run_cap(pending):
    client = MagicMock()
    client.get_or_create_board.return_value = "board-1"
    client.create_pin.side_effect = ["p-1", "p-2"]

    pinned = pipeline_pinterest.pin_new_listings(_config(), client)

    assert pinned == ["a", "b"]
    saved = ledger.load_pending_listings()
    assert saved["a"]["pinterest_pin_id"] == "p-1"
    assert saved["b"]["pinterest_pin_id"] == "p-2"
    assert "pinterest_pin_id" not in saved["c"]
    kwargs = client.create_pin.call_args_list[0].kwargs
    assert kwargs["link"] == "https://www.ebay.com/itm/1"
    assert kwargs["image_url"] == "https://images-api.printify.com/mockup/1.jpg"
    assert kwargs["title"].startswith("Technically I'm Awake")


def test_one_failed_pin_does_not_stop_the_rest(pending):
    client = MagicMock()
    client.get_or_create_board.return_value = "board-1"
    client.create_pin.side_effect = [PinterestApiError("POST", "u", 400, "bad image"), "p-2"]

    assert pipeline_pinterest.pin_new_listings(_config(), client) == ["b"]
    assert "pinterest_pin_id" not in ledger.load_pending_listings()["a"]


def test_nothing_to_pin_makes_no_api_calls(pending):
    for entry in pending.values():
        entry["pinterest_pin_id"] = "x"
    ledger.save_pending_listings(pending)
    client = MagicMock()

    assert pipeline_pinterest.pin_new_listings(_config(), client) == []
    client.get_or_create_board.assert_not_called()


def test_listings_pinned_by_the_csv_are_not_pinned_again(pending):
    assert pipeline_pinterest.mark_existing_as_pinned() == 3
    assert pipeline_pinterest.pin_new_listings(_config(), MagicMock()) == []


def test_skips_quietly_until_pinterest_is_configured():
    assert not pipeline_pinterest.configured(Config(pinterest_app_id="", pinterest_token_key=""))


def test_token_store_is_encrypted_at_rest(tmp_path):
    path = tmp_path / "t.enc"
    save_tokens(_config(), {"access_token": "AT-secret", "refresh_token": "RT"}, path)
    assert b"AT-secret" not in path.read_bytes()
    assert load_tokens(_config(), path)["access_token"] == "AT-secret"


class _Resp:
    def __init__(self, body):
        self.ok, self.status_code, self._body, self.text = True, 200, body, json.dumps(body)

    def json(self):
        return self._body


@pytest.fixture
def http(monkeypatch):
    calls = []
    replies = {}

    def post(url, data=None, auth=None, timeout=None):
        calls.append(("POST", url, data, None, None))
        return _Resp(replies[url])

    def request(method, url, headers=None, timeout=None, json=None, params=None):
        calls.append((method, url, json, headers, params))
        return _Resp(replies[url])

    monkeypatch.setattr(pinterest_client.requests, "post", post)
    monkeypatch.setattr(pinterest_client.requests, "request", request)
    return calls, replies


def _store(path, **tokens):
    values = {"access_token": "AT", "access_expires_at": int(time.time()) + 20 * 86400, "refresh_token": "RT", "refresh_expires_at": 0}
    values.update(tokens)
    save_tokens(_config(), values, path)


def test_expiring_access_token_is_refreshed_and_the_rotated_refresh_token_persisted(tmp_path, http):
    calls, replies = http
    path = tmp_path / "t.enc"
    _store(path, access_token="old", access_expires_at=int(time.time()) + 60, refresh_token="RT-1")
    replies[f"{BASE}/v5/oauth/token"] = {
        "access_token": "new", "expires_in": 2592000, "refresh_token": "RT-2", "refresh_token_expires_in": 5184000,
    }

    assert PinterestClient(_config(), path).access_token() == "new"
    assert calls[0][2] == {"grant_type": "refresh_token", "refresh_token": "RT-1"}
    # Pinterest has already spent RT-1; only RT-2 works from now on.
    assert load_tokens(_config(), path)["refresh_token"] == "RT-2"


def test_fresh_access_token_is_used_without_refreshing(tmp_path, http):
    calls, _ = http
    path = tmp_path / "t.enc"
    _store(path)
    assert PinterestClient(_config(), path).access_token() == "AT"
    assert calls == []


def test_create_pin_sends_the_listing_link_and_image(tmp_path, http):
    calls, replies = http
    path = tmp_path / "t.enc"
    _store(path)
    replies[f"{BASE}/v5/pins"] = {"id": "pin-9"}

    assert PinterestClient(_config(), path).create_pin("b-1", "T", "D", "https://l", "https://i.jpg") == "pin-9"
    method, url, sent, headers, _ = calls[0]
    assert sent["board_id"] == "b-1"
    assert sent["link"] == "https://l"
    assert sent["media_source"] == {"source_type": "image_url", "url": "https://i.jpg"}
    assert headers["Authorization"] == "Bearer AT"


def test_existing_board_is_reused_by_name(tmp_path, http):
    calls, replies = http
    path = tmp_path / "t.enc"
    _store(path)
    replies[f"{BASE}/v5/boards"] = {"items": [{"id": "b-7", "name": "funny coffee mugs"}], "bookmark": None}

    assert PinterestClient(_config(), path).get_or_create_board("Funny Coffee Mugs") == "b-7"
    assert [c[0] for c in calls] == ["GET"]
