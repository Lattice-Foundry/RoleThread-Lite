"""Single-entry and bulk tag edit controls for Manage Dataset."""
from typing import Any

import streamlit as st

from core.backups import auto_backups_enabled
from core.dataset import get_entry_tags
from core.tag_registry import prettify_tag_name
from services.dataset_service import (
    clear_tags_bulk_service,
    replace_single_entry_tags_service,
    replace_tags_bulk_service,
)
from ui.flash_messages import enqueue_dataset_result_flash
from ui.session_state import (
    apply_dataset_operation_result,
    ensure_entry_indexes,
    get_loaded_entry_by_uuid,
    get_loaded_entry_index_by_uuid,
)


def render_tag_editor(selected_uuids: list[str], tag_snapshot: Any) -> None:
    selected_count = len(selected_uuids)
    if selected_count < 1:
        return

    tag_label_map = tag_snapshot.tag_label_map
    all_slugs = tag_snapshot.active_tag_slugs
    all_slugs_set = set(all_slugs)

    if selected_count == 1:
        st.markdown("**Quick Tag Edit**")
        entry_uuid = selected_uuids[0]
        entry = get_loaded_entry_by_uuid(entry_uuid)
        if entry is None:
            return
        current_tags = get_entry_tags(entry)
        unknown = [tag for tag in current_tags if tag not in all_slugs_set]
        options = all_slugs + unknown
        chosen = st.multiselect(
            "Tags for selected entry",
            options=options,
            default=current_tags,
            format_func=lambda tag: tag_label_map.get(tag, prettify_tag_name(tag)),
            key=f"single_quick_tags_{entry_uuid}",
        )
        if st.button("Save Tags", key="btn_save_single_tags"):
            idx = get_loaded_entry_index_by_uuid(entry_uuid)
            if idx is not None:
                tag_result = replace_single_entry_tags_service(
                    dataset_path=st.session_state.get("loaded_path", ""),
                    entries=st.session_state.loaded_entries,
                    entry_index=idx,
                    tags=chosen,
                    backup_enabled=auto_backups_enabled(
                        st.session_state.get("prefs", {})
                    ),
                )
                if tag_result.ok and tag_result.entries is not None:
                    apply_dataset_operation_result(tag_result)
                    st.session_state.loaded_entries = tag_result.entries
                    ensure_entry_indexes()
                    backup_note = " Backup created." if tag_result.backup_path else ""
                    enqueue_dataset_result_flash(
                        f"{tag_result.message}{backup_note}",
                        tag_result,
                    )
                    st.rerun()
                else:
                    for err in tag_result.errors:
                        st.error(err)
                    if not tag_result.errors:
                        st.error(tag_result.message)
            else:
                st.error("Could not find the selected entry.")

    elif selected_count >= 2:
        _render_bulk_tag_editor(
            selected_uuids=selected_uuids,
            selected_count=selected_count,
            all_slugs=all_slugs,
            tag_label_map=tag_label_map,
        )


def _render_bulk_tag_editor(
    *,
    selected_uuids: list[str],
    selected_count: int,
    all_slugs: list[str],
    tag_label_map: dict[str, str],
) -> None:
    st.markdown("**Bulk Tag Edit**")
    bulk_chosen = st.multiselect(
        "Replacement tags",
        options=all_slugs,
        format_func=lambda tag: tag_label_map.get(tag, prettify_tag_name(tag)),
        key="bulk_replace_tags",
    )
    col_bulk_replace, col_bulk_clear = st.columns(2)
    with col_bulk_replace:
        if st.button(
            f"Replace tags on {selected_count} selected",
            key="btn_bulk_replace_tags",
            disabled=not bulk_chosen,
            width="stretch",
        ):
            indices = _selected_indices(selected_uuids)
            bulk_result = replace_tags_bulk_service(
                dataset_path=st.session_state.get("loaded_path", ""),
                entries=st.session_state.loaded_entries,
                entry_indices=indices,
                tags=bulk_chosen,
                backup_enabled=auto_backups_enabled(
                    st.session_state.get("prefs", {})
                ),
            )
            _handle_bulk_tag_result(bulk_result)
    with col_bulk_clear:
        if st.button(
            f"Clear tags on {selected_count} selected",
            key="btn_bulk_clear_tags",
            width="stretch",
        ):
            indices = _selected_indices(selected_uuids)
            bulk_result = clear_tags_bulk_service(
                dataset_path=st.session_state.get("loaded_path", ""),
                entries=st.session_state.loaded_entries,
                entry_indices=indices,
                backup_enabled=auto_backups_enabled(
                    st.session_state.get("prefs", {})
                ),
            )
            _handle_bulk_tag_result(bulk_result)


def _selected_indices(selected_uuids: list[str]) -> list[int]:
    return [
        idx for idx in (
            get_loaded_entry_index_by_uuid(selected_uuid)
            for selected_uuid in selected_uuids
        )
        if idx is not None
    ]


def _handle_bulk_tag_result(bulk_result) -> None:
    if bulk_result.ok and bulk_result.entries is not None:
        apply_dataset_operation_result(bulk_result)
        st.session_state.loaded_entries = bulk_result.entries
        ensure_entry_indexes()
        backup_note = " Backup created." if bulk_result.backup_path else ""
        enqueue_dataset_result_flash(
            f"{bulk_result.message}{backup_note}",
            bulk_result,
        )
        st.rerun()
    else:
        for err in bulk_result.errors:
            st.error(err)
        if not bulk_result.errors:
            st.error(bulk_result.message)
