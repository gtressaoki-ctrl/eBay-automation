"""The listing review day: once a month, open one issue that says, per live
export listing, how often eBay showed it, how often it was opened, and
whether it sold, over the last 30 days.

A title is only judged once eBay's crawler has had time to come back to
it: 14 days after the last title change (export_seo.py). Before that the
listing is left alone; after that, one that is shown but not opened needs
a better title or first photo, one that is opened but not bought needs a
better price, shipping or returns, and one that is not even shown needs
other search words.

Run via: python -m ebay_automation.export_review  (Japan Export Review workflow)
"""
from __future__ import annotations

import datetime
import logging

from . import export_markets, export_state
from .config import Config, load_config
from .ebay_client import EbayApiError, EbayClient
from .github_client import GithubClient

log = logging.getLogger(__name__)

SETTLE_DAYS = 14


def _days_since(stamp: str | None, now: datetime.datetime) -> int | None:
    if not stamp:
        return None
    return (now - datetime.datetime.fromisoformat(stamp)).days


def verdict(entry: dict, stats: dict[str, int], now: datetime.datetime) -> str:
    changed = _days_since(entry.get("title_changed_at") or entry.get("published_at"), now)
    if changed is not None and changed < SETTLE_DAYS:
        return f"様子見（タイトル変更から{changed}日。{SETTLE_DAYS}日までは触らない）"
    shown = stats.get("LISTING_IMPRESSION_TOTAL", 0)
    opened = stats.get("LISTING_VIEWS_TOTAL", 0)
    sold = stats.get("TRANSACTION", 0)
    if sold:
        return "売れている: そのまま"
    if shown < 50:
        return "**見直し**: ほとんど表示されていない → タイトルの検索語（型番・仕様）を見直す"
    if opened == 0 or opened / shown < 0.01:
        return "**見直し**: 表示されるが開かれない → タイトルの並び・1枚目の写真・価格を見直す"
    return "**見直し**: 開かれるが売れない → 価格・送料・返品条件・説明を見直す"


def report(config: Config, ebay_for: dict[str, EbayClient], now: datetime.datetime) -> str:
    live = [e for e in export_state.load_listings().values() if e.get("status") == "published"]
    traffic: dict[str, dict[str, int]] = {}
    for key, ebay in ebay_for.items():
        ids = [e["ebay_listing_id"] for e in live if export_markets.of(e).key == key and e.get("ebay_listing_id")]
        if not ids:
            continue
        try:
            traffic.update(ebay.get_traffic_report(ids, 30))
        except EbayApiError as exc:
            log.warning("Traffic report for %s failed: %s", key, exc.body[:200])
    lines = [
        f"## 出品ページの見直し（{now:%Y-%m-%d}）",
        "",
        "過去30日。タイトルを変えてから14日は判断しない（クローラーが戻ってくるまで待つ）。",
        "",
        "| サイト | 商品 | 価格 | 表示 / 閲覧 / 販売 | 判定 |",
        "|---|---|---|---|---|",
    ]
    for e in sorted(live, key=lambda e: export_markets.of(e).key):
        stats = traffic.get(e.get("ebay_listing_id", ""), {})
        price = export_markets.money(*export_markets.price_of(e))
        numbers = (
            f"{stats.get('LISTING_IMPRESSION_TOTAL', 0)} / {stats.get('LISTING_VIEWS_TOTAL', 0)} / "
            f"{stats.get('TRANSACTION', 0)}"
        )
        title = f"[{e['title'][:50]}]({e['listing_url']})" if e.get("listing_url") else e["title"][:50]
        lines.append(
            f"| {export_markets.of(e).key} | {title} | {price} | {numbers} | {verdict(e, stats, now)} |"
        )
    if not live:
        lines.append("| - | 出品中の輸出品なし | | | |")
    lines += [
        "",
        "見直したら、変えた箇所と日付をこのIssueにコメントして閉じる。変えたものは次の見直し日まで触らない。",
    ]
    return "\n".join(lines) + "\n"


def run(config: Config | None = None) -> None:
    config = config or load_config()
    config.require("ebay_app_id", "ebay_cert_id", "ebay_refresh_token")
    clients = {m.key: EbayClient(export_markets.market_config(config, m)) for m in export_markets.enabled(config)}
    now = datetime.datetime.now(datetime.timezone.utc)
    body = report(config, clients, now)
    print(body)
    if not config.dry_run:
        issue = GithubClient(config).create_issue(
            title=f"[見直し] 輸出出品ページ {now:%Y-%m}", body=body, labels=["export-review", "ebay-automation"]
        )
        log.info("Opened review issue #%s", issue["number"])


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run()
