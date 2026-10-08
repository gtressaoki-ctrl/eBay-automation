"""`/photos` on an export-photos issue: list a product with the seller's own photos.

For products with no eBay catalog photo, export_listing.py asks the seller
to buy one unit and photograph it. The comment carrying `/photos` and the
attached pictures (GitHub hosts them as user-attachments) is handled here:

1. the attached images are downloaded and re-uploaded to eBay Picture
   Services, so the listing never depends on GitHub keeping them online;
2. the listing is created and published straight away — the seller has
   just bought the item, which is the approval — with one unit on hand;
3. after that one unit sells, the listing carries on as buy-after-sale with
   the same photos (export_sync.py).
"""
from __future__ import annotations

import datetime
import logging
import re

import requests

from . import export_state
from .config import Config
from .ebay_client import EbayApiError, EbayClient
from .export_listing import put_listing
from .export_sync import source_check
from .github_client import GithubClient
from .pipeline_research import listing_url

log = logging.getLogger(__name__)

MAX_PHOTOS = 12
_MAX_BYTES = 12 * 1024 * 1024
_IMAGE_RE = re.compile(
    r"!\[[^\]]*\]\((https://[^)\s]+)\)|<img[^>]+src=\"(https://[^\"]+)\"", re.I
)
_TITLE_RE = re.compile(r"^\s*title:\s*(.+?)\s*$", re.I | re.M)
# Only images GitHub itself hosts for this comment are accepted, never an
# arbitrary URL someone pastes.
_ALLOWED_HOSTS = ("https://github.com/user-attachments/", "https://user-images.githubusercontent.com/",
                  "https://private-user-images.githubusercontent.com/")

_BRANDS = [
    (re.compile(r"tomytec|limited vintage", re.I), "Tomytec"),
    (re.compile(r"takara\s*tomy|tomica|plarail|beyblade", re.I), "Takara Tomy"),
    (re.compile(r"bandai|tamagotchi", re.I), "Bandai"),
]


def image_urls(comment: str) -> list[str]:
    urls = [a or b for a, b in _IMAGE_RE.findall(comment)]
    return [u for u in urls if u.startswith(_ALLOWED_HOSTS)][:MAX_PHOTOS]


def brand_for(title: str) -> str | None:
    for pattern, brand in _BRANDS:
        if pattern.search(title):
            return brand
    return None


def _download(url: str, config: Config) -> bytes:
    resp = requests.get(url, headers={"Authorization": f"Bearer {config.github_token}"}, timeout=60)
    resp.raise_for_status()
    if not resp.headers.get("Content-Type", "image/").startswith("image/"):
        raise ValueError(f"{url} is not an image")
    if len(resp.content) > _MAX_BYTES:
        raise ValueError(f"{url} is larger than 12MB")
    return resp.content


def handle_photos(config: Config, ebay: EbayClient, github: GithubClient, issue_number: int, comment: str) -> None:
    sku, entry = next(
        ((k, v) for k, v in export_state.load_listings().items() if v.get("issue_number") == issue_number),
        (None, None),
    )
    if entry is None:
        log.warning("No export listing for issue #%s", issue_number)
        return
    if entry.get("status") != "needs_photos":
        github.comment_issue(issue_number, f"この商品は処理済みです（status: {entry.get('status')}）。")
        return
    urls = image_urls(comment)
    if not urls:
        github.comment_issue(
            issue_number,
            "写真が見つかりませんでした。写真をこのIssueのコメント欄にドラッグ＆ドロップし、"
            "同じコメントに `/photos` と書いて送ってください。",
        )
        return

    try:
        eps_urls = [ebay.upload_image(_download(u, config), f"{sku}-{i + 1}.jpg") for i, u in enumerate(urls)]
    except (requests.RequestException, ValueError, EbayApiError) as exc:
        github.comment_issue(issue_number, f"写真のアップロードに失敗しました: {str(exc)[:400]}")
        return

    title_override = _TITLE_RE.search(comment)
    title = (title_override.group(1) if title_override else entry["title"])[:80]
    aspects = {"Brand": [brand_for(title)]} if brand_for(title) else {}
    product = {"title": title, "imageUrls": eps_urls, "aspects": aspects, "ean": [entry["jan"]]}
    try:
        offer_id = put_listing(config, ebay, sku, product, entry["category_id"], entry["price_usd"])
        listing_id = ebay.publish_offer(offer_id)
    except EbayApiError as exc:
        note = "今月の販売上限（出品数・金額）に達しています。" if exc.is_selling_limit else exc.body[:600]
        github.comment_issue(
            issue_number,
            f"出品に失敗しました: {note}\n\n直したら、もう一度写真つきで `/photos` を送ってください。",
        )
        return

    offer, profit, blocked = source_check(entry, config)
    entry.update(
        status="published",
        title=title,
        ebay_offer_id=offer_id,
        ebay_listing_id=listing_id,
        listing_url=listing_url(listing_id),
        image_urls=eps_urls,
        on_hand=1,
        quantity=1,
        expected_profit_jpy=profit,
        paused_reason=blocked,
        published_at=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
    )
    if offer:
        entry.update(source_price_jpy=offer.price_jpy, source_url=offer.url)
    export_state.save_listing(sku, entry)
    note = f"（今は仕入れ先が「{blocked}」のため、手元の1個が売れたら一時的に購入不可になります）" if blocked else ""
    github.comment_issue(
        issue_number,
        f"写真 {len(eps_urls)} 枚で出品しました: {entry['listing_url']}\n\n"
        f"手元の1個がまず売れ、その後は受注後仕入れで続けます。{note}",
    )
    github.close_issue(issue_number, "completed")
