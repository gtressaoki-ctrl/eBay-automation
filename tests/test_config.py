import pytest

from ebay_automation.config import Config


def test_require_raises_on_missing_fields():
    cfg = Config(ebay_app_id="", ebay_cert_id="set")
    with pytest.raises(RuntimeError, match="ebay_app_id"):
        cfg.require("ebay_app_id", "ebay_cert_id")


def test_require_passes_when_all_present():
    cfg = Config(ebay_app_id="a", ebay_cert_id="b")
    cfg.require("ebay_app_id", "ebay_cert_id")  # should not raise


def test_defaults_are_sane():
    cfg = Config()
    assert cfg.ebay_marketplace_id == "EBAY_US"
    assert cfg.daily_listing_quota == 3
    assert cfg.auto_publish is False


def test_blank_repository_variable_does_not_override_the_default(monkeypatch):
    """GitHub substitutes an unset repo variable as "", not as absent."""
    monkeypatch.setenv("EBAY_CATEGORY_ID", "")
    monkeypatch.setenv("EBAY_MARKETPLACE_ID", "")
    monkeypatch.setenv("PRINTIFY_VARIANT_IDS", "")
    monkeypatch.setenv("PRINTIFY_BLUEPRINT_ID", "")

    config = Config()

    assert config.ebay_category_id == "20675"
    assert config.ebay_marketplace_id == "EBAY_US"
    assert config.printify_variant_ids == [65216]
    assert config.printify_blueprint_id == 478


def test_repository_variables_still_win_when_actually_set(monkeypatch):
    monkeypatch.setenv("EBAY_CATEGORY_ID", "15687")
    monkeypatch.setenv("PRINTIFY_VARIANT_IDS", "1, 2 ,3")

    config = Config()

    assert config.ebay_category_id == "15687"
    assert config.printify_variant_ids == [1, 2, 3]
