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
