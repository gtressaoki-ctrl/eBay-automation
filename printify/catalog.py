"""Helpers for picking a blueprint / print provider / variant set out of the
Printify catalog without hardcoding IDs that drift over time."""
from __future__ import annotations

from .client import PrintifyClient


def pick_blueprint(client: PrintifyClient, keyword: str, blueprint_id: int | None = None) -> dict:
    if blueprint_id is not None:
        for blueprint in client.list_blueprints():
            if blueprint["id"] == blueprint_id:
                return blueprint
        raise ValueError(f"No blueprint with id={blueprint_id} found in the Printify catalog.")

    matches = client.find_blueprints(keyword)
    if not matches:
        raise ValueError(f"No blueprint title matched keyword '{keyword}'.")
    return matches[0]


def pick_print_provider(client: PrintifyClient, blueprint_id: int, print_provider_id: int | None = None) -> dict:
    providers = client.list_print_providers(blueprint_id)
    if not providers:
        raise ValueError(f"Blueprint {blueprint_id} has no print providers available.")
    if print_provider_id is not None:
        for provider in providers:
            if provider["id"] == print_provider_id:
                return provider
        raise ValueError(f"Print provider {print_provider_id} not offered for blueprint {blueprint_id}.")
    # Default: the provider offering the most variants tends to give the
    # widest size/colour range, which is a reasonable default for a new brand.
    best = None
    best_count = -1
    for provider in providers:
        variants = client.list_variants(blueprint_id, provider["id"]).get("variants", [])
        if len(variants) > best_count:
            best, best_count = provider, len(variants)
    return best


PREFERRED_POSITIONS = ["front", "default"]


def pick_placeholder_positions(variants_response: dict) -> list[str]:
    """Return a single print position (e.g. just the front of a T-shirt),
    not every placeholder a blueprint exposes (front/back/sleeves/neck),
    since we're only placing one design."""
    available: list[str] = []
    for variant in variants_response.get("variants", []):
        for placeholder in variant.get("placeholders", []):
            position = placeholder.get("position")
            if position and position not in available:
                available.append(position)
    if not available:
        return ["front"]
    for preferred in PREFERRED_POSITIONS:
        if preferred in available:
            return [preferred]
    return [available[0]]


# Printify caps a single product at 100 enabled variants. A well-known brand
# storefront doesn't need every colour Printify offers, so default to a
# curated palette/size range and fall back to "first N" for blueprints (e.g.
# stickers) that don't use colour/size options at all.
PRINTIFY_MAX_VARIANTS = 100
DEFAULT_COLORS = [
    "Black", "White", "Navy", "Sport Grey", "Red", "Royal", "Dark Heather", "Military Green",
]
DEFAULT_SIZES = ["S", "M", "L", "XL", "2XL"]


def select_variants(
    variants: list[dict],
    max_variants: int | None = None,
    preferred_colors: list[str] | None = None,
    preferred_sizes: list[str] | None = None,
) -> list[dict]:
    max_variants = max_variants or PRINTIFY_MAX_VARIANTS
    preferred_colors = preferred_colors or DEFAULT_COLORS
    preferred_sizes = preferred_sizes or DEFAULT_SIZES

    has_color = any("color" in v.get("options", {}) for v in variants)
    has_size = any("size" in v.get("options", {}) for v in variants)

    filtered = [
        v
        for v in variants
        if (not has_color or v["options"].get("color") in preferred_colors)
        and (not has_size or v["options"].get("size") in preferred_sizes)
    ]
    if not filtered:
        filtered = variants
    if len(filtered) > max_variants:
        filtered = filtered[:max_variants]
    return filtered
