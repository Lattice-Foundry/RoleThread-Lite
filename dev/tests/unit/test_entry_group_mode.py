from types import SimpleNamespace

from ui.ui_create import (
    ai_character_state_key,
    character_state_key,
    clear_character_state_values,
    entry_mode_key,
    matching_character_slug,
)


def test_entry_mode_keys_are_dataset_editor_scoped():
    assert entry_mode_key("create") == "create_entry_mode"
    assert entry_mode_key("full_edit") == "full_edit_entry_mode"


def test_character_state_keys_are_per_turn():
    assert character_state_key("create", 0) == "create_character_0"
    assert character_state_key("full_edit", 3) == "full_edit_character_3"
    assert ai_character_state_key("create") == "create_ai_character"


def test_clear_character_state_values_removes_group_character_keys_only():
    state = {
        "create_character_0": "scott",
        "create_new_character_0": "Logan",
        "create_ai_character": "emma",
        "create_turn_0": "Hi",
        "full_edit_character_0": "kai",
    }

    clear_character_state_values(state, "create")

    assert state == {
        "create_turn_0": "Hi",
        "full_edit_character_0": "kai",
    }


def test_clear_character_state_values_can_preserve_ai_character():
    state = {
        "create_character_0": "scott",
        "create_ai_character": "emma",
    }

    clear_character_state_values(state, "create", clear_ai=False)

    assert state == {"create_ai_character": "emma"}


def test_matching_character_slug_uses_normalized_settings_name():
    characters = [
        SimpleNamespace(slug="emma_frost", display_name="Emma Frost"),
        SimpleNamespace(slug="scott_summers", display_name="Scott Summers"),
    ]

    assert matching_character_slug("  Scott Summers  ", characters) == "scott_summers"
    assert matching_character_slug("Missing", characters) == ""
