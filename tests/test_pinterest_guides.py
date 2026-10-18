from unittest.mock import MagicMock

import pytest

from ebay_automation import ledger, pinterest_guides
from ebay_automation.config import Config
from ebay_automation.pinterest_client import PinterestApiError

SITE = "https://slowjapantrails.com/"


def _guide_html(slug: str, n: int) -> str:
    imgs = "".join(f'<img src="/images/{slug}/{i}.jpg" alt="Photo {i} of {slug}"/>' for i in range(n))
    return (
        f"<html><head><title>{slug.title()} Guide | Slow Japan Trails</title>"
        f'<meta name="description" content="All about {slug}."></head>'
        f'<body><img src="/logo.svg" alt="logo"/>{imgs}</body></html>'
    )


PAGES = {
    SITE: '<a href="/guides/garden">x</a><a href="/about">a</a><a href="https://other.com/guides/x">o</a>',
    SITE + "sitemap.xml": f"<urlset><url><loc>{SITE}guides/hike</loc></url><url><loc>{SITE}guides/garden</loc></url></urlset>",
    SITE + "guides/garden": _guide_html("garden", 3),
    SITE + "guides/hike": _guide_html("hike", 1),
}


def _config(**overrides) -> Config:
    values = dict(
        pinterest_guide_site=SITE,
        pinterest_guide_board_name="Shikoku Travel Guides",
        pinterest_guide_pins_per_run=2,
        pinterest_guide_images_per_guide=6,
    )
    values.update(overrides)
    return Config(**values)


@pytest.fixture(autouse=True)
def state_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(ledger, "_STATE_DIR", tmp_path)


def test_discovers_guides_from_homepage_and_sitemap():
    assert pinterest_guides.discover(SITE, PAGES.__getitem__) == [SITE + "guides/garden", SITE + "guides/hike"]


def test_parses_title_description_and_body_photos():
    guide = pinterest_guides.parse_guide(SITE + "guides/garden", PAGES[SITE + "guides/garden"])
    assert guide["title"] == "Garden Guide"
    assert guide["description"] == "All about garden."
    assert guide["images"][0] == (SITE + "images/garden/0.jpg", "Photo 0 of garden")
    assert len(guide["images"]) == 3  # the svg logo is skipped


def test_pins_round_robin_across_guides_and_never_twice():
    client = MagicMock()
    client.get_or_create_board.return_value = "b"
    client.create_pin.side_effect = ["p1", "p2", "p3", "p4"]

    first = pinterest_guides.pin_new_guides(_config(), client, PAGES.__getitem__)
    assert first == [SITE + "images/garden/0.jpg", SITE + "images/hike/0.jpg"]
    kwargs = client.create_pin.call_args_list[1].kwargs
    assert kwargs["link"] == SITE + "guides/hike"
    assert kwargs["title"] == "Hike Guide"
    assert kwargs["alt_text"] == "Photo 0 of hike"
    assert kwargs["description"].startswith("Photo 0 of hike. All about hike.")

    second = pinterest_guides.pin_new_guides(_config(), client, PAGES.__getitem__)
    assert second == [SITE + "images/garden/1.jpg", SITE + "images/garden/2.jpg"]
    assert pinterest_guides.pin_new_guides(_config(), client, PAGES.__getitem__) == []


def test_images_per_guide_cap_and_failed_pin_is_retried():
    client = MagicMock()
    client.get_or_create_board.return_value = "b"
    client.create_pin.side_effect = [PinterestApiError("POST", "u", 400, "bad"), "p2"]
    config = _config(pinterest_guide_images_per_guide=1)

    assert pinterest_guides.pin_new_guides(config, client, PAGES.__getitem__) == [SITE + "images/hike/0.jpg"]
    assert SITE + "images/garden/0.jpg" not in pinterest_guides.load_state()["pins"]
