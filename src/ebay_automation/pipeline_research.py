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
from .ebay_client import EbayApiError, EbayClient
from .github_client import GithubClient
from .printify_client import PrintifyClient
from .themes import Design, Theme

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# What Printify actually bills to produce one 11oz mug (blueprint 478,
# provider 99, variant 65216). Only an estimate for ranking — the real
# figure comes back with the product and is re-checked before listing —
# but it has to be close, because a padded estimate rejects niches that
# would in fact clear the profit floor.
#
# A one-off probe product put this at $5.03, but the first live research
# run built real products in two different niches and both landed on
# $6.13 exactly (backed out from realized unit_profit_cents at a known
# market price in both cases — not a rounding coincidence). Trusting two
# live builds over one probe.
DEFAULT_PRODUCTION_COST_CENTS = 613


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


def _sku_for(theme: Theme, design: Design) -> str:
    """eBay rejects SKUs over 50 characters. A 6-hex uniqueness suffix is
    non-negotiable (it's what stops two runs colliding on the same slug),
    so the theme/design portion is truncated to make room for it instead
    — this is an internal identifier, not shown to buyers, so a truncated
    slug costs nothing. Three long design slugs hit this in the first live
    run (e.g. "should-have-been-an-email" pushed the SKU to 54 chars) and
    every one of them failed outright with eBay's inventory API.
    """
    suffix = uuid.uuid4().hex[:6]
    base = f"POD-{theme.slug}-{design.slug}"
    return f"{base[: 50 - len(suffix) - 1]}-{suffix}"


def used_design_keys() -> set[str]:
    return {
        entry["design_key"]
        for entry in ledger.load_pending_listings().values()
        if entry.get("design_key")
    }


def select_active_themes(all_themes: tuple[Theme, ...], config: Config) -> tuple[Theme, ...]:
    """Which themes today's run researches: everything, or one committed brand.

    Running four unrelated themes forever never becomes a brand a buyer
    recognizes and comes back to — it stays four random side-hustles. Once
    a theme has enough published, profitable listings to have proven
    itself, research locks onto it exclusively and stops spinning up
    unrelated ones; until then every theme is explored to find which one
    earns that commitment.

    Locking is a floor, not a ceiling: it only fires once real profit
    exists, so a theme that merely got published first without selling
    cannot lock in ahead of one that is actually working.
    """
    stats = ledger.theme_stats()
    qualified = [
        theme
        for theme in all_themes
        if stats.get(theme.slug, {}).get("published", 0) >= config.brand_lock_min_published
        and stats.get(theme.slug, {}).get("profit_cents", 0) > 0
    ]
    if not qualified:
        return all_themes

    winner = max(qualified, key=lambda t: stats[t.slug]["profit_cents"])
    log.info(
        "Brand locked onto %r (%d published, $%.2f profit so far); other themes paused.",
        winner.slug,
        stats[winner.slug]["published"],
        stats[winner.slug]["profit_cents"] / 100,
    )
    return (winner,)


_TITLE_LIMIT = 80
# Bump when listing_title()/listing_aspects() change, so refresh_live_listings
# rewrites listings that went live under the older wording.
CONTENT_VERSION = 2


def _sentence_word(word: str) -> str:
    # str.title() turns "DON'T" into "Don'T"; eBay discourages all-caps titles.
    return word[:1].upper() + word[1:].lower()


def listing_title(theme: Theme, headline: str) -> str:
    """Search terms first, then as much of the design phrase as fits in
    eBay's 80 characters, cut on a word boundary."""
    prefix, _, suffix = theme.title_template.partition("{design}")
    room = _TITLE_LIMIT - len(prefix) - len(suffix)
    design = ""
    for word in headline.split():
        candidate = f"{design} {_sentence_word(word)}".strip()
        if len(candidate) > room:
            break
        design = candidate
    return f"{prefix}{design}{suffix}".strip(" -")


def listing_aspects(config: Config, theme: Theme, design: Design, colour: str) -> dict[str, list[str]]:
    """Item specifics. Buyers narrow search results with these filters, and
    a listing missing a value drops out of every search filtered on it."""
    return {
        "Brand": [config.brand_tagline or "Unbranded"],
        "Type": ["Coffee Mug"],
        "Material": ["Ceramic"],
        "Capacity": ["11 oz"],
        "Color": [colour or "White"],
        "Theme": [theme.item_theme],
        "Features": ["Dishwasher Safe", "Microwave Safe"],
        "Occasion": ["Birthday", "Christmas", "Father's Day", "Mother's Day"],
        "Department": ["Unisex Adult"],
        # Category 20675 (Mugs) requires this to publish (errorId 25002), and
        # a print-on-demand mug has no model number; the design slug is
        # unique per listing, which is what the aspect is for.
        "Model": [design.slug[:65]],
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

    # Everything past this point can fail independently (an invalid SKU, a
    # transient 500 from eBay) after the Printify product already exists.
    # Left alone that orphans a product with no listing and no record in
    # pending_listings.json — invisible clutter that just accumulates. Any
    # failure here deletes the product it just created before re-raising,
    # same cleanup pipeline_approve does on an explicit /reject.
    try:
        variants = product.get("variants", [])
        production_cost = max((v.get("cost", 0) for v in variants), default=0) or DEFAULT_PRODUCTION_COST_CENTS
        landed_cost = production_cost + config.shipping_cost_cents

        price_cents = research.target_price_cents(demand)
        unit_profit = research.unit_profit_cents(price_cents, landed_cost)
        images = [img["src"] for img in product.get("images", [])][:12]

        sku = _sku_for(theme, design)
        title = listing_title(theme, headline)
        # Blank until a shop name is chosen (that choice belongs to the
        # seller); once set, the same line goes on every listing so the
        # shop reads as one brand rather than as unrelated one-off products.
        tagline_html = f"<p><em>{config.brand_tagline}</em></p>" if config.brand_tagline else ""

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
                        f"{tagline_html}"
                    ),
                    "imageUrls": images,
                    "aspects": listing_aspects(config, theme, design, product_colour),
                },
                "condition": "NEW",
                "availability": {"shipToLocationAvailability": {"quantity": config.listing_quantity}},
            },
        )

        offer_id = ebay.create_offer(
            {
                "sku": sku,
                "marketplaceId": config.ebay_marketplace_id,
                "format": "FIXED_PRICE",
                "availableQuantity": config.listing_quantity,
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
    except Exception:
        try:
            printify.delete_product(product_id)
        except Exception:
            log.exception("Failed to clean up orphaned Printify product %s", product_id)
        raise

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
        "content_version": CONTENT_VERSION,
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


# updateOffer replaces the whole offer; getOffer also returns read-only
# fields (offerId, sku, marketplaceId, format, status, listing) it rejects.
_UPDATABLE_OFFER_FIELDS = {
    "availableQuantity",
    "categoryId",
    "listingDescription",
    "listingDuration",
    "listingPolicies",
    "merchantLocationKey",
    "pricingSummary",
    "quantityLimitPerBuyer",
    "storeCategoryNames",
    "tax",
}


def listing_url(listing_id: str) -> str:
    return f"https://www.ebay.com/itm/{listing_id}"


_MIN_AD_BID_PERCENTAGE = 2.0  # eBay's floor for cost-per-sale bids


def profitable_bid_percentage(config: Config, entry: dict) -> float | None:
    """The configured ad bid, capped so an ad-driven sale still clears the
    profit floor. None when even eBay's minimum bid would not.

    The ad fee is a percentage of the sale price, charged only when an ad
    click sells — but on a mug that nets ~$0.68, the old flat 10% bid
    (~$1.50) turned every ad-driven sale into a loss."""
    price = entry.get("price_cents")
    profit = entry.get("unit_profit_cents")
    if not price or profit is None:
        return None
    headroom = (profit - config.min_unit_profit_cents) / price * 100
    bid = min(config.promoted_listings_bid_percentage, int(headroom * 10) / 10)
    return bid if bid >= _MIN_AD_BID_PERCENTAGE else None


def promote_if_enabled(config: Config, ebay: EbayClient, sku: str, entry: dict) -> str | None:
    """Best-effort Promoted Listings enrollment for an already-live listing.

    Returns a note for the caller to surface, or None. A failure here never
    undoes the publish that already happened.
    """
    if not config.promoted_listings_enabled:
        return None
    bid = profitable_bid_percentage(config, entry)
    if bid is None:
        log.info("Not promoting %s: no ad bid leaves it profitable.", sku)
        return "利益が残る広告率が取れないため、広告は出していません。"
    try:
        campaign_id = ebay.get_or_create_cost_per_sale_campaign(config.promoted_listings_campaign_name, bid)
        ebay.promote_listing(campaign_id, sku, bid)
        log.info("Added %s to Promoted Listings campaign %s at %.1f%%", sku, campaign_id, bid)
        return None
    except Exception:
        log.exception("Failed to add %s to Promoted Listings; listing stays live without ads.", sku)
        return "広告掲載に失敗しました（出品自体は公開済みです）。"


def prepare_draft_for_publish(config: Config, ebay: EbayClient, sku: str, entry: dict) -> None:
    """Bring a draft created by an older version of this pipeline up to what
    publishOffer now requires: the Model aspect category 20675 demands, and
    a quantity that fits the account's selling limit (old drafts asked for
    50 units, which alone exceeds a new seller's whole monthly allowance)."""
    item = ebay.get_inventory_item(sku)
    product = item.get("product", {})
    aspects = product.setdefault("aspects", {})
    if not aspects.get("Model"):
        design_slug = (entry.get("design_key") or sku).rsplit("/", 1)[-1]
        aspects["Model"] = [design_slug[:65]]
    ebay.create_or_replace_inventory_item(
        sku,
        {
            "product": product,
            "condition": item.get("condition", "NEW"),
            "availability": {"shipToLocationAvailability": {"quantity": config.listing_quantity}},
        },
    )
    offer = ebay.get_offer(entry["ebay_offer_id"])
    offer = {k: v for k, v in offer.items() if k in _UPDATABLE_OFFER_FIELDS}
    offer["availableQuantity"] = config.listing_quantity
    ebay.update_offer(entry["ebay_offer_id"], offer)


def publish_backlog(config: Config, ebay: EbayClient, github: GithubClient) -> bool:
    """Publish drafts still waiting on an approval issue from before
    AUTO_PUBLISH was switched on, oldest first. With AUTO_PUBLISH on, the
    seller has delegated the publish decision, and these already cleared
    the same demand/margin checks as a fresh listing — leaving them parked
    behind an approval nobody is going to give just wastes the listings.

    Returns False once eBay's monthly selling limit is hit, so the caller
    stops rather than building new products that cannot be listed.
    """
    pending = ledger.load_pending_listings()
    for sku, entry in pending.items():
        if entry.get("status") != "pending_approval":
            continue
        try:
            prepare_draft_for_publish(config, ebay, sku, entry)
            listing_id = ebay.publish_offer(entry["ebay_offer_id"])
        except EbayApiError as exc:
            if exc.is_selling_limit:
                return False
            log.exception("Failed to publish backlog draft %s; leaving it pending.", sku)
            continue
        except Exception:
            log.exception("Failed to publish backlog draft %s; leaving it pending.", sku)
            continue

        url = listing_url(listing_id)
        ledger.update_listing_status(sku, "published", ebay_listing_id=listing_id, listing_url=url)
        ledger.record_listing_published()
        log.info("[auto-publish] Published backlog draft %s at %s", sku, url)
        ad_note = promote_if_enabled(config, ebay, sku, entry)

        if entry.get("issue_number"):
            comment = f"AUTO_PUBLISHにより自動公開しました: {url}"
            if ad_note:
                comment += f"\n\n⚠️ {ad_note}"
            try:
                github.comment_issue(entry["issue_number"], comment)
                github.close_issue(entry["issue_number"], "completed")
            except Exception:
                log.exception("Published %s but failed to update issue #%s", sku, entry["issue_number"])
    return True


def record_traffic(ebay: EbayClient) -> None:
    """Snapshot last-30-day impressions/views/sales for every live listing
    into state/traffic.json. Best-effort: a missing analytics scope must
    not stop the listing run."""
    live = {
        entry["ebay_listing_id"]: entry.get("headline", sku)
        for sku, entry in ledger.load_pending_listings().items()
        if entry.get("status") == "published" and entry.get("ebay_listing_id")
    }
    if not live:
        return
    try:
        report = ebay.get_traffic_report(list(live))
    except Exception:
        log.exception("Traffic report unavailable; skipping.")
        return
    snapshot = {}
    for listing_id, headline in live.items():
        m = report.get(listing_id, {})
        snapshot[listing_id] = {
            "headline": headline,
            "impressions": m.get("LISTING_IMPRESSION_TOTAL", 0),
            "views": m.get("LISTING_VIEWS_TOTAL", 0),
            "sales": m.get("TRANSACTION", 0),
        }
        log.info("Traffic %s %-45.45s %s", listing_id, headline, snapshot[listing_id])
    ledger.save_traffic(snapshot)


def refresh_live_listings(config: Config, ebay: EbayClient, colour: str) -> None:
    """Rewrite the title and item specifics of listings published under an
    older CONTENT_VERSION. Updating a published offer's inventory item
    revises the live listing in place — no relist, no fee."""
    by_slug = {theme.slug: theme for theme in themes.THEMES}
    for sku, entry in ledger.load_pending_listings().items():
        if entry.get("status") != "published" or entry.get("content_version") == CONTENT_VERSION:
            continue
        theme = by_slug.get(entry.get("theme", ""))
        design_slug = (entry.get("design_key") or "").rsplit("/", 1)[-1]
        design = next((d for d in theme.designs if d.slug == design_slug), None) if theme else None
        if design is None:
            continue
        try:
            item = ebay.get_inventory_item(sku)
            product = item.get("product", {})
            product["title"] = listing_title(theme, themes.headline(design))
            product["aspects"] = {**product.get("aspects", {}), **listing_aspects(config, theme, design, colour)}
            ebay.create_or_replace_inventory_item(
                sku,
                {
                    "product": product,
                    "condition": item.get("condition", "NEW"),
                    "availability": item.get(
                        "availability", {"shipToLocationAvailability": {"quantity": config.listing_quantity}}
                    ),
                },
            )
        except Exception:
            log.exception("Failed to refresh listing content for %s", sku)
            continue
        ledger.update_listing_status(sku, "published", content_version=CONTENT_VERSION)
        log.info("Refreshed title/item specifics for %s: %s", sku, product["title"])


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

    record_traffic(ebay)

    if config.auto_publish and not config.dry_run:
        if not publish_backlog(config, ebay, github):
            log.warning("eBay selling limit reached; not building new listings this run.")
            return

    product_colour, print_area = product_profile(config, printify)
    if not config.dry_run:
        refresh_live_listings(config, ebay, product_colour)
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

    active_themes = select_active_themes(themes.THEMES, config)

    # Cost floor for ranking. The exact production cost is only known once
    # Printify has the product, so rank on a conservative estimate and
    # re-check the real figure before the listing is drafted.
    estimated_cost = DEFAULT_PRODUCTION_COST_CENTS + config.shipping_cost_cents
    report = research.rank_niches(
        [theme.search_keyword for theme in active_themes],
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

    by_keyword = {theme.search_keyword: theme for theme in active_themes}
    used = used_design_keys()
    created = 0

    for demand in report.ranked:
        if created >= quota:
            break
        if demand.units_per_listing_per_month < config.min_units_per_listing_per_month:
            log.info(
                "Skipping %r: %.2f units/listing/month is below the %.2f demand floor.",
                demand.keyword,
                demand.units_per_listing_per_month,
                config.min_units_per_listing_per_month,
            )
            continue
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
                # build_listing already created the Printify product and
                # the eBay inventory item/offer before this margin check
                # ran — same cleanup as an explicit /reject, so a rejected
                # niche doesn't just pile up as clutter in both accounts.
                try:
                    printify.delete_product(entry["printify_product_id"])
                except Exception:
                    log.exception("Failed to clean up Printify product for dropped %s", entry["sku"])
                try:
                    ebay.delete_inventory_item(entry["sku"])
                except Exception:
                    log.exception("Failed to clean up eBay inventory item for dropped %s", entry["sku"])
                continue

            if config.dry_run:
                log.info("[dry-run] would open approval issue for %s", entry["sku"])
                ledger.add_pending_listing(entry["sku"], entry)
                created += 1
                continue

            if config.auto_publish:
                try:
                    entry["ebay_listing_id"] = ebay.publish_offer(entry["ebay_offer_id"])
                except Exception as exc:
                    # publishOffer is the one eBay call here with no upstream
                    # dry-run/margin check ahead of it to catch a category
                    # rule violation, so it is the one most likely to surprise
                    # us live (e.g. errorId 25002, a required item specific
                    # this category didn't demand until publish time). Left
                    # uncaught this took the whole run down mid-quota,
                    # orphaning the Printify product/eBay inventory item and
                    # silently skipping every design still queued behind it.
                    log.exception(
                        "Failed to publish %s; cleaning up and skipping.", entry["sku"]
                    )
                    try:
                        printify.delete_product(entry["printify_product_id"])
                    except Exception:
                        log.exception("Failed to clean up Printify product for %s", entry["sku"])
                    try:
                        ebay.delete_inventory_item(entry["sku"])
                    except Exception:
                        log.exception("Failed to clean up eBay inventory item for %s", entry["sku"])
                    if isinstance(exc, EbayApiError) and exc.is_selling_limit:
                        log.warning("eBay selling limit reached; stopping this run.")
                        log.info("Created %d draft listings.", created)
                        return
                    continue

                entry["status"] = "published"
                entry["listing_url"] = listing_url(entry["ebay_listing_id"])
                ledger.add_pending_listing(entry["sku"], entry)
                ledger.record_listing_created()
                ledger.record_listing_published()
                log.info("[auto-publish] Published %s at %s", entry["sku"], entry["listing_url"])
                promote_if_enabled(config, ebay, entry["sku"], entry)

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
