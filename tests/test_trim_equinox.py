import importlib.util

spec = importlib.util.spec_from_file_location("trim_equinox", "scripts/trim_equinox.py")
trim = importlib.util.module_from_spec(spec)
spec.loader.exec_module(trim)


def _v(listing, sku, title, size="", qty=1):
    return {"listing_id": listing, "sku": sku, "title": title, "size": size, "quantity": qty,
            "price": 24.99, "offer_id": "O" + sku, "group": "G" + listing}


def test_keeps_best_shirt_and_sticker_and_trims_variants():
    variants = [
        *[_v("A", f"A{s}", "EQUINOX Kamon T-Shirt", s) for s in ("S", "M", "L", "XL", "2XL")],
        *[_v("B", f"B{s}", "EQUINOX Ume T-Shirt", s) for s in ("M", "L")],
        *[_v("C", f"C{i}", "EQUINOX Sticker") for i in range(4)],
        *[_v("D", f"D{i}", "EQUINOX Aries Sticker") for i in range(4)],
    ]
    traffic = {"A": {"LISTING_VIEWS_TOTAL": 9}, "B": {"LISTING_VIEWS_TOTAL": 2}, "D": {"LISTING_IMPRESSION_TOTAL": 50}}

    kept, zeroed, ended = trim.plan(variants, traffic)

    assert set(kept) == {"A", "D"}
    assert [v["size"] for v in kept["A"]] == ["M", "L", "XL"]
    assert len(kept["D"]) == 1
    assert {v["sku"] for v in zeroed} == {"AS", "A2XL", "D1", "D2", "D3"}
    assert sorted(g[0]["listing_id"] for g in ended) == ["B", "C"]


def test_a_listing_that_sold_is_kept():
    variants = [_v("A", "A1", "EQUINOX T-Shirt", "M"), _v("B", "B1", "EQUINOX T-Shirt", "M")]
    kept, _, ended = trim.plan(variants, {"A": {"LISTING_VIEWS_TOTAL": 50}, "B": {"TRANSACTION": 1}})
    assert set(kept) == {"B"} and ended[0][0]["listing_id"] == "A"
