"""Print the URL to open in a browser to grant this app Sell API access on
your eBay seller account. This step needs an actual eBay login + click, so
it can't be automated headlessly - run this, open the printed URL yourself,
log in, and approve.

After approving, eBay redirects to your RuName's configured return URL with
a `?code=...` query parameter (a long, url-encoded string). Copy that whole
code and pass it to exchange_code.py to finish the process.

Usage:
    python -m ebay.oauth_consent
"""
from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

from .client import EbayClient


def main(argv: list[str] | None = None) -> int:
    load_dotenv()

    client = EbayClient(
        client_id=os.environ.get("EBAY_CLIENT_ID", ""),
        client_secret=os.environ.get("EBAY_CLIENT_SECRET", ""),
        ru_name=os.environ.get("EBAY_RU_NAME"),
        sandbox=os.environ.get("EBAY_SANDBOX") == "true",
    )
    print(client.consent_url(), file=sys.stderr)
    print(
        "\nOpen that URL in a browser, log into the eBay seller account, and approve access.\n"
        "eBay will redirect you to a URL containing '?code=...' - copy that code value and run:\n"
        "  python -m ebay.exchange_code \"<code>\"",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
