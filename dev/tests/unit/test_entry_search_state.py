from types import SimpleNamespace

import pytest

import ui.entry_search_state as search_state
from core.entry_search import (
    SEARCH_MATCH_ALL_WORDS,
    SEARCH_MATCH_CONTAINS,
    SEARCH_SCOPE_ASSISTANT,
    SEARCH_SCOPE_SYSTEM,
    SEARCH_SCOPE_USER,
)


class FakeSessionState(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name, value):
        self[name] = value


def _patch_state(monkeypatch):
    state = FakeSessionState()
    monkeypatch.setattr(search_state, "st", SimpleNamespace(session_state=state))
    return state


def test_default_search_state_initialization(monkeypatch):
    state = _patch_state(monkeypatch)

    search_state.init_entry_search_state()

    assert state.entry_search_query == ""
    assert state.entry_search_include_system is False
    assert state.entry_search_include_user is True
    assert state.entry_search_include_assistant is True
    assert state.entry_search_match_mode == SEARCH_MATCH_CONTAINS
    assert state.entry_search_dataset_identifier == ""


def test_search_state_persists_for_same_dataset_identifier(monkeypatch):
    state = _patch_state(monkeypatch)
    search_state.sync_entry_search_state_for_dataset("dataset-a")
    search_state.set_entry_search_query("lantern")
    search_state.set_entry_search_scope(include_system=True, include_user=False)
    search_state.set_entry_search_match_mode(SEARCH_MATCH_ALL_WORDS)

    search_state.sync_entry_search_state_for_dataset("dataset-a")

    assert state.entry_search_query == "lantern"
    assert state.entry_search_include_system is True
    assert state.entry_search_include_user is False
    assert state.entry_search_match_mode == SEARCH_MATCH_ALL_WORDS


def test_search_state_resets_when_dataset_identifier_changes(monkeypatch):
    state = _patch_state(monkeypatch)
    search_state.sync_entry_search_state_for_dataset("dataset-a")
    search_state.set_entry_search_query("lantern")
    search_state.set_entry_search_scope(include_system=True, include_assistant=False)
    search_state.set_entry_search_match_mode(SEARCH_MATCH_ALL_WORDS)

    search_state.sync_entry_search_state_for_dataset("dataset-b")

    assert state.entry_search_query == ""
    assert state.entry_search_include_system is False
    assert state.entry_search_include_user is True
    assert state.entry_search_include_assistant is True
    assert state.entry_search_match_mode == SEARCH_MATCH_CONTAINS
    assert state.entry_search_dataset_identifier == "dataset-b"


def test_clear_query_preserves_scope_and_match_settings(monkeypatch):
    state = _patch_state(monkeypatch)
    search_state.init_entry_search_state()
    search_state.set_entry_search_query("archive")
    search_state.set_entry_search_scope(include_system=True, include_assistant=False)
    search_state.set_entry_search_match_mode(SEARCH_MATCH_ALL_WORDS)

    search_state.clear_entry_search_query()

    assert state.entry_search_query == ""
    assert state.entry_search_include_system is True
    assert state.entry_search_include_user is True
    assert state.entry_search_include_assistant is False
    assert state.entry_search_match_mode == SEARCH_MATCH_ALL_WORDS


def test_get_entry_search_options_returns_core_options(monkeypatch):
    _patch_state(monkeypatch)
    search_state.set_entry_search_scope(
        include_system=True,
        include_user=False,
        include_assistant=True,
    )
    search_state.set_entry_search_match_mode(SEARCH_MATCH_ALL_WORDS)

    options = search_state.get_entry_search_options()

    assert options.scopes == (SEARCH_SCOPE_SYSTEM, SEARCH_SCOPE_ASSISTANT)
    assert options.match_mode == SEARCH_MATCH_ALL_WORDS


def test_no_dataset_loaded_initializes_safely(monkeypatch):
    state = _patch_state(monkeypatch)

    search_state.sync_entry_search_state_for_dataset(None)

    assert state.entry_search_dataset_identifier == ""
    assert search_state.get_entry_search_options().scopes == (
        SEARCH_SCOPE_USER,
        SEARCH_SCOPE_ASSISTANT,
    )


def test_invalid_match_mode_is_repaired_when_reading_options(monkeypatch):
    state = _patch_state(monkeypatch)
    search_state.init_entry_search_state()
    state.entry_search_match_mode = "regex"

    options = search_state.get_entry_search_options()

    assert options.match_mode == SEARCH_MATCH_CONTAINS
    assert state.entry_search_match_mode == SEARCH_MATCH_CONTAINS


def test_set_match_mode_rejects_invalid_values(monkeypatch):
    _patch_state(monkeypatch)

    with pytest.raises(ValueError, match="Unsupported entry search match mode"):
        search_state.set_entry_search_match_mode("regex")
