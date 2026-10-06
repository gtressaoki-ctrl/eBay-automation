"""Pin each newly published listing to our own Pinterest board.

eBay ranks a brand-new seller far down its own search, so listings get
seen in eBay results but almost never clicked. Pinterest is where people
browse gift ideas, and a Pin links straight to the listing — free
exposure that doesn't depend on eBay's ranking.

A few Pins a run rather than all at once: a steady trickle of fresh Pins
is what Pinterest's feed favours, and it keeps us well inside API limits.

Run (GitHub Actions does this daily):
    PYTHONPATH=src python -m ebay_automation.pipeline_pinterest
"""
from __future__ import annotations

from . import ledger, pinterest_content
from .config import Config, load_config
from .pinterest_client import PinterestApiError, PinterestClient


def configured(config: Config) -> bool:
    return bool(config.pinterest_app_id and config.pinterest_app_secret and config.pinterest_token_key)


def pin_new_listings(config: Config, client: PinterestClient) -> list[str]:
    """Pin up to `pinterest_pins_per_run` unpinned listings; returns their SKUs."""
    pending = ledger.load_pending_listings()
    todo = [
        sku
        for sku, entry in pending.items()
        if pinterest_content.pinnable(entry) and not entry.get("pinterest_pin_id")
    ][: config.pinterest_pins_per_run]
    if not todo:
        return []

    board_id = client.get_or_create_board(
        config.pinterest_board_name, "Original funny and sarcastic coffee mugs — office gifts for coffee lovers."
    )
    pinned = []
    for sku in todo:
        entry = pending[sku]
        try:
            pin_id = client.create_pin(
                board_id,
                title=pinterest_content.title(entry["headline"]),
                description=pinterest_content.description(entry["headline"]),
                link=entry["listing_url"],
                image_url=pinterest_content.image_url(entry),
            )
        except PinterestApiError as exc:
            # One bad listing (e.g. an image Pinterest can't fetch) must not
            # stop the rest; it is retried on the next run.
            print(f"Pin failed for {sku}: {exc}")
            continue
        ledger.update_listing_status(sku, entry["status"], pinterest_pin_id=pin_id)
        pinned.append(sku)
        print(f"Pinned {sku} -> https://www.pinterest.com/pin/{pin_id}/")
    return pinned


def mark_existing_as_pinned(marker: str = "csv") -> int:
    """Listings already pinned some other way (the bulk-create CSV) are
    marked so the publisher doesn't pin them a second time."""
    pending = ledger.load_pending_listings()
    count = 0
    for sku, entry in pending.items():
        if pinterest_content.pinnable(entry) and not entry.get("pinterest_pin_id"):
            entry["pinterest_pin_id"] = marker
            count += 1
    ledger.save_pending_listings(pending)
    return count


def run() -> None:
    config = load_config()
    if not configured(config):
        print("Pinterest not configured (PINTEREST_APP_ID / _APP_SECRET / _TOKEN_KEY); skipping.")
        return
    pinned = pin_new_listings(config, PinterestClient(config))
    print(f"Pinned {len(pinned)} listing(s).")


if __name__ == "__main__":
    run()
