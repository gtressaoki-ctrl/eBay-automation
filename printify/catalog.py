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


def pick_placeholder_positions(variants_response: dict) -> list[str]:
    positions: list[str] = []
    for variant in variants_response.get("variants", []):
        for placeholder in variant.get("placeholders", []):
            position = placeholder.get("position")
            if position and position not in positions:
                positions.append(position)
    return positions or ["front"]
