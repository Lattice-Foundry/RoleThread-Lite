"""Small text formatting helpers shared by UI and service messages."""
from __future__ import annotations


def count_phrase(count: int, singular: str, plural: str | None = None) -> str:
    """Return a human-readable counted noun phrase."""

    noun = singular if count == 1 else (plural or f"{singular}s")
    return f"{count} {noun}"
