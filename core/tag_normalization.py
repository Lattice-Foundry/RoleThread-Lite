"""Pure tag normalization helpers.

This module owns canonical tag string conversion only. It must not touch
datasets, databases, Streamlit, or session state.
"""
import re
from dataclasses import dataclass


_UPPERCASE_WORDS: frozenset[str] = frozenset({"ai", "id", "llm", "rp"})


@dataclass(frozen=True)
class NormalizedTag:
    """Canonical representation of one raw tag value."""

    raw: str
    slug: str
    display_name: str
    changed: bool


def normalize_tag(value: str) -> NormalizedTag:
    """Normalize one tag value into a slug and display name."""
    raw = value if isinstance(value, str) else ""
    slug = raw.strip().lower()
    slug = slug.replace("&", " ")
    slug = re.sub(r"[^a-z0-9]+", "_", slug)
    slug = re.sub(r"_+", "_", slug).strip("_")
    words = [
        word.upper() if word.lower() in _UPPERCASE_WORDS else word.capitalize()
        for word in slug.split("_")
        if word
    ]
    display_name = " ".join(words)
    return NormalizedTag(
        raw=raw,
        slug=slug,
        display_name=display_name,
        changed=(raw != slug),
    )
