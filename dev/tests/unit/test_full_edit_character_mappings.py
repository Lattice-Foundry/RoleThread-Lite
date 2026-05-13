from types import SimpleNamespace

import ui.ui_edit_entries as edit_entries
from ui.ui_create import entry_mode_key


class FakeSessionState(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name, value):
        self[name] = value


def _entry():
    return {
        "messages": [
            {"role": "system", "content": "System"},
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello"},
            {"role": "user", "content": "Again"},
            {"role": "assistant", "content": "Back"},
        ],
        "tags": ["known", "unknown"],
    }


def _patch_full_edit_state(monkeypatch, mappings):
    state = FakeSessionState()
    monkeypatch.setattr(edit_entries, "st", SimpleNamespace(session_state=state))
    monkeypatch.setattr(edit_entries, "get_loaded_entry_by_uuid", lambda _uuid: _entry())
    monkeypatch.setattr(edit_entries, "get_entry_character_turns", lambda _uuid: mappings)
    return state


def test_apply_existing_character_mappings_uses_system_offset():
    state = FakeSessionState()
    mappings = [
        SimpleNamespace(turn_index=0, character=SimpleNamespace(slug="system")),
        SimpleNamespace(turn_index=1, character=SimpleNamespace(slug="scott")),
        SimpleNamespace(turn_index=2, character=SimpleNamespace(slug="emma")),
    ]

    applied = edit_entries.apply_existing_character_mappings_to_full_edit_state(
        state,
        mappings,
    )

    assert applied == 2
    assert state["full_edit_character_0"] == "scott"
    assert state["full_edit_character_1"] == "emma"
    assert "full_edit_character_-1" not in state


def test_load_full_edit_buffer_loads_mappings_and_switches_to_group(monkeypatch):
    state = _patch_full_edit_state(
        monkeypatch,
        [
            SimpleNamespace(turn_index=1, character=SimpleNamespace(slug="scott")),
            SimpleNamespace(turn_index=2, character=SimpleNamespace(slug="emma")),
            SimpleNamespace(turn_index=4, character=SimpleNamespace(slug="emma")),
        ],
    )

    loaded = edit_entries.load_full_edit_buffer("entry-uuid", {"cat": ["known"]})

    assert loaded is True
    assert state[entry_mode_key("full_edit")] == "group"
    assert state["_full_edit_entry_mode_previous"] == "group"
    assert state["full_edit_character_0"] == "scott"
    assert state["full_edit_character_1"] == "emma"
    assert state["full_edit_character_3"] == "emma"
    assert state["full_edit_turn_0"] == "Hi"
    assert state["full_edit_unknown_tags"] == ["unknown"]


def test_load_full_edit_buffer_without_mappings_stays_standard(monkeypatch):
    state = _patch_full_edit_state(monkeypatch, [])
    state["full_edit_character_0"] = "stale"
    state["full_edit_entry_mode"] = "group"

    loaded = edit_entries.load_full_edit_buffer("entry-uuid", {"cat": ["known"]})

    assert loaded is True
    assert state[entry_mode_key("full_edit")] == "standard"
    assert state["_full_edit_entry_mode_previous"] == "standard"
    assert "full_edit_character_0" not in state
