from unittest.mock import MagicMock

import pytest

from ebay_automation import pipeline_research
from ebay_automation.config import Config
from ebay_automation.research import NicheDemand
from ebay_automation.themes import Design, Theme

THEME = Theme(
    slug="test-theme",
    search_keyword="japanese kanji mug",
    title_template="{design} - Ceramic Mug 11oz",
    keywords=("kanji",),
    designs=(
        Design(slug="one", lines=("FIRST", "COFFEE")),
        Design(slug="two", lines=("THEN YOUR", "PROBLEMS")),
    ),
)


def _config(**overrides) -> Config:
    defaults = dict(
        printify_blueprint_id=478,
        printify_print_provider_id=99,
        printify_variant_ids=[65216],
        ebay_marketplace_id="EBAY_US",
        ebay_category_id="20675",
        shipping_cost_cents=579,
        min_unit_profit_cents=100,
    )
    defaults.update(overrides)
    return Config(**defaults)


def _demand(**overrides) -> NicheDemand:
    defaults = dict(
        keyword="japanese kanji mug",
        active_listings=4200,
        sampled=12,
        listings_with_sales=7,
        units_sold=40,
        units_per_listing_per_month=1.4,
        median_price_selling_cents=1899,
        median_price_all_cents=2100,
        expected_monthly_profit_cents=100,
        unit_profit_cents=100,
    )
    defaults.update(overrides)
    return NicheDemand(**defaults)


@pytest.fixture
def fake_render(monkeypatch, tmp_path):
    def render(design, output_path, product_colour, print_area):
        path = tmp_path / f"{design.slug}.png"
        path.write_bytes(b"fake-png-bytes")
        return path

    monkeypatch.setattr(pipeline_research.design_gen, "render_design", render)


@pytest.fixture
def printify() -> MagicMock:
    client = MagicMock()
    client.upload_image_base64.return_value = "img-123"
    client.create_product.return_value = {
        "id": "prod-1",
        "variants": [{"id": 65216, "cost": 503}],
        "images": [{"src": "https://example.com/mockup.png"}],
    }
    return client


@pytest.fixture
def ebay() -> MagicMock:
    client = MagicMock()
    client.create_offer.return_value = "offer-1"
    return client


def test_build_listing_passes_image_id_to_create_product(fake_render, printify, ebay):
    pipeline_research.build_listing(
        _config(), printify, ebay, THEME, THEME.designs[0], _demand(), "White", (2000, 800)
    )

    printify.create_product.assert_called_once()
    _, kwargs = printify.create_product.call_args
    assert kwargs["image_id"] == "img-123"
    assert kwargs["blueprint_id"] == 478


def test_price_comes_from_what_comparable_listings_actually_sell_for(
    fake_render, printify, ebay
):
    entry = pipeline_research.build_listing(
        _config(), printify, ebay, THEME, THEME.designs[0], _demand(), "White", (2000, 800)
    )

    assert entry["price_cents"] == 1899
    _, kwargs = ebay.create_offer.call_args
    offer = ebay.create_offer.call_args[0][0]
    assert offer["pricingSummary"]["price"]["value"] == "18.99"


def test_landed_cost_includes_shipping(fake_render, printify, ebay):
    entry = pipeline_research.build_listing(
        _config(), printify, ebay, THEME, THEME.designs[0], _demand(), "White", (2000, 800)
    )

    assert entry["cost_cents"] == 503 + 579
    # 18.99 less eBay's cut less landed cost
    assert entry["unit_profit_cents"] == 1899 - (round(1899 * 0.1325) + 40) - (503 + 579)


def test_entry_records_the_design_so_it_is_never_listed_twice(
    fake_render, printify, ebay
):
    entry = pipeline_research.build_listing(
        _config(), printify, ebay, THEME, THEME.designs[0], _demand(), "White", (2000, 800)
    )

    assert entry["design_key"] == "test-theme/one"
    assert entry["theme"] == "test-theme"
    assert entry["headline"] == "FIRST COFFEE"


def test_entry_carries_the_demand_evidence_for_the_approval_issue(
    fake_render, printify, ebay
):
    entry = pipeline_research.build_listing(
        _config(), printify, ebay, THEME, THEME.designs[0], _demand(), "White", (2000, 800)
    )

    assert entry["demand"]["active_listings"] == 4200
    assert entry["demand"]["sell_through_pct"] == 58
    assert entry["demand"]["units_per_listing_per_month"] == 1.4
    assert pipeline_research._issue_body(entry)


def test_ebay_title_stays_within_the_80_character_limit(fake_render, printify, ebay):
    long_theme = Theme(
        slug="long",
        search_keyword="k",
        title_template="{design} - Japanese Kanji Ceramic Coffee Mug 11oz Novelty Gift For Him And Her",
        keywords=(),
        designs=(Design(slug="x", lines=("I SURVIVED", "ANOTHER MEETING")),),
    )

    pipeline_research.build_listing(
        _config(), printify, ebay, long_theme, long_theme.designs[0], _demand(), "White", (2000, 800)
    )

    _, kwargs = ebay.create_or_replace_inventory_item.call_args
    item = ebay.create_or_replace_inventory_item.call_args[0][1]
    assert len(item["product"]["title"]) <= 80


def test_product_profile_reads_colour_and_print_area_from_the_catalogue():
    client = MagicMock()
    client.get_blueprint_variants.return_value = {
        "variants": [
            {"id": 1, "options": {"color": "Black"}, "placeholders": []},
            {
                "id": 65216,
                "options": {"color": "White"},
                "placeholders": [
                    {"position": "back", "width": 10, "height": 10},
                    {"position": "front", "width": 2475, "height": 1155},
                ],
            },
        ]
    }

    colour, area = pipeline_research.product_profile(_config(), client)

    assert colour == "White"
    assert area == (2475, 1155)


def test_product_profile_fails_loudly_on_an_unknown_variant():
    client = MagicMock()
    client.get_blueprint_variants.return_value = {"variants": []}

    with pytest.raises(RuntimeError, match="65216"):
        pipeline_research.product_profile(_config(), client)


def test_used_design_keys_reads_pending_listings(monkeypatch):
    monkeypatch.setattr(
        pipeline_research.ledger,
        "load_pending_listings",
        lambda: {
            "SKU-1": {"design_key": "test-theme/one"},
            "SKU-2": {},  # entries written before design keys existed
        },
    )

    assert pipeline_research.used_design_keys() == {"test-theme/one"}
