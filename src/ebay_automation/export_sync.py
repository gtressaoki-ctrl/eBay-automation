"""Recurring entrypoint for live export listings: source stock and new orders.

1. Stock/price guard. For every published export listing, re-check the
   cheapest new, in-stock offer for its JAN on Yahoo!ショッピング. If none
   is left, or it no longer clears EXPORT_MIN_PROFIT_JPY at our price (or
   fails the pack-size checks), the listing goes to quantity 0 — it stays
   up but cannot be bought, so a sale we could not source never happens
   (a cancelled order is a seller defect on eBay). When the source comes
   back, quantity returns to 1. A sale also leaves quantity at 0; the next
   run puts it back once the source is confirmed.

2. New orders. Each new order for a JX- SKU opens a GitHub issue with
   what to buy and where. The buyer's name and address never go into the
   issue or the committed state: this repository is public. The seller
   reads them in Seller Hub.

The seller then buys, receives the item at their own address, inspects,
packs and ships it, and comments `/shipped <carrier> <tracking>` on the
issue (export_commands.py).

Run via: python -m ebay_automation.export_sync
"""
from __future__ import annotations

import datetime
import logging

import requests

from . import export_research, export_state, yahoo_shopping
from .config import Config, load_config
from .ebay_client import EbayApiError, EbayClient
from .export_research import ProductOpportunity
from .github_client import GithubClient

log = logging.getLogger(__name__)


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def source_check(entry: dict, config: Config) -> tuple[yahoo_shopping.DomesticOffer | None, int | None, str]:
    """Current offer, profit at our price, and why we can't sell ("" if we can)."""
    offer = yahoo_shopping.cheapest_new_offer(entry["jan"], config)
    if offer is None:
        return None, None, "仕入れ先の在庫なし"
    computed = export_research.profit_jpy(
        entry["price_usd"], "USD", offer.price_jpy, offer.free_shipping, config.export_listing_size, config
    )
    if computed is None:
        return offer, None, "為替レート取得失敗"
    profit = computed[0]
    probe = ProductOpportunity(
        title=entry["title"], ebay_url="", jan=entry["jan"], sale_price=entry["price_usd"],
        currency="USD", units_per_month=0,
    )
    mismatch = export_research._mismatch_reason(probe, offer, config)
    if mismatch:
        return offer, profit, mismatch
    if profit < config.export_min_profit_jpy:
        return offer, profit, f"利益 ¥{profit:,} が下限 ¥{config.export_min_profit_jpy:,} 未満"
    return offer, profit, ""


def sync_stock(config: Config, ebay: EbayClient) -> None:
    for sku, entry in export_state.load_listings().items():
        if entry.get("status") != "published":
            continue
        try:
            offer, profit, blocked = source_check(entry, config)
        except requests.HTTPError:
            log.warning("Source check failed for %s; leaving it as is.", sku)
            continue
        want = 0 if blocked else 1
        if offer:
            entry.update(source_price_jpy=offer.price_jpy, source_url=offer.url, source_name=offer.name)
        entry["expected_profit_jpy"] = profit
        entry["checked_at"] = _now()
        if entry.get("quantity") != want:
            try:
                ebay.set_available_quantity(sku, entry["ebay_offer_id"], want)
            except EbayApiError:
                log.exception("Could not set %s to quantity %d", sku, want)
                continue
            entry["quantity"] = want
            log.info("%s -> quantity %d %s", sku, want, f"({blocked})" if blocked else "")
        entry["paused_reason"] = blocked
        export_state.save_listing(sku, entry)


def order_issue_body(order: dict, items: list[dict], config: Config) -> str:
    country = (
        order.get("fulfillmentStartInstructions", [{}])[0]
        .get("shippingStep", {}).get("shipTo", {}).get("contactAddress", {}).get("countryCode", "?")
    )
    lines = [
        f"eBay注文 `{order['orderId']}`（発送先の国: **{country}**）",
        "",
        "| 商品 | 数量 | 販売価格 | 今の最安仕入れ | 想定利益/個 |",
        "|---|---|---|---|---|",
    ]
    for it in items:
        source = f"[¥{it['source_price_jpy']:,}]({it['source_url']})" if it.get("source_url") else "要確認"
        profit = f"¥{it['expected_profit_jpy']:,}" if it.get("expected_profit_jpy") is not None else "-"
        lines.append(f"| {it['title'][:50]} | {it['quantity']} | ${it['price_usd']:.2f} | {source} | {profit} |")
    lines += [
        "",
        "### やること",
        "1. 上の仕入れ先（またはそれより安い店）で購入する。**届け先は自分の住所**にする（購入者へ直送しない＝eBay規約）",
        f"2. 届いたら検品・梱包し、発送する（ハンドリング期限: 注文から {config.export_handling_days}営業日）",
        f"3. 購入者の氏名・住所は [Seller Hub の注文ページ](https://www.ebay.com/sh/ord/details?orderid={order['orderId']}) で確認",
        "4. 発送したら、このIssueに次の形でコメントする:",
        "   `/shipped japanpost EJ123456789JP 1980`（運送会社・追跡番号・実際の仕入れ値（円、省略可））",
        "",
        "仕入れられない場合は、早めに Seller Hub から購入者に連絡してキャンセルしてください（評価への影響を最小にするため）。",
    ]
    return "\n".join(lines) + "\n"


def sync_orders(config: Config, ebay: EbayClient, github: GithubClient | None) -> int:
    listings = export_state.load_listings()
    known = export_state.load_orders()
    opened = 0
    for order in ebay.get_orders():
        order_id = order["orderId"]
        if order_id in known:
            continue
        items = []
        for li in order.get("lineItems", []):
            sku = li.get("sku")
            if not export_state.is_export_sku(sku) or sku not in listings:
                continue
            entry = listings[sku]
            unit = float((li.get("lineItemCost") or {}).get("value") or entry["price_usd"]) / max(1, int(li["quantity"]))
            items.append(
                {
                    "sku": sku,
                    "line_item_id": li["lineItemId"],
                    "quantity": int(li["quantity"]),
                    "title": entry["title"],
                    "price_usd": round(unit, 2),
                    "source_price_jpy": entry.get("source_price_jpy"),
                    "source_url": entry.get("source_url"),
                    "expected_profit_jpy": entry.get("expected_profit_jpy"),
                }
            )
            # eBay took the listing to 0 with the sale; record that so the
            # stock guard restores it only after re-checking the source.
            entry["quantity"] = 0
            export_state.save_listing(sku, entry)
        if not items:
            continue
        record = {"status": "to_buy", "items": items, "created_at": _now()}
        if github is not None:
            issue = github.create_issue(
                title=f"[仕入れ] {items[0]['title'][:50]} ×{sum(i['quantity'] for i in items)}（注文 {order_id}）",
                body=order_issue_body(order, items, config),
                labels=["export-order", "ebay-automation"],
            )
            record["issue_number"] = issue["number"]
        export_state.save_order(order_id, record)
        opened += 1
        log.info("Opened purchase issue for export order %s", order_id)
    return opened


def run(config: Config | None = None) -> None:
    config = config or load_config()
    config.require("ebay_app_id", "ebay_cert_id", "ebay_refresh_token", "yahoo_app_id")
    ebay = EbayClient(config)
    github = None if config.dry_run else GithubClient(config)
    # Orders first: a sale that just happened must be recorded before the
    # stock guard decides what quantity the listing should have.
    sync_orders(config, ebay, github)
    sync_stock(config, ebay)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run()
