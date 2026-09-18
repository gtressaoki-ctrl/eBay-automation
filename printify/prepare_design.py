"""Turn the flat white-background artwork scan into a transparent PNG so it
prints as just the ink (on the shirt/sticker's own color) instead of a white
rectangle. Also required for Printify's kiss-cut stickers, which trace the
cut line from the image's alpha channel.

Usage:
    python -m printify.prepare_design assets/designs/aries-ram-lineart.jpg \
        assets/designs/aries-ram-lineart-transparent.png
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image

# Pixels lighter than WHITE_THRESHOLD are treated as background (fully
# transparent). Pixels darker than WHITE_THRESHOLD - BAND keep their
# original color at full opacity. In between, alpha ramps smoothly so the
# cut edge isn't jagged.
WHITE_THRESHOLD = 245
BAND = 40


def remove_white_background(
    input_path: str | Path,
    output_path: str | Path,
    white_threshold: int = WHITE_THRESHOLD,
    band: int = BAND,
    trim: bool = True,
) -> Path:
    image = Image.open(input_path).convert("RGB")
    rgb = np.array(image)
    gray = np.array(image.convert("L")).astype(np.float32)

    alpha = np.clip((white_threshold - gray) / band * 255.0, 0, 255).astype(np.uint8)

    rgba = np.dstack([rgb, alpha])
    result = Image.fromarray(rgba, mode="RGBA")

    if trim:
        bbox = result.getbbox()
        if bbox:
            result = result.crop(bbox)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.save(output_path)
    return output_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("input", help="Source image (e.g. a JPEG scan on a white background).")
    parser.add_argument("output", help="Where to write the transparent PNG.")
    parser.add_argument("--white-threshold", type=int, default=WHITE_THRESHOLD)
    parser.add_argument("--band", type=int, default=BAND)
    parser.add_argument("--no-trim", action="store_true", help="Keep the original canvas size instead of cropping to the opaque content.")
    args = parser.parse_args(argv)

    out = remove_white_background(
        args.input, args.output, args.white_threshold, args.band, trim=not args.no_trim
    )
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
