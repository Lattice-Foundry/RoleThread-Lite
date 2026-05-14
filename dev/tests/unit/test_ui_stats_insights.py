"""Tests for pure Insights page helper calculations."""

from ui.ui_stats import (
    _long_exchange_entry_uuids,
    _narrative_ratio_distribution_rows,
    _top_tag_usage_rows,
)


def _entry(entry_uuid: str, tags: list[str] | None = None, exchanges: int = 1) -> dict:
    messages = [{"role": "system", "content": "You are helpful."}]
    for idx in range(exchanges):
        messages.append({"role": "user", "content": f"Question {idx}"})
        messages.append({"role": "assistant", "content": f"Answer {idx}"})
    return {
        "messages": messages,
        "tags": tags or [],
        "_loreforge": {"entry_uuid": entry_uuid},
    }


def test_top_tag_usage_rows_counts_tagged_entry_share() -> None:
    entries = [
        _entry("one", ["romance", "slow_burn"]),
        _entry("two", ["romance"]),
        _entry("three", []),
    ]

    rows = _top_tag_usage_rows(
        entries,
        {"romance": "Genre / Romance", "slow_burn": "Tone / Slow Burn"},
    )

    assert rows[0] == {
        "Tag": "Genre / Romance",
        "Entries": 2,
        "Share": "100.0%",
    }
    assert rows[1] == {
        "Tag": "Tone / Slow Burn",
        "Entries": 1,
        "Share": "50.0%",
    }


def test_narrative_ratio_distribution_rows_bins_entries() -> None:
    rows = _narrative_ratio_distribution_rows((0.0, 0.21, 0.45, 0.79, 1.0))

    assert rows == [
        {"Dialogue Density": "0-20%", "Entries": 1},
        {"Dialogue Density": "20-40%", "Entries": 1},
        {"Dialogue Density": "40-60%", "Entries": 1},
        {"Dialogue Density": "60-80%", "Entries": 1},
        {"Dialogue Density": "80-100%", "Entries": 1},
    ]


def test_long_exchange_entry_uuids_flags_split_candidates() -> None:
    entries = [
        _entry("short", exchanges=7),
        _entry("long", exchanges=8),
        _entry("longer", exchanges=10),
    ]

    assert _long_exchange_entry_uuids(entries) == ["long", "longer"]
