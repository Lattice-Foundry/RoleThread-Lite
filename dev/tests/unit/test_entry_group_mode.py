from types import SimpleNamespace

from ui.ui_create import (
    apply_pending_character_assignment,
    character_state_key,
    clear_character_state_values,
    default_character_slug_for_turn,
    entry_mode_key,
    group_character_display_names_from_state,
    matching_character_slug,
    pending_character_state_key,
)


def test_entry_mode_keys_are_dataset_editor_scoped():
    assert entry_mode_key("create") == "create_entry_mode"
    assert entry_mode_key("full_edit") == "full_edit_entry_mode"


def test_character_state_keys_are_per_turn():
    assert character_state_key("create", 0) == "create_character_0"
    assert character_state_key("full_edit", 3) == "full_edit_character_3"
    assert pending_character_state_key("create", 0) == "create_pending_character_0"


def test_clear_character_state_values_removes_group_character_keys_only():
    state = {
        "create_character_0": "scott",
        "create_new_character_0": "Logan",
        "create_pending_character_0": "logan",
        "create_turn_0": "Hi",
        "full_edit_character_0": "kai",
    }

    clear_character_state_values(state, "create")

    assert state == {
        "create_turn_0": "Hi",
        "full_edit_character_0": "kai",
    }


def test_matching_character_slug_uses_normalized_settings_name():
    characters = [
        SimpleNamespace(slug="emma_frost", display_name="Emma Frost"),
        SimpleNamespace(slug="scott_summers", display_name="Scott Summers"),
    ]

    assert matching_character_slug("  Scott Summers  ", characters) == "scott_summers"
    assert matching_character_slug("Missing", characters) == ""


def test_default_character_slug_for_first_exchange_uses_settings_names():
    characters = [
        SimpleNamespace(slug="emma_frost", display_name="Emma Frost"),
        SimpleNamespace(slug="scott_summers", display_name="Scott Summers"),
    ]
    state = {
        "preview_user_name": "Scott Summers",
        "preview_assistant_name": "Emma Frost",
    }

    assert default_character_slug_for_turn(state, "create", 0, "user", characters) == "scott_summers"
    assert default_character_slug_for_turn(state, "create", 1, "assistant", characters) == "emma_frost"


def test_default_character_slug_for_new_exchange_inherits_previous_selection():
    characters = [
        SimpleNamespace(slug="emma_frost", display_name="Emma Frost"),
        SimpleNamespace(slug="kai", display_name="Kai"),
        SimpleNamespace(slug="scott_summers", display_name="Scott Summers"),
    ]
    state = {
        "preview_user_name": "Scott Summers",
        "preview_assistant_name": "Emma Frost",
        "create_character_0": "kai",
        "create_character_1": "emma_frost",
    }

    assert default_character_slug_for_turn(state, "create", 2, "user", characters) == "kai"
    assert default_character_slug_for_turn(state, "create", 3, "assistant", characters) == "emma_frost"


def test_default_character_slug_for_new_exchange_inherits_unselected_previous_turn():
    characters = [
        SimpleNamespace(slug="emma_frost", display_name="Emma Frost"),
        SimpleNamespace(slug="scott_summers", display_name="Scott Summers"),
    ]
    state = {
        "preview_user_name": "Scott Summers",
        "preview_assistant_name": "Emma Frost",
        "create_character_0": "",
    }

    assert default_character_slug_for_turn(state, "create", 2, "user", characters) == ""


def test_apply_pending_character_assignment_updates_widget_key_before_render():
    state = {
        "create_character_0": "__new_character__",
        "create_pending_character_0": "logan",
    }

    assert apply_pending_character_assignment(state, "create", 0, {"logan"}) is True
    assert state == {"create_character_0": "logan"}


def test_apply_pending_character_assignment_waits_for_valid_slug():
    state = {
        "create_character_0": "__new_character__",
        "create_pending_character_0": "logan",
    }

    assert apply_pending_character_assignment(state, "create", 0, {"scott"}) is False
    assert state["create_character_0"] == "__new_character__"
    assert state["create_pending_character_0"] == "logan"


def test_group_character_display_names_uses_live_dropdown_state():
    characters = [
        SimpleNamespace(slug="emma", display_name="Emma"),
        SimpleNamespace(slug="scott", display_name="Scott"),
    ]
    state = {
        "create_character_0": "scott",
        "create_character_1": "emma",
        "create_character_2": "",
    }
    turns = [
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "Hello"},
        {"role": "user", "content": "Unassigned"},
    ]

    assert group_character_display_names_from_state(
        state,
        "create",
        turns,
        characters,
    ) == {0: "Scott", 1: "Emma"}
