"""Exchange the authorization code from oauth_consent.py's browser flow for
a refresh_token, and print it so you can save it to .env as
EBAY_REFRESH_TOKEN. The refresh token is what lets every other script in
this repo act on your eBay seller account without logging in again (it's
valid for about 18 months).

Usage:
    python -m ebay.exchange_code "<code from the redirect URL>"
"""
from __future__ import annotations

import argparse
import os
import sys

from dotenv import load_dotenv

from .client import EbayClient


def main(argv: list[str] | None = None) -> int:
    load_dotenv()

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("code", help="The 'code' query-parameter value from the OAuth consent redirect.")
    args = parser.parse_args(argv)

    client = EbayClient(
        client_id=os.environ.get("EBAY_CLIENT_ID", ""),
        client_secret=os.environ.get("EBAY_CLIENT_SECRET", ""),
        ru_name=os.environ.get("EBAY_RU_NAME"),
        sandbox=os.environ.get("EBAY_SANDBOX") == "true",
    )
    result = client.exchange_authorization_code(args.code)
    print("Save this to .env as EBAY_REFRESH_TOKEN:\n", file=sys.stderr)
    print(result["refresh_token"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
