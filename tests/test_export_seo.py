from ebay_automation import export_seo


def test_maker_moves_to_the_front_and_title_is_filled():
    title = export_seo.seo_title("Modal Soul by Nujabes (Record, 2024)", {"Artist": ["Nujabes"], "Format": ["Record"]})
    assert title.startswith("Nujabes Modal Soul")
    assert "by Nujabes" not in title
    assert "Free Shipping" in title or "F/S" in title
    assert 60 <= len(title) <= 80


def test_model_and_specs_come_before_fillers():
    title = export_seo.seo_title(
        "Tomytec LV-N191A 1/64 Hanamidai Motor Bike",
        {"Brand": ["Tomytec"], "Model": ["LV-N191A"], "Scale": ["1/64"], "Color": ["Red"]},
    )
    assert title.startswith("Tomytec LV-N191A 1/64")
    assert title.index("Red") < title.index("New")
    assert len(title) <= 80


def test_brand_already_first_is_not_repeated():
    title = export_seo.seo_title("Fujifilm PROVIA 100F 135-36", {"Brand": ["Fujifilm"]})
    assert title.lower().count("fujifilm") == 1


def test_long_titles_are_cut_at_a_word():
    title = export_seo.seo_title("Word " * 30, {})
    assert len(title) <= 80 and not title.endswith(" ")


def test_no_claims_we_cannot_keep():
    title = export_seo.seo_title("Thing", {"Brand": ["Acme"]})
    for word in ("FedEx", "DHL", "In Hand"):
        assert word not in title


def test_ean_added_once():
    assert export_seo.with_ean({"Brand": ["X"]}, "4904810098492")["EAN"] == ["4904810098492"]
    assert export_seo.with_ean({"EAN": ["1"]}, "4904810098492")["EAN"] == ["1"]
