"""Publish a single existing Printify product (leaving any other draft
products untouched).

Usage:
    python -m printify.publish_product <product_id> [<product_id> ...]
"""
from __future__ import annotations

import argparse
import os
import sys

from dotenv import load_dotenv

from .client import PrintifyClient


def main(argv: list[str] | None = None) -> int:
    load_dotenv()

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("product_ids", nargs="+", help="Printify product id(s) to publish.")
    parser.add_argument("--shop-id", default=os.environ.get("PRINTIFY_SHOP_ID"), help="Printify shop id.")
    parser.add_argument("--api-token", default=os.environ.get("PRINTIFY_API_TOKEN"), help="Printify API token.")
    args = parser.parse_args(argv)

    if not args.api_token:
        parser.error("PRINTIFY_API_TOKEN is not set (env var or --api-token).")
    if not args.shop_id:
        parser.error("PRINTIFY_SHOP_ID is not set (env var or --shop-id).")

    client = PrintifyClient(args.api_token)

    for product_id in args.product_ids:
        product = client.get_product(args.shop_id, product_id)
        print(f"Publishing '{product['title']}' (id={product_id})...", file=sys.stderr)
        client.publish_product(args.shop_id, product_id)
        client.mark_publish_succeeded(
            args.shop_id, product_id, external_id=product_id, handle=f"/products/{product_id}"
        )
        print("   done.", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
