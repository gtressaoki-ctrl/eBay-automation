"""Create a T-shirt and a sticker product on Printify from a single artwork
file, using one shop (= one "brand") as the destination.

Printify itself does not expose a "create shop" API call for arbitrary
brands - a shop/store connection is created once, by hand, in the Printify
dashboard (Add new store -> pick a sales channel, or "Printify API" for a
manual/API-only store). This script picks up from there: give it the
resulting shop id and an API token and it uploads the artwork, creates both
products against the live Printify catalog, and (optionally) publishes them.

Usage:
    python -m printify.create_brand_products \
        --brand-name "Half Moon Ram" \
        --design assets/designs/aries-ram-lineart.jpg \
        --publish

Required environment variables (see .env.example):
    PRINTIFY_API_TOKEN   Personal access token from Printify account settings.
    PRINTIFY_SHOP_ID     The shop id shown for your store connection.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from .catalog import (
    available_positions,
    pick_blueprint,
    pick_placeholder_positions,
    pick_print_provider,
    select_variants,
)
from .client import PrintifyClient

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DESIGN = REPO_ROOT / "assets" / "designs" / "aries-ram-lineart-transparent.png"

# A "one point" left-chest print: small badge-sized logo sitting where a
# breast-pocket would go, rather than a full front-panel print.
LEFT_CHEST_PLACEMENT = {"position": "front", "x": 0.28, "y": 0.22, "scale": 0.22, "angle": 0}
# A single sleeve print, centered in the (small) sleeve print area.
DEFAULT_SLEEVE_PLACEMENT = {"position": "left_sleeve", "x": 0.5, "y": 0.5, "scale": 0.8, "angle": 0}


def build_print_areas(variant_ids: list[int], placements: list[dict], image_id: str) -> list[dict]:
    return [
        {
            "variant_ids": variant_ids,
            "placeholders": [
                {
                    "position": placement["position"],
                    "images": [
                        {
                            "id": image_id,
                            "x": placement.get("x", 0.5),
                            "y": placement.get("y", 0.5),
                            "scale": placement.get("scale", 1),
                            "angle": placement.get("angle", 0),
                        }
                    ],
                }
                for placement in placements
            ],
        }
    ]


def build_product_payload(
    client: PrintifyClient,
    *,
    keyword: str,
    blueprint_id: int | None,
    print_provider_id: int | None,
    image_id: str,
    title: str,
    description: str,
    tags: list[str],
    price_cents: int,
    max_variants: int | None,
    placements: list[dict] | None = None,
    extra_variant_ids: list[int] | None = None,
) -> dict:
    blueprint = pick_blueprint(client, keyword, blueprint_id)
    provider = pick_print_provider(client, blueprint["id"], print_provider_id)
    variants_response = client.list_variants(blueprint["id"], provider["id"])
    all_variants = variants_response.get("variants", [])
    if not all_variants:
        raise ValueError(f"Blueprint {blueprint['id']} / provider {provider['id']} has no variants.")

    enabled_variants = select_variants(all_variants, max_variants=max_variants)
    enabled_ids = {v["id"] for v in enabled_variants}
    # "Printify Choice" (and possibly other meta-providers) can sell a wider
    # variant set than its own /variants.json catalog listing reports. When
    # updating a product that's already live with such a provider, folding
    # in its current variant ids keeps our "submit every variant" payload
    # (see below) a superset of what Printify already has on file.
    all_variant_ids = sorted(set(v["id"] for v in all_variants) | set(extra_variant_ids or []))

    if placements is None:
        placements = [{"position": p, "x": 0.5, "y": 0.5, "scale": 1, "angle": 0} for p in pick_placeholder_positions(variants_response)]
    else:
        offered = available_positions(variants_response)
        missing = [p["position"] for p in placements if p["position"] not in offered]
        if missing:
            raise ValueError(
                f"Blueprint {blueprint['id']} does not offer placement(s) {missing}. "
                f"Available: {offered}"
            )

    # Printify's create endpoint silently expands a partial variant list to
    # the blueprint's full set (disabling whatever we didn't ask for), but
    # its update endpoint rejects a partial list outright ("Variants do not
    # match selected blueprint and print provider"). Submitting the full
    # set ourselves - enabled only for our chosen variants - works for both
    # and keeps a create followed by an update idempotent.
    payload = {
        "title": title,
        "description": description,
        "blueprint_id": blueprint["id"],
        "print_provider_id": provider["id"],
        "variants": [
            {"id": vid, "price": price_cents, "is_enabled": vid in enabled_ids} for vid in all_variant_ids
        ],
        "print_areas": build_print_areas(all_variant_ids, placements, image_id),
        "tags": tags,
    }

    positions = [p["position"] for p in placements]
    print(
        f"-> '{title}' using blueprint '{blueprint['title']}' (id={blueprint['id']}), "
        f"provider '{provider['title']}' (id={provider['id']}), {len(enabled_ids)}/{len(all_variant_ids)} variants enabled, "
        f"placements={positions}",
        file=sys.stderr,
    )
    return payload


def create_or_update_product(client: PrintifyClient, shop_id: str, existing_product_id: str | None, payload: dict) -> dict:
    if existing_product_id:
        print(f"   updating existing product {existing_product_id}", file=sys.stderr)
        return client.update_product(shop_id, existing_product_id, payload)
    return client.create_product(shop_id, payload)


def main(argv: list[str] | None = None) -> int:
    load_dotenv()

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--brand-name", required=True, help="Brand name used in product titles/descriptions.")
    parser.add_argument("--design", default=str(DEFAULT_DESIGN), help="Path to the artwork file to print.")
    parser.add_argument("--shop-id", default=os.environ.get("PRINTIFY_SHOP_ID"), help="Printify shop id.")
    parser.add_argument("--api-token", default=os.environ.get("PRINTIFY_API_TOKEN"), help="Printify API token.")
    parser.add_argument("--tshirt-keyword", default=os.environ.get("TSHIRT_BLUEPRINT_KEYWORD", "Unisex Heavy Cotton Tee"))
    parser.add_argument("--sticker-keyword", default=os.environ.get("STICKER_BLUEPRINT_KEYWORD", "Kiss-Cut Stickers"))
    parser.add_argument("--tshirt-blueprint-id", type=int, default=_int_env("TSHIRT_BLUEPRINT_ID"))
    parser.add_argument("--sticker-blueprint-id", type=int, default=_int_env("STICKER_BLUEPRINT_ID"))
    parser.add_argument("--tshirt-print-provider-id", type=int, default=_int_env("TSHIRT_PRINT_PROVIDER_ID"))
    parser.add_argument("--sticker-print-provider-id", type=int, default=_int_env("STICKER_PRINT_PROVIDER_ID"))
    parser.add_argument("--tshirt-price-cents", type=int, default=_int_env("TSHIRT_PRICE_CENTS", 2499))
    parser.add_argument("--sticker-price-cents", type=int, default=_int_env("STICKER_PRICE_CENTS", 499))
    parser.add_argument("--tshirt-max-variants", type=int, default=_int_env("TSHIRT_MAX_VARIANTS"))
    parser.add_argument("--sticker-max-variants", type=int, default=_int_env("STICKER_MAX_VARIANTS"))
    parser.add_argument("--tshirt-chest-product-id", default=os.environ.get("TSHIRT_CHEST_PRODUCT_ID"), help="Update this existing left-chest T-shirt product instead of creating a new one.")
    parser.add_argument("--tshirt-sleeve-product-id", default=os.environ.get("TSHIRT_SLEEVE_PRODUCT_ID"), help="Update this existing sleeve T-shirt product instead of creating a new one.")
    parser.add_argument("--sticker-product-id", default=os.environ.get("STICKER_PRODUCT_ID"), help="Update this existing product instead of creating a new one.")
    parser.add_argument("--sleeve-position", default=os.environ.get("TSHIRT_SLEEVE_POSITION", "left_sleeve"), choices=["left_sleeve", "right_sleeve"])
    parser.add_argument("--publish", action="store_true", default=os.environ.get("PRINTIFY_PUBLISH") == "true")
    parser.add_argument("--out", default=str(REPO_ROOT / "printify" / "last_run.json"), help="Where to write a JSON summary of created products.")
    args = parser.parse_args(argv)

    if not args.api_token:
        parser.error("PRINTIFY_API_TOKEN is not set (env var or --api-token).")
    if not args.shop_id:
        parser.error(
            "PRINTIFY_SHOP_ID is not set. Create a store connection in the Printify "
            "dashboard first (Add new store), then copy its shop id from "
            "GET /v1/shops.json or the dashboard URL."
        )
    if not Path(args.design).exists():
        parser.error(f"Design file not found: {args.design}")

    client = PrintifyClient(args.api_token)

    print(f"Uploading design '{args.design}' to Printify...", file=sys.stderr)
    image = client.upload_image(args.design)
    print(f"   uploaded as image id={image['id']}", file=sys.stderr)

    tags = [args.brand_name, "Aries", "Ram", "zodiac"]

    chest_extra_variant_ids = _existing_variant_ids(client, args.shop_id, args.tshirt_chest_product_id)
    tshirt_chest_payload = build_product_payload(
        client,
        keyword=args.tshirt_keyword,
        blueprint_id=args.tshirt_blueprint_id,
        print_provider_id=args.tshirt_print_provider_id,
        image_id=image["id"],
        title=f"{args.brand_name} - Aries Ram Left Chest T-Shirt",
        description=(
            f"{args.brand_name} original Aries ram line-art - a small left-chest "
            "logo print on a soft everyday unisex tee."
        ),
        tags=tags + ["T-Shirt", "Left Chest"],
        price_cents=args.tshirt_price_cents,
        max_variants=args.tshirt_max_variants,
        placements=[LEFT_CHEST_PLACEMENT],
        extra_variant_ids=chest_extra_variant_ids,
    )
    tshirt_chest = create_or_update_product(client, args.shop_id, args.tshirt_chest_product_id, tshirt_chest_payload)

    sleeve_extra_variant_ids = _existing_variant_ids(client, args.shop_id, args.tshirt_sleeve_product_id)
    tshirt_sleeve_payload = build_product_payload(
        client,
        keyword=args.tshirt_keyword,
        blueprint_id=args.tshirt_blueprint_id,
        print_provider_id=args.tshirt_print_provider_id,
        image_id=image["id"],
        title=f"{args.brand_name} - Aries Ram Sleeve T-Shirt",
        description=(
            f"{args.brand_name} original Aries ram line-art - a small sleeve "
            "logo print on a soft everyday unisex tee."
        ),
        tags=tags + ["T-Shirt", "Sleeve"],
        price_cents=args.tshirt_price_cents,
        max_variants=args.tshirt_max_variants,
        placements=[{**DEFAULT_SLEEVE_PLACEMENT, "position": args.sleeve_position}],
        extra_variant_ids=sleeve_extra_variant_ids,
    )
    tshirt_sleeve = create_or_update_product(client, args.shop_id, args.tshirt_sleeve_product_id, tshirt_sleeve_payload)

    sticker_extra_variant_ids = _existing_variant_ids(client, args.shop_id, args.sticker_product_id)
    sticker_payload = build_product_payload(
        client,
        keyword=args.sticker_keyword,
        blueprint_id=args.sticker_blueprint_id,
        print_provider_id=args.sticker_print_provider_id,
        image_id=image["id"],
        title=f"{args.brand_name} - Aries Ram Sticker",
        description=f"{args.brand_name} original Aries ram line-art die-cut sticker.",
        tags=tags + ["Sticker"],
        price_cents=args.sticker_price_cents,
        max_variants=args.sticker_max_variants,
        extra_variant_ids=sticker_extra_variant_ids,
    )
    sticker = create_or_update_product(client, args.shop_id, args.sticker_product_id, sticker_payload)

    results = {
        "image": image,
        "tshirt_left_chest": tshirt_chest,
        "tshirt_sleeve": tshirt_sleeve,
        "sticker": sticker,
        "published": False,
    }

    if args.publish:
        for label, product in (
            ("left-chest t-shirt", tshirt_chest),
            ("sleeve t-shirt", tshirt_sleeve),
            ("sticker", sticker),
        ):
            print(f"Publishing {label} (product id={product['id']})...", file=sys.stderr)
            client.publish_product(args.shop_id, product["id"])
            client.mark_publish_succeeded(
                args.shop_id,
                product["id"],
                external_id=product["id"],
                handle=f"/products/{product['id']}",
            )
        results["published"] = True
    else:
        print(
            "Products created as drafts (not published). Review them in the Printify "
            "dashboard, then re-run with --publish once you're happy with the mockups.",
            file=sys.stderr,
        )

    Path(args.out).write_text(json.dumps(results, indent=2))
    print(f"Summary written to {args.out}", file=sys.stderr)
    return 0


def _int_env(name: str, default: int | None = None) -> int | None:
    value = os.environ.get(name)
    return int(value) if value else default


def _existing_variant_ids(client: PrintifyClient, shop_id: str, product_id: str | None) -> list[int] | None:
    if not product_id:
        return None
    product = client.get_product(shop_id, product_id)
    return [v["id"] for v in product.get("variants", [])]


if __name__ == "__main__":
    raise SystemExit(main())
