"""Daily entrypoint: research niches -> generate designs -> create Printify
products -> create DRAFT eBay offers (never auto-published) -> open one
GitHub Issue per candidate for human approval.

Run via: python -m ebay_automation.pipeline_research
Triggered on a schedule by .github/workflows/research_and_list.yml.
"""
from __future__ import annotations

import base64
import logging
import tempfile
import uuid
from pathlib import Path

from . import design_gen, ledger, research
from .config import load_config
from .ebay_client import EbayClient
from .github_client import GithubClient
from .printify_client import PrintifyClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

DEFAULT_PRODUCTION_COST_CENTS = 1300  # conservative fallback if Printify omits variant cost


def _slugify(text: str) -> str:
    return "-".join(text.lower().split())[:40]


def build_listing_for_niche(config, printify: PrintifyClient, ebay: EbayClient, niche: research.NicheScore) -> dict | None:
    config.require("printify_blueprint_id", "printify_print_provider_id", "printify_variant_ids")

    with tempfile.TemporaryDirectory() as tmp:
        image_path, phrase = design_gen.generate_design_for_niche(niche.keyword, Path(tmp) / "design.png")
        image_b64 = base64.b64encode(image_path.read_bytes()).decode("ascii")
        image_id = printify.upload_image_base64(f"{_slugify(niche.keyword)}.png", image_b64)

        product = printify.create_product(
            title=f"{phrase} - Unisex Graphic Tee",
            description=(
                f"{phrase} graphic tee. Original design, printed on demand and shipped "
                "directly from our print partner. Please allow standard production time "
                "before shipment."
            ),
            blueprint_id=config.printify_blueprint_id,
            print_provider_id=config.printify_print_provider_id,
            variant_ids=config.printify_variant_ids,
        )

    product_id = product["id"]
    variants = product.get("variants", [])
    base_cost_cents = max((v.get("cost", 0) for v in variants), default=DEFAULT_PRODUCTION_COST_CENTS)
    if base_cost_cents <= 0:
        base_cost_cents = DEFAULT_PRODUCTION_COST_CENTS
    price_cents = round(base_cost_cents * config.default_markup_multiplier)
    images = [img["src"] for img in product.get("images", [])][:12] or []

    sku = f"POD-{_slugify(niche.keyword)}-{uuid.uuid4().hex[:8]}"

    ebay.create_or_replace_inventory_item(
        sku,
        {
            "product": {
                "title": (f"{phrase} - Graphic T-Shirt")[:80],
                "description": (
                    f"<p>{phrase} original graphic t-shirt.</p>"
                    "<p>Printed to order and shipped by our production partner. "
                    "Please allow a few extra days for production before shipment.</p>"
                ),
                "imageUrls": images,
            },
            "condition": "NEW",
            "availability": {"shipToLocationAvailability": {"quantity": 999}},
        },
    )

    offer = {
        "sku": sku,
        "marketplaceId": config.ebay_marketplace_id,
        "format": "FIXED_PRICE",
        "availableQuantity": 999,
        "categoryId": config.ebay_category_id,
        "listingDescription": f"{phrase} original graphic t-shirt, printed to order.",
        "pricingSummary": {"price": {"value": f"{price_cents / 100:.2f}", "currency": "USD"}},
        "merchantLocationKey": config.ebay_merchant_location_key,
        "listingPolicies": {
            "fulfillmentPolicyId": config.ebay_fulfillment_policy_id,
            "paymentPolicyId": config.ebay_payment_policy_id,
            "returnPolicyId": config.ebay_return_policy_id,
        },
    }
    offer_id = ebay.create_offer(offer)

    return {
        "sku": sku,
        "keyword": niche.keyword,
        "phrase": phrase,
        "printify_product_id": product_id,
        "ebay_offer_id": offer_id,
        "price_cents": price_cents,
        "cost_cents": base_cost_cents,
        "image_url": images[0] if images else None,
        "status": "pending_approval",
        # v1 limitation: one fixed size/color per listing (the first
        # configured variant), not a full eBay variation listing.
        "printify_variant_id": config.printify_variant_ids[0],
    }


def _issue_body(entry: dict) -> str:
    profit_estimate = (entry["price_cents"] - entry["cost_cents"]) / 100
    image_md = f"\n\n![mockup]({entry['image_url']})" if entry.get("image_url") else ""
    return (
        f"**SKU**: `{entry['sku']}`\n"
        f"**ニッチ**: {entry['keyword']}\n"
        f"**販売価格**: ${entry['price_cents'] / 100:.2f} / **原価(参考)**: ${entry['cost_cents'] / 100:.2f} "
        f"/ **粗利(参考)**: ${profit_estimate:.2f}\n"
        f"**eBay offerId**: `{entry['ebay_offer_id']}` (まだ公開されていません)\n"
        f"{image_md}\n\n"
        "---\n"
        "このコメントで承認/却下してください:\n"
        "- `/approve` — eBayに公開します\n"
        "- `/reject` — Printify商品を削除し、この候補を破棄します\n"
    )


def run() -> None:
    config = load_config()
    ledger_data = ledger.load_ledger()
    if ledger_data.get("paused"):
        log.warning("Pipeline is paused (%s); skipping research run.", ledger_data.get("pause_reason"))
        return

    quota = ledger.adjust_daily_quota()
    log.info("Today's listing quota: %d", quota)

    printify = PrintifyClient(config)
    ebay = EbayClient(config)
    github = GithubClient(config)

    candidates = research.pick_candidates(config, quota)
    log.info("Selected %d candidate niches: %s", len(candidates), [c.keyword for c in candidates])

    for niche in candidates:
        try:
            entry = build_listing_for_niche(config, printify, ebay, niche)
        except Exception:
            log.exception("Failed to build listing for niche %r; skipping.", niche.keyword)
            continue

        if config.dry_run:
            log.info("[dry-run] would open approval issue for %s", entry["sku"])
            ledger.add_pending_listing(entry["sku"], entry)
            continue

        if config.auto_publish:
            # Fully autonomous mode: skip the human approval issue and
            # publish immediately. Only enable AUTO_PUBLISH once you trust
            # the pipeline's output quality and pricing.
            listing_id = ebay.publish_offer(entry["ebay_offer_id"])
            entry["status"] = "published"
            entry["ebay_listing_id"] = listing_id
            ledger.add_pending_listing(entry["sku"], entry)
            ledger.record_listing_created()
            ledger.record_listing_published()
            log.info("[auto-publish] Published %s as listing %s", entry["sku"], listing_id)
            continue

        issue = github.create_issue(
            title=f"[承認待ち] {entry['phrase']} ({entry['sku']})",
            body=_issue_body(entry),
            labels=["pending-approval", "ebay-automation"],
        )
        entry["issue_number"] = issue["number"]
        ledger.add_pending_listing(entry["sku"], entry)
        ledger.record_listing_created()
        log.info("Opened approval issue #%s for %s", issue["number"], entry["sku"])


if __name__ == "__main__":
    run()
