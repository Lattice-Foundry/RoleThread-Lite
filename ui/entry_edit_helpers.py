"""Pure helpers for deciding which entry editor can handle an entry."""
from __future__ import annotations

from core.dataset import analyze_entry
from core.entry_analysis import (
    BASE_MISSING_TAGS,
    BASE_NOT_DICT,
    CHATML_EMPTY_SYSTEM_CONTENT,
    CHATML_INSUFFICIENT_MESSAGES,
    CHATML_MISSING_SYSTEM_ROLE,
    CHATML_MESSAGES_NOT_LIST,
    CHATML_MISSING_MESSAGES,
    CHATML_SYSTEM_NOT_DICT,
    RepairKind,
)

_QUICK_EDIT_BLOCKING_CODES = {
    BASE_MISSING_TAGS,
    BASE_NOT_DICT,
    CHATML_EMPTY_SYSTEM_CONTENT,
    CHATML_INSUFFICIENT_MESSAGES,
    CHATML_MISSING_SYSTEM_ROLE,
    CHATML_MISSING_MESSAGES,
    CHATML_MESSAGES_NOT_LIST,
    CHATML_SYSTEM_NOT_DICT,
}


def requires_full_edit_for_quick_edit(entry: object) -> bool:
    """Return True when Quick Edit cannot safely repair this entry."""

    result = analyze_entry(entry)
    codes = {diagnostic.code for diagnostic in result.diagnostics}
    if codes & _QUICK_EDIT_BLOCKING_CODES:
        return True

    messages = entry.get("messages") if isinstance(entry, dict) else None
    if not isinstance(messages, list):
        return True
    return len(messages) == 0


def has_entry_notification_issue(entry: object, errors: list[str] | None = None) -> bool:
    """Return True when an entry should show a browser warning marker."""

    if errors:
        return True
    result = analyze_entry(entry)
    return any(
        diagnostic.fixable and diagnostic.repair_kind == RepairKind.AUTOMATIC
        for diagnostic in result.diagnostics
    )
