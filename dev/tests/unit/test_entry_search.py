from copy import deepcopy

import pytest

from core.entry_search import (
    EntrySearchOptions,
    SEARCH_MATCH_ALL_WORDS,
    SEARCH_MATCH_CONTAINS,
    SEARCH_MATCH_EXACT_PHRASE,
    SEARCH_SCOPE_ASSISTANT,
    SEARCH_SCOPE_SYSTEM,
    SEARCH_SCOPE_USER,
    build_entry_search_text,
    entry_matches_search,
    filter_entries_by_search,
    search_entries,
)


def _entry(system="System prompt", user="Hello there", assistant="Hi back"):
    return {
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
            {"role": "assistant", "content": assistant},
        ],
        "tags": [],
    }


def _pairs():
    return [
        ("uuid-1", _entry(user="A lantern glows in the archive.")),
        ("uuid-2", _entry(assistant="The captain checks the star map.")),
        ("uuid-3", _entry(system="Use a noir style.", user="Open the door.")),
    ]


def test_blank_query_returns_all_entries_unchanged():
    pairs = _pairs()

    assert filter_entries_by_search(pairs, "   ") == pairs
    result = search_entries(pairs, "")

    assert result.entry_uuids == ("uuid-1", "uuid-2", "uuid-3")
    assert result.count == 3


def test_contains_search_is_case_insensitive():
    pairs = _pairs()

    matches = filter_entries_by_search(pairs, "LANTERN")

    assert [entry_uuid for entry_uuid, _entry in matches] == ["uuid-1"]


def test_scope_controls_system_user_and_assistant_roles():
    entry = _entry(
        system="System-only oracle",
        user="User-only lantern",
        assistant="Assistant-only compass",
    )

    assert entry_matches_search(
        entry,
        "oracle",
        EntrySearchOptions(scopes=(SEARCH_SCOPE_SYSTEM,)),
    )
    assert entry_matches_search(
        entry,
        "lantern",
        EntrySearchOptions(scopes=(SEARCH_SCOPE_USER,)),
    )
    assert entry_matches_search(
        entry,
        "compass",
        EntrySearchOptions(scopes=(SEARCH_SCOPE_ASSISTANT,)),
    )
    assert not entry_matches_search(
        entry,
        "compass",
        EntrySearchOptions(scopes=(SEARCH_SCOPE_USER,)),
    )


def test_default_scope_excludes_system_messages():
    entry = _entry(system="Secret system phrase", user="Visible user text")

    assert not entry_matches_search(entry, "secret")
    assert entry_matches_search(
        entry,
        "secret",
        EntrySearchOptions(scopes=(SEARCH_SCOPE_SYSTEM,)),
    )


def test_all_words_mode_requires_every_query_word():
    entry = _entry(user="Lanterns glow across the archive shelves.")
    options = EntrySearchOptions(match_mode=SEARCH_MATCH_ALL_WORDS)

    assert entry_matches_search(entry, "archive lanterns", options)
    assert not entry_matches_search(entry, "archive ocean", options)


def test_exact_phrase_mode_matches_normalized_phrase():
    entry = _entry(user="The bright   archive lantern waits.")
    options = EntrySearchOptions(match_mode=SEARCH_MATCH_EXACT_PHRASE)

    assert entry_matches_search(entry, "bright archive lantern", options)
    assert not entry_matches_search(entry, "archive bright lantern", options)


def test_all_scopes_disabled_matches_blank_query_only():
    entry = _entry(user="Visible text")
    options = EntrySearchOptions(scopes=())

    assert entry_matches_search(entry, "", options)
    assert not entry_matches_search(entry, "visible", options)


def test_filter_preserves_input_order():
    pairs = [
        ("uuid-1", _entry(user="match one")),
        ("uuid-2", _entry(user="skip")),
        ("uuid-3", _entry(user="match two")),
    ]

    matches = filter_entries_by_search(pairs, "match")

    assert [entry_uuid for entry_uuid, _entry in matches] == ["uuid-1", "uuid-3"]


def test_search_does_not_mutate_entries():
    pairs = _pairs()
    original = deepcopy(pairs)

    filter_entries_by_search(pairs, "archive")

    assert pairs == original


def test_multi_turn_entries_search_all_selected_role_messages():
    entry = {
        "messages": [
            {"role": "system", "content": "Ignore this"},
            {"role": "user", "content": "First clue"},
            {"role": "assistant", "content": "A partial answer"},
            {"role": "user", "content": "Second lantern clue"},
        ],
        "tags": [],
    }
    options = EntrySearchOptions(match_mode=SEARCH_MATCH_ALL_WORDS)

    assert entry_matches_search(entry, "first lantern", options)


def test_missing_or_malformed_fields_degrade_safely():
    assert build_entry_search_text({}, (SEARCH_SCOPE_USER,)) == ""
    assert not entry_matches_search({"messages": "not-a-list"}, "anything")
    assert not entry_matches_search(
        {"messages": [{"role": "user"}, {"content": "missing role"}]},
        "missing",
    )


def test_unsupported_match_mode_raises_clear_error():
    with pytest.raises(ValueError, match="Unsupported entry search match mode"):
        entry_matches_search(
            _entry(user="hello"),
            "hello",
            EntrySearchOptions(match_mode="regex"),
        )


def test_search_entries_returns_matching_pairs_and_uuids():
    pairs = _pairs()

    result = search_entries(
        pairs,
        "star map",
        EntrySearchOptions(match_mode=SEARCH_MATCH_CONTAINS),
    )

    assert result.entry_uuids == ("uuid-2",)
    assert result.entry_pairs == (pairs[1],)
