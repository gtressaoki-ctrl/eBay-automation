"""Pin wording for a listing, shared by the API publisher and the CSV export."""
from __future__ import annotations

import re

KEYWORDS = "funny coffee mug, sarcastic mug, office gift, coworker gift, coffee lover gift"


def sentence(headline: str) -> str:
    text = headline.capitalize()
    text = re.sub(r"\bi('m|'ve|'d)?\b", lambda m: "I" + (m.group(1) or ""), text)
    return re.sub(r"([.!?] )([a-z])", lambda m: m.group(1) + m.group(2).upper(), text)


def title(headline: str) -> str:
    words = re.sub(r"\b(\w)", lambda m: m.group(1).upper(), headline.lower())
    words = re.sub(r"'([A-Z])", lambda m: "'" + m.group(1).lower(), words)
    return f"{words} – Funny Sarcastic Coffee Mug"[:100]


def description(headline: str) -> str:
    return (
        f'"{sentence(headline)}" — an 11oz ceramic coffee mug for anyone who runs on coffee '
        "and sarcasm. Funny office gift for coworkers, bosses and friends. Dishwasher and microwave "
        "safe. #funnymug #coffeemug #officegift #sarcasticgifts #giftsforcoworkers"
    )[:500]


def image_url(entry: dict) -> str:
    # Printify's mockup URL works without its camera query string, and
    # Pinterest's CSV importer wants a URL ending in the file extension.
    return entry["image_url"].split("?")[0]


def pinnable(entry: dict) -> bool:
    return (
        entry.get("status") == "published"
        and bool(entry.get("listing_url"))
        and bool(entry.get("image_url"))
        and bool(entry.get("headline"))
    )
