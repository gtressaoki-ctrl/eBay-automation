"""Daily entrypoint: measure demand -> pick a design -> draft an eBay listing.

Order of operations matters here. Demand is measured first, against live
sold-quantity data, and the price comes from what comparable listings
actually sell for. A design is only produced for a niche that clears the
profit floor at that price — the first version of this pipeline worked the
other way round, inventing a design and then marking its cost up by a
fixed multiple, which is how listings ended up priced at $33 in niches
where nothing above $10 had sold in years.

Run via: python -m ebay_automation.pipeline_research
"""
from __future__ import annotations

import base64
import logging
import tempfile
import uuid
from pathlib import Path

from . import design_gen, ledger, research, themes
from .config import Config, load_config
from .ebay_client import EbayClient
from .github_client import GithubClient
from .printify_client import PrintifyClient
from .themes import Design, Theme

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# What Printify actually bills to produce one 11oz mug (blueprint 478,
# provider 99, variant 65216), measured by creating a probe product and
# reading back its variant cost. Only an estimate for ranking — the real
# figure comes back with the product and is re-checked before listing —
# but it has to be close, because a padded estimate rejects niches that
# would in fact clear the profit floor. At $6.00 it put the sarcastic-mug
# niche at $0.81 per unit when the true figure was $1.78.
DEFAULT_PRODUCTION_COST_CENTS = 503


def _slugify(text: str) -> str:
    return "-".join(text.lower().split())[:40]


def product_profile(config: Config, printify: PrintifyClient) -> tuple[str, tuple[int, int]]:
    """The colour we print onto and the print area, read from the catalogue.

    Both drive the artwork: ink has to contrast with the product, and the
    canvas has to match the print area's aspect or Printify scales a
    mostly-empty sheet down and the design prints small.
    """
    catalogue = printify.get_blueprint_variants(
        config.printify_blueprint_id, config.printify_print_provider_id
    )
    target_id = config.printify_variant_ids[0]
    for variant in catalogue.get("variants", []):
        if variant.get("id") != target_id:
            continue
        colour = (variant.get("options", {}) or {}).get("color") or variant.get("title", "")
        for placeholder in variant.get("placeholders", []):
            if placeholder.get("position") == "front":
                return colour, (placeholder["width"], placeholder["height"])
    raise RuntimeError(
        f"Variant {target_id} not found for blueprint {config.printify_blueprint_id}; "
        "check PRINTIFY_VARIANT_IDS against scripts/list_printify_catalog.py"
    )


def used_design_keys() -> set[str]:
    return {
        entry["design_key"]
        for entry in ledger.load_pending_listings().values()
        if entry.get("design_key")
    }


def build_listing(
    config: Config,
    printify: PrintifyClient,
    ebay: EbayClient,
    theme: Theme,
    design: Design,
    demand: research.NicheDemand,
    product_colour: str,
    print_area: tuple[int, int],
) -> dict:
    headline = themes.headline(design)

    with tempfile.TemporaryDirectory() as tmp:
        artwork = design_gen.render_design(
            design, Path(tmp) / f"{design.slug}.png", product_colour, print_area
        )
        encoded = base64.b64encode(artwork.read_bytes()).decode("ascii")
        image_id = printify.upload_image_base64(f"{theme.slug}-{design.slug}.png", encoded)

        product = printify.create_product(
            title=theme.title_template.format(design=headline),
            description=(
                f"{headline}. Printed to order on a ceramic mug and shipped directly "
                "by our print partner. Dishwasher and microwave safe. Please allow a "
                "few days for production before dispatch."
            ),
            image_id=image_id,
            blueprint_id=config.printify_blueprint_id,
            print_provider_id=config.printify_print_provider_id,
            variant_ids=config.printify_variant_ids,
        )

    product_id = product["id"]
    variants = product.get("variants", [])
    production_cost = max((v.get("cost", 0) for v in variants), default=0) or DEFAULT_PRODUCTION_COST_CENTS
    landed_cost = production_cost + config.shipping_cost_cents

    price_cents = research.target_price_cents(demand)
    unit_profit = research.unit_profit_cents(price_cents, landed_cost)
    images = [img["src"] for img in product.get("images", [])][:12]

    sku = f"POD-{theme.slug}-{design.slug}-{uuid.uuid4().hex[:6]}"
    title = theme.title_template.format(design=headline)[:80]

    ebay.create_or_replace_inventory_item(
        sku,
        {
            "product": {
                "title": title,
                "description": (
                    f"<p><strong>{headline}</strong></p>"
                    "<p>Ceramic mug, 11oz. Printed to order and shipped by our production "
                    "partner. Dishwasher and microwave safe.</p>"
                    "<p>Please allow a few days for production before dispatch.</p>"
                ),
                "imageUrls": images,
                "aspects": {"Brand": ["Unbranded"], "Material": ["Ceramic"], "Capacity": ["11 oz"]},
            },
            "condition": "NEW",
            "availability": {"shipToLocationAvailability": {"quantity": 50}},
        },
    )

    offer_id = ebay.create_offer(
        {
            "sku": sku,
            "marketplaceId": config.ebay_marketplace_id,
            "format": "FIXED_PRICE",
            "availableQuantity": 50,
            "categoryId": config.ebay_category_id,
            "listingDescription": f"{headline} - ceramic mug, printed to order.",
            "pricingSummary": {"price": {"value": f"{price_cents / 100:.2f}", "currency": "USD"}},
            "merchantLocationKey": config.ebay_merchant_location_key,
            "listingPolicies": {
                "fulfillmentPolicyId": config.ebay_fulfillment_policy_id,
                "paymentPolicyId": config.ebay_payment_policy_id,
                "returnPolicyId": config.ebay_return_policy_id,
            },
        }
    )

    return {
        "sku": sku,
        "design_key": f"{theme.slug}/{design.slug}",
        "theme": theme.slug,
        "headline": headline,
        "keyword": demand.keyword,
        "printify_product_id": product_id,
        "printify_variant_id": config.printify_variant_ids[0],
        "ebay_offer_id": offer_id,
        "price_cents": price_cents,
        "cost_cents": landed_cost,
        "unit_profit_cents": unit_profit,
        "image_url": images[0] if images else None,
        "demand": {
            "active_listings": demand.active_listings,
            "sell_through_pct": round(demand.sell_through_rate * 100),
            "units_per_listing_per_month": demand.units_per_listing_per_month,
            "expected_monthly_profit_cents": demand.expected_monthly_profit_cents,
        },
        "status": "pending_approval",
    }


def _issue_body(entry: dict) -> str:
    demand = entry["demand"]
    image = f"\n\n![mockup]({entry['image_url']})" if entry.get("image_url") else ""
    return (
        f"**{entry['headline']}**\n\n"
        f"| | |\n|---|---|\n"
        f"| SKU | `{entry['sku']}` |\n"
        f"| 販売価格 | ${entry['price_cents'] / 100:.2f}(この価格帯で実際に売れている) |\n"
        f"| 原価(製造+送料) | ${entry['cost_cents'] / 100:.2f} |\n"
        f"| 1個あたり利益 | **${entry['unit_profit_cents'] / 100:.2f}** |\n"
        f"| 調査キーワード | {entry['keyword']} |\n"
        f"| 競合出品数 | {demand['active_listings']:,} |\n"
        f"| 1個以上売れた割合 | {demand['sell_through_pct']}% |\n"
        f"| 月間販売数/出品 | {demand['units_per_listing_per_month']} |\n"
        f"| 想定月間利益/出品 | ${demand['expected_monthly_profit_cents'] / 100:.2f} |\n"
        f"| eBay offerId | `{entry['ebay_offer_id']}`(未公開) |"
        f"{image}\n\n"
        "---\n"
        "- `/approve` — eBayに公開\n"
        "- `/reject` — 破棄(Printify商品も削除)\n"
    )


def run() -> None:
    config = load_config()
    if ledger.load_ledger().get("paused"):
        log.warning("Pipeline is paused; skipping research run.")
        return

    quota = ledger.adjust_daily_quota()
    log.info("Today's listing quota: %d", quota)

    printify = PrintifyClient(config)
    ebay = EbayClient(config)
    github = GithubClient(config)

    product_colour, print_area = product_profile(config, printify)
    # Printed in full because repository variables silently override the
    # defaults here: a stale value from a previous product shows up as a
    # mismatch on this line rather than as a batch of wrong listings.
    log.info(
        "Product: blueprint %s / provider %s / variant %s, %r, print area %dx%d, "
        "eBay category %s",
        config.printify_blueprint_id,
        config.printify_print_provider_id,
        config.printify_variant_ids[0],
        product_colour,
        *print_area,
        config.ebay_category_id,
    )

    # Cost floor for ranking. The exact production cost is only known once
    # Printify has the product, so rank on a conservative estimate and
    # re-check the real figure before the listing is drafted.
    estimated_cost = DEFAULT_PRODUCTION_COST_CENTS + config.shipping_cost_cents
    report = research.rank_niches(
        [theme.search_keyword for theme in themes.THEMES],
        config,
        product_cost_cents=estimated_cost,
        min_unit_profit_cents=config.min_unit_profit_cents,
    )

    for rejected in report.rejected:
        # The demand figures go out with the rejection: a niche that sells
        # well and still fails the floor is a costing problem worth acting
        # on, while one that fails on both counts is simply not a market.
        log.warning(
            "Niche %r rejected: unit profit $%.2f at market price $%.2f is below the "
            "$%.2f floor (%d active, %.0f%% sell-through, %.2f units/listing/month).",
            rejected.keyword,
            rejected.unit_profit_cents / 100,
            (research.target_price_cents(rejected) or 0) / 100,
            config.min_unit_profit_cents / 100,
            rejected.active_listings,
            rejected.sell_through_rate * 100,
            rejected.units_per_listing_per_month,
        )
    if not report.ranked:
        log.error("No niche cleared the profit floor; nothing listed.")
        return

    by_keyword = {theme.search_keyword: theme for theme in themes.THEMES}
    used = used_design_keys()
    created = 0

    for demand in report.ranked:
        if created >= quota:
            break
        theme = by_keyword[demand.keyword]
        log.info(
            "%r: %d active, %.0f%% sell-through, %.2f units/listing/month, market price $%.2f",
            demand.keyword,
            demand.active_listings,
            demand.sell_through_rate * 100,
            demand.units_per_listing_per_month,
            (research.target_price_cents(demand) or 0) / 100,
        )

        while created < quota:
            design = themes.pick_unused_design(theme, used)
            if design is None:
                log.info("All designs in theme %r are already listed.", theme.slug)
                break
            used.add(f"{theme.slug}/{design.slug}")

            try:
                entry = build_listing(
                    config, printify, ebay, theme, design, demand, product_colour, print_area
                )
            except Exception:
                log.exception("Failed to build listing for %s/%s; skipping.", theme.slug, design.slug)
                continue

            if entry["unit_profit_cents"] < config.min_unit_profit_cents:
                log.warning(
                    "Dropping %s: real landed cost leaves only $%.2f per unit.",
                    entry["sku"],
                    entry["unit_profit_cents"] / 100,
                )
                continue

            if config.dry_run:
                log.info("[dry-run] would open approval issue for %s", entry["sku"])
                ledger.add_pending_listing(entry["sku"], entry)
                created += 1
                continue

            if config.auto_publish:
                entry["ebay_listing_id"] = ebay.publish_offer(entry["ebay_offer_id"])
                entry["status"] = "published"
                ledger.add_pending_listing(entry["sku"], entry)
                ledger.record_listing_created()
                ledger.record_listing_published()
                log.info("[auto-publish] Published %s", entry["sku"])
                created += 1
                continue

            issue = github.create_issue(
                title=f"[承認待ち] {entry['headline']} ({entry['sku']})",
                body=_issue_body(entry),
                labels=["pending-approval", "ebay-automation"],
            )
            entry["issue_number"] = issue["number"]
            ledger.add_pending_listing(entry["sku"], entry)
            ledger.record_listing_created()
            created += 1
            log.info("Opened approval issue #%s for %s", issue["number"], entry["sku"])

    log.info("Created %d draft listings.", created)


if __name__ == "__main__":
    run()
