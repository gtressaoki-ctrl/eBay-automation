"""Design themes: what actually goes on the product, and what to sell it as.

The first version of this pipeline derived the printed phrase from the
eBay search keyword by deleting the word "shirt" — which is how a mug
ended up reading "CAMPING LIFE". A search query is not a design. This
module keeps the two separate: `search_keyword` is what we measure demand
with, `designs` is what a buyer would actually want on their desk.

Everything here is original wording or public-domain material (kanji
characters are not copyrightable), so there is no trademark or copyright
exposure in what gets printed.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Design:
    """One printable design."""

    slug: str
    # Lines of the main statement, already broken the way they should read.
    # Empty for grid designs, which carry their content in `grid` instead.
    lines: tuple[str, ...] = ()
    # Index of the line that carries the accent colour, if any.
    accent_line: int | None = None
    # Small supporting line under the statement.
    subtitle: str | None = None
    # Dense character grid (kanji sets) rendered instead of `lines`.
    grid: tuple[str, ...] = ()
    # Romaji/meaning captions shown under each grid cell.
    grid_captions: tuple[str, ...] = ()


@dataclass(frozen=True)
class Theme:
    """A group of designs sold under one search intent."""

    slug: str
    # Phrase used to measure live demand on eBay.
    search_keyword: str
    # eBay listing title template; `{design}` is the design's headline.
    title_template: str
    keywords: tuple[str, ...]
    designs: tuple[Design, ...]


def _headline(design: Design) -> str:
    if design.grid:
        return design.subtitle or design.slug.replace("-", " ").title()
    return " ".join(design.lines)


def headline(design: Design) -> str:
    """Human-readable name for the design, used in titles and issue subjects."""
    return _headline(design)


SARCASTIC_COFFEE = Theme(
    slug="sarcastic-coffee",
    search_keyword="funny sarcastic mug gift",
    title_template="{design} - Funny Sarcastic Coffee Mug 11oz Novelty Gift",
    keywords=("funny mug", "sarcastic gift", "coffee lover", "office gift", "novelty mug"),
    designs=(
        Design(
            slug="until-this-is-empty",
            lines=("DON'T TALK", "TO ME UNTIL", "THIS IS EMPTY"),
            accent_line=2,
        ),
        Design(
            slug="caffeine-and-spite",
            lines=("RUNNING ON", "CAFFEINE", "AND SPITE"),
            accent_line=1,
        ),
        Design(
            slug="technically-awake",
            lines=("TECHNICALLY", "I'M AWAKE"),
            accent_line=1,
        ),
        Design(
            slug="should-have-been-an-email",
            lines=("I SURVIVED", "ANOTHER MEETING", "THAT SHOULD HAVE", "BEEN AN EMAIL"),
            accent_line=3,
        ),
        Design(
            slug="professional-overthinker",
            lines=("PROFESSIONAL", "OVERTHINKER"),
            accent_line=1,
            subtitle="SINCE BIRTH",
        ),
        Design(
            slug="explaining-why-im-right",
            lines=("I'M NOT ARGUING", "I'M EXPLAINING", "WHY I'M RIGHT"),
            accent_line=2,
        ),
        Design(
            slug="first-coffee",
            lines=("FIRST COFFEE", "THEN YOUR", "PROBLEMS"),
            accent_line=0,
        ),
        Design(
            slug="blood-type-coffee",
            lines=("BLOOD TYPE:", "COFFEE"),
            accent_line=1,
        ),
    ),
)


JAPANESE_KANJI = Theme(
    slug="japanese-kanji",
    search_keyword="japanese kanji mug",
    title_template="{design} - Japanese Kanji Ceramic Coffee Mug 11oz Gift",
    keywords=("japanese mug", "kanji", "japan gift", "sushi", "japanese art"),
    designs=(
        Design(
            slug="fish-kanji",
            grid=("鮪", "鯛", "鰻", "鰹", "鯖", "鮭", "鰤", "鱚", "鮃", "鰺", "鱈", "鮎"),
            grid_captions=(
                "MAGURO", "TAI", "UNAGI", "KATSUO", "SABA", "SAKE",
                "BURI", "KISU", "HIRAME", "AJI", "TARA", "AYU",
            ),
            subtitle="SUSHI FISH KANJI",
        ),
        Design(
            slug="zodiac-kanji",
            grid=("子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"),
            grid_captions=(
                "RAT", "OX", "TIGER", "RABBIT", "DRAGON", "SNAKE",
                "HORSE", "GOAT", "MONKEY", "ROOSTER", "DOG", "BOAR",
            ),
            subtitle="JAPANESE ZODIAC",
        ),
        Design(
            slug="ichigo-ichie",
            lines=("一期一会",),
            subtitle="ICHIGO ICHIE - ONE TIME, ONE MEETING",
        ),
        Design(
            slug="ganbaru",
            lines=("頑張る",),
            subtitle="GANBARU - TO PERSEVERE",
        ),
    ),
)


THEMES: tuple[Theme, ...] = (SARCASTIC_COFFEE, JAPANESE_KANJI)


def all_designs() -> list[tuple[Theme, Design]]:
    return [(theme, design) for theme in THEMES for design in theme.designs]


def find_design(theme_slug: str, design_slug: str) -> tuple[Theme, Design] | None:
    for theme, design in all_designs():
        if theme.slug == theme_slug and design.slug == design_slug:
            return theme, design
    return None


def pick_unused_design(theme: Theme, used_slugs: set[str]) -> Design | None:
    """Next design in this theme that has not been listed yet."""
    for design in theme.designs:
        if f"{theme.slug}/{design.slug}" not in used_slugs:
            return design
    return None
