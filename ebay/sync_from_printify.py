"""Create eBay multiple-variation listings from an existing Printify
product (one eBay listing per Printify product, one eBay variation per
enabled Printify variant).

This assumes the one-time eBay account setup is already done: a developer
keyset + refresh token (oauth_consent.py / exchange_code.py), and a
merchant location + fulfillment/payment/return policies (setup_account.py,
or created by hand in Seller Hub). See the README's eBay section.

Usage:
    python -m ebay.sync_from_printify <printify_product_id> \
        --sku-prefix EQX-CHEST --category-query "T-Shirt" --publish
"""
from __future__ import annotations

import argparse
import os
import sys

from dotenv import load_dotenv

from ebay.client import EbayClient
from printify.client import PrintifyClient


def build_description_html(brand_name: str, printify_description: str) -> str:
    return (
        f"<h2>{brand_name}</h2><p>{printify_description}</p>"
        "<p>Printed to order and shipped directly from our print partner.</p>"
    )


def image_urls_for_variant(images: list[dict], variant_id: int, default_url: str | None) -> list[str]:
    for image in images:
        if variant_id in (image.get("variant_ids") or []):
            return [image["src"]]
    return [default_url] if default_url else []


def sync_product(
    ebay: EbayClient,
    printify: PrintifyClient,
    *,
    shop_id: str,
    product_id: str,
    sku_prefix: str,
    category_query: str,
    category_id: str | None,
    marketplace_id: str,
    merchant_location_key: str,
    fulfillment_policy_id: str,
    payment_policy_id: str,
    return_policy_id: str,
    quantity: int,
    brand_name: str,
    publish: bool,
) -> dict:
    product = printify.get_product(shop_id, product_id)
    blueprint_id = product["blueprint_id"]
    print_provider_id = product["print_provider_id"]
    catalog_variants = {
        v["id"]: v for v in printify.list_variants(blueprint_id, print_provider_id).get("variants", [])
    }

    enabled = [v for v in product["variants"] if v.get("is_enabled")]
    if not enabled:
        raise ValueError(f"Product {product_id} has no enabled variants to list.")

    images = product.get("images", [])
    default_image = next((img["src"] for img in images if img.get("is_default")), images[0]["src"] if images else None)

    description_html = build_description_html(brand_name, product.get("description", ""))

    if category_id is None:
        tree_id = ebay.get_default_category_tree_id(marketplace_id)
        suggestions = ebay.get_category_suggestions(tree_id, category_query)
        if not suggestions:
            raise ValueError(f"No eBay category suggestions for '{category_query}'.")
        category_id = suggestions[0]["category"]["categoryId"]
        print(f"   auto-picked eBay category {category_id} ({suggestions[0]['category']['categoryName']}) for '{category_query}'", file=sys.stderr)

    aspect_names: set[str] = set()
    skus: list[tuple[str, dict, dict]] = []  # (sku, printify_variant, catalog_variant)
    for variant in enabled:
        catalog_variant = catalog_variants.get(variant["id"])
        if not catalog_variant:
            print(f"   skipping variant {variant['id']} (not in current catalog listing)", file=sys.stderr)
            continue
        sku = f"{sku_prefix}-{variant['id']}"
        skus.append((sku, variant, catalog_variant))
        aspect_names.update(catalog_variant.get("options", {}).keys())

    if not skus:
        raise ValueError(f"Product {product_id}: no enabled variant matched the current catalog listing.")

    for sku, variant, catalog_variant in skus:
        aspects = {name.capitalize(): [value] for name, value in catalog_variant.get("options", {}).items()}
        payload = {
            "condition": "NEW",
            "product": {
                "title": product["title"][:80],
                "description": description_html,
                "aspects": aspects,
                "imageUrls": image_urls_for_variant(images, variant["id"], default_image),
                "brand": brand_name,
            },
            "availability": {"shipToLocationAvailability": {"quantity": quantity}},
        }
        ebay.create_or_replace_inventory_item(sku, payload)

    group_key = f"{sku_prefix}-GROUP"
    group_payload = {
        "title": product["title"][:80],
        "description": description_html,
        "imageUrls": [default_image] if default_image else [],
        "variantSKUs": [sku for sku, _, _ in skus],
        "variesBy": {
            "specifications": [
                {
                    "name": name.capitalize(),
                    "values": sorted({cv["options"][name] for _, _, cv in skus if name in cv.get("options", {})}),
                }
                for name in sorted(aspect_names)
            ]
        },
    }
    ebay.create_or_replace_inventory_item_group(group_key, group_payload)

    offer_ids = []
    for sku, variant, _ in skus:
        price_dollars = variant["price"] / 100
        offer_payload = {
            "sku": sku,
            "marketplaceId": marketplace_id,
            "format": "FIXED_PRICE",
            "availableQuantity": quantity,
            "categoryId": category_id,
            "listingDescription": description_html,
            "pricingSummary": {"price": {"value": f"{price_dollars:.2f}", "currency": "USD"}},
            "listingPolicies": {
                "fulfillmentPolicyId": fulfillment_policy_id,
                "paymentPolicyId": payment_policy_id,
                "returnPolicyId": return_policy_id,
            },
            "merchantLocationKey": merchant_location_key,
        }
        existing = ebay.get_offers_for_sku(sku)
        if existing:
            offer_id = existing[0]["offerId"]
            ebay.update_offer(offer_id, offer_payload)
        else:
            offer_id = ebay.create_offer(offer_payload)["offerId"]
        offer_ids.append(offer_id)
        print(f"   offer ready for {sku} (offer id={offer_id})", file=sys.stderr)

    result = {"group_key": group_key, "category_id": category_id, "offer_ids": offer_ids, "published": False}

    if publish:
        publish_result = ebay.publish_offer_by_inventory_item_group(group_key, marketplace_id)
        result["published"] = True
        result["listing_id"] = publish_result.get("listingId")
        print(f"   published as eBay listing id={result['listing_id']}", file=sys.stderr)
    else:
        print("   offers created but not published (pass --publish to go live).", file=sys.stderr)

    return result


def main(argv: list[str] | None = None) -> int:
    load_dotenv()

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("printify_product_id")
    parser.add_argument("--sku-prefix", required=True, help="Prefix for eBay SKUs / inventory item group key, e.g. EQX-CHEST.")
    parser.add_argument("--category-query", default="T-Shirt", help="Keyword used to auto-pick an eBay category (ignored if --category-id is set).")
    parser.add_argument("--category-id", default=os.environ.get("EBAY_CATEGORY_ID"))
    parser.add_argument("--quantity", type=int, default=int(os.environ.get("EBAY_AVAILABLE_QUANTITY", "999")))
    parser.add_argument("--publish", action="store_true", default=os.environ.get("EBAY_PUBLISH") == "true")
    parser.add_argument("--brand-name", default=os.environ.get("BRAND_NAME", "EQUINOX"))
    args = parser.parse_args(argv)

    required_env = [
        "PRINTIFY_API_TOKEN",
        "PRINTIFY_SHOP_ID",
        "EBAY_CLIENT_ID",
        "EBAY_CLIENT_SECRET",
        "EBAY_REFRESH_TOKEN",
        "EBAY_MERCHANT_LOCATION_KEY",
        "EBAY_FULFILLMENT_POLICY_ID",
        "EBAY_PAYMENT_POLICY_ID",
        "EBAY_RETURN_POLICY_ID",
    ]
    missing = [name for name in required_env if not os.environ.get(name)]
    if missing:
        parser.error(f"Missing required .env values: {', '.join(missing)}")

    printify = PrintifyClient(os.environ["PRINTIFY_API_TOKEN"])
    ebay = EbayClient(
        client_id=os.environ["EBAY_CLIENT_ID"],
        client_secret=os.environ["EBAY_CLIENT_SECRET"],
        ru_name=os.environ.get("EBAY_RU_NAME"),
        refresh_token=os.environ["EBAY_REFRESH_TOKEN"],
        sandbox=os.environ.get("EBAY_SANDBOX") == "true",
    )

    result = sync_product(
        ebay,
        printify,
        shop_id=os.environ["PRINTIFY_SHOP_ID"],
        product_id=args.printify_product_id,
        sku_prefix=args.sku_prefix,
        category_query=args.category_query,
        category_id=args.category_id,
        marketplace_id=os.environ.get("EBAY_MARKETPLACE_ID", "EBAY_US"),
        merchant_location_key=os.environ["EBAY_MERCHANT_LOCATION_KEY"],
        fulfillment_policy_id=os.environ["EBAY_FULFILLMENT_POLICY_ID"],
        payment_policy_id=os.environ["EBAY_PAYMENT_POLICY_ID"],
        return_policy_id=os.environ["EBAY_RETURN_POLICY_ID"],
        quantity=args.quantity,
        brand_name=args.brand_name,
        publish=args.publish,
    )
    print(result, file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
