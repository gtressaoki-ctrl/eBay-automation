import pytest

from ebay_automation import export_commands, export_listing, export_state, export_sync, fx, yahoo_shopping
from ebay_automation.config import Config
from ebay_automation.ebay_client import EbayApiError
from ebay_automation.yahoo_shopping import DomesticOffer

JAN = "4904810098492"


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setattr(export_state, "LISTINGS_PATH", tmp_path / "export_listings.json")
    monkeypatch.setattr(export_state, "ORDERS_PATH", tmp_path / "export_orders.json")
    monkeypatch.setattr(export_state, "_STATE_DIR", tmp_path)
    monkeypatch.setattr(fx, "rate_to_jpy", lambda currency, config: {"USD": 150.0}.get(currency))
    export_listing._policy_cache.clear()
    # Duty has its own test; the rest of these numbers predate it.
    monkeypatch.setenv("EXPORT_SELLER_DUTY_RATE", "0")


def _offer(price, name="ベイブレードX BX-01"):
    return DomesticOffer(JAN, name, price, True, f"https://store.example/{price}", "shop")


class FakeEbay:
    def __init__(self):
        self.calls = []
        self.publish_error = None
        self.location = {"name": "Japan (export)"}
        self.policy_id = "FP-BY-NAME"

    def get_location(self, key):
        return self.location

    def find_fulfillment_policy_id(self, name):
        return self.policy_id

    def set_available_quantity(self, sku, offer_id, qty):
        self.calls.append(("qty", sku, qty))

    def create_or_replace_inventory_item(self, sku, item):
        self.calls.append(("item", sku, item))

    def create_offer(self, offer):
        self.calls.append(("offer", offer))
        return "OFFER1"

    def publish_offer(self, offer_id):
        if self.publish_error:
            raise self.publish_error
        return "1234567890"

    def delete_inventory_item(self, sku):
        self.calls.append(("delete", sku))

    def create_shipping_fulfillment(self, **kwargs):
        self.calls.append(("ship", kwargs))
        return "F1"

    def get_orders(self):
        return self.orders


class FakeGithub:
    def __init__(self):
        self.comments, self.closed, self.issues = [], [], []

    def comment_issue(self, n, body):
        self.comments.append(body)

    def close_issue(self, n, reason="completed"):
        self.closed.append(reason)

    def create_issue(self, title, body, labels=None):
        self.issues.append({"title": title, "body": body, "labels": labels})
        return {"number": 7}


def _entry(**kw):
    entry = {
        "sku": export_state.sku_for(JAN), "jan": JAN, "title": "Beyblade X BX-01 Dran Sword",
        "status": "published", "ebay_offer_id": "OFFER1", "price_usd": 60.0, "quantity": 1, "issue_number": 3,
    }
    entry.update(kw)
    return entry


# ---- listing ---------------------------------------------------------------


def test_evaluate_prices_under_competitor_and_requires_profit(monkeypatch):
    monkeypatch.setattr(export_listing, "_cheapest_competitor", lambda jan, config: 60.0)
    monkeypatch.setattr(yahoo_shopping, "cheapest_new_offer", lambda jan, config: _offer(2500))
    info = {"rate": 12.0, "category_id": "1234", "title": "Beyblade X BX-01"}

    candidate = export_listing.evaluate(JAN, info, Config(export_undercut_usd_cents=50))

    assert candidate.price == 59.5
    assert candidate.profit_jpy >= 1500
    assert candidate.expected_monthly_profit_jpy == round(candidate.profit_jpy * 12.0)


def test_evaluate_rejects_thin_margin_and_pack_mismatch(monkeypatch):
    monkeypatch.setattr(export_listing, "_cheapest_competitor", lambda jan, config: 30.0)
    monkeypatch.setattr(yahoo_shopping, "cheapest_new_offer", lambda jan, config: _offer(2500))
    info = {"rate": 12.0, "category_id": "1", "title": "Beyblade X BX-01"}
    assert export_listing.evaluate(JAN, info, Config()) is None  # thin margin

    monkeypatch.setattr(export_listing, "_cheapest_competitor", lambda jan, config: 120.0)
    monkeypatch.setattr(yahoo_shopping, "cheapest_new_offer", lambda jan, config: _offer(600, "1パック"))
    info = {"rate": 12.0, "category_id": "1", "title": "Beyblade X Booster Box"}
    assert export_listing.evaluate(JAN, info, Config()) is None  # box vs single pack


def test_create_draft_uses_catalog_photos_and_export_policies():
    ebay = FakeEbay()
    config = Config(
        export_merchant_location_key="jp-home", export_fulfillment_policy_id="FP-JP",
        ebay_payment_policy_id="PAY", ebay_return_policy_id="RET",
    )
    candidate = export_listing.Candidate(JAN, "1234", 12.0, 60.0, 59.5, _offer(2500), 3000, 0.3)
    product = {
        "epid": "999", "title": "Beyblade X BX-01 Starter Dran Sword 3-60F",
        "image": {"imageUrl": "https://i.ebayimg.com/a.jpg"},
        "additionalImages": [{"imageUrl": "https://i.ebayimg.com/b.jpg"}],
        "aspects": [{"localizedName": "Brand", "localizedValues": ["Takara Tomy"]}],
    }

    entry = export_listing.create_draft(config, ebay, candidate, product)

    _, sku, item = ebay.calls[0]
    _, offer = ebay.calls[1]
    assert sku == "JX-" + JAN
    assert item["product"]["epid"] == "999"
    assert item["product"]["imageUrls"] == ["https://i.ebayimg.com/a.jpg", "https://i.ebayimg.com/b.jpg"]
    assert item["product"]["aspects"] == {"Brand": ["Takara Tomy"]}
    assert offer["merchantLocationKey"] == "jp-home"
    assert offer["listingPolicies"]["fulfillmentPolicyId"] == "FP-JP"
    assert offer["pricingSummary"]["price"]["value"] == "59.50"
    assert entry["status"] == "pending_approval"


def test_create_draft_refuses_catalog_product_without_photo():
    candidate = export_listing.Candidate(JAN, "1", 1.0, 60.0, 59.5, _offer(2500), 3000, 0.3)
    with pytest.raises(ValueError):
        export_listing.create_draft(Config(), FakeEbay(), candidate, {"epid": "1", "title": "x"})


# ---- stock guard and orders -------------------------------------------------


def test_stock_guard_pauses_and_restores(monkeypatch):
    export_state.save_listing("JX-" + JAN, _entry())
    ebay = FakeEbay()

    monkeypatch.setattr(yahoo_shopping, "cheapest_new_offer", lambda jan, config: None)
    export_sync.sync_stock(Config(), ebay)
    assert ebay.calls[-1] == ("qty", "JX-" + JAN, 0)
    assert export_state.load_listings()["JX-" + JAN]["paused_reason"] == "仕入れ先の在庫なし"

    monkeypatch.setattr(yahoo_shopping, "cheapest_new_offer", lambda jan, config: _offer(2500))
    export_sync.sync_stock(Config(), ebay)
    assert ebay.calls[-1] == ("qty", "JX-" + JAN, 1)
    assert export_state.load_listings()["JX-" + JAN]["paused_reason"] == ""

    n = len(ebay.calls)
    export_sync.sync_stock(Config(), ebay)  # unchanged: no API call
    assert len(ebay.calls) == n


def test_stock_guard_pauses_when_source_price_rises(monkeypatch):
    export_state.save_listing("JX-" + JAN, _entry())
    monkeypatch.setattr(yahoo_shopping, "cheapest_new_offer", lambda jan, config: _offer(7000))
    ebay = FakeEbay()
    export_sync.sync_stock(Config(), ebay)
    assert ebay.calls[-1] == ("qty", "JX-" + JAN, 0)


def _order():
    return {
        "orderId": "12-34567-89012",
        "lineItems": [
            {"sku": "JX-" + JAN, "lineItemId": "L1", "quantity": 1, "lineItemCost": {"value": "59.50"}},
            {"sku": "MUG-1", "lineItemId": "L2", "quantity": 1},
        ],
        "fulfillmentStartInstructions": [
            {"shippingStep": {"shipTo": {"fullName": "Jane Buyer", "contactAddress": {
                "addressLine1": "1 Secret St", "city": "Austin", "postalCode": "78701", "countryCode": "US"}}}}
        ],
    }


def test_new_order_opens_issue_without_buyer_details():
    export_state.save_listing("JX-" + JAN, _entry(source_price_jpy=2500, source_url="https://store/x", expected_profit_jpy=3000))
    ebay, github = FakeEbay(), FakeGithub()
    ebay.orders = [_order()]

    assert export_sync.sync_orders(Config(), ebay, github) == 1
    assert export_sync.sync_orders(Config(), ebay, github) == 0  # not twice

    body = github.issues[0]["body"]
    assert "https://store/x" in body and "**US**" in body
    for secret in ("Jane", "Secret St", "78701", "Austin"):
        assert secret not in body
    record = export_state.load_orders()["12-34567-89012"]
    assert [i["sku"] for i in record["items"]] == ["JX-" + JAN]
    assert "Jane" not in str(record)
    assert export_state.load_listings()["JX-" + JAN]["quantity"] == 0


# ---- commands ---------------------------------------------------------------


def test_approve_publishes_when_source_ok(monkeypatch):
    export_state.save_listing("JX-" + JAN, _entry(status="pending_approval", quantity=None))
    monkeypatch.setattr(yahoo_shopping, "cheapest_new_offer", lambda jan, config: _offer(2500))
    github = FakeGithub()
    export_commands.handle_approval(Config(), FakeEbay(), github, 3, approve=True)
    entry = export_state.load_listings()["JX-" + JAN]
    assert entry["status"] == "published" and entry["quantity"] == 1
    assert entry["listing_url"].endswith("/1234567890")
    assert github.closed == ["completed"]


def test_approve_holds_when_source_out_of_stock(monkeypatch):
    export_state.save_listing("JX-" + JAN, _entry(status="pending_approval"))
    monkeypatch.setattr(yahoo_shopping, "cheapest_new_offer", lambda jan, config: None)
    github = FakeGithub()
    export_commands.handle_approval(Config(), FakeEbay(), github, 3, approve=True)
    assert export_state.load_listings()["JX-" + JAN]["status"] == "pending_approval"
    assert "在庫なし" in github.comments[0] and not github.closed


def test_approve_reports_selling_limit(monkeypatch):
    export_state.save_listing("JX-" + JAN, _entry(status="pending_approval"))
    monkeypatch.setattr(yahoo_shopping, "cheapest_new_offer", lambda jan, config: _offer(2500))
    ebay, github = FakeEbay(), FakeGithub()
    ebay.publish_error = EbayApiError("POST", "u", 400, "you've reached the number of items")
    export_commands.handle_approval(Config(), ebay, github, 3, approve=True)
    assert "販売上限" in github.comments[0]


def test_shipped_marks_order_and_records_profit():
    export_state.save_order("O1", {"status": "to_buy", "issue_number": 9, "items": [
        {"sku": "JX-" + JAN, "line_item_id": "L1", "quantity": 1, "price_usd": 59.5}]})
    ebay, github = FakeEbay(), FakeGithub()
    match = export_commands._SHIPPED_RE.match("/shipped japanpost EJ123456789JP ¥2,480")
    export_commands.handle_shipped(Config(), ebay, github, 9, match)

    _, call = ebay.calls[0]
    assert call["shipping_carrier_code"] == "JapanPost"
    assert call["tracking_number"] == "EJ123456789JP"
    assert call["line_items"] == [{"lineItemId": "L1", "quantity": 1}]
    record = export_state.load_orders()["O1"]
    assert record["status"] == "shipped" and record["purchase_cost_jpy"] == 2480
    assert record["profit_jpy"] > 0


@pytest.mark.parametrize("text, ok", [("/shipped fedex 123", True), (" /shipped dhl 1 980", True), ("/shipped", False)])
def test_shipped_regex(text, ok):
    assert bool(export_commands._SHIPPED_RE.match(text)) is ok


def test_pod_fulfillment_ignores_export_skus(monkeypatch):
    from ebay_automation import ledger, pipeline_fulfill

    seen = []
    monkeypatch.setattr(ledger, "get_pending_listing", lambda sku: seen.append(sku))
    order = _order()
    assert pipeline_fulfill._submit_to_printify(Config(), None, None, order) is None
    assert seen == ["MUG-1"]


def test_dry_run_needs_no_export_setup_and_creates_nothing(monkeypatch, tmp_path):
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    candidate = export_listing.Candidate(JAN, "1", 12.0, 60.0, 59.5, _offer(2500), 3000, 0.3)
    monkeypatch.setattr(export_listing, "find_candidates", lambda config, skip: [candidate])

    class CatalogOnly(FakeEbay):
        def __init__(self, config):
            super().__init__()

        def find_catalog_product(self, gtin):
            return {"epid": "1", "title": "Beyblade X BX-01"}

    monkeypatch.setattr(export_listing, "EbayClient", CatalogOnly)
    config = Config(ebay_app_id="a", ebay_cert_id="c", ebay_refresh_token="r", yahoo_app_id="y", dry_run=True)

    assert export_listing.run(config) == 1
    assert export_state.load_listings() == {}
    assert "Beyblade X BX-01" in summary.read_text()


def test_unconfigured_scheduled_run_falls_back_to_dry_run(monkeypatch, tmp_path):
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(tmp_path / "s.md"))
    monkeypatch.setattr(export_listing, "find_candidates", lambda config, skip: [])
    unset = FakeEbay()
    unset.location, unset.policy_id = None, None  # Japan Export Setup never ran
    monkeypatch.setattr(export_listing, "EbayClient", lambda config: unset)
    config = Config(ebay_app_id="a", ebay_cert_id="c", ebay_refresh_token="r", yahoo_app_id="y",
                    ebay_payment_policy_id="p", ebay_return_policy_id="r", dry_run=False)
    assert export_listing.run(config) == 0
    assert "DRY RUN" in (tmp_path / "s.md").read_text()


@pytest.mark.parametrize(
    "title, size",
    [
        ("Takara Tomy Beyblade X Extreme Stadium BX-10", "large"),
        ("Plarail Basic Set Takara Tomy", "large"),
        ("Beyblade X BX-01 Starter Dran Sword", "small"),
        ("Beyblade X Launcher Grip BX-11", "medium"),
        ("Tomica Premium 01 Nissan Skyline", "small"),
    ],
)
def test_size_for(title, size):
    assert export_listing.size_for(title, Config(export_listing_size="small")) == size


def test_stadium_is_priced_with_large_shipping(monkeypatch):
    # The first live dry run priced BX-10 at small-parcel shipping and
    # showed ¥3,014 profit; at the large rate it no longer clears the floor.
    monkeypatch.setattr(export_listing, "_cheapest_competitor", lambda jan, config: 66.81)
    monkeypatch.setattr(yahoo_shopping, "cheapest_new_offer", lambda jan, config: _offer(2750))
    info = {"rate": 3.5, "category_id": "1", "title": "Takara Tomy Beyblade X Extreme Stadium - BX-10"}
    assert export_listing.evaluate(JAN, info, Config()) is None

    info["title"] = "Takara Tomy Beyblade X BX-10 Starter"
    assert export_listing.evaluate(JAN, info, Config()).size == "small"


def test_stock_guard_uses_the_listing_size(monkeypatch):
    # Profitable as a small parcel, not as a large one.
    export_state.save_listing("JX-" + JAN, _entry(size="large"))
    monkeypatch.setattr(yahoo_shopping, "cheapest_new_offer", lambda jan, config: _offer(2500))
    ebay = FakeEbay()
    export_sync.sync_stock(Config(), ebay)
    assert ebay.calls[-1] == ("qty", "JX-" + JAN, 0)


# ---- own photos --------------------------------------------------------------

from ebay_automation import export_photos  # noqa: E402


def test_image_urls_only_take_github_hosted_images():
    comment = (
        "![IMG_1](https://github.com/user-attachments/assets/aaa)\n"
        '<img width="300" src="https://github.com/user-attachments/assets/bbb" />\n'
        "![x](https://evil.example/c.jpg)\n/photos"
    )
    assert export_photos.image_urls(comment) == [
        "https://github.com/user-attachments/assets/aaa",
        "https://github.com/user-attachments/assets/bbb",
    ]


def test_brand_for():
    assert export_photos.brand_for("Tomica Limited Vintage LV-N") == "Tomytec"
    assert export_photos.brand_for("Tomica Premium 01") == "Takara Tomy"
    assert export_photos.brand_for("Tamagotchi Uni") == "Bandai"
    assert export_photos.brand_for("Something") is None


def _photo_entry(**kw):
    candidate = export_listing.Candidate(JAN, "222", 2.0, 40.0, 39.5, _offer(1500), 2000, 0.3, "small",
                                         "Tomica Premium 01 Nissan Skyline")
    entry = export_listing.candidate_entry(candidate, candidate.title, "needs_photos", Config())
    entry["issue_number"] = 5
    entry.update(kw)
    return entry


class PhotoEbay(FakeEbay):
    def upload_image(self, data, filename):
        self.calls.append(("upload", filename, data))
        return f"https://i.ebayimg.com/{filename}"


def test_photos_upload_to_eps_and_publish_with_one_on_hand(monkeypatch):
    export_state.save_listing("JX-" + JAN, _photo_entry())
    monkeypatch.setattr(export_photos, "_download", lambda url, config: b"jpeg-bytes")
    monkeypatch.setattr(yahoo_shopping, "cheapest_new_offer", lambda jan, config: _offer(1500))
    ebay, github = PhotoEbay(), FakeGithub()
    comment = "![a](https://github.com/user-attachments/assets/1)\n![b](https://github.com/user-attachments/assets/2)\n/photos"

    export_photos.handle_photos(Config(), ebay, github, 5, comment)

    uploads = [c for c in ebay.calls if c[0] == "upload"]
    assert len(uploads) == 2
    _, sku, item = next(c for c in ebay.calls if c[0] == "item")
    assert item["product"]["imageUrls"] == ["https://i.ebayimg.com/JX-%s-1.jpg" % JAN, "https://i.ebayimg.com/JX-%s-2.jpg" % JAN]
    assert item["product"]["ean"] == [JAN]
    assert item["product"]["aspects"] == {"Brand": ["Takara Tomy"]}
    _, offer = next(c for c in ebay.calls if c[0] == "offer")
    assert offer["categoryId"] == "222"
    entry = export_state.load_listings()["JX-" + JAN]
    assert entry["status"] == "published" and entry["on_hand"] == 1
    assert github.closed == ["completed"]


def test_photos_title_override_and_missing_images(monkeypatch):
    export_state.save_listing("JX-" + JAN, _photo_entry())
    github = FakeGithub()
    export_photos.handle_photos(Config(), PhotoEbay(), github, 5, "/photos")
    assert "写真が見つかりませんでした" in github.comments[0]
    assert export_state.load_listings()["JX-" + JAN]["status"] == "needs_photos"

    monkeypatch.setattr(export_photos, "_download", lambda url, config: b"x")
    monkeypatch.setattr(yahoo_shopping, "cheapest_new_offer", lambda jan, config: _offer(1500))
    ebay = PhotoEbay()
    export_photos.handle_photos(
        Config(), ebay, FakeGithub(), 5,
        "![a](https://github.com/user-attachments/assets/1)\n/photos\ntitle: Tomica Premium 01 Skyline GT-R Japan",
    )
    _, _, item = next(c for c in ebay.calls if c[0] == "item")
    assert item["product"]["title"] == "Tomica Premium 01 Skyline GT-R Japan"


def test_unit_on_hand_stays_buyable_when_source_is_out(monkeypatch):
    export_state.save_listing("JX-" + JAN, _entry(on_hand=1, quantity=1))
    monkeypatch.setattr(yahoo_shopping, "cheapest_new_offer", lambda jan, config: None)
    ebay = FakeEbay()
    export_sync.sync_stock(Config(), ebay)
    assert not [c for c in ebay.calls if c[0] == "qty"]  # stays at 1


def test_first_order_ships_from_hand():
    export_state.save_listing("JX-" + JAN, _entry(on_hand=1, source_price_jpy=2500, source_url="https://store/x"))
    ebay, github = FakeEbay(), FakeGithub()
    ebay.orders = [_order()]
    export_sync.sync_orders(Config(), ebay, github)
    assert "手元の在庫" in github.issues[0]["body"]
    assert export_state.load_listings()["JX-" + JAN]["on_hand"] == 0
    assert export_state.load_orders()["12-34567-89012"]["items"][0]["from_stock"] is True


def test_run_opens_photo_request_when_catalog_has_no_product(monkeypatch):
    candidate = export_listing.Candidate(JAN, "222", 2.0, 40.0, 39.5, _offer(1500), 2000, 0.3, "small", "Tomica Premium 01")
    monkeypatch.setattr(export_listing, "find_candidates", lambda config, skip: [candidate])

    class NoCatalog(FakeEbay):
        def __init__(self, config):
            super().__init__()

        def find_catalog_product(self, gtin):
            return None

    github = FakeGithub()
    monkeypatch.setattr(export_listing, "EbayClient", NoCatalog)
    monkeypatch.setattr(export_listing, "GithubClient", lambda config: github)
    config = Config(ebay_app_id="a", ebay_cert_id="c", ebay_refresh_token="r", yahoo_app_id="y",
                    export_merchant_location_key="jp", export_fulfillment_policy_id="fp",
                    ebay_payment_policy_id="p", ebay_return_policy_id="r", github_token="t", github_repository="o/r",
                    export_daily_photo_requests=2)

    export_listing.run(config)

    assert github.issues[0]["labels"][0] == "export-photos"
    assert "/photos" in github.issues[0]["body"]
    assert export_state.load_listings()["JX-" + JAN]["status"] == "needs_photos"


def test_photo_reject_is_remembered():
    export_state.save_listing("JX-" + JAN, _photo_entry())
    github = FakeGithub()
    export_commands.handle_photo_reject(github, 5)
    assert export_state.load_listings()["JX-" + JAN]["status"] == "rejected"
    assert github.closed == ["not_planned"]


@pytest.mark.parametrize(
    "raw, cleaned",
    [
        ("PRESALE Beyblade X BX-52 Luster Dragoon 6-60LC Starter Takara Tomy", "Beyblade X BX-52 Luster Dragoon 6-60LC Starter Takara Tomy Japan"),
        ("PREORDER Tamagotchi Paradise My Lab 4582770018813 From Japan", "Tamagotchi Paradise My Lab 4582770018813 Japan"),
        ("Tomica Premium 01 Nissan Skyline Japan", "Tomica Premium 01 Nissan Skyline Japan"),
    ],
)
def test_clean_title(raw, cleaned):
    assert export_listing.clean_title(raw) == cleaned


def test_policy_is_found_by_name_unless_set():
    ebay = FakeEbay()
    assert export_listing.export_policy_id(Config(), ebay) == "FP-BY-NAME"
    assert export_listing.export_policy_id(Config(export_fulfillment_policy_id="EXPLICIT"), ebay) == "EXPLICIT"
    ebay.location, ebay.policy_id = None, None
    export_listing._policy_cache.clear()
    missing = export_listing.setup_missing(Config(ebay_payment_policy_id="p", ebay_return_policy_id="r"), ebay)
    assert len(missing) == 2 and "Japan Export Setup" in missing[0]


def test_setup_policy_body_is_free_shipping_with_handling_days():
    import importlib.util
    spec = importlib.util.spec_from_file_location("export_setup", "scripts/export_setup.py")
    setup = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(setup)
    body = setup.policy_body("Japan export", "EBAY_US", 5, "EconomyShippingFromOutsideUS")
    service = body["shippingOptions"][0]["shippingServices"][0]
    assert body["handlingTime"] == {"value": 5, "unit": "DAY"}
    assert service["freeShipping"] is True and service["shippingServiceCode"] == "EconomyShippingFromOutsideUS"


def test_slow_sellers_do_not_get_photo_requests(monkeypatch):
    slow = export_listing.Candidate(JAN, "1", 0.1, 166.3, 165.8, _offer(9900), 8808, 0.35, "small", "TLV-NEO F355")
    monkeypatch.setattr(export_listing, "find_candidates", lambda config, skip: [slow])

    class NoCatalog(FakeEbay):
        def __init__(self, config):
            super().__init__()

        def find_catalog_product(self, gtin):
            return None

    github = FakeGithub()
    monkeypatch.setattr(export_listing, "EbayClient", NoCatalog)
    monkeypatch.setattr(export_listing, "GithubClient", lambda config: github)
    config = Config(ebay_app_id="a", ebay_cert_id="c", ebay_refresh_token="r", yahoo_app_id="y",
                    ebay_payment_policy_id="p", ebay_return_policy_id="r")
    export_listing.run(config)
    assert github.issues == []


def test_yahoo_retries_through_rate_limits(monkeypatch):
    monkeypatch.setattr(yahoo_shopping, "_MIN_INTERVAL_S", 0)
    monkeypatch.setattr(yahoo_shopping.time, "sleep", lambda s: None)
    statuses = iter([429, 429, 429, 200])

    class Resp:
        def __init__(self):
            self.status_code = next(statuses)

        def raise_for_status(self):
            if self.status_code >= 400:
                raise yahoo_shopping.requests.HTTPError(str(self.status_code))

        def json(self):
            return {"hits": [{"price": 3300, "inStock": True, "condition": "new", "url": "u"}]}

    monkeypatch.setattr(yahoo_shopping.requests, "get", lambda *a, **k: Resp())
    assert yahoo_shopping.cheapest_new_offer(JAN, Config(yahoo_app_id="y")).price_jpy == 3300


def test_unprofitable_photo_request_is_withdrawn(monkeypatch):
    export_state.save_listing("JX-" + JAN, _photo_entry())  # $39.50 sale
    monkeypatch.setattr(yahoo_shopping, "cheapest_new_offer", lambda jan, config: _offer(1500))
    github = FakeGithub()
    export_sync.sync_photo_requests(Config(export_seller_duty_rate=0.15), github)
    entry = export_state.load_listings()["JX-" + JAN]
    assert entry["status"] == "withdrawn"
    assert "買わないで" in github.comments[0] and github.closed == ["not_planned"]


def test_profitable_photo_request_stays_open(monkeypatch):
    export_state.save_listing("JX-" + JAN, _photo_entry(price_usd=80.0))
    monkeypatch.setattr(yahoo_shopping, "cheapest_new_offer", lambda jan, config: _offer(3000))
    github = FakeGithub()
    export_sync.sync_photo_requests(Config(export_seller_duty_rate=0.15), github)
    assert export_state.load_listings()["JX-" + JAN]["status"] == "needs_photos"
    assert github.comments == []


def _catalog_run(monkeypatch, candidates, publish_error=None, **cfg):
    monkeypatch.setattr(export_listing, "find_candidates", lambda config, skip: candidates)
    monkeypatch.setattr(yahoo_shopping, "cheapest_new_offer", lambda jan, config: _offer(2500))

    class Catalog(FakeEbay):
        def __init__(self, config):
            super().__init__()
            self.publish_error = publish_error

        def find_catalog_product(self, gtin):
            return {"epid": "9", "title": f"Beyblade X {gtin}", "image": {"imageUrl": "https://i.ebayimg.com/a.jpg"}}

    github = FakeGithub()
    monkeypatch.setattr(export_listing, "EbayClient", Catalog)
    monkeypatch.setattr(export_listing, "GithubClient", lambda config: github)
    config = Config(ebay_app_id="a", ebay_cert_id="c", ebay_refresh_token="r", yahoo_app_id="y",
                    ebay_payment_policy_id="p", ebay_return_policy_id="r", **cfg)
    export_listing.run(config)
    return github


def _cand(jan):
    return export_listing.Candidate(jan, "1", 12.0, 60.0, 59.5, _offer(2500), 3000, 0.3, "small", "Beyblade X")


def test_catalog_candidates_publish_without_approval(monkeypatch):
    github = _catalog_run(monkeypatch, [_cand(JAN)])
    assert github.issues[0]["title"].startswith("[輸出・出品済み]")
    assert github.closed == ["completed"] and "公開しました" in github.comments[0]
    assert export_state.load_listings()["JX-" + JAN]["status"] == "published"


def test_approval_still_available_when_auto_publish_is_off(monkeypatch):
    github = _catalog_run(monkeypatch, [_cand(JAN)], export_auto_publish=False)
    assert github.issues[0]["title"].startswith("[輸出・承認待ち]") and github.closed == []
    assert export_state.load_listings()["JX-" + JAN]["status"] == "pending_approval"


def test_selling_limit_stops_the_day(monkeypatch):
    limit = EbayApiError("POST", "u", 400, "you've reached the number of items")
    github = _catalog_run(monkeypatch, [_cand(JAN), _cand("4549660000006")], publish_error=limit)
    assert len(github.issues) == 1
    assert "販売上限" in github.issues[0]["body"]


def test_sweep_covers_categories_and_sets_size_floor(monkeypatch):
    calls = []

    def fake_browse(path, config, params=None):
        if path == "/item_summary/search":
            calls.append(params)
            if params.get("category_ids") == "619":
                return {"itemSummaries": [{"itemId": "v1|guitar"}]}
            return {"itemSummaries": []}
        return {"gtin": JAN, "title": "Yamaha Guitar", "categoryId": "33034",
                "estimatedAvailabilities": [{"estimatedSoldQuantity": 3}], "itemCreationDate": None}

    monkeypatch.setattr(export_listing, "_browse_get", fake_browse)
    config = Config(export_listing_queries=["beyblade x"], export_sweep_categories=["220", "619"])
    found = export_listing._selling_jans(config)

    assert [c.get("q") or c.get("category_ids") for c in calls] == ["beyblade x", "220", "619"]
    assert all("itemLocationCountry:JP" in c["filter"] for c in calls)
    assert found[JAN]["size_floor"] == "large"


def test_size_floor_raises_shipping(monkeypatch):
    monkeypatch.setattr(export_listing, "_cheapest_competitor", lambda jan, config: 60.0)
    monkeypatch.setattr(yahoo_shopping, "cheapest_new_offer", lambda jan, config: _offer(2500))
    info = {"rate": 5.0, "category_id": "1", "title": "Item", "size_floor": "large"}
    candidate = export_listing.evaluate(JAN, info, Config(export_min_profit_jpy=-100000))
    assert candidate.size == "large"
