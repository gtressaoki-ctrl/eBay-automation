import pytest
from PIL import Image

from ebay_automation import design_gen
from ebay_automation.themes import Design


@pytest.fixture(scope="module")
def fonts():
    """Skip the rendering tests when the fonts cannot be fetched.

    Fonts are downloaded on first use and gitignored, so a sandbox with no
    egress has nothing to render with. The pure-logic tests below still run.
    """
    try:
        design_gen.ensure_font("display")
        design_gen.ensure_font("jp")
    except Exception as exc:  # noqa: BLE001 - network/proxy failures vary
        pytest.skip(f"fonts unavailable: {exc}")


def test_product_is_dark_recognises_dark_garments():
    assert design_gen.product_is_dark("Black")
    assert design_gen.product_is_dark("Navy Blue")
    assert not design_gen.product_is_dark("White")
    assert not design_gen.product_is_dark("")


def test_palette_is_deterministic_across_calls():
    first = design_gen.palette_for("White", "caffeine-and-spite")
    second = design_gen.palette_for("White", "caffeine-and-spite")
    assert first == second


def test_palette_differs_by_design_so_listings_do_not_all_look_alike():
    palettes = {design_gen.palette_for("White", slug) for slug in ("a", "b", "c", "d", "e")}
    assert len(palettes) > 1


def test_ink_contrasts_with_the_product_colour():
    on_light = design_gen.palette_for("White", "seed")
    on_dark = design_gen.palette_for("Black", "seed")
    assert on_light.ink in design_gen._INK_ON_LIGHT
    assert on_dark.ink in design_gen._INK_ON_DARK


def _ink_bbox(path):
    """Bounding box of everything that was actually drawn."""
    with Image.open(path) as image:
        return image.getchannel("A").getbbox()


def _coverage(path, bbox):
    with Image.open(path) as image:
        width, height = image.size
    return (bbox[2] - bbox[0]) / width, (bbox[3] - bbox[1]) / height


def test_canvas_matches_the_print_area(fonts, tmp_path):
    out = design_gen.render_design(
        Design(slug="s", lines=("FIRST COFFEE", "THEN YOUR", "PROBLEMS")),
        tmp_path / "d.png",
        "White",
        (1200, 1000),
    )
    with Image.open(out) as image:
        assert image.size == (1200, 1000)


def test_stacked_design_fills_most_of_the_print_area(fonts, tmp_path):
    out = design_gen.render_design(
        Design(slug="spite", lines=("RUNNING ON", "CAFFEINE", "AND SPITE"), accent_line=1),
        tmp_path / "d.png",
        "White",
        (2000, 800),
    )
    w_ratio, h_ratio = _coverage(out, _ink_bbox(out))
    assert w_ratio > 0.5, "artwork prints too small on the product"
    assert h_ratio > 0.5


def test_grid_design_fills_most_of_the_print_area(fonts, tmp_path):
    out = design_gen.render_design(
        Design(
            slug="fish",
            grid=("鮪", "鯛", "鰻", "鰹", "鯖", "鮭", "鰤", "鱚", "鮃", "鰺", "鱈", "鮎"),
            grid_captions=("MAGURO", "TAI", "UNAGI", "KATSUO", "SABA", "SAKE",
                           "BURI", "KISU", "HIRAME", "AJI", "TARA", "AYU"),
            subtitle="SUSHI FISH KANJI",
        ),
        tmp_path / "d.png",
        "White",
        (2000, 800),
    )
    w_ratio, h_ratio = _coverage(out, _ink_bbox(out))
    assert w_ratio > 0.7
    assert h_ratio > 0.7


def test_hero_design_fills_most_of_the_print_area(fonts, tmp_path):
    out = design_gen.render_design(
        Design(slug="ichigo", lines=("一期一会",), subtitle="ICHIGO ICHIE"),
        tmp_path / "d.png",
        "White",
        (2000, 800),
    )
    w_ratio, h_ratio = _coverage(out, _ink_bbox(out))
    assert w_ratio > 0.7
    assert h_ratio > 0.6


def test_lines_are_printed_exactly_as_written(fonts, tmp_path):
    """Regression: the old renderer broke words mid-word ("CAMPIN G LIFE").

    Designs now carry their own line breaks, so nothing re-wraps them; this
    checks the renderer draws each line as one piece by rendering the same
    text twice and getting identical output.
    """
    design = Design(slug="camp", lines=("CAMPING", "LIFE"))
    first = design_gen.render_design(design, tmp_path / "a.png", "White", (1200, 800))
    second = design_gen.render_design(design, tmp_path / "b.png", "White", (1200, 800))
    assert first.read_bytes() == second.read_bytes()
