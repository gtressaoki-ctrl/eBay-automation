"""Environment-driven configuration for the pipeline.

All secrets come from environment variables (GitHub Actions secrets in CI,
a local .env file for manual runs). Nothing sensitive is ever hard-coded.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field


def _bool_env(name: str, default: bool) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


def _int_env(name: str, default: int) -> int:
    val = os.environ.get(name)
    return int(val) if val else default


@dataclass(frozen=True)
class Config:
    # eBay
    ebay_app_id: str = field(default_factory=lambda: os.environ.get("EBAY_APP_ID", ""))
    ebay_cert_id: str = field(default_factory=lambda: os.environ.get("EBAY_CERT_ID", ""))
    ebay_dev_id: str = field(default_factory=lambda: os.environ.get("EBAY_DEV_ID", ""))
    ebay_refresh_token: str = field(default_factory=lambda: os.environ.get("EBAY_REFRESH_TOKEN", ""))
    ebay_marketplace_id: str = field(default_factory=lambda: os.environ.get("EBAY_MARKETPLACE_ID", "EBAY_US"))
    ebay_merchant_location_key: str = field(
        default_factory=lambda: os.environ.get("EBAY_MERCHANT_LOCATION_KEY", "")
    )
    ebay_fulfillment_policy_id: str = field(
        default_factory=lambda: os.environ.get("EBAY_FULFILLMENT_POLICY_ID", "")
    )
    ebay_payment_policy_id: str = field(default_factory=lambda: os.environ.get("EBAY_PAYMENT_POLICY_ID", ""))
    ebay_return_policy_id: str = field(default_factory=lambda: os.environ.get("EBAY_RETURN_POLICY_ID", ""))
    ebay_env: str = field(default_factory=lambda: os.environ.get("EBAY_ENV", "PRODUCTION"))  # or SANDBOX
    # eBay US "T-Shirts" category as of this writing; verify with the
    # Taxonomy API (getCategorySuggestions) before relying on it, eBay
    # category IDs occasionally change.
    ebay_category_id: str = field(default_factory=lambda: os.environ.get("EBAY_CATEGORY_ID", "15687"))

    # Printify
    printify_api_key: str = field(default_factory=lambda: os.environ.get("PRINTIFY_API_KEY", ""))
    printify_shop_id: str = field(default_factory=lambda: os.environ.get("PRINTIFY_SHOP_ID", ""))
    # Defaults are the 11oz ceramic mug from Printify Choice. Demand
    # measurement put mug niches at roughly twelve times the monthly
    # profit per listing of graphic tees, which is why this is the
    # default product rather than apparel. Override via repo variables to
    # sell something else; scripts/list_printify_catalog.py lists IDs.
    printify_blueprint_id: int = field(default_factory=lambda: _int_env("PRINTIFY_BLUEPRINT_ID", 478))
    printify_print_provider_id: int = field(default_factory=lambda: _int_env("PRINTIFY_PRINT_PROVIDER_ID", 99))
    printify_variant_ids: list[int] = field(
        default_factory=lambda: [
            int(v) for v in os.environ.get("PRINTIFY_VARIANT_IDS", "65216").split(",") if v.strip()
        ]
    )

    # GitHub (for opening approval issues)
    github_token: str = field(default_factory=lambda: os.environ.get("GITHUB_TOKEN", ""))
    github_repository: str = field(default_factory=lambda: os.environ.get("GITHUB_REPOSITORY", ""))

    # Pipeline behavior
    daily_listing_quota: int = field(default_factory=lambda: _int_env("DAILY_LISTING_QUOTA", 3))
    auto_publish: bool = field(default_factory=lambda: _bool_env("AUTO_PUBLISH", False))
    dry_run: bool = field(default_factory=lambda: _bool_env("DRY_RUN", False))
    # Never list a design whose unit economics at the going market price
    # come in under this, however well the niche sells.
    min_unit_profit_cents: int = field(default_factory=lambda: _int_env("MIN_UNIT_PROFIT_CENTS", 100))
    # Landed cost per unit is production plus shipping; Printify bills
    # both, and ignoring shipping is what made the first pricing pass
    # look profitable when it was not.
    shipping_cost_cents: int = field(default_factory=lambda: _int_env("SHIPPING_COST_CENTS", 579))

    def require(self, *names: str) -> None:
        missing = [n for n in names if not getattr(self, n)]
        if missing:
            raise RuntimeError(
                f"Missing required configuration: {', '.join(missing)}. "
                "See docs/SETUP.md for how to obtain and set these."
            )


def load_config() -> Config:
    return Config()
