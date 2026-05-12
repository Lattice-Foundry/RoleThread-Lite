"""Pure helpers for deciding which entry editor can handle an entry."""
from __future__ import annotations

from core.dataset import analyze_entry
from core.entry_analysis import (
    BASE_INVALID_TAG_VALUE,
    BASE_NOT_DICT,
    BASE_TAGS_NOT_LIST,
    CHATML_MESSAGE_NOT_DICT,
    CHATML_MESSAGES_NOT_LIST,
    CHATML_MISSING_MESSAGES,
    CHATML_MISSING_SYSTEM_ROLE,
    CHATML_SYSTEM_NOT_DICT,
    CHATML_WRONG_ROLE,
)

_QUICK_EDIT_BLOCKING_CODES = {
    BASE_NOT_DICT,
    BASE_TAGS_NOT_LIST,
    BASE_INVALID_TAG_VALUE,
    CHATML_MISSING_MESSAGES,
    CHATML_MESSAGES_NOT_LIST,
    CHATML_SYSTEM_NOT_DICT,
    CHATML_MISSING_SYSTEM_ROLE,
    CHATML_MESSAGE_NOT_DICT,
    CHATML_WRONG_ROLE,
}


def requires_full_edit_for_quick_edit(entry: dict) -> bool:
    """Return True when Quick Edit cannot safely repair this entry."""

    result = analyze_entry(entry)
    codes = {diagnostic.code for diagnostic in result.diagnostics}
    if codes & _QUICK_EDIT_BLOCKING_CODES:
        return True

    messages = entry.get("messages") if isinstance(entry, dict) else None
    if not isinstance(messages, list):
        return True
    return not any(
        isinstance(message, dict) and message.get("role") in {"user", "assistant"}
        for message in messages
    )
