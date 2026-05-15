"""Full Edit workspace rendering and actions."""

import streamlit as st

from core.backups import auto_backups_enabled
from core.dataset import make_entry, validate_entry
from core.format_conversion import FORMAT_SHAREGPT, chatml_to_sharegpt_entry
from core.loreforge_meta import get_entry_uuid
from core.text_helpers import count_phrase
from services.dataset_service import save_full_edit_service, split_entry_service
from ui.edit_entries.state import (
    cancel_full_edit,
    editor_turn_display_names,
    load_full_edit_buffer,
    reset_full_edit_to_browser,
)
from ui.flash_messages import enqueue_dataset_result_flash
from ui.session_state import (
    apply_dataset_operation_result,
    clear_entry_edit_state,
    ensure_entry_indexes,
    get_loaded_entry_by_uuid,
    get_loaded_entry_index_by_uuid,
)
from ui.system_prompt_selector import render_system_prompt_template_selector
from ui.system_prompt_template_actions import render_save_system_prompt_template_action
from ui.ui_components import (
    calculate_exchange_metrics,
    render_conversation_preview,
    render_json_preview,
    render_tag_multiselects,
)
from ui.ui_create import (
    ENTRY_MODE_GROUP,
    collect_group_character_turn_mappings,
    disabled_save_reason,
    entry_mode_key,
    group_character_display_names_from_state,
    render_entry_mode_toggle,
    render_turn_builder,
)


def save_full_edit(active_registry: dict[str, list[str]]) -> bool:
    """Build the workspace buffer, validate, save, and return to browser mode."""

    entry_uuid = st.session_state.get("full_edit_entry_uuid") or st.session_state.get(
        "editing_entry_uuid"
    )
    if not entry_uuid:
        st.error("No entry selected for editing.")
        return False

    turns_now = [
        {
            "role": t["role"],
            "content": st.session_state.get(f"full_edit_turn_{i}", ""),
        }
        for i, t in enumerate(st.session_state.get("full_edit_turns", []))
    ]

    system_prompt: str = st.session_state.get("full_edit_system_prompt", "")

    selected_tags: list[str] = []
    for category in active_registry:
        selected_tags.extend(st.session_state.get(f"full_edit_tags_{category}", []))
    unknown_tags: list[str] = st.session_state.get("full_edit_unknown_tags", [])

    edited_entry = make_entry(
        turns=turns_now,
        system_prompt=system_prompt,
        tags=selected_tags + unknown_tags,
    )

    errors = validate_entry(edited_entry)
    if errors:
        for err in errors:
            st.error(err)
        return False

    entry_index = get_loaded_entry_index_by_uuid(entry_uuid)
    if entry_index is None:
        st.error("Could not find the selected entry.")
        return False

    result = save_full_edit_service(
        dataset_path=st.session_state.get("loaded_path", ""),
        entries=st.session_state.loaded_entries,
        entry_index=entry_index,
        updated_entry=edited_entry,
        character_turns=(
            collect_group_character_turn_mappings("full_edit", turns_now)
            if st.session_state.get(entry_mode_key("full_edit")) == ENTRY_MODE_GROUP
            else None
        ),
        clear_character_mappings=(
            st.session_state.get(entry_mode_key("full_edit")) != ENTRY_MODE_GROUP
        ),
        backup_enabled=auto_backups_enabled(st.session_state.get("prefs", {})),
    )
    if not result.ok:
        for err in result.errors:
            st.error(err)
        if not result.errors:
            st.error(result.message)
        return False

    if result.entries is not None:
        apply_dataset_operation_result(result)
        st.session_state.loaded_entries = result.entries
        ensure_entry_indexes()

    backup_note = " Backup created." if result.backup_path else ""
    enqueue_dataset_result_flash(f"{result.message}{backup_note}", result)
    cancel_full_edit()
    return True


def split_button_visible(turns_now: list[dict]) -> bool:
    return len(turns_now) > 2 and len(turns_now) % 2 == 0


def split_complete_message(split_after_exchange: int) -> str:
    noun = "Exchange" if split_after_exchange == 1 else "Exchanges"
    return (
        f"Split complete. {noun} 1-{split_after_exchange} "
        "saved as a new entry."
    )


def render_live_split_divider(
    *,
    entry_uuid: str,
    split_after_exchange: int,
    active_registry: dict[str, list[str]],
) -> None:
    """Render one immediate split divider between exchanges."""

    _left_space, middle, _right_space = st.columns([2, 1, 2])
    with middle:
        if not st.button(
            f"Split @ Exchange {split_after_exchange}",
            key=f"btn_live_split_after_exchange_{split_after_exchange}",
            width="stretch",
        ):
            return

    apply_live_split(
        entry_uuid=entry_uuid,
        split_after_exchange=split_after_exchange,
        active_registry=active_registry,
    )


def apply_live_split(
    *,
    entry_uuid: str,
    split_after_exchange: int,
    active_registry: dict[str, list[str]],
) -> None:
    """Split above the divider and keep editing the lower remaining entry."""

    original_index = get_loaded_entry_index_by_uuid(entry_uuid)
    result = split_entry_service(
        dataset_path=st.session_state.get("loaded_path", ""),
        entry_uuid=entry_uuid,
        split_points=[split_after_exchange],
        entries=st.session_state.loaded_entries,
        backup_enabled=auto_backups_enabled(st.session_state.get("prefs", {})),
    )
    if not result.ok or result.entries is None:
        for error in result.errors:
            st.error(error)
        if not result.errors:
            st.error(result.message)
        return

    apply_dataset_operation_result(result)
    st.session_state.loaded_entries = result.entries
    ensure_entry_indexes()

    remaining_uuid = None
    if original_index is not None:
        remaining_index = original_index + 1
        if 0 <= remaining_index < len(result.entries):
            remaining_entry = result.entries[remaining_index]
            remaining_uuid = get_entry_uuid(remaining_entry)

    backup_note = " Backup created." if result.backup_path else ""
    enqueue_dataset_result_flash(
        f"{split_complete_message(split_after_exchange)}{backup_note}",
        result,
    )

    if remaining_uuid and load_full_edit_buffer(remaining_uuid, active_registry):
        st.session_state.editing_entry_uuid = remaining_uuid
        st.session_state.edit_entries_mode = "workspace"
    else:
        clear_entry_edit_state()
    st.rerun()


def render_full_edit_workspace(active_registry: dict[str, list[str]]) -> None:
    """Render the full-edit workspace for the selected entry."""

    entry_uuid = st.session_state.get("editing_entry_uuid")

    if not entry_uuid:
        st.warning("No entry selected for editing.")
        if st.button("Back to Edit Entries", key="btn_back_no_id"):
            cancel_full_edit()
        return

    current_entry = get_loaded_entry_by_uuid(entry_uuid)
    if current_entry is None:
        st.error("Selected entry could not be found.")
        if st.button("Back to Edit Entries", key="btn_back_not_found"):
            cancel_full_edit()
        return

    st.subheader("Full Edit Entry")
    st.caption(f"Entry UUID: {entry_uuid}")
    if st.button("Back to Entry List", key="btn_back_full_edit_top"):
        reset_full_edit_to_browser()
    render_entry_mode_toggle("full_edit")

    st.divider()
    st.subheader("System Prompt")
    render_system_prompt_template_selector(
        target_key="full_edit_system_prompt",
        select_key="full_edit_system_prompt_template",
    )
    st.text_area(
        "System Prompt",
        key="full_edit_system_prompt",
        height=120,
        label_visibility="collapsed",
    )
    render_save_system_prompt_template_action(
        prompt_text=st.session_state.get("full_edit_system_prompt", ""),
        prefix="full_edit",
    )

    st.divider()
    split_divider_callback = None
    if split_button_visible(st.session_state.get("full_edit_turns", [])):
        split_divider_callback = lambda exchange_index: render_live_split_divider(
            entry_uuid=entry_uuid,
            split_after_exchange=exchange_index,
            active_registry=active_registry,
        )
    turns_now = render_turn_builder(
        "full_edit",
        active_registry,
        show_exchange_numbers=True,
        exchange_divider_callback=split_divider_callback,
    )

    st.subheader("Conversation Preview")
    render_conversation_preview(
        turns_now,
        "full_edit",
        display_names=(
            group_character_display_names_from_state(
                st.session_state,
                "full_edit",
                turns_now,
            )
            if st.session_state.get(entry_mode_key("full_edit")) == ENTRY_MODE_GROUP
            else editor_turn_display_names(current_entry)
        ),
    )

    st.divider()
    st.subheader("Tag & Complete Exchange")
    selected_tags = render_tag_multiselects("full_edit", active_registry)

    unknown_tags: list[str] = st.session_state.get("full_edit_unknown_tags", [])
    if unknown_tags:
        st.warning(
            "This entry contains unknown tags not currently in the tag registry: "
            + ", ".join(unknown_tags)
        )

    planned_exchanges = st.session_state.get("full_edit_planned_exchanges", 1)
    metrics = calculate_exchange_metrics(turns_now, planned_exchanges)
    current_exchanges = metrics["current_exchanges"]

    has_content = any(t["content"].strip() for t in turns_now)
    entry_valid = False
    if has_content:
        entry_preview = make_entry(
            turns=turns_now,
            system_prompt=st.session_state.get("full_edit_system_prompt", ""),
            tags=selected_tags + unknown_tags,
        )
        json_preview = entry_preview
        if st.session_state.get("dataset_source_format") == FORMAT_SHAREGPT:
            json_preview = chatml_to_sharegpt_entry(entry_preview).entry
        render_json_preview(json_preview, expanded=False)
        errors = validate_entry(entry_preview)
        if errors:
            for err in errors:
                st.error(err)
        else:
            st.success("Entry looks valid.")
            entry_valid = True

    if planned_exchanges > 1 and current_exchanges < planned_exchanges:
        st.warning("You have not reached your planned number of exchanges yet.")
    if metrics["overage"] > 0:
        st.info(
            f"You are {count_phrase(metrics['overage'], 'exchange')} over your planned count. "
            "You can still save this exchange."
        )
    if planned_exchanges > 1 and metrics["blank_pairs"] > 0:
        blank_pair_verb = "has" if metrics["blank_pairs"] == 1 else "have"
        st.warning(
            f"{count_phrase(metrics['blank_pairs'], 'exchange pair')} "
            f"{blank_pair_verb} empty fields and will not be saved. "
            "Fill them in or remove them before completing."
        )

    st.divider()
    col_save, col_cancel = st.columns(2)
    with col_save:
        save_disabled = not entry_valid or current_exchanges < planned_exchanges
        if st.button(
            "Save Edits",
            key="btn_save_full_edit",
            type="primary",
            disabled=save_disabled,
            width="stretch",
        ):
            save_full_edit(active_registry)
        if save_disabled:
            st.caption(
                disabled_save_reason(
                    entry_valid,
                    current_exchanges,
                    planned_exchanges,
                )
            )
    with col_cancel:
        if st.button(
            "Cancel / Back to Edit Entries",
            key="btn_cancel_full_edit",
            width="stretch",
        ):
            cancel_full_edit()

