#!/usr/bin/env python3
"""One-time Pinterest authorization.

    # 1. Print the consent link, open it, approve, copy the code shown:
    PYTHONPATH=src python scripts/pinterest_authorize.py url
    # 2. Exchange the code for the encrypted token store (the
    #    "Pinterest authorize" workflow does this and commits the result):
    PYTHONPATH=src python scripts/pinterest_authorize.py exchange <code> [--csv-uploaded]
    # Generate a value for the PINTEREST_TOKEN_KEY secret:
    PYTHONPATH=src python scripts/pinterest_authorize.py newkey

--csv-uploaded marks every listing that is live today as already pinned,
for when those Pins were created with the bulk-create CSV.
"""
from __future__ import annotations

import datetime
import sys

from cryptography.fernet import Fernet

from ebay_automation.config import load_config
from ebay_automation.pinterest_client import PinterestClient, authorize_url
from ebay_automation.pipeline_pinterest import mark_existing_as_pinned


def main() -> None:
    command = sys.argv[1] if len(sys.argv) > 1 else "url"
    if command == "newkey":
        print(Fernet.generate_key().decode())
        return
    config = load_config()
    if command == "url":
        config.require("pinterest_app_id")
        print(authorize_url(config))
    elif command == "exchange":
        config.require("pinterest_app_id", "pinterest_app_secret", "pinterest_token_key")
        code = sys.argv[2].strip()
        tokens = PinterestClient(config).exchange_code(code)
        expires = datetime.datetime.fromtimestamp(tokens["refresh_expires_at"], datetime.timezone.utc)
        print(f"Token stored; renews itself on use (current refresh token expires {expires:%Y-%m-%d}).")
        if "--csv-uploaded" in sys.argv:
            print(f"Marked {mark_existing_as_pinned()} live listing(s) as already pinned via CSV.")
    else:
        raise SystemExit(f"Unknown command {command!r}; use url, exchange or newkey.")


if __name__ == "__main__":
    main()
