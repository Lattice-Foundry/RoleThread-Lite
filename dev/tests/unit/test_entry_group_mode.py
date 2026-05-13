from types import SimpleNamespace

from ui.ui_create import (
    ENTRY_MODE_GROUP,
    ENTRY_MODE_STANDARD,
    apply_pending_character_assignment,
    apply_entry_mode_transition,
    character_state_key,
    clear_character_state_values,
    default_character_slug_for_turn,
    entry_mode_key,
    group_character_display_names_from_state,
    matching_character_slug,
    pending_character_state_key,
    remove_last_exchange_state,
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


def test_mode_switch_to_standard_preserves_content_and_clears_character_state():
    state = {
        "create_entry_mode": ENTRY_MODE_GROUP,
        "_create_entry_mode_previous": ENTRY_MODE_GROUP,
        "create_turn_0": "Keep this",
        "create_character_0": "scott",
        "create_pending_character_0": "scott",
        "create_new_character_0": "Scott",
    }

    apply_entry_mode_transition(state, "create", ENTRY_MODE_STANDARD)

    assert state["create_turn_0"] == "Keep this"
    assert "_create_entry_mode_previous" in state
    assert "create_character_0" not in state
    assert "create_pending_character_0" not in state
    assert "create_new_character_0" not in state


def test_mode_switch_back_and_forth_does_not_accumulate_stale_character_state():
    state = {
        "full_edit_entry_mode": ENTRY_MODE_STANDARD,
        "_full_edit_entry_mode_previous": ENTRY_MODE_STANDARD,
        "full_edit_turn_0": "Still here",
    }

    apply_entry_mode_transition(state, "full_edit", ENTRY_MODE_GROUP)
    state["full_edit_character_0"] = "emma"
    apply_entry_mode_transition(state, "full_edit", ENTRY_MODE_STANDARD)
    apply_entry_mode_transition(state, "full_edit", ENTRY_MODE_GROUP)

    assert state["full_edit_turn_0"] == "Still here"
    assert "full_edit_character_0" not in state


def test_remove_last_exchange_cleans_removed_character_state_only():
    state = {
        "create_turns": [
            {"role": "user"},
            {"role": "assistant"},
            {"role": "user"},
            {"role": "assistant"},
        ],
        "create_turn_0": "One",
        "create_turn_1": "Two",
        "create_turn_2": "Three",
        "create_turn_3": "Four",
        "create_character_0": "scott",
        "create_character_1": "emma",
        "create_character_2": "kai",
        "create_character_3": "yuki",
        "create_pending_character_3": "yuki",
        "create_new_character_3": "Yuki",
    }

    assert remove_last_exchange_state(state, "create") is True

    assert state["create_turns"] == [{"role": "user"}, {"role": "assistant"}]
    assert state["create_turn_0"] == "One"
    assert state["create_turn_1"] == "Two"
    assert state["create_character_0"] == "scott"
    assert state["create_character_1"] == "emma"
    assert "create_turn_2" not in state
    assert "create_turn_3" not in state
    assert "create_character_2" not in state
    assert "create_character_3" not in state
    assert "create_pending_character_3" not in state
    assert "create_new_character_3" not in state


def test_remove_last_exchange_keeps_single_exchange_unchanged():
    state = {
        "create_turns": [{"role": "user"}, {"role": "assistant"}],
        "create_character_0": "scott",
    }

    assert remove_last_exchange_state(state, "create") is False
    assert state["create_turns"] == [{"role": "user"}, {"role": "assistant"}]
    assert state["create_character_0"] == "scott"
