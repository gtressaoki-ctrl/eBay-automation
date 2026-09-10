"""Generate original, copyright-free typography designs for POD products.

v1 keeps this deliberately simple and deterministic: turn a niche keyword
into a short uppercase phrase and render it as centered text on a
transparent-background PNG using an open-license (SIL OFL) Google Font.
No third-party artwork, logos, or characters are ever used, so there is
no trademark/copyright exposure. Swap in an image-generation model later
for more visual variety once the pipeline is proven.
"""
from __future__ import annotations

import re
import textwrap
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont

_ASSETS_DIR = Path(__file__).resolve().parent.parent.parent / "assets"
_FONT_DIR = _ASSETS_DIR / "fonts"
_FONT_URL = "https://github.com/google/fonts/raw/main/ofl/anton/Anton-Regular.ttf"
_FONT_PATH = _FONT_DIR / "Anton-Regular.ttf"

_SUFFIXES_TO_STRIP = ["shirt", "mug", "hoodie", "t-shirt", "tee", "gift"]

# A small, hand-picked, brand-neutral color palette (hex) reused across
# designs so the shop has a consistent look.
PALETTE = ["#1d1d1d", "#2f3e46", "#6a4c93", "#d64550", "#1b998b"]


def ensure_font() -> Path:
    _FONT_DIR.mkdir(parents=True, exist_ok=True)
    if not _FONT_PATH.exists():
        resp = requests.get(_FONT_URL, timeout=30)
        resp.raise_for_status()
        _FONT_PATH.write_bytes(resp.content)
    return _FONT_PATH


def keyword_to_phrase(keyword: str) -> str:
    phrase = keyword.lower()
    for suffix in _SUFFIXES_TO_STRIP:
        phrase = re.sub(rf"\b{re.escape(suffix)}\b", "", phrase)
    phrase = re.sub(r"\s+", " ", phrase).strip()
    return phrase.upper() or keyword.upper()


def _fit_font(draw: ImageDraw.ImageDraw, lines: list[str], font_path: Path, max_width: int, max_height: int) -> ImageFont.FreeTypeFont:
    size = 400
    while size > 20:
        font = ImageFont.truetype(str(font_path), size)
        line_heights = []
        max_line_width = 0
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            max_line_width = max(max_line_width, bbox[2] - bbox[0])
            line_heights.append(bbox[3] - bbox[1])
        total_height = sum(line_heights) + (len(lines) - 1) * (size // 4)
        if max_line_width <= max_width and total_height <= max_height:
            return font
        size -= 10
    return ImageFont.truetype(str(font_path), 20)


def render_design(phrase: str, output_path: str | Path, color: str, width: int = 3000, height: int = 3600) -> Path:
    font_path = ensure_font()
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    lines = textwrap.wrap(phrase, width=max(6, len(phrase) // 2)) or [phrase]
    padding = int(width * 0.1)
    font = _fit_font(draw, lines, font_path, width - 2 * padding, height - 2 * padding)

    line_bboxes = [draw.textbbox((0, 0), line, font=font) for line in lines]
    line_heights = [b[3] - b[1] for b in line_bboxes]
    gap = font.size // 3
    total_height = sum(line_heights) + gap * (len(lines) - 1)
    y = (height - total_height) // 2

    for line, bbox, line_height in zip(lines, line_bboxes, line_heights):
        line_width = bbox[2] - bbox[0]
        x = (width - line_width) // 2
        draw.text((x, y - bbox[1]), line, font=font, fill=color)
        y += line_height + gap

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path)
    return output_path


def generate_design_for_niche(keyword: str, output_path: str | Path, color: str | None = None) -> tuple[Path, str]:
    phrase = keyword_to_phrase(keyword)
    chosen_color = color or PALETTE[hash(keyword) % len(PALETTE)]
    path = render_design(phrase, output_path, chosen_color)
    return path, phrase
