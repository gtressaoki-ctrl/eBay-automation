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


DOG_THEME = Theme(
    slug="dog-mom",
    search_keyword="dog mom mug gift",
    title_template="{design} - Ceramic Mug 11oz",
    keywords=(),
    designs=(Design(slug="only", lines=("DOG", "MOM")),),
)


def test_select_active_themes_explores_everything_with_no_track_record(monkeypatch):
    monkeypatch.setattr(pipeline_research.ledger, "theme_stats", lambda: {})

    result = pipeline_research.select_active_themes((THEME, DOG_THEME), _config())

    assert result == (THEME, DOG_THEME)


def test_select_active_themes_ignores_a_theme_published_but_never_sold(monkeypatch):
    monkeypatch.setattr(
        pipeline_research.ledger,
        "theme_stats",
        lambda: {"test-theme": {"published": 5, "profit_cents": 0}},
    )

    result = pipeline_research.select_active_themes((THEME, DOG_THEME), _config(brand_lock_min_published=3))

    assert result == (THEME, DOG_THEME)


def test_select_active_themes_locks_onto_a_theme_that_has_proven_itself(monkeypatch):
    monkeypatch.setattr(
        pipeline_research.ledger,
        "theme_stats",
        lambda: {
            "test-theme": {"published": 3, "profit_cents": 500},
            "dog-mom": {"published": 1, "profit_cents": 0},
        },
    )

    result = pipeline_research.select_active_themes(
        (THEME, DOG_THEME), _config(brand_lock_min_published=3)
    )

    assert result == (THEME,)


def test_select_active_themes_picks_the_most_profitable_qualified_theme(monkeypatch):
    monkeypatch.setattr(
        pipeline_research.ledger,
        "theme_stats",
        lambda: {
            "test-theme": {"published": 3, "profit_cents": 500},
            "dog-mom": {"published": 4, "profit_cents": 1500},
        },
    )

    result = pipeline_research.select_active_themes(
        (THEME, DOG_THEME), _config(brand_lock_min_published=3)
    )

    assert result == (DOG_THEME,)


def test_brand_tagline_is_appended_to_the_listing_when_set(fake_render, printify, ebay):
    entry = pipeline_research.build_listing(
        _config(brand_tagline="Maple & Co."),
        printify,
        ebay,
        THEME,
        THEME.designs[0],
        _demand(),
        "White",
        (2000, 800),
    )

    item = ebay.create_or_replace_inventory_item.call_args[0][1]
    assert "Maple &amp; Co." in item["product"]["description"] or "Maple & Co." in item["product"]["description"]
    assert item["product"]["aspects"]["Brand"] == ["Maple & Co."]


def test_brand_tagline_defaults_to_unbranded_when_unset(fake_render, printify, ebay):
    entry = pipeline_research.build_listing(
        _config(), printify, ebay, THEME, THEME.designs[0], _demand(), "White", (2000, 800)
    )

    item = ebay.create_or_replace_inventory_item.call_args[0][1]
    assert item["product"]["aspects"]["Brand"] == ["Unbranded"]


def test_model_aspect_is_set_from_the_design_slug(fake_render, printify, ebay):
    pipeline_research.build_listing(
        _config(), printify, ebay, THEME, THEME.designs[0], _demand(), "White", (2000, 800)
    )

    item = ebay.create_or_replace_inventory_item.call_args[0][1]
    # Category 20675 (Mugs) rejects publishOffer with errorId 25002 ("Model
    # is missing") unless this aspect is present — createOrReplaceInventoryItem
    # itself accepts its absence, which is why this only surfaced at publish
    # time in production. The design slug is unique per listing and stands
    # in for a real model number.
    assert item["product"]["aspects"]["Model"] == [THEME.designs[0].slug]


def test_sku_never_exceeds_ebays_50_character_limit():
    long_theme = Theme(
        slug="sarcastic-coffee",
        search_keyword="k",
        title_template="{design}",
        keywords=(),
        designs=(Design(slug="should-have-been-an-email", lines=("X",)),),
    )
    sku = pipeline_research._sku_for(long_theme, long_theme.designs[0])
    assert len(sku) <= 50


def test_sku_keeps_the_uniqueness_suffix_even_when_truncated():
    long_theme = Theme(
        slug="sarcastic-coffee", search_keyword="k", title_template="{design}", keywords=(),
        designs=(Design(slug="professional-overthinker", lines=("X",)),),
    )
    a = pipeline_research._sku_for(long_theme, long_theme.designs[0])
    b = pipeline_research._sku_for(long_theme, long_theme.designs[0])
    assert a != b
    assert len(a) <= 50 and len(b) <= 50


def test_build_listing_cleans_up_the_printify_product_if_ebay_rejects_it(
    fake_render, printify
):
    ebay = MagicMock()
    ebay.create_or_replace_inventory_item.side_effect = RuntimeError("400: invalid SKU")

    with pytest.raises(RuntimeError):
        pipeline_research.build_listing(
            _config(), printify, ebay, THEME, THEME.designs[0], _demand(), "White", (2000, 800)
        )

    printify.delete_product.assert_called_once_with("prod-1")


def test_dropped_listing_is_cleaned_up_from_both_printify_and_ebay(monkeypatch):
    # A theme with exactly one design: pick_unused_design (the real
    # implementation, not mocked) naturally returns None on the second
    # pass once that one design is marked used, ending the inner loop
    # after a single drop+cleanup instead of spinning until quota.
    one_design_theme = Theme(
        slug="test-theme", search_keyword="japanese kanji mug", title_template="{design}",
        keywords=(), designs=(Design(slug="one", lines=("FIRST", "COFFEE")),),
    )
    printify = MagicMock()
    ebay = MagicMock()
    config = _config(min_unit_profit_cents=100)

    monkeypatch.setattr(pipeline_research, "product_profile", lambda c, p: ("White", (2000, 800)))
    monkeypatch.setattr(
        pipeline_research,
        "build_listing",
        lambda *a, **k: {
            "sku": "POD-x-1",
            "design_key": "test-theme/one",
            "printify_product_id": "prod-1",
            "unit_profit_cents": 5,  # below the floor
        },
    )
    monkeypatch.setattr(pipeline_research, "select_active_themes", lambda themes_, cfg: (one_design_theme,))
    monkeypatch.setattr(
        pipeline_research.research,
        "rank_niches",
        lambda *a, **k: pipeline_research.research.DemandReport(ranked=[_demand()], rejected=[]),
    )
    monkeypatch.setattr(pipeline_research.ledger, "load_ledger", lambda: {})
    monkeypatch.setattr(pipeline_research.ledger, "adjust_daily_quota", lambda: 3)
    monkeypatch.setattr(pipeline_research, "used_design_keys", lambda: set())
    monkeypatch.setattr(pipeline_research, "PrintifyClient", lambda config: printify)
    monkeypatch.setattr(pipeline_research, "EbayClient", lambda config: ebay)
    monkeypatch.setattr(pipeline_research, "GithubClient", lambda config: MagicMock())
    monkeypatch.setattr(pipeline_research, "load_config", lambda: config)

    pipeline_research.run()

    printify.delete_product.assert_called_once_with("prod-1")
    ebay.delete_inventory_item.assert_called_once_with("POD-x-1")


def test_auto_publish_failure_cleans_up_and_does_not_crash_the_run(monkeypatch):
    # publishOffer failing (e.g. a category rule 400) used to be the one
    # eBay call in run() with no try/except around it, which crashed the
    # whole process mid-quota and orphaned the Printify product/eBay
    # inventory item it had just created. Same one-design-theme trick as
    # the dropped-listing test above to end the loop after one attempt.
    one_design_theme = Theme(
        slug="test-theme", search_keyword="japanese kanji mug", title_template="{design}",
        keywords=(), designs=(Design(slug="one", lines=("FIRST", "COFFEE")),),
    )
    printify = MagicMock()
    ebay = MagicMock()
    ebay.publish_offer.side_effect = RuntimeError("400: item specific Model is missing")
    config = _config(min_unit_profit_cents=10, auto_publish=True)

    monkeypatch.setattr(pipeline_research, "product_profile", lambda c, p: ("White", (2000, 800)))
    monkeypatch.setattr(
        pipeline_research,
        "build_listing",
        lambda *a, **k: {
            "sku": "POD-x-1",
            "design_key": "test-theme/one",
            "printify_product_id": "prod-1",
            "ebay_offer_id": "offer-1",
            "unit_profit_cents": 500,  # clears the floor
        },
    )
    monkeypatch.setattr(pipeline_research, "select_active_themes", lambda themes_, cfg: (one_design_theme,))
    monkeypatch.setattr(
        pipeline_research.research,
        "rank_niches",
        lambda *a, **k: pipeline_research.research.DemandReport(ranked=[_demand()], rejected=[]),
    )
    monkeypatch.setattr(pipeline_research.ledger, "load_ledger", lambda: {})
    monkeypatch.setattr(pipeline_research.ledger, "adjust_daily_quota", lambda: 3)
    monkeypatch.setattr(pipeline_research, "used_design_keys", lambda: set())
    monkeypatch.setattr(pipeline_research, "PrintifyClient", lambda config: printify)
    monkeypatch.setattr(pipeline_research, "EbayClient", lambda config: ebay)
    monkeypatch.setattr(pipeline_research, "GithubClient", lambda config: MagicMock())
    monkeypatch.setattr(pipeline_research, "load_config", lambda: config)
    monkeypatch.setattr(pipeline_research, "publish_backlog", lambda *a: True)

    pipeline_research.run()  # must not raise

    printify.delete_product.assert_called_once_with("prod-1")
    ebay.delete_inventory_item.assert_called_once_with("POD-x-1")


def _auto_publish_run_fixture(monkeypatch, theme, publish_side_effect):
    printify = MagicMock()
    ebay = MagicMock()
    ebay.publish_offer.side_effect = publish_side_effect
    config = _config(min_unit_profit_cents=10, auto_publish=True)
    builds = []

    def fake_build(*a, **k):
        builds.append(a[4].slug)
        return {
            "sku": f"POD-x-{a[4].slug}",
            "design_key": f"test-theme/{a[4].slug}",
            "printify_product_id": f"prod-{a[4].slug}",
            "ebay_offer_id": f"offer-{a[4].slug}",
            "unit_profit_cents": 500,
        }

    monkeypatch.setattr(pipeline_research, "product_profile", lambda c, p: ("White", (2000, 800)))
    monkeypatch.setattr(pipeline_research, "build_listing", fake_build)
    monkeypatch.setattr(pipeline_research, "select_active_themes", lambda themes_, cfg: (theme,))
    monkeypatch.setattr(
        pipeline_research.research,
        "rank_niches",
        lambda *a, **k: pipeline_research.research.DemandReport(ranked=[_demand()], rejected=[]),
    )
    monkeypatch.setattr(pipeline_research.ledger, "load_ledger", lambda: {})
    monkeypatch.setattr(pipeline_research.ledger, "adjust_daily_quota", lambda: 3)
    monkeypatch.setattr(pipeline_research, "used_design_keys", lambda: set())
    monkeypatch.setattr(pipeline_research, "PrintifyClient", lambda config: printify)
    monkeypatch.setattr(pipeline_research, "EbayClient", lambda config: ebay)
    monkeypatch.setattr(pipeline_research, "GithubClient", lambda config: MagicMock())
    monkeypatch.setattr(pipeline_research, "load_config", lambda: config)
    monkeypatch.setattr(pipeline_research, "publish_backlog", lambda *a: True)
    return printify, ebay, builds


def test_hitting_the_selling_limit_stops_the_run_instead_of_burning_more_products(monkeypatch):
    # Once eBay says the account's monthly selling limit is reached, every
    # further publish fails identically — building more Printify products
    # just to delete them again is pure waste.
    from ebay_automation.ebay_client import EbayApiError

    limit_error = EbayApiError(
        "POST", "u", 400, '{"errors":[{"message":"This listing would cause you to exceed the number of items"}]}'
    )
    _, ebay, builds = _auto_publish_run_fixture(monkeypatch, THEME, limit_error)

    pipeline_research.run()

    assert builds == ["one"]
    ebay.delete_inventory_item.assert_called_once_with("POD-x-one")


def test_other_publish_failures_move_on_to_the_next_design(monkeypatch):
    _, _, builds = _auto_publish_run_fixture(monkeypatch, THEME, RuntimeError("500"))

    pipeline_research.run()

    assert builds == ["one", "two"]


def test_ad_bid_is_capped_so_an_ad_driven_sale_stays_profitable():
    config = _config(min_unit_profit_cents=10, promoted_listings_bid_percentage=10.0)
    # $14.99 mug netting $0.68: 10% ($1.50) would lose money on every ad
    # sale; the cap leaves at least the $0.10 floor.
    bid = pipeline_research.profitable_bid_percentage(config, {"price_cents": 1499, "unit_profit_cents": 68})
    assert bid == 3.8
    assert 1499 * bid / 100 <= 68 - 10


def test_no_ad_when_even_the_minimum_bid_would_lose_money():
    config = _config(min_unit_profit_cents=10, promoted_listings_bid_percentage=10.0)
    assert pipeline_research.profitable_bid_percentage(config, {"price_cents": 1499, "unit_profit_cents": 30}) is None


def test_ad_bid_never_exceeds_the_configured_bid():
    config = _config(min_unit_profit_cents=10, promoted_listings_bid_percentage=5.0)
    assert pipeline_research.profitable_bid_percentage(config, {"price_cents": 1499, "unit_profit_cents": 900}) == 5.0


def test_listing_quantity_comes_from_config(fake_render, printify, ebay):
    pipeline_research.build_listing(
        _config(listing_quantity=1), printify, ebay, THEME, THEME.designs[0], _demand(), "White", (2000, 800)
    )

    item = ebay.create_or_replace_inventory_item.call_args[0][1]
    offer = ebay.create_offer.call_args[0][0]
    # A new seller's monthly limit counts quantity x price across all live
    # listings; the old hard-coded 50 exceeded it with a single listing.
    assert item["availability"]["shipToLocationAvailability"]["quantity"] == 1
    assert offer["availableQuantity"] == 1


def _backlog_fixture(monkeypatch, pending):
    updates = []
    monkeypatch.setattr(pipeline_research.ledger, "load_pending_listings", lambda: pending)
    monkeypatch.setattr(
        pipeline_research.ledger, "update_listing_status", lambda sku, status, **kw: updates.append((sku, status, kw))
    )
    monkeypatch.setattr(pipeline_research.ledger, "record_listing_published", lambda: None)
    ebay = MagicMock()
    ebay.get_inventory_item.return_value = {
        "sku": "POD-old-1",
        "condition": "NEW",
        "availability": {"shipToLocationAvailability": {"quantity": 50}},
        "product": {"title": "T", "aspects": {"Brand": ["Unbranded"]}},
    }
    ebay.get_offer.return_value = {
        "offerId": "offer-old",
        "sku": "POD-old-1",
        "marketplaceId": "EBAY_US",
        "format": "FIXED_PRICE",
        "status": "UNPUBLISHED",
        "availableQuantity": 50,
        "categoryId": "20675",
        "pricingSummary": {"price": {"value": "14.99", "currency": "USD"}},
    }
    ebay.publish_offer.return_value = "1234567890"
    github = MagicMock()
    return ebay, github, updates


def test_backlog_drafts_are_patched_and_published(monkeypatch):
    pending = {
        "POD-old-1": {
            "status": "pending_approval",
            "ebay_offer_id": "offer-old",
            "design_key": "sarcastic-coffee/caffeine-and-spite",
            "issue_number": 19,
        },
        "POD-done": {"status": "published", "ebay_offer_id": "x"},
    }
    ebay, github, updates = _backlog_fixture(monkeypatch, pending)

    assert pipeline_research.publish_backlog(_config(listing_quantity=1), ebay, github) is True

    sku, item = ebay.create_or_replace_inventory_item.call_args[0]
    assert sku == "POD-old-1"
    assert item["product"]["aspects"]["Model"] == ["caffeine-and-spite"]
    assert item["availability"]["shipToLocationAvailability"]["quantity"] == 1
    offer_id, offer = ebay.update_offer.call_args[0]
    assert offer_id == "offer-old"
    assert offer == {
        "availableQuantity": 1,
        "categoryId": "20675",
        "pricingSummary": {"price": {"value": "14.99", "currency": "USD"}},
    }
    ebay.publish_offer.assert_called_once_with("offer-old")
    assert updates == [
        ("POD-old-1", "published", {"ebay_listing_id": "1234567890", "listing_url": "https://www.ebay.com/itm/1234567890"})
    ]
    github.close_issue.assert_called_once_with(19, "completed")


def test_backlog_stops_and_reports_the_selling_limit(monkeypatch):
    from ebay_automation.ebay_client import EbayApiError

    pending = {"POD-old-1": {"status": "pending_approval", "ebay_offer_id": "offer-old"}}
    ebay, github, updates = _backlog_fixture(monkeypatch, pending)
    ebay.publish_offer.side_effect = EbayApiError("POST", "u", 400, "would exceed the number of items")

    assert pipeline_research.publish_backlog(_config(), ebay, github) is False
    assert updates == []
