#!/usr/bin/env python3
"""Turn a product photo into a Pinterest Idea Pin title + description.

Pinterest has no public API for creating Idea Pins under third-party
automation, so this is a manual tool like scripts/list_printify_catalog.py:
run it locally, read the output, paste it into the Idea Pin composer
yourself. See docs/SETUP.md for how to get an ANTHROPIC_API_KEY and set
the brand/affiliate-link variables this draws on.

Usage:
    ANTHROPIC_API_KEY=... python scripts/generate_idea_pin.py photo.jpg
    ANTHROPIC_API_KEY=... python scripts/generate_idea_pin.py photo.jpg \\
        --context "11oz ceramic mug, sarcastic-coffee theme, dishwasher safe"
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ebay_automation.config import load_config  # noqa: E402
from ebay_automation.idea_pin_gen import IdeaPinGenError, generate_idea_pin_content  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("image", type=Path, help="Path to the product photo (jpg/png/webp/gif)")
    parser.add_argument("--context", default="", help="Optional extra context about the photo")
    args = parser.parse_args()

    if not args.image.exists():
        parser.error(f"No such file: {args.image}")

    config = load_config()
    try:
        content = generate_idea_pin_content(args.image, config, extra_context=args.context)
    except IdeaPinGenError as exc:
        print(f"Failed to generate content: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"Title ({len(content.title)} chars):\n{content.title}\n")
    print(f"Description ({len(content.description)} chars):\n{content.description}")


if __name__ == "__main__":
    main()
