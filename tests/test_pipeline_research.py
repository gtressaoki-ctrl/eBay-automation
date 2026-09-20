from unittest.mock import MagicMock

from ebay_automation.config import Config
from ebay_automation.pipeline_research import build_listing_for_niche
from ebay_automation.research import NicheScore


def test_build_listing_for_niche_passes_image_id_to_create_product(monkeypatch, tmp_path):
    config = Config(
        printify_blueprint_id=145,
        printify_print_provider_id=99,
        printify_variant_ids=[38178],
        ebay_marketplace_id="EBAY_US",
        ebay_category_id="15687",
    )

    monkeypatch.setattr(
        "ebay_automation.pipeline_research.design_gen.generate_design_for_niche",
        lambda keyword, output_path: (
            (lambda p: (p.write_bytes(b"fake-png-bytes"), p)[1])(tmp_path / "design.png"),
            "GYM MOTIVATION",
        ),
    )

    printify = MagicMock()
    printify.upload_image_base64.return_value = "img-123"
    printify.create_product.return_value = {
        "id": "prod-1",
        "variants": [{"id": 38178, "cost": 1250}],
        "images": [{"src": "https://example.com/mockup.png"}],
    }

    ebay = MagicMock()
    ebay.create_offer.return_value = "offer-1"

    niche = NicheScore(keyword="gym motivation shirt", total_listings=3000, avg_price=24.0, score=0.9)

    entry = build_listing_for_niche(config, printify, ebay, niche)

    assert entry is not None
    printify.create_product.assert_called_once()
    _, kwargs = printify.create_product.call_args
    assert kwargs["image_id"] == "img-123"
    assert kwargs["blueprint_id"] == 145
