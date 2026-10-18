"""Listing titles and item specifics written for eBay's search crawler.

The crawler reads a title from the left, so it is built as
maker -> product name -> specs (model, format, size...) and then filled
to eBay's 80-character limit with true selling points; a short title
reads as a page with little information.

Fillers only say what is true of every export listing: brand new, genuine,
free shipping, shipped from Japan with tracking. Nothing about carriers we
do not use (FedEx, DHL) or stock we do not hold ("In Hand").

A title is changed once, to this format, and then left alone: the crawler
comes back to a page every few weeks at best, so changing it again sooner
only resets what it learned. The monthly review (export_review.py) is
where a title that still does not sell gets looked at.
"""
from __future__ import annotations

import re

TITLE_MAX = 80
# Marks a listing whose title has been rewritten to this format.
SEO_VERSION = 3

# Who made it, in the order eBay's own aspects are trusted: music is sold
# by artist, everything else by brand.
_MAKER_ASPECTS = ["Artist", "Brand", "Manufacturer"]
_MODEL_ASPECTS = ["Model", "MPN", "Manufacturer Part Number"]
# Specs worth the characters when the catalog title leaves them out.
# Not "Type": catalog values there can be odd ("Prototype" on a retail
# Beyblade stadium) and a wrong word in a title misleads buyers.
_SPEC_ASPECTS = ["Format", "Scale", "Size", "Number of Exposures", "Number in Pack", "Color", "Capacity"]
_FILLERS = ["New", "Free Shipping", "from Japan", "Genuine", "Tracked"]
_SHORT = {"Free Shipping": "F/S"}
_NOT_A_VALUE = {"", "does not apply", "n/a", "na", "unbranded", "none", "other"}


def _first(aspects: dict[str, list[str]], names: list[str]) -> str:
    for name in names:
        for value in aspects.get(name) or []:
            if value and value.strip().lower() not in _NOT_A_VALUE:
                return value.strip()
    return ""


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _contains(title: str, words: str) -> bool:
    """"1:64" is already in a title that says "1/64"."""
    return _norm(words) in _norm(title)


def _useful_spec(value: str) -> bool:
    """Catalog values that say something: a model or size, not "Beyblade
    Stadium" as a model or "1:1 (Life Size)" as a scale (both seen live)."""
    if not value or re.search(r"life\s*size|\b1\s*[:/]\s*1\b", value, re.I):
        return False
    return bool(re.search(r"\d", value)) or len(value.split()) == 1


def _fits(title: str, extra: str) -> bool:
    return len(f"{title} {extra}") <= TITLE_MAX


def seo_title(catalog_title: str, aspects: dict[str, list[str]]) -> str:
    """maker -> product -> specs -> fillers, at most 80 characters."""
    core = re.sub(r"\s{2,}", " ", catalog_title or "").strip()
    maker = _first(aspects, _MAKER_ASPECTS)
    # Already near the front ("Takara Tomy Beyblade" for brand "TOMY"): leave it.
    by_maker = bool(maker) and re.search(rf"\bby\s+{re.escape(maker)}\b", core, re.I)
    if maker and not core.lower().startswith(maker.lower()) and (by_maker or maker.lower() not in core[:25].lower()):
        # "Modal Soul by Nujabes" -> "Nujabes Modal Soul": the maker moves to the front.
        core = re.sub(rf"\s*(?:\bby\s+)?{re.escape(maker)}\b", "", core, count=1, flags=re.I).strip(" -,/|")
        core = f"{maker} {core}".strip()
    if len(core) > TITLE_MAX:
        return core[:TITLE_MAX].rsplit(" ", 1)[0]
    title = core
    for value in [_first(aspects, _MODEL_ASPECTS)] + [_first(aspects, [a]) for a in _SPEC_ASPECTS]:
        if not _useful_spec(value):
            continue
        if not _contains(title, value) and _fits(title, value):
            title = f"{title} {value}"
    for filler in _FILLERS:
        if _contains(title, filler):
            continue
        if _fits(title, filler):
            title = f"{title} {filler}"
        elif filler in _SHORT and _fits(title, _SHORT[filler]):
            title = f"{title} {_SHORT[filler]}"
    return title


def with_ean(aspects: dict[str, list[str]], jan: str) -> dict[str, list[str]]:
    """Item specifics plus the JAN as EAN, which buyers and the catalog match on."""
    out = dict(aspects)
    if jan and not out.get("EAN"):
        out["EAN"] = [jan]
    return out
