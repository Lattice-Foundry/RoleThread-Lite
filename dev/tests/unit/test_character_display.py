from core.character_display import build_character_display_cache, get_turn_display_names
from core.rolethread_meta import ROLETHREAD_META_KEY
import core.character_display as character_display


def _entry(entry_uuid="entry-1"):
    return {
        ROLETHREAD_META_KEY: {"native": True, "entry_uuid": entry_uuid},
        "messages": [
            {"role": "system", "content": "System"},
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello"},
            {"role": "narrator", "content": "Aside"},
        ],
        "tags": [],
    }


def test_get_turn_display_names_uses_character_mapping_then_defaults(monkeypatch):
    monkeypatch.setattr(
        character_display,
        "get_character_display_for_entry",
        lambda entry_uuid: {1: "Scott"} if entry_uuid == "entry-1" else {},
    )

    assert get_turn_display_names(_entry(), "Player", "Muse") == {
        0: "System",
        1: "Scott",
        2: "Muse",
        3: "narrator",
    }


def test_get_turn_display_names_uses_cache_without_query(monkeypatch):
    def fail_query(_entry_uuid):
        raise AssertionError("single-entry query should not run")

    monkeypatch.setattr(character_display, "get_character_display_for_entry", fail_query)

    assert get_turn_display_names(
        _entry(),
        "Player",
        "Muse",
        {"entry-1": {2: "Emma"}},
    ) == {
        0: "System",
        1: "Player",
        2: "Emma",
        3: "narrator",
    }


def test_get_turn_display_names_handles_entries_without_uuid():
    entry = _entry()
    entry.pop(ROLETHREAD_META_KEY)

    assert get_turn_display_names(entry, "Player", "Muse") == {
        0: "System",
        1: "Player",
        2: "Muse",
        3: "narrator",
    }


def test_build_character_display_cache_queries_entry_uuids(monkeypatch):
    captured = {}

    def fake_bulk(entry_uuids):
        captured["entry_uuids"] = entry_uuids
        return {"entry-1": {1: "Scott"}}

    monkeypatch.setattr(character_display, "get_character_display_for_entries", fake_bulk)

    assert build_character_display_cache([_entry(), _entry("entry-2"), {}]) == {
        "entry-1": {1: "Scott"}
    }
    assert captured["entry_uuids"] == {"entry-1", "entry-2"}

