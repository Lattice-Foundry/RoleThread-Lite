from types import SimpleNamespace

from ui.ui_character_management import (
    character_checkbox_key,
    _enqueue_deleted_character_prompt_reference_warnings,
    reconcile_character_selection_state,
    set_character_selection_state,
)


def _character(slug):
    return SimpleNamespace(slug=slug)


def test_reconcile_character_selection_state_uses_current_checkbox_values():
    characters = [_character("scott"), _character("emma")]
    state = {
        "selected_character_slugs": {"scott", "emma"},
        character_checkbox_key("scott"): False,
        character_checkbox_key("emma"): True,
    }

    selected = reconcile_character_selection_state(state, characters)

    assert selected == {"emma"}
    assert state["selected_character_slugs"] == {"emma"}


def test_reconcile_character_selection_state_initializes_missing_checkbox_keys():
    characters = [_character("scott"), _character("emma")]
    state = {"selected_character_slugs": {"scott"}}

    selected = reconcile_character_selection_state(state, characters)

    assert selected == {"scott"}
    assert state[character_checkbox_key("scott")] is True
    assert state[character_checkbox_key("emma")] is False


def test_set_character_selection_state_updates_storage_and_widget_keys():
    characters = [_character("scott"), _character("emma")]
    state = {
        "selected_character_slugs": set(),
        character_checkbox_key("scott"): False,
        character_checkbox_key("emma"): True,
    }

    set_character_selection_state(state, characters, {"scott"})

    assert state["selected_character_slugs"] == {"scott"}
    assert state[character_checkbox_key("scott")] is True
    assert state[character_checkbox_key("emma")] is False


def test_deactivated_character_reference_warning_is_enqueued(monkeypatch):
    import ui.ui_character_management as character_management

    state = {
        "loaded_entries": [{"messages": []}],
    }
    monkeypatch.setattr(
        character_management,
        "st",
        SimpleNamespace(session_state=state),
    )
    monkeypatch.setattr(
        character_management,
        "find_entries_referencing_character",
        lambda entries, display_name: ["entry-1", "entry-2"]
        if display_name == "Kai"
        else [],
    )
    flashes = []
    monkeypatch.setattr(
        character_management,
        "enqueue_flash",
        lambda level, message: flashes.append((level, message)),
    )

    _enqueue_deleted_character_prompt_reference_warnings(
        ["kai"],
        [SimpleNamespace(slug="kai", display_name="Kai")],
    )

    assert flashes == [
        (
            "warning",
            "Character 'Kai' deactivated. 2 entries have system prompts "
            "referencing 'Kai'. Use Entry Search to review.",
        )
    ]
