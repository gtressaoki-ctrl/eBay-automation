"""Pin the Slow Japan Trails travel guides to our own Pinterest board.

Pinterest is a trip-planning search engine as much as a gift-ideas feed,
and every guide already carries tall photos with good alt text — exactly
what a Pin needs. Each photo becomes its own Pin linking back to its
guide, so one guide keeps feeding fresh Pins for days.

Guides are discovered from the site itself (homepage links plus the
sitemap), so a newly published guide gets pinned without any change here.
Pins are spread round-robin: the guide with the fewest Pins goes next.
"""
from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Callable
from urllib.parse import urljoin, urlsplit

import requests

from . import ledger
from .config import Config
from .pinterest_client import PinterestApiError

_STATE_NAME = "pinterest_guides.json"
_SITE_SUFFIX = re.compile(r"\s*[|\-–—]\s*Slow Japan Trails\s*$")
_BOARD_DESCRIPTION = "Slow, practical travel guides to rural Japan — Shikoku hikes, gardens, shrines and itineraries."
_HASHTAGS = "#japantravel #shikoku #slowtravel"

Fetch = Callable[[str], str]


def _fetch(url: str) -> str:
    resp = requests.get(url, timeout=30, headers={"User-Agent": "SlowJapanTrailsPublisher/1.0"})
    resp.raise_for_status()
    return resp.text


class _PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self.description = ""
        self.links: list[str] = []
        self.images: list[tuple[str, str]] = []
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "title":
            self._in_title = True
        elif tag == "meta" and a.get("name") == "description":
            self.description = a.get("content") or ""
        elif tag == "a" and a.get("href"):
            self.links.append(a["href"])
        elif tag == "img" and a.get("src"):
            self.images.append((a["src"], a.get("alt") or ""))

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data


def _parse(html: str) -> _PageParser:
    parser = _PageParser()
    parser.feed(html)
    return parser


def _is_guide(site: str, url: str) -> bool:
    parts = urlsplit(url)
    return parts.netloc == urlsplit(site).netloc and re.fullmatch(r"/guides/[\w-]+/?", parts.path) is not None


def discover(site: str, fetch: Fetch = _fetch) -> list[str]:
    """Guide URLs linked from the homepage or listed in the sitemap, in order found."""
    found: list[str] = []
    candidates = [urljoin(site, href) for href in _parse(fetch(site)).links]
    try:
        candidates += re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", fetch(urljoin(site, "/sitemap.xml")))
    except requests.RequestException:
        pass  # the homepage alone is enough
    for url in candidates:
        url = url.split("#")[0].split("?")[0].rstrip("/")
        if _is_guide(site, url) and url not in found:
            found.append(url)
    return found


def parse_guide(url: str, html: str) -> dict:
    page = _parse(html)
    images = []
    for src, alt in page.images:
        absolute = urljoin(url, src).split("?")[0]
        # Body photos only: skip logos/icons and anything not a photo.
        if absolute.lower().endswith((".jpg", ".jpeg", ".png", ".webp")) and alt and absolute not in images:
            images.append((absolute, alt))
    return {
        "url": url,
        "title": _SITE_SUFFIX.sub("", page.title.strip()),
        "description": page.description.strip(),
        "images": images,
    }


def pin_text(guide: dict, alt: str) -> tuple[str, str]:
    title = guide["title"][:100]
    description = f"{alt.rstrip('.')}. {guide['description']} {_HASHTAGS}".strip()
    return title, description[:800]


def _state_path() -> Path:
    return ledger._STATE_DIR / _STATE_NAME


def load_state() -> dict:
    path = _state_path()
    return json.loads(path.read_text()) if path.exists() else {"pins": {}}


def save_state(data: dict) -> None:
    ledger._STATE_DIR.mkdir(parents=True, exist_ok=True)
    _state_path().write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def pin_new_guides(config: Config, client, fetch: Fetch = _fetch) -> list[str]:
    """Pin up to `pinterest_guide_pins_per_run` new guide photos; returns their image URLs."""
    state = load_state()
    pins: dict = state.setdefault("pins", {})
    guides = []
    for url in discover(config.pinterest_guide_site, fetch):
        try:
            guides.append(parse_guide(url, fetch(url)))
        except requests.RequestException as exc:
            print(f"Could not read guide {url}: {exc}")

    # Round-robin: repeatedly take the next unpinned photo of the guide
    # with the fewest Pins so far.
    count = {g["url"]: sum(1 for p in pins.values() if p["guide"] == g["url"]) for g in guides}
    queue = {g["url"]: [img for img in g["images"] if img[0] not in pins] for g in guides}
    todo = []
    while len(todo) < config.pinterest_guide_pins_per_run:
        open_guides = [
            g for g in guides if queue[g["url"]] and count[g["url"]] < config.pinterest_guide_images_per_guide
        ]
        if not open_guides:
            break
        guide = min(open_guides, key=lambda g: count[g["url"]])
        todo.append((guide, queue[guide["url"]].pop(0)))
        count[guide["url"]] += 1
    if not todo:
        return []

    board_id = client.get_or_create_board(config.pinterest_guide_board_name, _BOARD_DESCRIPTION)
    pinned = []
    for guide, (image, alt) in todo:
        title, description = pin_text(guide, alt)
        try:
            pin_id = client.create_pin(
                board_id, title=title, description=description, link=guide["url"], image_url=image, alt_text=alt[:500]
            )
        except PinterestApiError as exc:
            print(f"Pin failed for {image}: {exc}")
            continue
        pins[image] = {"guide": guide["url"], "pin_id": pin_id}
        save_state(state)
        pinned.append(image)
        print(f"Pinned {image} -> https://www.pinterest.com/pin/{pin_id}/")
    return pinned
