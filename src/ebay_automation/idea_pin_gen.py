"""Pinterest Idea Pin title/description generation from a product photo.

Pinterest has no public API for creating Idea Pins under third-party
automation (it needs Pinterest Business approval scoped per-account), so
this stays a human-in-the-loop tool: it turns a photo into ready-to-paste
copy for the Idea Pin composer, the same way scripts/list_printify_catalog.py
surfaces IDs for a step this pipeline can't complete on its own. What it
does automate is the part that doesn't need Pinterest's approval — looking
at the photo and writing on-brand, SEO-aware copy that always nudges the
reader toward the affiliate link, so voice stays consistent pin over pin
instead of depending on whoever is pasting that day.

Uses Claude's vision input directly over the Messages API (see
https://docs.anthropic.com/en/api/messages) rather than pulling in the
`anthropic` SDK, since a single POST is all this needs and every other
client in this package (ebay_client, printify_client) is a thin `requests`
wrapper for the same reason.
"""
from __future__ import annotations

import base64
import json
import mimetypes
from dataclasses import dataclass
from pathlib import Path

import requests

from .config import Config

_API_URL = "https://api.anthropic.com/v1/messages"
_API_VERSION = "2023-06-01"

# Pinterest truncates past these lengths in the Idea Pin composer.
TITLE_MAX_CHARS = 100
DESCRIPTION_MAX_CHARS = 500

_SUPPORTED_MEDIA_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}


class IdeaPinGenError(RuntimeError):
    """Raised when the API call fails or returns something unusable.

    This tool is read by a human before anything gets pasted into
    Pinterest, so a raised error with the model's raw text is more useful
    here than a silent fallback title/description would be.
    """


@dataclass(frozen=True)
class IdeaPinContent:
    title: str
    description: str


def _encode_image(image_path: Path) -> tuple[str, str]:
    media_type, _ = mimetypes.guess_type(image_path.name)
    if media_type not in _SUPPORTED_MEDIA_TYPES:
        raise IdeaPinGenError(
            f"Unsupported image type for {image_path.name} ({media_type}); "
            f"use one of {sorted(_SUPPORTED_MEDIA_TYPES)}"
        )
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return media_type, encoded


def _build_prompt(config: Config, extra_context: str) -> str:
    brand = config.idea_pin_brand_name
    if config.idea_pin_affiliate_url:
        cta = (
            "Close with one natural sentence pointing the reader to the link in "
            f"{brand}'s Pinterest profile to shop this. Do not print a URL — Idea "
            "Pin descriptions don't render links as clickable, so a raw link just "
            "reads as clutter."
        )
    else:
        cta = "End with a warm sign-off; no shop link is configured yet."

    context_line = f"\nExtra context about this photo: {extra_context}" if extra_context else ""

    return (
        f'You are writing a Pinterest Idea Pin for the brand "{brand}". Look at '
        "the attached photo and write:\n"
        f"1. A title, {TITLE_MAX_CHARS} characters or fewer, that a Pinterest user "
        "would actually search for — concrete and keyword-first, not clickbait.\n"
        f"2. A description, {DESCRIPTION_MAX_CHARS} characters or fewer, in a warm, "
        f'confident voice consistent with a brand called "{brand}", using 3-5 '
        "relevant Pinterest SEO keywords naturally in the text."
        f"{context_line}\n"
        f"{cta}\n\n"
        'Respond with ONLY a JSON object shaped {"title": "...", "description": '
        '"..."}. No markdown code fences, no other text before or after it.'
    )


def generate_idea_pin_content(
    image_path: Path,
    config: Config,
    extra_context: str = "",
    session: requests.Session | None = None,
) -> IdeaPinContent:
    """Ask Claude to look at `image_path` and draft an Idea Pin title/description."""
    config.require("anthropic_api_key")
    media_type, encoded = _encode_image(image_path)
    session = session or requests

    response = session.post(
        _API_URL,
        headers={
            "x-api-key": config.anthropic_api_key,
            "anthropic-version": _API_VERSION,
            "content-type": "application/json",
        },
        json={
            "model": config.anthropic_model,
            "max_tokens": 1024,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {"type": "base64", "media_type": media_type, "data": encoded},
                        },
                        {"type": "text", "text": _build_prompt(config, extra_context)},
                    ],
                }
            ],
        },
        timeout=60,
    )
    if not response.ok:
        raise IdeaPinGenError(f"Claude API returned {response.status_code}: {response.text}")

    payload = response.json()
    text = "".join(
        block.get("text", "") for block in payload.get("content", []) if block.get("type") == "text"
    ).strip()

    try:
        parsed = json.loads(text)
        title = str(parsed["title"]).strip()
        description = str(parsed["description"]).strip()
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise IdeaPinGenError(f"Could not parse title/description out of Claude's reply: {text!r}") from exc

    if not title or not description:
        raise IdeaPinGenError(f"Claude returned an empty title or description: {text!r}")

    return IdeaPinContent(title=title[:TITLE_MAX_CHARS], description=description[:DESCRIPTION_MAX_CHARS])
