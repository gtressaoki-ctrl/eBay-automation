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


def _float_env(name: str, default: float) -> float:
    val = os.environ.get(name)
    return float(val) if val else default


def _str_env(name: str, default: str = "") -> str:
    """Read a string setting, treating an empty value as unset.

    GitHub Actions substitutes an unset repository variable as the empty
    string, so `${{ vars.EBAY_CATEGORY_ID }}` arrives as "" rather than
    being absent. os.environ.get(name, default) then returns "" and
    silently overrides the default — which is how a run once went out
    with no category at all. Anything blank falls back here instead.
    """
    return os.environ.get(name, "").strip() or default


def _int_list_env(name: str, default: list[int]) -> list[int]:
    values = [int(v) for v in os.environ.get(name, "").split(",") if v.strip()]
    return values or default


@dataclass(frozen=True)
class Config:
    # eBay
    ebay_app_id: str = field(default_factory=lambda: _str_env("EBAY_APP_ID"))
    ebay_cert_id: str = field(default_factory=lambda: _str_env("EBAY_CERT_ID"))
    ebay_dev_id: str = field(default_factory=lambda: _str_env("EBAY_DEV_ID"))
    ebay_refresh_token: str = field(default_factory=lambda: _str_env("EBAY_REFRESH_TOKEN"))
    ebay_marketplace_id: str = field(default_factory=lambda: _str_env("EBAY_MARKETPLACE_ID", "EBAY_US"))
    ebay_merchant_location_key: str = field(
        default_factory=lambda: _str_env("EBAY_MERCHANT_LOCATION_KEY")
    )
    ebay_fulfillment_policy_id: str = field(
        default_factory=lambda: _str_env("EBAY_FULFILLMENT_POLICY_ID")
    )
    ebay_payment_policy_id: str = field(default_factory=lambda: _str_env("EBAY_PAYMENT_POLICY_ID"))
    ebay_return_policy_id: str = field(default_factory=lambda: _str_env("EBAY_RETURN_POLICY_ID"))
    ebay_env: str = field(default_factory=lambda: _str_env("EBAY_ENV", "PRODUCTION"))  # or SANDBOX
    # eBay US "Mugs" category as of this writing; verify with the Taxonomy
    # API (getCategorySuggestions) before relying on it, eBay category IDs
    # occasionally change. Change this alongside the Printify blueprint —
    # listing a mug under the old T-Shirts category (15687) is how a run
    # ends up in front of the wrong buyers.
    ebay_category_id: str = field(default_factory=lambda: _str_env("EBAY_CATEGORY_ID", "20675"))

    # Printify
    printify_api_key: str = field(default_factory=lambda: _str_env("PRINTIFY_API_KEY"))
    printify_shop_id: str = field(default_factory=lambda: _str_env("PRINTIFY_SHOP_ID"))
    # Defaults are the 11oz ceramic mug from Printify Choice. Demand
    # measurement put mug niches at roughly twelve times the monthly
    # profit per listing of graphic tees, which is why this is the
    # default product rather than apparel. Override via repo variables to
    # sell something else; scripts/list_printify_catalog.py lists IDs.
    printify_blueprint_id: int = field(default_factory=lambda: _int_env("PRINTIFY_BLUEPRINT_ID", 478))
    printify_print_provider_id: int = field(default_factory=lambda: _int_env("PRINTIFY_PRINT_PROVIDER_ID", 99))
    printify_variant_ids: list[int] = field(
        default_factory=lambda: _int_list_env("PRINTIFY_VARIANT_IDS", [65216])
    )

    # GitHub (for opening approval issues)
    github_token: str = field(default_factory=lambda: _str_env("GITHUB_TOKEN"))
    github_repository: str = field(default_factory=lambda: _str_env("GITHUB_REPOSITORY"))

    # Pipeline behavior
    daily_listing_quota: int = field(default_factory=lambda: _int_env("DAILY_LISTING_QUOTA", 3))
    auto_publish: bool = field(default_factory=lambda: _bool_env("AUTO_PUBLISH", False))
    dry_run: bool = field(default_factory=lambda: _bool_env("DRY_RUN", False))
    # Never list a design whose unit economics at the going market price
    # come in under this, however well the niche sells. Kept low (not
    # zero) on purpose: a brand-new seller with no Feedback gets almost no
    # organic visibility regardless of listing quality (see README), so
    # the near-term goal is real sales and reviews rather than protecting
    # margin on them — but a listing still has to not lose money outright
    # before any ad spend. $1.00 rejected every niche the first live run
    # found (best case $0.68/unit); $0.10 is the floor that says "must be
    # profitable" without pretending today's mug economics support more.
    min_unit_profit_cents: int = field(default_factory=lambda: _int_env("MIN_UNIT_PROFIT_CENTS", 10))
    # Landed cost per unit is production plus shipping; Printify bills
    # both, and ignoring shipping is what made the first pricing pass
    # look profitable when it was not.
    shipping_cost_cents: int = field(default_factory=lambda: _int_env("SHIPPING_COST_CENTS", 579))
    # Scattering listings across unrelated themes forever never becomes a
    # brand a buyer recognizes and returns to. Once one theme has this many
    # published, profitable listings, research locks onto it exclusively;
    # below that, every theme is still explored to find which one deserves
    # the commitment. See pipeline_research.select_active_themes().
    brand_lock_min_published: int = field(
        default_factory=lambda: _int_env("BRAND_LOCK_MIN_PUBLISHED", 3)
    )
    # Optional line appended to every listing description's footer, e.g. a
    # shop name/tagline. Choosing one is a business decision (trademark,
    # what it signals) that belongs to the seller, not this pipeline — this
    # only wires it through once chosen. Blank changes nothing.
    brand_tagline: str = field(default_factory=lambda: _str_env("BRAND_TAGLINE"))

    # A brand-new seller with zero feedback is ranked far down eBay's own
    # search regardless of listing quality — Promoted Listings Standard
    # (cost-per-sale) is the one paid lever that fits near-zero effort/idle
    # cost: eBay only takes its cut when an ad click leads to an actual
    # sale, nothing if it doesn't. Off by default, like auto_publish, since
    # it is still a real (if bounded) spend decision.
    promoted_listings_enabled: bool = field(
        default_factory=lambda: _bool_env("PROMOTED_LISTINGS_ENABLED", False)
    )
    # eBay requires 2.0-100.0. Defaults high enough to plausibly absorb the
    # entire per-unit margin on today's best niche — the point right now is
    # buying the first sales and feedback, not preserving profit on them.
    promoted_listings_bid_percentage: float = field(
        default_factory=lambda: _float_env("PROMOTED_LISTINGS_BID_PERCENTAGE", 10.0)
    )
    promoted_listings_campaign_name: str = field(
        default_factory=lambda: _str_env("PROMOTED_LISTINGS_CAMPAIGN_NAME", "ebay-automation-cps")
    )

    def require(self, *names: str) -> None:
        missing = [n for n in names if not getattr(self, n)]
        if missing:
            raise RuntimeError(
                f"Missing required configuration: {', '.join(missing)}. "
                "See docs/SETUP.md for how to obtain and set these."
            )


def load_config() -> Config:
    return Config()
