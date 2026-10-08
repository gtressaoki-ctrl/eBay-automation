"""Issue commands for export listings and orders.

On an `export-approval` issue (opened by export_listing.py):
  /approve  re-checks the source, then publishes the draft
  /reject   deletes the draft

On an `export-order` issue (opened by export_sync.py):
  /shipped <carrier> <tracking> [purchase price in yen]
            marks the eBay order shipped with that tracking number

Only the repository owner, collaborators and members are obeyed — the
same gate as pipeline_approve.py.

Run via: python -m ebay_automation.export_commands  (issue_comment event)
"""
from __future__ import annotations

import datetime
import json
import logging
import os
import re

from . import export_research, export_state
from .config import Config, load_config
from .ebay_client import EbayApiError, EbayClient
from .export_sync import source_check
from .github_client import GithubClient
from .pipeline_research import listing_url

log = logging.getLogger(__name__)

_ALLOWED_ASSOCIATIONS = {"OWNER", "COLLABORATOR", "MEMBER"}
_APPROVE_RE = re.compile(r"^\s*/approve\b", re.I)
_REJECT_RE = re.compile(r"^\s*/reject\b", re.I)
_SHIPPED_RE = re.compile(r"^\s*/shipped\s+(\S+)\s+(\S+)(?:\s+[¥￥]?([\d,]+))?", re.I)

# eBay carrier codes for the carriers a Japan-based seller is likely to
# use; anything else is passed through as typed.
CARRIERS = {
    "japanpost": "JapanPost",
    "jp": "JapanPost",
    "jppost": "JapanPost",
    "ems": "JapanPost",
    "yuubin": "JapanPost",
    "fedex": "FedEx",
    "dhl": "DHL",
    "ups": "UPS",
    "yamato": "Yamato",
    "sagawa": "Sagawa",
}


def carrier_code(name: str) -> str:
    return CARRIERS.get(name.strip().lower(), name.strip())


def _find(records: dict, issue_number: int) -> tuple[str | None, dict | None]:
    for key, record in records.items():
        if record.get("issue_number") == issue_number:
            return key, record
    return None, None


def handle_approval(config: Config, ebay: EbayClient, github: GithubClient, issue_number: int, approve: bool) -> None:
    sku, entry = _find(export_state.load_listings(), issue_number)
    if entry is None:
        log.warning("No export listing for issue #%s", issue_number)
        return
    if entry.get("status") != "pending_approval":
        github.comment_issue(issue_number, f"この下書きは処理済みです（status: {entry.get('status')}）。")
        return

    if not approve:
        try:
            ebay.delete_inventory_item(sku)
        except EbayApiError:
            log.exception("Deleting %s failed (continuing)", sku)
        entry["status"] = "rejected"
        export_state.save_listing(sku, entry)
        github.comment_issue(issue_number, "却下しました。下書きを削除しました。")
        github.close_issue(issue_number, "not_planned")
        return

    offer, profit, blocked = source_check(entry, config)
    if blocked:
        github.comment_issue(
            issue_number,
            f"今は公開しません: {blocked}。仕入れ先が戻ったら、もう一度 `/approve` してください。",
        )
        return
    try:
        listing_id = ebay.publish_offer(entry["ebay_offer_id"])
    except EbayApiError as exc:
        note = "今月の販売上限（出品数・金額）に達しています。" if exc.is_selling_limit else exc.body[:500]
        github.comment_issue(issue_number, f"公開に失敗しました: {note}")
        return
    entry.update(
        status="published",
        quantity=1,
        ebay_listing_id=listing_id,
        listing_url=listing_url(listing_id),
        expected_profit_jpy=profit,
        source_price_jpy=offer.price_jpy,
        source_url=offer.url,
        published_at=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
    )
    export_state.save_listing(sku, entry)
    github.comment_issue(
        issue_number,
        f"公開しました: {entry['listing_url']}\n\n今の仕入れ値 ¥{offer.price_jpy:,}、想定利益 ¥{profit:,}/個。"
        "仕入れ先の在庫は2時間ごとに確認します。",
    )
    github.close_issue(issue_number, "completed")


def handle_shipped(config: Config, ebay: EbayClient, github: GithubClient, issue_number: int, match: re.Match) -> None:
    order_id, record = _find(export_state.load_orders(), issue_number)
    if record is None:
        log.warning("No export order for issue #%s", issue_number)
        return
    if record.get("status") == "shipped":
        github.comment_issue(issue_number, f"発送済みとして登録済みです（追跡番号 {record.get('tracking_number')}）。")
        return
    carrier, tracking = carrier_code(match.group(1)), match.group(2)
    cost = int(match.group(3).replace(",", "")) if match.group(3) else None
    try:
        ebay.create_shipping_fulfillment(
            order_id=order_id,
            line_items=[{"lineItemId": i["line_item_id"], "quantity": i["quantity"]} for i in record["items"]],
            tracking_number=tracking,
            shipping_carrier_code=carrier,
        )
    except EbayApiError as exc:
        github.comment_issue(
            issue_number,
            f"eBayへの発送登録に失敗しました: {exc.body[:500]}\n\n運送会社コードが違う場合は "
            "`japanpost` / `fedex` / `dhl` / `ups` のどれかで再度コメントしてください。",
        )
        return

    record.update(
        status="shipped",
        carrier=carrier,
        tracking_number=tracking,
        shipped_at=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
    )
    note = ""
    if cost is not None:
        record["purchase_cost_jpy"] = cost
        sale = sum(i["price_usd"] * i["quantity"] for i in record["items"])
        size = record["items"][0].get("size", config.export_listing_size)
        computed = export_research.profit_jpy(sale, "USD", cost, True, size, config)
        if computed:
            record["profit_jpy"] = computed[0]
            note = f"\n\n実際の仕入れ値 ¥{cost:,} での利益（概算・国際送料は設定値）: **¥{computed[0]:,}**"
    export_state.save_order(order_id, record)
    github.comment_issue(issue_number, f"eBayに発送済みとして登録しました（{carrier} {tracking}）。{note}")
    github.close_issue(issue_number, "completed")


def run() -> None:
    event = json.loads(open(os.environ["GITHUB_EVENT_PATH"], encoding="utf-8").read())
    if "comment" not in event or "issue" not in event:
        return
    body = event["comment"]["body"] or ""
    issue = event["issue"]
    labels = {label["name"] for label in issue.get("labels", [])}
    approve, reject, shipped = _APPROVE_RE.match(body), _REJECT_RE.match(body), _SHIPPED_RE.match(body)
    is_approval_cmd = "export-approval" in labels and (approve or reject)
    is_order_cmd = "export-order" in labels and shipped
    if not (is_approval_cmd or is_order_cmd):
        return

    config = load_config()
    github = GithubClient(config)
    if event["comment"].get("author_association", "NONE") not in _ALLOWED_ASSOCIATIONS:
        github.comment_issue(issue["number"], "このコマンドはリポジトリのオーナー/コラボレーターのみ実行できます。")
        return
    ebay = EbayClient(config)
    if is_approval_cmd:
        handle_approval(config, ebay, github, issue["number"], bool(approve))
    else:
        handle_shipped(config, ebay, github, issue["number"], shipped)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run()
