import json

import pytest

from ebay_automation import idea_pin_gen as idea_pin_gen_module
from ebay_automation.config import Config
from ebay_automation.idea_pin_gen import (
    DESCRIPTION_MAX_CHARS,
    TITLE_MAX_CHARS,
    IdeaPinGenError,
    generate_idea_pin_content,
)


class FakeResponse:
    def __init__(self, status_code=200, json_data=None, text=""):
        self.status_code = status_code
        self.ok = 200 <= status_code < 300
        self._json = json_data or {}
        self.text = text or str(self._json)

    def json(self):
        return self._json


def _claude_reply(title: str, description: str) -> FakeResponse:
    body = json.dumps({"title": title, "description": description})
    return FakeResponse(200, {"content": [{"type": "text", "text": body}]})


@pytest.fixture
def config():
    return Config(anthropic_api_key="key", idea_pin_brand_name="EQUINOX", idea_pin_affiliate_url="https://example.com/shop")


@pytest.fixture
def photo(tmp_path):
    path = tmp_path / "mug.jpg"
    path.write_bytes(b"\xff\xd8\xff\xe0fakejpegdata")
    return path


def test_missing_api_key_raises(photo):
    with pytest.raises(RuntimeError, match="anthropic_api_key"):
        generate_idea_pin_content(photo, Config(anthropic_api_key=""))


def test_unsupported_image_type_raises(config, tmp_path):
    bad = tmp_path / "mug.txt"
    bad.write_text("not an image")
    with pytest.raises(IdeaPinGenError, match="Unsupported image type"):
        generate_idea_pin_content(bad, config)


def test_generate_returns_title_and_description(monkeypatch, config, photo):
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        return _claude_reply("Sarcastic Coffee Mug Gift", "Perfect for your morning ritual. Shop the link in our bio.")

    monkeypatch.setattr(idea_pin_gen_module.requests, "post", fake_post)

    content = generate_idea_pin_content(photo, config)

    assert content.title == "Sarcastic Coffee Mug Gift"
    assert "Shop the link in our bio." in content.description
    assert captured["url"] == "https://api.anthropic.com/v1/messages"
    assert captured["headers"]["x-api-key"] == "key"
    assert captured["json"]["model"] == config.anthropic_model
    image_block = captured["json"]["messages"][0]["content"][0]
    assert image_block["source"]["media_type"] == "image/jpeg"
    prompt_text = captured["json"]["messages"][0]["content"][1]["text"]
    assert "EQUINOX" in prompt_text
    assert "link in" in prompt_text


def test_generate_without_affiliate_url_uses_signoff_prompt(monkeypatch, photo):
    config = Config(anthropic_api_key="key", idea_pin_brand_name="EQUINOX", idea_pin_affiliate_url="")

    def fake_post(url, headers=None, json=None, timeout=None):
        return _claude_reply("A Title", "A description.")

    monkeypatch.setattr(idea_pin_gen_module.requests, "post", fake_post)

    content = generate_idea_pin_content(photo, config)

    assert content.title == "A Title"


def test_output_is_truncated_to_pinterest_limits(monkeypatch, config, photo):
    long_title = "T" * (TITLE_MAX_CHARS + 50)
    long_description = "D" * (DESCRIPTION_MAX_CHARS + 200)

    def fake_post(url, headers=None, json=None, timeout=None):
        return _claude_reply(long_title, long_description)

    monkeypatch.setattr(idea_pin_gen_module.requests, "post", fake_post)

    content = generate_idea_pin_content(photo, config)

    assert len(content.title) == TITLE_MAX_CHARS
    assert len(content.description) == DESCRIPTION_MAX_CHARS


def test_non_json_reply_raises(monkeypatch, config, photo):
    def fake_post(url, headers=None, json=None, timeout=None):
        return FakeResponse(200, {"content": [{"type": "text", "text": "not json at all"}]})

    monkeypatch.setattr(idea_pin_gen_module.requests, "post", fake_post)

    with pytest.raises(IdeaPinGenError, match="Could not parse"):
        generate_idea_pin_content(photo, config)


def test_api_error_response_raises(monkeypatch, config, photo):
    def fake_post(url, headers=None, json=None, timeout=None):
        return FakeResponse(401, {}, text="invalid x-api-key")

    monkeypatch.setattr(idea_pin_gen_module.requests, "post", fake_post)

    with pytest.raises(IdeaPinGenError, match="401"):
        generate_idea_pin_content(photo, config)
