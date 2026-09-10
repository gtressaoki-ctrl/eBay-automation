"""Handles the human approval step: parses a GitHub issue_comment event
(`/approve` or `/reject`) on a pending-approval issue and either publishes
the corresponding eBay offer or tears down the draft.

Triggered by .github/workflows/approve_listing.yml on `issue_comment`.
Only comments from the repo owner/collaborators/members are honored —
this is the one gate standing between a draft and real money changing
hands on eBay, so it must not be triggerable by arbitrary commenters.
"""
from __future__ import annotations

import json
import logging
import os
import re

from . import ledger
from .config import load_config
from .ebay_client import EbayClient
from .github_client import GithubClient
from .printify_client import PrintifyClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

_ALLOWED_ASSOCIATIONS = {"OWNER", "COLLABORATOR", "MEMBER"}
_APPROVE_RE = re.compile(r"^\s*/approve\b", re.IGNORECASE)
_REJECT_RE = re.compile(r"^\s*/reject\b", re.IGNORECASE)


def _load_event() -> dict:
    event_path = os.environ["GITHUB_EVENT_PATH"]
    return json.loads(open(event_path, encoding="utf-8").read())


def _find_sku_by_issue(pending: dict, issue_number: int) -> str | None:
    for sku, entry in pending.items():
        if entry.get("issue_number") == issue_number:
            return sku
    return None


def _listing_url(config, listing_id: str) -> str:
    domain = "www.ebay.com" if config.ebay_marketplace_id == "EBAY_US" else "www.ebay.com"
    return f"https://{domain}/itm/{listing_id}"


def run() -> None:
    event = _load_event()
    if "comment" not in event or "issue" not in event:
        log.info("Not an issue_comment event; nothing to do.")
        return

    comment_body = event["comment"]["body"] or ""
    association = event["comment"].get("author_association", "NONE")
    issue = event["issue"]
    issue_number = issue["number"]
    labels = {label["name"] for label in issue.get("labels", [])}

    if "pending-approval" not in labels:
        log.info("Issue #%s is not a pending-approval issue; ignoring.", issue_number)
        return

    is_approve = bool(_APPROVE_RE.match(comment_body))
    is_reject = bool(_REJECT_RE.match(comment_body))
    if not (is_approve or is_reject):
        log.info("Comment on #%s is not /approve or /reject; ignoring.", issue_number)
        return

    config = load_config()
    github = GithubClient(config)

    if association not in _ALLOWED_ASSOCIATIONS:
        log.warning("Comment on #%s from unauthorized association %s; ignoring.", issue_number, association)
        github.comment_issue(
            issue_number,
            "このコマンドはリポジトリのオーナー/コラボレーターのみ実行できます。無視されました。",
        )
        return

    pending = ledger.load_pending_listings()
    sku = _find_sku_by_issue(pending, issue_number)
    if sku is None:
        log.warning("No pending listing found for issue #%s", issue_number)
        return

    entry = pending[sku]
    if entry.get("status") != "pending_approval":
        github.comment_issue(issue_number, f"このリスティングは既に処理済みです (status: {entry.get('status')})。")
        return

    if is_approve:
        ebay = EbayClient(config)
        listing_id = ebay.publish_offer(entry["ebay_offer_id"])
        url = _listing_url(config, listing_id)
        ledger.update_listing_status(sku, "published", ebay_listing_id=listing_id, listing_url=url)
        ledger.record_listing_published()
        github.comment_issue(issue_number, f"承認されました。eBayに公開しました: {url}")
        github.close_issue(issue_number, "completed")
        log.info("Published SKU %s as listing %s", sku, listing_id)
    else:
        printify = PrintifyClient(config)
        ebay = EbayClient(config)
        try:
            printify.delete_product(entry["printify_product_id"])
        except Exception:
            log.exception("Failed to delete Printify product for %s (continuing)", sku)
        try:
            ebay.delete_inventory_item(sku)
        except Exception:
            log.exception("Failed to delete eBay inventory item for %s (continuing)", sku)
        ledger.update_listing_status(sku, "rejected")
        github.comment_issue(issue_number, "却下されました。関連リソースを削除しました。")
        github.close_issue(issue_number, "not_planned")
        log.info("Rejected and cleaned up SKU %s", sku)


if __name__ == "__main__":
    run()
