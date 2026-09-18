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

from .catalog import pick_blueprint, pick_placeholder_positions, pick_print_provider
from .client import PrintifyClient

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DESIGN = REPO_ROOT / "assets" / "designs" / "aries-ram-lineart.jpg"


def build_print_areas(variant_ids: list[int], positions: list[str], image_id: str) -> list[dict]:
    return [
        {
            "variant_ids": variant_ids,
            "placeholders": [
                {
                    "position": position,
                    "images": [
                        {"id": image_id, "x": 0.5, "y": 0.5, "scale": 1, "angle": 0}
                    ],
                }
                for position in positions
            ],
        }
    ]


def create_product(
    client: PrintifyClient,
    shop_id: str,
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
) -> dict:
    blueprint = pick_blueprint(client, keyword, blueprint_id)
    provider = pick_print_provider(client, blueprint["id"], print_provider_id)
    variants_response = client.list_variants(blueprint["id"], provider["id"])
    all_variants = variants_response.get("variants", [])
    if not all_variants:
        raise ValueError(f"Blueprint {blueprint['id']} / provider {provider['id']} has no variants.")

    enabled_variants = all_variants[:max_variants] if max_variants else all_variants
    variant_ids = [v["id"] for v in enabled_variants]
    positions = pick_placeholder_positions(variants_response)

    payload = {
        "title": title,
        "description": description,
        "blueprint_id": blueprint["id"],
        "print_provider_id": provider["id"],
        "variants": [
            {"id": vid, "price": price_cents, "is_enabled": True} for vid in variant_ids
        ],
        "print_areas": build_print_areas(variant_ids, positions, image_id),
        "tags": tags,
    }

    print(
        f"-> creating '{title}' using blueprint '{blueprint['title']}' (id={blueprint['id']}), "
        f"provider '{provider['title']}' (id={provider['id']}), {len(variant_ids)} variants",
        file=sys.stderr,
    )
    return client.create_product(shop_id, payload)


def main(argv: list[str] | None = None) -> int:
    load_dotenv()

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--brand-name", required=True, help="Brand name used in product titles/descriptions.")
    parser.add_argument("--design", default=str(DEFAULT_DESIGN), help="Path to the artwork file to print.")
    parser.add_argument("--shop-id", default=os.environ.get("PRINTIFY_SHOP_ID"), help="Printify shop id.")
    parser.add_argument("--api-token", default=os.environ.get("PRINTIFY_API_TOKEN"), help="Printify API token.")
    parser.add_argument("--tshirt-keyword", default=os.environ.get("TSHIRT_BLUEPRINT_KEYWORD", "Unisex Heavy Cotton Tee"))
    parser.add_argument("--sticker-keyword", default=os.environ.get("STICKER_BLUEPRINT_KEYWORD", "Kiss Cut Stickers"))
    parser.add_argument("--tshirt-blueprint-id", type=int, default=_int_env("TSHIRT_BLUEPRINT_ID"))
    parser.add_argument("--sticker-blueprint-id", type=int, default=_int_env("STICKER_BLUEPRINT_ID"))
    parser.add_argument("--tshirt-print-provider-id", type=int, default=_int_env("TSHIRT_PRINT_PROVIDER_ID"))
    parser.add_argument("--sticker-print-provider-id", type=int, default=_int_env("STICKER_PRINT_PROVIDER_ID"))
    parser.add_argument("--tshirt-price-cents", type=int, default=_int_env("TSHIRT_PRICE_CENTS", 2499))
    parser.add_argument("--sticker-price-cents", type=int, default=_int_env("STICKER_PRICE_CENTS", 499))
    parser.add_argument("--tshirt-max-variants", type=int, default=_int_env("TSHIRT_MAX_VARIANTS"))
    parser.add_argument("--sticker-max-variants", type=int, default=_int_env("STICKER_MAX_VARIANTS"))
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

    tshirt = create_product(
        client,
        args.shop_id,
        keyword=args.tshirt_keyword,
        blueprint_id=args.tshirt_blueprint_id,
        print_provider_id=args.tshirt_print_provider_id,
        image_id=image["id"],
        title=f"{args.brand_name} - Aries Ram Unisex T-Shirt",
        description=(
            f"{args.brand_name} original Aries ram line-art print, "
            "on a soft everyday unisex tee."
        ),
        tags=tags + ["T-Shirt"],
        price_cents=args.tshirt_price_cents,
        max_variants=args.tshirt_max_variants,
    )

    sticker = create_product(
        client,
        args.shop_id,
        keyword=args.sticker_keyword,
        blueprint_id=args.sticker_blueprint_id,
        print_provider_id=args.sticker_print_provider_id,
        image_id=image["id"],
        title=f"{args.brand_name} - Aries Ram Sticker",
        description=f"{args.brand_name} original Aries ram line-art die-cut sticker.",
        tags=tags + ["Sticker"],
        price_cents=args.sticker_price_cents,
        max_variants=args.sticker_max_variants,
    )

    results = {"image": image, "tshirt": tshirt, "sticker": sticker, "published": False}

    if args.publish:
        for label, product in (("t-shirt", tshirt), ("sticker", sticker)):
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


if __name__ == "__main__":
    raise SystemExit(main())
