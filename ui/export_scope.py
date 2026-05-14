"""Helpers for resolving Export page entry scope."""

from __future__ import annotations


EXPORT_SCOPE_ALL = "all"
EXPORT_SCOPE_SELECTED_FILTERED = "selected_filtered"


def scoped_export_pairs(
    all_pairs: list[tuple[str, dict]],
    *,
    selected_uuids: set[str] | None = None,
    filtered_pairs: list[tuple[str, dict]] | None = None,
    filters_active: bool = False,
) -> tuple[list[tuple[str, dict]], str]:
    """Return export pairs and a user-facing scope label."""

    selected = selected_uuids or set()
    if selected:
        return (
            [
                (entry_uuid, entry)
                for entry_uuid, entry in all_pairs
                if entry_uuid in selected
            ],
            "selected entries",
        )
    if filters_active and filtered_pairs is not None:
        return filtered_pairs, "filtered entries"
    return all_pairs, "all entries"
