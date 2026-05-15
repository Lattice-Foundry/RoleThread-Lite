"""Full Edit buffer and session-state helpers."""

import streamlit as st

from core.character_display import get_turn_display_names
from core.character_registry import get_entry_character_turns
from core.dataset import count_exchanges, get_entry_tags
from ui.message_scaffolding import canonical_editor_role, scaffold_user_assistant_turns
from ui.session_state import (
    clear_entry_edit_state,
    get_loaded_entry_by_uuid,
)
from ui.ui_create import (
    ENTRY_MODE_GROUP,
    ENTRY_MODE_STANDARD,
    character_state_key,
    clear_character_state_values,
    entry_mode_key,
)


BROWSER_STATE_KEYS = (
    "edit_filter_tags",
    "edit_filter_only_used",
    "edit_filter_match_mode",
    "edit_entry_page",
    "edit_entries_per_page",
)


def entry_to_edit_buffer(entry: dict) -> dict:
    """Extract editable fields from an entry into a plain buffer dict."""
    msgs = entry.get("messages", [])
    if not isinstance(msgs, list):
        msgs = []

    system_prompt = ""
    turns: list[dict] = []
    for msg in msgs:
        if not isinstance(msg, dict):
            continue
        role = msg.get("role")
        content = msg.get("content", "")
        canonical_role = canonical_editor_role(role)
        if canonical_role == "system" and not system_prompt:
            system_prompt = content
        elif canonical_role in ("user", "assistant"):
            turns.append({"role": canonical_role, "content": content})
        elif isinstance(role, str):
            turns.append({"role": role, "content": content})

    turns = scaffold_user_assistant_turns(turns)
    tags = get_entry_tags(entry)
    planned_exchanges = max(1, count_exchanges(entry))

    return {
        "system_prompt": system_prompt,
        "turns": turns,
        "tags": tags,
        "planned_exchanges": planned_exchanges,
    }


def editor_turn_display_names(entry: dict) -> dict[int, str]:
    """Map original message display names onto the full-edit turn buffer."""

    display_names = get_turn_display_names(
        entry,
        st.session_state.get("preview_user_name", "Scott"),
        st.session_state.get("preview_assistant_name", "Nicole"),
    )
    messages = entry.get("messages") if isinstance(entry, dict) else None
    if not isinstance(messages, list):
        return {}

    editor_display_names: dict[int, str] = {}
    editor_index = 0
    for message_index, message in enumerate(messages):
        if not isinstance(message, dict):
            continue
        role = message.get("role")
        canonical_role = canonical_editor_role(role)
        if canonical_role == "system":
            continue
        if canonical_role in ("user", "assistant") or isinstance(role, str):
            if message_index in display_names:
                editor_display_names[editor_index] = display_names[message_index]
            editor_index += 1
    return editor_display_names


def apply_existing_character_mappings_to_full_edit_state(state, mappings) -> int:
    """Load existing entry-character mappings into full-edit turn state."""

    mapped_turns = 0
    for mapping in mappings:
        editor_turn_index = getattr(mapping, "turn_index", -1) - 1
        if editor_turn_index < 0:
            continue
        character_key = character_state_key("full_edit", editor_turn_index)
        character = getattr(mapping, "character", None)
        if character is not None and getattr(character, "is_active", True) is False:
            state[character_key] = ""
            mapped_turns += 1
            continue
        character_slug = getattr(character, "slug", None) or getattr(
            mapping,
            "character_slug",
            None,
        )
        if not character_slug:
            state[character_key] = ""
            mapped_turns += 1
            continue
        state[character_key] = character_slug
        mapped_turns += 1
    return mapped_turns


def set_full_edit_mode_state(state, mode: str) -> None:
    """Set Full Edit mode and its previous-mode guard together."""

    mode_key = entry_mode_key("full_edit")
    state[mode_key] = mode
    state[f"_{mode_key}_previous"] = mode


def load_full_edit_buffer(
    entry_uuid: str,
    active_registry: dict[str, list[str]],
) -> bool:
    """Load entry data into full_edit_* session-state keys.

    Returns True on success, False if the entry cannot be found.
    Unknown tags (not found in any DB registry category) are stored separately
    in full_edit_unknown_tags and are never discarded.
    """
    entry = get_loaded_entry_by_uuid(entry_uuid)
    if entry is None:
        return False

    clear_character_state_values(st.session_state, "full_edit")
    buf = entry_to_edit_buffer(entry)

    st.session_state["full_edit_entry_uuid"] = entry_uuid
    st.session_state["full_edit_system_prompt"] = buf["system_prompt"]
    st.session_state["full_edit_turns"] = [{"role": t["role"]} for t in buf["turns"]]
    st.session_state["full_edit_planned_exchanges"] = buf["planned_exchanges"]

    for i, turn in enumerate(buf["turns"]):
        st.session_state[f"full_edit_turn_{i}"] = turn["content"]

    registry = active_registry
    all_known: set[str] = set()
    for category, options in registry.items():
        cat_tags = [t for t in buf["tags"] if t in options]
        st.session_state[f"full_edit_tags_{category}"] = cat_tags
        all_known.update(options)

    st.session_state["full_edit_unknown_tags"] = [
        t for t in buf["tags"] if t not in all_known
    ]
    set_full_edit_mode_state(st.session_state, ENTRY_MODE_STANDARD)

    mappings = get_entry_character_turns(entry_uuid)
    if mappings and apply_existing_character_mappings_to_full_edit_state(
        st.session_state,
        mappings,
    ):
        set_full_edit_mode_state(st.session_state, ENTRY_MODE_GROUP)

    return True


def start_full_edit(
    entry_uuid: str,
    active_registry: dict[str, list[str]],
) -> None:
    """Load edit buffer, snapshot browser state, enter workspace, and rerun."""
    if not load_full_edit_buffer(entry_uuid, active_registry):
        st.error(f"Could not load entry `{entry_uuid}` for editing.")
        return

    st.session_state["_ee_browser_snapshot"] = {
        k: st.session_state.get(k) for k in BROWSER_STATE_KEYS
    }
    st.session_state.editing_entry_uuid = entry_uuid
    st.session_state.edit_entries_mode = "workspace"
    st.rerun()


def cancel_full_edit() -> None:
    """Clear the edit buffer, restore browser state, and return to browser mode."""

    for key in (
        "full_edit_entry_uuid",
        "full_edit_system_prompt",
        "full_edit_turns",
        "full_edit_planned_exchanges",
        "full_edit_unknown_tags",
        "editing_entry_uuid",
    ):
        st.session_state.pop(key, None)

    for key in [k for k in st.session_state if k.startswith("full_edit_turn_")]:
        del st.session_state[key]

    for key in [k for k in st.session_state if k.startswith("full_edit_tags_")]:
        del st.session_state[key]
    clear_character_state_values(st.session_state, "full_edit")

    snapshot = st.session_state.pop("_ee_browser_snapshot", {})
    for key, value in snapshot.items():
        if value is not None:
            st.session_state[key] = value

    st.session_state.edit_entries_mode = "browser"
    st.rerun()


def reset_full_edit_to_browser() -> None:
    """Clear stale full-edit state and return to the entry browser."""

    clear_character_state_values(st.session_state, "full_edit")
    clear_entry_edit_state()
    st.rerun()
