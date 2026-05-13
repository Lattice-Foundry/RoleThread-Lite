"""Pure dataset entry search helpers."""
from __future__ import annotations

from dataclasses import dataclass

SEARCH_SCOPE_SYSTEM = "system"
SEARCH_SCOPE_USER = "user"
SEARCH_SCOPE_ASSISTANT = "assistant"
SEARCH_SCOPES = (
    SEARCH_SCOPE_SYSTEM,
    SEARCH_SCOPE_USER,
    SEARCH_SCOPE_ASSISTANT,
)

SEARCH_MATCH_CONTAINS = "contains"
SEARCH_MATCH_ALL_WORDS = "all_words"
SEARCH_MATCH_EXACT_PHRASE = "exact_phrase"
SEARCH_MATCH_MODES = (
    SEARCH_MATCH_CONTAINS,
    SEARCH_MATCH_ALL_WORDS,
    SEARCH_MATCH_EXACT_PHRASE,
)

DEFAULT_SEARCH_SCOPES = (
    SEARCH_SCOPE_USER,
    SEARCH_SCOPE_ASSISTANT,
)


@dataclass(frozen=True)
class EntrySearchOptions:
    """Options controlling deterministic loaded-entry search."""

    scopes: tuple[str, ...] = DEFAULT_SEARCH_SCOPES
    match_mode: str = SEARCH_MATCH_CONTAINS


@dataclass(frozen=True)
class EntrySearchResult:
    """Search result carrying matching entry UUIDs and pairs."""

    query: str
    options: EntrySearchOptions
    entry_uuids: tuple[str, ...]
    entry_pairs: tuple[tuple[str, dict], ...]

    @property
    def count(self) -> int:
        """Return the number of matching entries."""

        return len(self.entry_pairs)


def build_entry_search_text(
    entry: dict,
    scopes: tuple[str, ...] | list[str] | set[str] = DEFAULT_SEARCH_SCOPES,
) -> str:
    """Return joined message content for roles included in ``scopes``."""

    if not isinstance(entry, dict):
        return ""
    enabled_scopes = set(_normalize_scopes(scopes))
    if not enabled_scopes:
        return ""

    messages = entry.get("messages")
    if not isinstance(messages, list):
        return ""

    content_parts: list[str] = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        role = message.get("role")
        if not isinstance(role, str):
            continue
        if role.strip().casefold() not in enabled_scopes:
            continue
        content = message.get("content")
        if isinstance(content, str):
            content_parts.append(content)
    return "\n".join(content_parts)


def entry_matches_search(
    entry: dict,
    query: str,
    options: EntrySearchOptions | None = None,
) -> bool:
    """Return True when ``entry`` matches ``query`` under ``options``."""

    options = options or EntrySearchOptions()
    normalized_query = _normalize_text(query)
    if not normalized_query:
        return True
    if not _normalize_scopes(options.scopes):
        return False

    searchable_text = _normalize_text(build_entry_search_text(entry, options.scopes))
    if not searchable_text:
        return False

    if options.match_mode == SEARCH_MATCH_CONTAINS:
        return normalized_query in searchable_text
    if options.match_mode == SEARCH_MATCH_ALL_WORDS:
        return all(word in searchable_text for word in normalized_query.split())
    if options.match_mode == SEARCH_MATCH_EXACT_PHRASE:
        return normalized_query in searchable_text
    raise ValueError(f"Unsupported entry search match mode: {options.match_mode}")


def filter_entries_by_search(
    entry_pairs: list[tuple[str, dict]] | tuple[tuple[str, dict], ...],
    query: str,
    options: EntrySearchOptions | None = None,
) -> list[tuple[str, dict]]:
    """Return entry pairs matching ``query`` while preserving input order."""

    options = options or EntrySearchOptions()
    if not _normalize_text(query):
        return list(entry_pairs)
    return [
        (entry_uuid, entry)
        for entry_uuid, entry in entry_pairs
        if entry_matches_search(entry, query, options)
    ]


def search_entries(
    entry_pairs: list[tuple[str, dict]] | tuple[tuple[str, dict], ...],
    query: str,
    options: EntrySearchOptions | None = None,
) -> EntrySearchResult:
    """Search entry pairs and return matching UUIDs plus matching pairs."""

    options = options or EntrySearchOptions()
    matches = filter_entries_by_search(entry_pairs, query, options)
    return EntrySearchResult(
        query=query,
        options=options,
        entry_uuids=tuple(entry_uuid for entry_uuid, _entry in matches),
        entry_pairs=tuple(matches),
    )


def _normalize_text(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.casefold().strip().split())


def _normalize_scopes(
    scopes: tuple[str, ...] | list[str] | set[str],
) -> tuple[str, ...]:
    normalized: list[str] = []
    for scope in scopes or ():
        if not isinstance(scope, str):
            continue
        normalized_scope = scope.strip().casefold()
        if normalized_scope in SEARCH_SCOPES and normalized_scope not in normalized:
            normalized.append(normalized_scope)
    return tuple(normalized)
