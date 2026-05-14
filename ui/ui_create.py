"""Streamlit page for creating dataset entries.

This module owns widgets and form state. Durable entry appends delegate to
services.
"""
from pathlib import Path

import streamlit as st

from core.character_registry import (
    create_character,
    get_all_characters,
    normalize_character_name,
)
from core.dataset import clear_validate_entry_cache, make_entry, validate_entry
from core.format_conversion import FORMAT_SHAREGPT, chatml_to_sharegpt_entry
from core.tag_registry import get_tag_registry_snapshot
from core.text_helpers import count_phrase
from ui.session_state import apply_dataset_operation_result, update_prefs, ensure_entry_indexes
from services.dataset_service import create_entry_service
from ui.flash_messages import enqueue_dataset_result_flash, render_flash_messages
from ui.guidance import render_manage_dataset_cta
from ui.system_prompt_selector import render_system_prompt_template_selector
from ui.ui_components import (
    _NON_STANDARD_ROLE_COLOR,
    _ROLE_COLOR,
    calculate_exchange_metrics,
    render_conversation_preview,
    render_json_preview,
    render_tag_multiselects,
)

ENTRY_MODE_STANDARD = "standard"
ENTRY_MODE_GROUP = "group"
_NEW_CHARACTER_OPTION = "__new_character__"
_NO_CHARACTER_OPTION = ""

_ROLE_PLACEHOLDER = {
    "user": "What the user says…",
    "assistant": "What the assistant replies…",
}


# ── Editor state ───────────────────────────────────────────────────────────────

def init_editor_state(prefix: str) -> None:
    """Initialise session state keys for an entry editor instance.

    Safe to call multiple times — only sets keys that don't exist yet.
    """
    if f"{prefix}_turns" not in st.session_state:
        st.session_state[f"{prefix}_turns"] = [
            {"role": "user"}, {"role": "assistant"}
        ]
    if f"{prefix}_planned_exchanges" not in st.session_state:
        st.session_state[f"{prefix}_planned_exchanges"] = 1
    if f"{prefix}_clear" not in st.session_state:
        st.session_state[f"{prefix}_clear"] = False


def entry_mode_key(prefix: str) -> str:
    """Return the session-state key that stores one editor's entry mode."""

    return "create_entry_mode" if prefix == "create" else f"{prefix}_entry_mode"


def character_state_key(prefix: str, turn_index: int) -> str:
    """Return the session-state key for one group-mode turn character."""

    return f"{prefix}_character_{turn_index}"


def pending_character_state_key(prefix: str, turn_index: int) -> str:
    """Return the non-widget key used to select a newly created character."""

    return f"{prefix}_pending_character_{turn_index}"


def clear_character_state_values(state, prefix: str) -> None:
    """Clear group-mode character state for one editor prefix."""

    prefixes = (
        f"{prefix}_character_",
        f"{prefix}_new_character_",
        f"{prefix}_pending_character_",
    )
    for key in [key for key in state if str(key).startswith(prefixes)]:
        state.pop(key, None)


def apply_entry_mode_transition(state, prefix: str, mode: str) -> str:
    """Persist an editor mode transition and clear group state when leaving it."""

    mode_key = entry_mode_key(prefix)
    previous_key = f"_{mode_key}_previous"
    previous_mode = state.get(previous_key, state.get(mode_key, ENTRY_MODE_STANDARD))
    if mode != previous_mode and mode == ENTRY_MODE_STANDARD:
        clear_character_state_values(state, prefix)
    state[previous_key] = mode
    return mode


def on_entry_mode_changed(prefix: str) -> None:
    """Apply mode transition cleanup from a Streamlit widget callback."""

    mode = st.session_state.get(entry_mode_key(prefix), ENTRY_MODE_STANDARD)
    apply_entry_mode_transition(st.session_state, prefix, mode)


def remove_last_exchange_state(state, prefix: str) -> bool:
    """Remove the final exchange and its per-turn editor state."""

    turns_key = f"{prefix}_turns"
    turns = list(state.get(turns_key, []))
    if len(turns) <= 2:
        return False

    removed_start = len(turns) - 2
    state[turns_key] = turns[:-2]
    for turn_index in (removed_start, removed_start + 1):
        state.pop(f"{prefix}_turn_{turn_index}", None)
        state.pop(character_state_key(prefix, turn_index), None)
        state.pop(pending_character_state_key(prefix, turn_index), None)
        state.pop(f"{prefix}_new_character_{turn_index}", None)
    return True


def matching_character_slug(name: str, characters) -> str:
    """Return the slug for a character matching a configured display name."""

    normalized_slug, _display_name = normalize_character_name(name)
    if not normalized_slug:
        return ""
    for character in characters:
        if character.slug == normalized_slug:
            return character.slug
    return ""


def default_character_slug_for_turn(
    state,
    prefix: str,
    turn_index: int,
    role: str,
    characters,
) -> str:
    """Return the inherited or settings-backed default character for a turn."""

    if turn_index >= 2:
        previous_key = character_state_key(prefix, turn_index - 2)
        if previous_key in state and state.get(previous_key) != _NEW_CHARACTER_OPTION:
            previous_slug = state.get(previous_key, "")
            return previous_slug

    if role == "assistant":
        return matching_character_slug(
            state.get("preview_assistant_name", "Assistant"),
            characters,
        )
    if role == "user":
        return matching_character_slug(
            state.get("preview_user_name", "User"),
            characters,
        )
    return ""


def apply_pending_character_assignment(
    state,
    prefix: str,
    turn_index: int,
    valid_slugs: set[str] | None = None,
) -> bool:
    """Apply a pending inline-created character before its selectbox renders."""

    pending_key = pending_character_state_key(prefix, turn_index)
    if pending_key not in state:
        return False
    pending_slug = state.get(pending_key, "")
    if valid_slugs is not None and pending_slug not in valid_slugs:
        return False
    state[character_state_key(prefix, turn_index)] = pending_slug
    state.pop(pending_key, None)
    return True


def collect_group_character_turn_mappings(
    prefix: str,
    turns: list[dict],
    characters=None,
) -> list[dict]:
    """Collect DB mapping payloads from one editor's group-mode state."""

    character_list = list(characters if characters is not None else get_all_characters())
    character_by_slug = {character.slug: character for character in character_list}
    mappings: list[dict] = []
    for turn_index, turn in enumerate(turns):
        role = turn.get("role")
        if role not in ("user", "assistant"):
            continue
        character_slug = st.session_state.get(character_state_key(prefix, turn_index), "")
        if not character_slug or character_slug == _NEW_CHARACTER_OPTION:
            continue
        character = character_by_slug.get(character_slug)
        if character is None:
            continue
        mappings.append({
            "turn_index": turn_index + 1,
            "character_slug": character.slug,
            "training_role": role,
            "source_role_label": character.display_name,
        })
    return mappings


def group_character_display_names_from_state(
    state,
    prefix: str,
    turns: list[dict],
    characters=None,
) -> dict[int, str]:
    """Return live preview display names from group-mode character dropdowns."""

    character_list = list(characters if characters is not None else get_all_characters())
    character_by_slug = {character.slug: character for character in character_list}
    display_names: dict[int, str] = {}
    for turn_index, turn in enumerate(turns):
        if turn.get("role") not in ("user", "assistant"):
            continue
        character_slug = state.get(character_state_key(prefix, turn_index), "")
        if not character_slug or character_slug == _NEW_CHARACTER_OPTION:
            continue
        character = character_by_slug.get(character_slug)
        if character is not None:
            display_names[turn_index] = character.display_name
    return display_names


def render_entry_mode_toggle(prefix: str) -> str:
    """Render the Default/Group Chat editor mode toggle."""

    mode_key = entry_mode_key(prefix)
    st.session_state.setdefault(mode_key, ENTRY_MODE_STANDARD)
    mode = st.radio(
        "Entry mode",
        options=[ENTRY_MODE_STANDARD, ENTRY_MODE_GROUP],
        format_func=lambda value: (
            "Default" if value == ENTRY_MODE_STANDARD else "Group Chat"
        ),
        horizontal=True,
        key=mode_key,
        on_change=on_entry_mode_changed,
        args=(prefix,),
        help=(
            "Default: two-character exchanges using your Settings display names. "
            "Group Chat: multi-character exchanges with per-turn character selection."
        ),
    )
    return mode


# ── Turn builder ───────────────────────────────────────────────────────────────

def render_turn_builder(
    prefix: str,
    active_registry: dict[str, list[str]],
    *,
    show_exchange_numbers: bool = False,
    exchange_divider_callback=None,
) -> list[dict]:
    """Render the multi-turn conversation builder for an editor instance.

    Handles the pending-clear logic, tag-backup restore, planned-exchanges
    input, planning metrics, turn pair widgets, Add/Remove buttons, and the
    exchange-count caption.  Returns _turns_now — the list of
    {role, content} dicts reflecting the current widget values.
    """
    # ── DB-backed category names (used for tag backup/restore/clear loops) ───────
    # Fetched once per render; falls back to hardcoded TAGS if DB not seeded.
    _tag_registry = active_registry
    if not _tag_registry:
        from core.dataset import TAGS as _TAGS_FB
        _tag_registry = _TAGS_FB
    _tag_cat_names = list(_tag_registry.keys())

    # ── Pending clear ──────────────────────────────────────────────────────────
    if st.session_state.pop(f"{prefix}_clear", False):
        _old_turn_count = len(st.session_state.get(f"{prefix}_turns", []))
        st.session_state[f"{prefix}_turns"] = [{"role": "user"}, {"role": "assistant"}]
        st.session_state[f"{prefix}_turn_0"] = ""
        st.session_state[f"{prefix}_turn_1"] = ""
        for _i in range(2, _old_turn_count):
            st.session_state.pop(f"{prefix}_turn_{_i}", None)
        for _cat in _tag_cat_names:
            st.session_state[f"{prefix}_tags_{_cat}"] = []
        clear_character_state_values(st.session_state, prefix)

    # ── Tag backup restore ─────────────────────────────────────────────────────
    for _cat in _tag_cat_names:
        _bk = f"_{prefix}_tags_backup_{_cat}"
        if _bk in st.session_state:
            st.session_state[f"{prefix}_tags_{_cat}"] = st.session_state.pop(_bk)

    # ── _turns_now snapshot (read before widgets render) ──────────────────────
    _turns_now = [
        {"role": t["role"], "content": st.session_state.get(f"{prefix}_turn_{i}", "")}
        for i, t in enumerate(st.session_state[f"{prefix}_turns"])
    ]

    # ── Planned exchanges number input ────────────────────────────────────────
    _col_planned, _col_planned_spacer = st.columns([0.55, 4])
    with _col_planned:
        st.number_input(
            "Planned exchanges",
            min_value=1,
            step=1,
            key=f"{prefix}_planned_exchanges",
        )

    # ── Planning metrics (recomputed every run) ────────────────────────────────
    # Only count an exchange as complete when BOTH turns are filled in.
    _current_exchanges = sum(
        1
        for _pi in range(0, len(_turns_now), 2)
        if (
            _pi + 1 < len(_turns_now)
            and _turns_now[_pi]["content"].strip()
            and _turns_now[_pi + 1]["content"].strip()
        )
    )
    _planned_exchanges = st.session_state[f"{prefix}_planned_exchanges"]
    _remaining = max(0, _planned_exchanges - len(_turns_now) // 2)
    _overage = max(0, _current_exchanges - _planned_exchanges)
    _group_mode = st.session_state.get(entry_mode_key(prefix)) == ENTRY_MODE_GROUP
    _characters = get_all_characters() if _group_mode else []
    if _group_mode:
        st.caption(
            "Group Chat mode lets you assign characters to each turn. Training data "
            "stays as standard user/assistant roles - character names are preserved "
            "as display metadata only."
        )
    if _group_mode and not _characters:
        st.caption("Add characters in Metadata or from a turn dropdown to use group mode.")

    # ── Turn pair rendering loop ───────────────────────────────────────────────
    for _pair in range(0, len(st.session_state[f"{prefix}_turns"]), 2):
        _col_user, _col_asst = st.columns(2)
        for _col, _idx in ((_col_user, _pair), (_col_asst, _pair + 1)):
            if _idx >= len(st.session_state[f"{prefix}_turns"]):
                break
            _turn = st.session_state[f"{prefix}_turns"][_idx]
            _role = _turn["role"]
            _color = _ROLE_COLOR.get(_role, _NON_STANDARD_ROLE_COLOR)
            with _col:
                if _group_mode:
                    _render_group_turn_header(
                        prefix,
                        _idx,
                        _role,
                        _color,
                        _characters,
                    )
                else:
                    st.markdown(
                        f"<span style='color:{_color};font-weight:bold;"
                        f"text-transform:uppercase'>{_role}</span>",
                        unsafe_allow_html=True,
                    )
                st.text_area(
                    label=f"{prefix}_turn_{_idx}",
                    placeholder=_ROLE_PLACEHOLDER.get(_role, ""),
                    key=f"{prefix}_turn_{_idx}",
                    height=150,
                    label_visibility="collapsed",
                )
        _exchange_number = _pair // 2 + 1
        if (
            exchange_divider_callback is not None
            and _exchange_number >= 2
            and _pair + 2 < len(st.session_state[f"{prefix}_turns"])
        ):
            exchange_divider_callback(_exchange_number)
    # ── Add / Remove Exchange buttons ─────────────────────────────────────────
    _add_label = (
        f"Add Exchange ({_remaining} Remaining)"
        if _remaining > 0 and _planned_exchanges >= 2
        else "Add Exchange"
    )
    _btn_add, _btn_remove = st.columns(2)
    with _btn_add:
        if st.button(_add_label, key=f"{prefix}_btn_add", width="stretch"):
            for _cat in _tag_cat_names:
                st.session_state[f"_{prefix}_tags_backup_{_cat}"] = list(
                    st.session_state.get(f"{prefix}_tags_{_cat}", [])
                )
            st.session_state[f"{prefix}_turns"] += [{"role": "user"}, {"role": "assistant"}]
            st.rerun()
    with _btn_remove:
        if st.button(
            "Remove Last Exchange",
            key=f"{prefix}_btn_remove",
            disabled=len(st.session_state[f"{prefix}_turns"]) <= 2,
            width="stretch",
        ):
            for _cat in _tag_cat_names:
                st.session_state[f"_{prefix}_tags_backup_{_cat}"] = list(
                    st.session_state.get(f"{prefix}_tags_{_cat}", [])
                )
            remove_last_exchange_state(st.session_state, prefix)
            st.rerun()

    return _turns_now


def _render_group_turn_header(
    prefix: str,
    turn_index: int,
    role: str,
    color: str,
    characters,
) -> None:
    header_label, header_select = st.columns([1, 2])
    with header_label:
        st.markdown(
            f"<span style='color:{color};font-weight:bold;"
            f"text-transform:uppercase'>{role}</span>",
            unsafe_allow_html=True,
        )
    with header_select:
        _render_turn_character_select(
            prefix,
            turn_index,
            role,
            characters,
        )


def _render_turn_character_select(
    prefix: str,
    turn_index: int,
    role: str,
    characters,
) -> str:
    character_key = character_state_key(prefix, turn_index)
    character_by_slug = {character.slug: character for character in characters}
    apply_pending_character_assignment(
        st.session_state,
        prefix,
        turn_index,
        set(character_by_slug),
    )
    _ensure_turn_character_default(
        prefix,
        turn_index,
        role,
        characters,
    )
    options = (
        [_NO_CHARACTER_OPTION]
        + [character.slug for character in characters]
        + [_NEW_CHARACTER_OPTION]
    )
    selected_slug = st.selectbox(
        "Character",
        options=options,
        format_func=lambda slug: _format_character_option(slug, character_by_slug),
        key=character_key,
        label_visibility="collapsed",
    )
    if selected_slug == _NEW_CHARACTER_OPTION:
        _render_inline_character_create(prefix, turn_index)
    return selected_slug


def _ensure_turn_character_default(
    prefix: str,
    turn_index: int,
    role: str,
    characters,
) -> None:
    character_key = character_state_key(prefix, turn_index)
    if character_key in st.session_state:
        return

    default_slug = default_character_slug_for_turn(
        st.session_state,
        prefix,
        turn_index,
        role,
        characters,
    )
    if default_slug:
        st.session_state[character_key] = default_slug


def _render_inline_character_create(prefix: str, turn_index: int) -> None:
    input_key = f"{prefix}_new_character_{turn_index}"
    st.text_input("New character name", key=input_key)
    if st.button("Add Character", key=f"{prefix}_add_character_{turn_index}"):
        name = st.session_state.get(input_key, "").strip()
        if not name:
            st.error("Character name cannot be empty.")
            return
        try:
            character = create_character(name)
        except Exception as exc:
            st.error(str(exc))
            return
        st.session_state[pending_character_state_key(prefix, turn_index)] = character.slug
        st.session_state.pop(input_key, None)
        st.rerun()


def _format_character_option(slug: str, character_by_slug: dict) -> str:
    if slug == _NO_CHARACTER_OPTION:
        return "No character"
    if slug == _NEW_CHARACTER_OPTION:
        return "New character..."
    character = character_by_slug.get(slug)
    return character.display_name if character is not None else slug


# ── Entry actions ──────────────────────────────────────────────────────────────

def render_entry_actions(
    turns_now: list[dict],
    prefix: str,
    active_registry: dict[str, list[str]],
) -> None:
    """Render the tag selector, JSON preview, validation, planning warnings,
    and save button for a create-entry editor instance.
    """
    st.divider()
    st.subheader("Tag & Complete Exchange")

    # ── Tag selectors ──────────────────────────────────────────────────────────
    selected_tags = render_tag_multiselects(prefix, active_registry)

    # ── Entry preview & validation ─────────────────────────────────────────────
    _has_content = any(t["content"].strip() for t in turns_now)

    entry_preview = None
    _entry_valid = False
    if _has_content:
        entry_preview = make_entry(
            turns=turns_now,
            system_prompt=st.session_state.system_prompt,
            tags=selected_tags,
        )
        errors = validate_entry(entry_preview)

        _json_preview = entry_preview
        if st.session_state.get("dataset_source_format") == FORMAT_SHAREGPT:
            _json_preview = chatml_to_sharegpt_entry(entry_preview).entry
        render_json_preview(_json_preview, expanded=False)

        if errors:
            for err in errors:
                st.error(err)
        else:
            st.success("Entry looks valid.")
            _entry_valid = True

    # ── Planning warnings ──────────────────────────────────────────────────────
    _planned_exchanges = st.session_state.get(f"{prefix}_planned_exchanges", 1)
    _m = calculate_exchange_metrics(turns_now, _planned_exchanges)
    _current_exchanges = _m["current_exchanges"]

    if _planned_exchanges > 1 and _current_exchanges < _planned_exchanges:
        st.warning("You have not reached your planned number of exchanges yet.")
    if _m["overage"] > 0:
        st.info(
            f"You are {count_phrase(_m['overage'], 'exchange')} over your planned count. "
            "You can still save this exchange."
        )
    if _planned_exchanges > 1 and _m["blank_pairs"] > 0:
        _blank_pair_verb = "has" if _m["blank_pairs"] == 1 else "have"
        st.warning(
            f"{count_phrase(_m['blank_pairs'], 'exchange pair')} "
            f"{_blank_pair_verb} empty fields and will not be saved. "
            "Fill them in or remove them before completing."
        )

    # ── Save button ────────────────────────────────────────────────────────────
    _complete_disabled = not _entry_valid or _current_exchanges < _planned_exchanges
    _complete_col, _complete_spacer = st.columns([2, 3])
    with _complete_col:
        complete_clicked = st.button(
            "Complete Exchange",
            disabled=_complete_disabled,
            type="primary",
            width="stretch",
        )
    if _complete_disabled:
        st.caption(disabled_save_reason(_entry_valid, _current_exchanges, _planned_exchanges))
    if complete_clicked:
        save_path = st.session_state.get("loaded_path", "").strip()
        if not save_path:
            st.error("No dataset loaded. Please load or create a dataset before saving an exchange.")
        else:
            character_turns = None
            if st.session_state.get(entry_mode_key(prefix)) == ENTRY_MODE_GROUP:
                character_turns = collect_group_character_turn_mappings(prefix, turns_now)
            result = create_entry_service(
                dataset_path=save_path,
                entries=st.session_state.loaded_entries,
                new_entry=entry_preview,
                character_turns=character_turns,
            )
            if result.ok and result.entries is not None:
                apply_dataset_operation_result(result)
                st.session_state.loaded_entries = result.entries
                ensure_entry_indexes()
                update_prefs({
                    "last_loaded_dataset_path": result.dataset_path or save_path,
                })
                st.session_state["manage_load_path_pending"] = result.dataset_path or save_path
                st.session_state[f"{prefix}_clear"] = True
                enqueue_dataset_result_flash(
                    f"Entry appended to `{Path(save_path).resolve()}`.",
                    result,
                )
                st.rerun()
            else:
                for err in result.errors:
                    st.error(err)
                if not result.errors:
                    st.error(result.message)


# ── Page renderer ──────────────────────────────────────────────────────────────

def render_create_page() -> None:
    """Render the Create Entry page."""
    clear_validate_entry_cache()
    _tag_snapshot = get_tag_registry_snapshot()

    render_flash_messages()
    if not st.session_state.get("loaded_path"):
        st.info("Load or create a dataset before creating entries.")
        render_manage_dataset_cta(key="create_go_to_manage_empty")
        return

    render_entry_mode_toggle("create")

    st.subheader("System Prompt")

    def _persist_system_prompt():
        update_prefs({"last_system_prompt": st.session_state.sys_prompt_input})

    st.session_state.setdefault("sys_prompt_input", st.session_state.system_prompt)
    _library_col, _library_spacer = st.columns([1, 1])
    with _library_col:
        render_system_prompt_template_selector(
            target_key="sys_prompt_input",
            select_key="create_system_prompt_template",
            mirror_keys=("system_prompt",),
            on_apply=lambda content: update_prefs({"last_system_prompt": content}),
        )

    st.text_area(
        "Default system prompt (applied to every entry)",
        height=100,
        key="sys_prompt_input",
        on_change=_persist_system_prompt,
    )
    st.session_state.system_prompt = st.session_state.get("sys_prompt_input", "")

    st.divider()
    st.subheader("New Entry")
    turns_now = render_turn_builder("create", _tag_snapshot.active_registry)

    # ── Conversation preview (full width, below Add/Remove buttons) ────────────
    st.subheader("Conversation Preview")
    preview_display_names = (
        group_character_display_names_from_state(st.session_state, "create", turns_now)
        if st.session_state.get(entry_mode_key("create")) == ENTRY_MODE_GROUP
        else None
    )
    render_conversation_preview(turns_now, "create", display_names=preview_display_names)

    render_entry_actions(turns_now, "create", _tag_snapshot.active_registry)


def disabled_save_reason(entry_valid: bool, current_exchanges: int, planned_exchanges: int) -> str:
    if current_exchanges < planned_exchanges:
        return "Complete all planned exchanges to enable save."
    if not entry_valid:
        return "Fix validation errors to enable save."
    return "Complete the entry to enable save."
