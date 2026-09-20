"""Render printable designs sized to the product's actual print area.

Two things went wrong in the first version and both are fixed here.

The canvas was a 3000x3600 portrait sheet holding one small line of text,
so Printify scaled that mostly-empty sheet down into the print area and
the artwork came out tiny on the product. Now the canvas matches the
print area's real aspect ratio and the content is laid out to fill it.

Ink colour was picked without reference to the product colour, so dark
purple was printed on a black shirt. Colour now comes from the garment
colour: only inks with real contrast against it are eligible.

Fonts are SIL OFL (Anton, Noto Sans JP) and all artwork is generated from
our own text, so nothing here carries licensing risk.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont

from .themes import Design

_ASSETS_DIR = Path(__file__).resolve().parent.parent.parent / "assets"
_FONT_DIR = _ASSETS_DIR / "fonts"

# raw.githubusercontent.com rather than github.com/.../raw/... — the latter
# is blocked by some egress proxies and fails the whole run.
_FONTS = {
    "display": (
        "Anton-Regular.ttf",
        "https://raw.githubusercontent.com/google/fonts/main/ofl/anton/Anton-Regular.ttf",
    ),
    "jp": (
        "NotoSansJP.ttf",
        "https://raw.githubusercontent.com/google/fonts/main/ofl/notosansjp/NotoSansJP%5Bwght%5D.ttf",
    ),
}

# Inks that hold up on a light product, and on a dark one.
_INK_ON_LIGHT = ("#111111", "#1b3a5c", "#7a2020", "#1f4d3d", "#4a2c6b")
_INK_ON_DARK = ("#f5f5f5", "#ffd166", "#7fd1c1", "#ff8fa3", "#a9d6ff")
_ACCENT_ON_LIGHT = ("#c1272d", "#c77d02", "#0f7b6c", "#3c5ccf")
_ACCENT_ON_DARK = ("#ffd166", "#ff8fa3", "#7fd1c1", "#ffffff")

_DARK_PRODUCT_WORDS = ("black", "navy", "charcoal", "forest", "military", "dark", "purple", "red", "royal")


@dataclass(frozen=True)
class Palette:
    ink: str
    accent: str


def product_is_dark(product_colour: str) -> bool:
    lowered = (product_colour or "").lower()
    return any(word in lowered for word in _DARK_PRODUCT_WORDS)


def palette_for(product_colour: str, seed: str) -> Palette:
    """Pick ink and accent that contrast with the product, deterministically.

    Uses a stable digest rather than hash(), whose value changes between
    processes, so the same design renders identically on every run.
    """
    digest = int(hashlib.sha256(seed.encode("utf-8")).hexdigest(), 16)
    if product_is_dark(product_colour):
        inks, accents = _INK_ON_DARK, _ACCENT_ON_DARK
    else:
        inks, accents = _INK_ON_LIGHT, _ACCENT_ON_LIGHT
    return Palette(ink=inks[digest % len(inks)], accent=accents[(digest // 7) % len(accents)])


def ensure_font(kind: str = "display") -> Path:
    file_name, url = _FONTS[kind]
    path = _FONT_DIR / file_name
    if not path.exists():
        _FONT_DIR.mkdir(parents=True, exist_ok=True)
        resp = requests.get(url, timeout=120)
        resp.raise_for_status()
        path.write_bytes(resp.content)
    return path


def _font(kind: str, size: int) -> ImageFont.FreeTypeFont:
    font = ImageFont.truetype(str(ensure_font(kind)), size)
    if kind == "jp":
        # Noto Sans JP ships as a variable font whose default instance is
        # Thin (weight 100) — far too light to print legibly.
        font.set_variation_by_name("Bold")
    return font


def _text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> tuple[int, int]:
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0], box[3] - box[1]


def _fit_text(
    draw: ImageDraw.ImageDraw, text: str, kind: str, max_width: int, max_height: int
) -> ImageFont.FreeTypeFont:
    """Largest font size at which a single string fits the box."""
    size = 20
    best = _font(kind, size)
    while size < 1200:
        candidate = _font(kind, size)
        width, height = _text_size(draw, text, candidate)
        if width > max_width or height > max_height:
            break
        best = candidate
        size += 10
    return best


def _fit_lines(
    draw: ImageDraw.ImageDraw,
    lines: tuple[str, ...],
    kind: str,
    max_width: int,
    max_height: int,
    line_gap_ratio: float = 0.22,
) -> ImageFont.FreeTypeFont:
    """Largest font size at which all lines fit the box — grows to fill it."""
    size = 20
    best = _font(kind, size)
    while size < 1200:
        candidate = _font(kind, size)
        widest = max(_text_size(draw, line, candidate)[0] for line in lines)
        total_height = sum(_text_size(draw, line, candidate)[1] for line in lines)
        total_height += int(size * line_gap_ratio) * (len(lines) - 1)
        if widest > max_width or total_height > max_height:
            break
        best = candidate
        size += 10
    return best


def _regroup_lines(
    lines: tuple[str, ...], accent_line: int | None, groups: tuple[int, ...]
) -> tuple[tuple[str, ...], int | None]:
    """Join the design's lines into `groups` consecutive runs.

    `groups` holds the number of source lines in each output line. Lines are
    only ever joined at their existing breaks, never split, so a word can
    never end up straddling two rows.
    """
    merged: list[str] = []
    accent: int | None = None
    index = 0
    for position, count in enumerate(groups):
        run = lines[index : index + count]
        if accent_line is not None and index <= accent_line < index + count:
            accent = position
        merged.append(" ".join(run))
        index += count
    return tuple(merged), accent


def _groupings(count: int):
    """Every way of splitting `count` ordered lines into consecutive runs."""
    if count == 0:
        return
    if count == 1:
        yield (1,)
        return
    for first in range(1, count + 1):
        if first == count:
            yield (count,)
            continue
        for rest in _groupings(count - first):
            yield (first,) + rest


def _layout_lines(
    draw: ImageDraw.ImageDraw,
    lines: tuple[str, ...],
    accent_line: int | None,
    kind: str,
    max_width: int,
    max_height: int,
) -> tuple[tuple[str, ...], int | None, ImageFont.FreeTypeFont]:
    """Pick the arrangement of `lines` that fills the box best.

    A design's line breaks read well on a tall print area but waste a wide
    one: three stacked rows in a 2:1 mug panel are height-capped and end up
    covering less than half its width. Trying each way of joining adjacent
    lines and keeping the largest type that still fits lets the same design
    adapt to whatever panel the product actually has.
    """
    best: tuple[tuple[str, ...], int | None, ImageFont.FreeTypeFont] | None = None
    best_size = -1
    for groups in _groupings(len(lines)):
        merged, accent = _regroup_lines(lines, accent_line, groups)
        font = _fit_lines(draw, merged, kind, max_width, max_height)
        if font.size > best_size:
            best_size = font.size
            best = (merged, accent, font)
    assert best is not None
    return best


def _draw_lines(
    draw: ImageDraw.ImageDraw,
    lines: tuple[str, ...],
    font: ImageFont.FreeTypeFont,
    palette: Palette,
    accent_line: int | None,
    box: tuple[int, int, int, int],
) -> None:
    left, top, right, bottom = box
    gap = int(font.size * 0.22)
    boxes = [draw.textbbox((0, 0), line, font=font) for line in lines]
    heights = [b[3] - b[1] for b in boxes]
    total = sum(heights) + gap * (len(lines) - 1)
    y = top + ((bottom - top) - total) // 2

    for index, (line, bbox, height) in enumerate(zip(lines, boxes, heights)):
        width = bbox[2] - bbox[0]
        x = left + ((right - left) - width) // 2
        colour = palette.accent if index == accent_line else palette.ink
        draw.text((x - bbox[0], y - bbox[1]), line, font=font, fill=colour)
        y += height + gap


def _render_stacked(image: Image.Image, design: Design, palette: Palette) -> None:
    draw = ImageDraw.Draw(image)
    width, height = image.size
    margin_x, margin_y = int(width * 0.05), int(height * 0.08)

    subtitle_height = int(height * 0.16) if design.subtitle else 0
    body_box = (margin_x, margin_y, width - margin_x, height - margin_y - subtitle_height)
    lines, accent, font = _layout_lines(
        draw,
        design.lines,
        design.accent_line,
        "display",
        body_box[2] - body_box[0],
        body_box[3] - body_box[1],
    )
    _draw_lines(draw, lines, font, palette, accent, body_box)

    if design.subtitle:
        sub_font = _fit_lines(
            draw, (design.subtitle,), "jp", width - 2 * margin_x, int(subtitle_height * 0.55)
        )
        sub_w, sub_h = _text_size(draw, design.subtitle, sub_font)
        box = draw.textbbox((0, 0), design.subtitle, font=sub_font)
        draw.text(
            ((width - sub_w) // 2 - box[0], height - margin_y - sub_h - box[1]),
            design.subtitle,
            font=sub_font,
            fill=palette.accent,
        )


def _render_hero(image: Image.Image, design: Design, palette: Palette) -> None:
    """One oversized glyph or word, with a caption underneath."""
    draw = ImageDraw.Draw(image)
    width, height = image.size
    margin = int(height * 0.08)
    caption_height = int(height * 0.18) if design.subtitle else 0

    hero_box = (margin, margin, width - margin, height - margin - caption_height)
    font = _fit_lines(draw, design.lines, "jp", hero_box[2] - hero_box[0], hero_box[3] - hero_box[1])
    _draw_lines(draw, design.lines, font, palette, None, hero_box)

    if design.subtitle:
        cap_font = _fit_lines(draw, (design.subtitle,), "jp", int(width * 0.9), int(caption_height * 0.5))
        cap_w, cap_h = _text_size(draw, design.subtitle, cap_font)
        box = draw.textbbox((0, 0), design.subtitle, font=cap_font)
        draw.text(
            ((width - cap_w) // 2 - box[0], height - margin - cap_h - box[1]),
            design.subtitle,
            font=cap_font,
            fill=palette.accent,
        )


def _render_grid(image: Image.Image, design: Design, palette: Palette) -> None:
    """Dense character grid with small romaji captions, sushi-shop style."""
    draw = ImageDraw.Draw(image)
    width, height = image.size
    margin_x, margin_y = int(width * 0.04), int(height * 0.08)
    title_height = int(height * 0.16) if design.subtitle else 0

    cells = list(design.grid)
    captions = list(design.grid_captions) + [""] * (len(cells) - len(design.grid_captions))

    columns = 6 if len(cells) > 6 else len(cells)
    rows = (len(cells) + columns - 1) // columns

    area_w = width - 2 * margin_x
    area_h = height - 2 * margin_y - title_height
    cell_w = area_w // columns
    cell_h = area_h // rows

    # Each glyph is sized to fill its own cell. Sizing the whole set as
    # stacked lines (as this did originally) shrank every character to a
    # twelfth of the available height.
    widest_caption = max((c for c in captions if c), key=len, default="A")
    glyph_font = _fit_text(draw, cells[0], "jp", int(cell_w * 0.85), int(cell_h * 0.62))
    caption_font = _fit_text(draw, widest_caption, "jp", int(cell_w * 0.92), int(cell_h * 0.18))

    for index, glyph in enumerate(cells):
        row, column = divmod(index, columns)
        cx = margin_x + column * cell_w + cell_w // 2
        cell_top = margin_y + row * cell_h

        gw, gh = _text_size(draw, glyph, glyph_font)
        gbox = draw.textbbox((0, 0), glyph, font=glyph_font)
        colour = palette.accent if index % 5 == 0 else palette.ink
        glyph_y = cell_top + int(cell_h * 0.08)
        draw.text((cx - gw // 2 - gbox[0], glyph_y - gbox[1]), glyph, font=glyph_font, fill=colour)

        caption = captions[index]
        if caption:
            cw, ch = _text_size(draw, caption, caption_font)
            cbox = draw.textbbox((0, 0), caption, font=caption_font)
            draw.text(
                (cx - cw // 2 - cbox[0], glyph_y + gh + int(cell_h * 0.06) - cbox[1]),
                caption,
                font=caption_font,
                fill=palette.ink,
            )

    if design.subtitle:
        t_font = _fit_lines(draw, (design.subtitle,), "jp", int(width * 0.8), int(title_height * 0.55))
        tw, th = _text_size(draw, design.subtitle, t_font)
        tbox = draw.textbbox((0, 0), design.subtitle, font=t_font)
        draw.text(
            ((width - tw) // 2 - tbox[0], height - margin_y - th - tbox[1]),
            design.subtitle,
            font=t_font,
            fill=palette.accent,
        )


def render_design(
    design: Design,
    output_path: str | Path,
    product_colour: str,
    print_area: tuple[int, int],
) -> Path:
    """Render `design` onto a transparent canvas matching the print area."""
    width, height = print_area
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    palette = palette_for(product_colour, design.slug)

    if design.grid:
        _render_grid(image, design, palette)
    elif len(design.lines) == 1 and len(design.lines[0]) <= 6:
        _render_hero(image, design, palette)
    else:
        _render_stacked(image, design, palette)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path)
    return output_path
