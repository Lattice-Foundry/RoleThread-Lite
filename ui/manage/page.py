"""Manage Dataset page dispatcher and load-section rendering."""
from pathlib import Path

import streamlit as st

from core.dataset import (
    analyze_entry,
    clear_validate_entry_cache,
    load_dataset_with_summary,
    save_dataset,
)
from core.format_conversion import FORMAT_CHATML, FORMAT_SHAREGPT, FORMAT_UNKNOWN
from core.preferences import get_initial_dir
from core.tag_registry import get_tag_registry_snapshot
from core.text_helpers import count_phrase
from core.working_copy import canonical_training_dataset_path
from services.dataset_service import save_repaired_entries_service
from services.registry_sidecar_service import export_registry_sidecar
from ui.file_dialogs import JSONL_TYPES, browse_open_file, path_input, safe_saveas_filename
from ui.flash_messages import render_flash_messages
from ui.manage.actions import render_actions
from ui.manage.entry_list import render_entry_list
from ui.manage.filters import render_filters
from ui.session_state import (
    apply_dataset_operation_result,
    clear_selected_entries,
    ensure_entry_indexes,
    ensure_selection_state,
    get_all_entry_pairs,
    persist_loaded_normalization,
    set_loaded_entries,
    should_persist_loaded_normalization,
    update_prefs,
)

_UNTAGGED = "__untagged__"


def _format_source_format(source_format: str) -> str:
    labels = {
        FORMAT_CHATML: "ChatML",
        FORMAT_SHAREGPT: "ShareGPT",
        FORMAT_UNKNOWN: "Unknown",
    }
    return labels.get(source_format, source_format or "Unknown")


def _render_load_format_summary(
    normalization,
    *,
    loaded_dataset_path: str | None = None,
    loaded_entry_count: int | None = None,
    correction_saved: bool = False,
    correction_failed: bool = False,
    normalized_entries: int = 0,
) -> None:
    source_format = normalization.source_format
    if source_format == FORMAT_SHAREGPT:
        st.info(
            "Detected format: ShareGPT. "
            "Export as ShareGPT to preserve the original format."
        )
    else:
        st.info(f"Detected format: {_format_source_format(source_format)}.")

    if loaded_dataset_path is not None and loaded_entry_count is not None:
        diagnostics = normalization.diagnostics
        issue_entries = max(0, diagnostics.entries_analyzed - diagnostics.valid_entries)
        st.success(
            f"Loaded {count_phrase(loaded_entry_count, 'entry', 'entries')} "
            f"from `{loaded_dataset_path}`. "
            f"({diagnostics.valid_entries} valid, {issue_entries} with issues)."
        )

    if correction_saved:
        diagnostics = normalization.diagnostics
        issue_entries = max(0, diagnostics.entries_analyzed - diagnostics.valid_entries)
        validation_note = (
            " See Validation page for remaining issues."
            if issue_entries
            else ""
        )
        st.info(
            "LoreForge automatically normalized "
            f"{count_phrase(normalized_entries, 'entry', 'entries')} on load "
            "(role formatting, missing metadata). Your original file is preserved. "
            f"{validation_note}"
        )
    elif correction_failed:
        st.warning(
            "Automatic normalization was applied in memory, but was not saved."
        )

    if normalization.parse_error_count:
        st.warning(
            f"Loaded {count_phrase(normalization.parsed_entry_count, 'entry', 'entries')} "
            f"from {count_phrase(normalization.source_line_count, 'non-empty line')}. "
            f"{count_phrase(normalization.parse_error_count, 'line')} had parse errors."
        )
    if normalization.role_values_normalized or normalization.message_content_trimmed:
        st.caption(
            "Normalized "
            f"{count_phrase(normalization.role_values_normalized, 'role value')} and "
            f"{count_phrase(normalization.message_content_trimmed, 'message content field')}."
        )
    if normalization.alias_rewrites:
        rewrite_items = list(normalization.alias_rewrites.items())
        preview = ", ".join(
            f"{old_slug} -> {new_slug}"
            for old_slug, new_slug in rewrite_items[:3]
        )
        if len(rewrite_items) > 3:
            preview += f", and {count_phrase(len(rewrite_items) - 3, 'more alias')}"
        st.caption(f"Resolved stale tag aliases: {preview}.")

    warnings = list(normalization.format_warnings or [])
    for warning in warnings[:3]:
        st.caption(f"Conversion warning: {warning}")
    if len(warnings) > 3:
        st.caption(
            f"{count_phrase(len(warnings) - 3, 'additional conversion warning')} hidden."
        )

    working_copy = st.session_state.get("working_copy_summary")
    if working_copy and not correction_saved:
        st.info(
            "Original file preserved. "
            f"Working copy created at `{working_copy.get('working_path')}`."
        )

    character_candidates = st.session_state.get("character_candidates")
    if character_candidates and character_candidates.has_candidates:
        labels = [
            candidate.source_role_label
            for candidate in character_candidates.candidates
        ]
        preview = ", ".join(labels[:5])
        if len(labels) > 5:
            preview += f", and {count_phrase(len(labels) - 5, 'more')}"
        st.info(
            f"{count_phrase(len(labels), 'custom role name')} detected "
            f"({preview}). Review on Validation page."
        )

    _render_sidecar_summary()
    _render_pending_trust_summary()


def _render_sidecar_summary() -> None:
    sidecar_summary = st.session_state.get("sidecar_import_summary")
    if not sidecar_summary:
        return

    if sidecar_summary.get("ok"):
        category_count = len(sidecar_summary.get("categories_created", []) or [])
        created_count = len(sidecar_summary.get("tags_created", []) or [])
        promoted_count = len(sidecar_summary.get("tags_promoted", []) or [])
        alias_count = len(sidecar_summary.get("aliases_imported", []) or [])
        character_count = len(sidecar_summary.get("characters_created", []) or [])
        mapping_count = len(sidecar_summary.get("character_mappings_imported", []) or [])
        if any(
            (
                category_count,
                created_count,
                promoted_count,
                alias_count,
                character_count,
                mapping_count,
            )
        ):
            st.info(
                "Registry sidecar restored: "
                f"{count_phrase(category_count, 'category', 'categories')}, "
                f"{count_phrase(created_count, 'tag')}, "
                f"{count_phrase(promoted_count, 'promoted tag')}."
            )
    else:
        st.warning(
            "Registry sidecar could not be restored. "
            "Dataset loading continued normally."
        )
        for error in (sidecar_summary.get("errors") or [])[:3]:
            st.caption(f"Sidecar warning: {error}")

    conflicts = sidecar_summary.get("conflicts") or []
    if conflicts:
        st.warning(
            f"{count_phrase(len(conflicts), 'tag conflict')} detected - resolve on Validation page."
        )


def _render_pending_trust_summary() -> None:
    pending_trust = st.session_state.get("pending_tag_trust") or {}
    if not pending_trust:
        return

    summary = st.session_state.get("tag_normalization_summary", {}) or {}
    adopted_slugs = set(summary.get("adopted_slugs", []) or [])
    newly_imported_count = sum(1 for slug in pending_trust if slug in adopted_slugs)
    already_archived_count = max(0, len(pending_trust) - newly_imported_count)
    suffix = "Assign categories to make them available in tag pickers."
    if newly_imported_count:
        st.warning(
            f"{count_phrase(newly_imported_count, 'unknown tag')} imported to archive "
            f"in Tag Management. {suffix}"
        )
    if already_archived_count:
        st.warning(
            f"{count_phrase(already_archived_count, 'tag')} in this dataset "
            f"{'is' if already_archived_count == 1 else 'are'} archived in "
            f"Tag Management. {suffix}"
        )


def _entry_has_reportable_diagnostics(entry: dict) -> bool:
    result = analyze_entry(entry)
    return any(
        diagnostic.severity.value in {"error", "warning"}
        or (diagnostic.fixable and diagnostic.repair_kind.value == "automatic")
        for diagnostic in result.diagnostics
    )


def _render_load_errors(normalization, errors: list[str], entries: list[dict]) -> bool:
    """Render load errors and return True when loading should stop."""

    zero_entry_parse_failure = (
        bool(errors)
        and not entries
        and normalization.parsed_entry_count == 0
        and normalization.parse_error_count > 0
    )
    if zero_entry_parse_failure:
        st.error(
            "No valid entries found. The file does not appear to contain training "
            "data in a supported format (ChatML, ShareGPT, or JSON array). "
            f"{count_phrase(normalization.parse_error_count, 'line')} could not be parsed."
        )
        parse_details = [error for error in errors if error.startswith("Line ")]
        if parse_details:
            with st.expander("Show parse details"):
                for error in parse_details:
                    st.error(error)
        return True

    if errors:
        for error in errors[:3]:
            st.error(error)
        if len(errors) > 3:
            st.caption(
                f"{count_phrase(len(errors) - 3, 'additional load error')} hidden."
            )
    if errors and not entries:
        st.error("No dataset was loaded.")
        return True
    return False


def _same_dataset_path(left: str | None, right: str | None) -> bool:
    if not left or not right:
        return False
    try:
        return Path(left).expanduser().resolve() == Path(right).expanduser().resolve()
    except (OSError, RuntimeError, ValueError):
        return str(left).strip() == str(right).strip()


def render_manage_page() -> None:
    """Render the Manage Dataset page."""
    clear_validate_entry_cache()
    ensure_entry_indexes()
    ensure_selection_state()
    tag_snapshot = get_tag_registry_snapshot(untagged_key=_UNTAGGED)
    stale_last_path_notice = st.empty()

    st.subheader("Load Dataset")
    render_flash_messages()
    _render_load_controls()

    with stale_last_path_notice:
        if st.session_state.stale_last_path and not st.session_state.loaded_path:
            st.warning(
                f"Last dataset `{st.session_state.stale_last_path}` no longer exists. "
                "Please load or create a dataset."
            )

    entries = st.session_state.loaded_entries
    all_pairs = get_all_entry_pairs()
    if not all_pairs:
        return

    st.divider()
    st.subheader(f"Entries ({len(all_pairs)})")
    _render_entry_issue_summary(entries)

    filter_result = render_filters(
        entries=entries,
        all_pairs=all_pairs,
        tag_snapshot=tag_snapshot,
        untagged_key=_UNTAGGED,
    )
    if filter_result is None:
        return

    render_actions(
        visible_pairs=filter_result.visible_pairs,
        filter_tags=filter_result.filter_tags,
        match_mode=filter_result.match_mode,
        per_page=filter_result.per_page,
        current_page=filter_result.current_page,
        start=filter_result.start,
        end=filter_result.end,
        total_filtered=filter_result.total_filtered,
        total_all=filter_result.total_all,
        tag_snapshot=tag_snapshot,
    )
    render_entry_list(
        visible_pairs=filter_result.visible_pairs,
        start=filter_result.start,
        tag_snapshot=tag_snapshot,
        tag_label_map=tag_snapshot.tag_label_map_with_untagged,
        character_display_cache=filter_result.character_display_cache,
        last_page=filter_result.last_page,
        current_page=filter_result.current_page,
    )


def _render_load_controls() -> None:
    load_path = path_input(
        "File path",
        state_key="manage_load_path",
        browse_fn=browse_open_file,
        browse_kwargs={"pref_path_key": "last_loaded_dataset_path"},
        default=st.session_state.prefs.get("last_loaded_dataset_path")
        or st.session_state.loaded_path
        or "dataset.jsonl",
    )

    col_load, col_new = st.columns(2)
    with col_load:
        _render_load_button(load_path)
    with col_new:
        _render_new_dataset_button()


def _render_load_button(load_path: str) -> None:
    dataset_already_loaded = _same_dataset_path(
        load_path.strip(),
        st.session_state.get("loaded_path"),
    )
    if dataset_already_loaded:
        st.caption("Dataset already loaded.")
    if st.button(
        "Load",
        width="stretch",
        disabled=not load_path.strip() or dataset_already_loaded,
    ):
        _load_dataset(load_path.strip())


def _load_dataset(path: str) -> None:
    auto_correct_enabled = st.session_state.get(
        "auto_correct_validation_errors",
        st.session_state.get("prefs", {}).get(
            "auto_correct_validation_errors",
            st.session_state.get("prefs", {}).get("auto_normalize_on_load", True),
        ),
    )
    normalization, errors = load_dataset_with_summary(
        path,
        auto_normalize=auto_correct_enabled,
    )
    entries = normalization.entries
    if _render_load_errors(normalization, errors, entries):
        return
    loaded_dataset_path = set_loaded_entries(
        entries,
        normalization_summary=normalization,
        dataset_path=path,
    ) or path
    st.session_state.loaded_path = loaded_dataset_path
    st.session_state.stale_last_path = ""
    st.session_state.entry_page = 0
    st.session_state["manage_select_all_mode"] = False
    clear_selected_entries()
    normalization_saved = False
    normalization_failed = False
    normalized_entries = int(
        st.session_state.get("tag_normalization_summary", {}).get(
            "changed_entries",
            0,
        )
        or 0
    )
    if should_persist_loaded_normalization(
        parse_errors=errors,
        normalization_pending=st.session_state.get("normalization_pending", False),
    ):
        normalize_result = persist_loaded_normalization(loaded_dataset_path)
        if normalize_result.ok:
            normalization_saved = True
        else:
            normalization_failed = True
            st.error(normalize_result.message)
            for error in normalize_result.errors:
                st.error(error)
    update_prefs({
        "last_loaded_dataset_path": loaded_dataset_path,
        "last_open_directory": str(Path(loaded_dataset_path).parent),
    })
    _render_load_format_summary(
        normalization,
        loaded_dataset_path=loaded_dataset_path,
        loaded_entry_count=len(entries),
        correction_saved=normalization_saved,
        correction_failed=normalization_failed,
        normalized_entries=normalized_entries,
    )


def _render_new_dataset_button() -> None:
    if not st.button("New Dataset", width="stretch"):
        return

    prefs = st.session_state.prefs
    new_path = safe_saveas_filename(
        title="Create new dataset",
        defaultextension=".jsonl",
        initialfile="dataset.jsonl",
        initialdir=get_initial_dir(prefs, dir_key="default_dataset_directory"),
        filetypes=JSONL_TYPES,
    )

    if new_path:
        new_path = _save_current_before_switch(new_path)
    if new_path:
        _create_new_dataset(new_path)


def _save_current_before_switch(new_path: str) -> str:
    if not (st.session_state.loaded_entries and st.session_state.loaded_path):
        return new_path

    result = save_repaired_entries_service(
        dataset_path=st.session_state.loaded_path,
        repaired_entries=st.session_state.loaded_entries,
        backup_reason="before_new_dataset_switch",
    )
    if result.ok:
        apply_dataset_operation_result(result)
        st.session_state.loaded_entries = result.entries or []
        return new_path

    st.error(
        "Could not save current dataset before switching: "
        f"{result.message}"
    )
    return ""


def _create_new_dataset(new_path: str) -> None:
    try:
        new_path = str(canonical_training_dataset_path(new_path))
        # New dataset bootstrap has no existing contents to protect; create the
        # empty JSONL and sibling sidecar directly, then normal service saves take over.
        save_dataset(new_path, [])
        sidecar_result = export_registry_sidecar(
            dataset_path=new_path,
            entries=[],
        )
        if not sidecar_result.ok:
            st.warning(sidecar_result.message)
        set_loaded_entries([])
        st.session_state.loaded_path = new_path
        st.session_state.stale_last_path = ""
        st.session_state.entry_page = 0
        st.session_state["manage_select_all_mode"] = False
        clear_selected_entries()
        st.session_state["manage_load_path_pending"] = new_path
        st.session_state["clear_entry_fields"] = True
        update_prefs({
            "last_loaded_dataset_path": new_path,
            "last_open_directory": str(Path(new_path).parent),
        })
        st.success(f"New dataset created at `{Path(new_path).resolve()}`.")
        st.rerun()
    except Exception as exc:
        st.error(f"Failed to create dataset: {exc}")


def _render_entry_issue_summary(entries: list[dict]) -> None:
    invalid_count = sum(1 for entry in entries if _entry_has_reportable_diagnostics(entry))
    if invalid_count:
        st.warning(
            f"{count_phrase(invalid_count, 'entry', 'entries')} "
            "have validation issues."
        )
    else:
        st.success("All entries are valid.")
