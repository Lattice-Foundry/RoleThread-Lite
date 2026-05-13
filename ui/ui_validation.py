"""Validation page for dataset diagnostics and automatic repairs."""
from __future__ import annotations

import json
from typing import Any

import streamlit as st

from core.dataset import (
    build_uuid_index,
    clear_validate_entry_cache,
    summarize_entry_analysis,
)
from core.character_registry import find_inactive_character_prompt_references
from core.entry_analysis import CHARACTER_INACTIVE_REFERENCE_IN_PROMPT
from core.loreforge_meta import get_entry_uuid
from core.text_helpers import count_phrase
from core.validation_actions import (
    AutoFixGroup,
    AutoFixSample,
    apply_all_auto_repairs,
    apply_group_repairs,
    collect_auto_fixable_groups,
)
from services.character_mapping_service import apply_character_mapping_service
from services.dataset_service import save_repaired_entries_service
from ui.flash_messages import enqueue_dataset_result_flash, enqueue_flash, render_flash_messages
from ui.session_state import apply_dataset_operation_result, ensure_entry_indexes


def render_validation_page() -> None:
    """Render auto-fixable validation issues for the loaded dataset."""

    ensure_entry_indexes()
    st.subheader("Validation")
    render_flash_messages()

    entries = st.session_state.get("loaded_entries", [])
    if not entries:
        st.info("Load a dataset to review validation issues.")
        _clear_pending_fix()
        return

    groups = collect_auto_fixable_groups(entries)
    diagnostics = summarize_entry_analysis(entries)
    total_fix_count = sum(group.count for group in groups)
    affected_entry_count = len({
        index
        for group in groups
        for index in group.entry_indices
    })

    _render_summary(
        total_entries=len(entries),
        valid_entries=diagnostics.valid_entries,
        entries_with_issues=max(0, diagnostics.entries_analyzed - diagnostics.valid_entries),
        auto_fixable_count=total_fix_count,
    )

    if total_fix_count == 0:
        _clear_pending_fix()
        st.info("No auto-fixable issues found.")
    else:
        _render_master_fix(total_fix_count, affected_entry_count)
        _render_pending_confirmation(groups)

        st.divider()
        for group in groups:
            _render_group(group)

    _render_character_mapping_section(entries)
    _render_inactive_character_prompt_reference_section(entries)


def _render_summary(
    *,
    total_entries: int,
    valid_entries: int,
    entries_with_issues: int,
    auto_fixable_count: int,
) -> None:
    col_total, col_valid, col_issues, col_auto = st.columns(4)
    col_total.metric("Total Entries", total_entries)
    col_valid.metric("Valid Entries", valid_entries)
    col_issues.metric("Entries With Issues", entries_with_issues)
    col_auto.metric("Auto-Fixable Issues", auto_fixable_count)


def _render_master_fix(total_fix_count: int, affected_entry_count: int) -> None:
    if st.button(
        f"Fix All Auto-Fixable Issues ({total_fix_count} fixes)",
        type="primary",
        width="stretch",
    ):
        st.session_state.validation_pending_fix = {
            "mode": "all",
            "code": None,
            "title": "All Auto-Fixable Issues",
            "issue_count": total_fix_count,
            "entry_count": affected_entry_count,
        }
        st.rerun()


def _render_pending_confirmation(groups: list[AutoFixGroup]) -> None:
    pending = st.session_state.get("validation_pending_fix")
    if not pending:
        return

    pending = _validate_pending_fix(pending, groups)
    if not pending:
        _clear_pending_fix()
        st.warning("The selected validation repair is no longer available.")
        return

    st.warning(
        "This will modify "
        f"{count_phrase(pending['entry_count'], 'entry', 'entries')} "
        "and save to disk. Proceed?"
    )
    col_confirm, col_cancel, _spacer = st.columns([1, 1, 4])
    with col_confirm:
        if st.button("Proceed", type="primary", key="validation_confirm_fix"):
            _execute_pending_fix(pending)
    with col_cancel:
        if st.button("Cancel", key="validation_cancel_fix"):
            _clear_pending_fix()
            st.rerun()


def _render_group(group: AutoFixGroup) -> None:
    st.markdown(f"**{group.title}**")
    st.caption(group.description)
    st.caption(
        f"{count_phrase(group.count, 'fix')} across "
        f"{count_phrase(len(group.entry_indices), 'affected entry', 'affected entries')}."
    )

    with st.expander("Preview affected entries", expanded=False):
        if not group.sample_entries:
            st.caption("No preview samples available.")
        for sample in group.sample_entries:
            _render_sample(sample)

    if st.button(f"Fix {group.title}", key=f"validation_fix_{group.code}"):
        st.session_state.validation_pending_fix = {
            "mode": "group",
            "code": group.code,
            "title": group.title,
            "issue_count": group.count,
            "entry_count": len(group.entry_indices),
        }
        st.rerun()

    st.divider()


def _render_sample(sample: AutoFixSample) -> None:
    st.caption(f"Entry {sample.entry_index + 1} - {_format_path(sample.path)}")
    col_before, col_after = st.columns(2)
    with col_before:
        st.caption("Before")
        st.write(_friendly_value(sample, before=True))
    with col_after:
        st.caption("After")
        st.write(_friendly_value(sample, before=False))
    with st.expander("Raw details", expanded=False):
        raw_before, raw_after = st.columns(2)
        with raw_before:
            st.caption("Before")
            st.code(_format_value(sample.original_value), language="json")
        with raw_after:
            st.caption("After")
            st.code(_format_value(sample.normalized_value), language="json")


def _validate_pending_fix(pending: dict, groups: list[AutoFixGroup]) -> dict | None:
    mode = pending.get("mode")
    if mode == "all":
        issue_count = sum(group.count for group in groups)
        entry_count = len({
            index
            for group in groups
            for index in group.entry_indices
        })
        if issue_count <= 0:
            return None
        return {
            **pending,
            "issue_count": issue_count,
            "entry_count": entry_count,
        }

    if mode == "group":
        code = pending.get("code")
        group = next((group for group in groups if group.code == code), None)
        if group is None:
            return None
        return {
            **pending,
            "title": group.title,
            "issue_count": group.count,
            "entry_count": len(group.entry_indices),
        }

    return None


def _execute_pending_fix(pending: dict) -> None:
    entries = st.session_state.get("loaded_entries", [])
    if pending.get("mode") == "all":
        repaired_entries, changed_indices = apply_all_auto_repairs(entries)
        backup_reason = "before_validation_fix_all"
    else:
        repaired_entries, changed_indices = apply_group_repairs(
            entries,
            str(pending.get("code") or ""),
        )
        backup_reason = f"before_validation_fix_{pending.get('code') or 'group'}"

    if not changed_indices:
        _clear_pending_fix()
        enqueue_flash("warning", "No entries needed repair.")
        st.rerun()
        return

    result = save_repaired_entries_service(
        dataset_path=st.session_state.get("loaded_path", ""),
        repaired_entries=repaired_entries,
        backup_reason=backup_reason,
    )
    if not result.ok:
        _clear_pending_fix()
        st.error(result.message)
        for error in result.errors:
            st.error(error)
        return

    persisted_entries = result.entries or repaired_entries
    apply_dataset_operation_result(result)
    st.session_state.loaded_entries = persisted_entries
    st.session_state.uuid_to_index = build_uuid_index(persisted_entries)
    clear_validate_entry_cache()
    _refresh_diagnostic_summary(persisted_entries)
    _clear_pending_fix()

    backup_note = " Backup created." if result.backup_path else ""
    enqueue_dataset_result_flash(
        f"Fixed {count_phrase(pending['issue_count'], 'issue')} in "
        f"{count_phrase(len(changed_indices), 'entry', 'entries')}.{backup_note}",
        result,
    )
    st.rerun()


def _refresh_diagnostic_summary(entries: list[dict]) -> None:
    diagnostics = summarize_entry_analysis(entries)
    summary = dict(st.session_state.get("tag_normalization_summary", {}) or {})
    summary["diagnostics"] = {
        "entries_analyzed": diagnostics.entries_analyzed,
        "valid_entries": diagnostics.valid_entries,
        "entries_with_errors": diagnostics.entries_with_errors,
        "entries_with_warnings": diagnostics.entries_with_warnings,
        "entries_with_info": diagnostics.entries_with_info,
        "error_count": diagnostics.error_count,
        "warning_count": diagnostics.warning_count,
        "info_count": diagnostics.info_count,
        "auto_repairable_count": diagnostics.auto_repairable_count,
    }
    st.session_state.tag_normalization_summary = summary
    st.session_state.normalization_pending = False


def _render_character_mapping_section(entries: list[dict]) -> None:
    report = st.session_state.get("character_candidates")
    candidates = tuple(getattr(report, "candidates", ()) or ())
    if not candidates:
        return

    st.divider()
    st.markdown("**Character Role Mapping**")
    pattern_summary = getattr(report, "pattern_summary", None)
    if pattern_summary:
        st.info(pattern_summary)

    st.caption(
        "Review the suggested training roles, then apply the mapping. LoreForge "
        "keeps character names as metadata while saving standard user/assistant roles."
    )

    role_mappings: dict[str, str] = {}
    for candidate in candidates:
        selected_role = _render_character_candidate(candidate, entries)
        role_mappings[candidate.source_role_label] = selected_role

    if st.button(
        "Apply Character Mapping",
        type="primary",
        key="validation_apply_character_mapping",
    ):
        _execute_character_mapping(role_mappings)


def _render_character_candidate(candidate, entries: list[dict]) -> str:
    st.markdown(f"**{candidate.suggested_display_name}**")
    st.caption(
        f"{count_phrase(candidate.occurrence_count, 'turn')} across "
        f"{count_phrase(len(candidate.entry_uuids), 'entry', 'entries')}."
    )
    role_options = ["user", "assistant"]
    selected_role = (
        candidate.suggested_training_role
        if candidate.suggested_training_role in role_options
        else "user"
    )
    selected = st.selectbox(
        "Training role",
        role_options,
        index=role_options.index(selected_role),
        key=f"validation_character_role_{candidate.suggested_slug}",
    )
    preview = _candidate_preview(candidate, entries)
    if preview:
        st.caption(f"Example: {preview}")
    return selected


def _candidate_preview(candidate, entries: list[dict]) -> str | None:
    if not candidate.turn_locations:
        return None
    location = candidate.turn_locations[0]
    entry_uuid = location.get("entry_uuid")
    turn_index = location.get("turn_index")
    if not isinstance(turn_index, int):
        return None

    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            continue
        # Defensive fallback for in-memory entries created outside the load
        # pipeline; persisted datasets should have stable entry UUIDs.
        current_uuid = get_entry_uuid(entry) or f"entry_index:{index}"
        if current_uuid != entry_uuid:
            continue
        messages = entry.get("messages")
        if not isinstance(messages, list) or turn_index >= len(messages):
            return None
        message = messages[turn_index]
        if not isinstance(message, dict):
            return None
        content = str(message.get("content", "")).strip()
        if len(content) > 140:
            content = content[:137] + "..."
        return content or "Blank turn"
    return None


def _execute_character_mapping(role_mappings: dict[str, str]) -> None:
    if not role_mappings:
        st.warning("No suggested character mapping is available.")
        return

    result = apply_character_mapping_service(
        dataset_path=st.session_state.get("loaded_path", ""),
        entries=st.session_state.get("loaded_entries", []),
        role_mappings=role_mappings,
    )
    if not result.ok:
        st.error(result.message)
        for error in result.errors:
            st.error(error)
        return

    persisted_entries = result.entries or st.session_state.get("loaded_entries", [])
    apply_dataset_operation_result(result)
    st.session_state.loaded_entries = persisted_entries
    st.session_state.uuid_to_index = build_uuid_index(persisted_entries)
    clear_validate_entry_cache()
    _refresh_diagnostic_summary(persisted_entries)
    st.session_state.pop("character_candidates", None)
    _clear_pending_fix()

    backup_note = " Backup created." if result.backup_path else ""
    created_note = (
        f" Created {count_phrase(len(result.characters_created), 'character')}."
        if result.characters_created
        else ""
    )
    enqueue_flash(
        "success",
        f"Mapped {count_phrase(result.mapped_turns, 'character turn')} across "
        f"{count_phrase(result.mapped_entries, 'entry', 'entries')}."
        f"{created_note}{backup_note}",
    )
    st.rerun()


def _render_inactive_character_prompt_reference_section(entries: list[dict]) -> None:
    references = find_inactive_character_prompt_references(entries)
    if not references:
        return

    st.divider()
    st.markdown("**Inactive Character Prompt References**")
    st.caption(
        "Some system prompts still mention deactivated characters. "
        f"Diagnostic code: `{CHARACTER_INACTIVE_REFERENCE_IN_PROMPT}`."
    )
    for display_name, entry_uuids in sorted(
        references.items(),
        key=lambda item: item[0].casefold(),
    ):
        st.warning(
            f"Inactive character '{display_name}' appears in "
            f"{count_phrase(len(entry_uuids), 'system prompt')}. "
            "Use Entry Search to review."
        )
        with st.expander(f"Entries referencing {display_name}", expanded=False):
            for entry_uuid in entry_uuids[:25]:
                st.caption(f"Entry UUID: {entry_uuid}")
            if len(entry_uuids) > 25:
                st.caption(
                    f"{count_phrase(len(entry_uuids) - 25, 'additional entry', 'additional entries')} hidden."
                )


def _clear_pending_fix() -> None:
    st.session_state.pop("validation_pending_fix", None)


def _format_path(path: tuple[str | int, ...]) -> str:
    if not path:
        return "entry"
    return ".".join(str(part) for part in path)


def _format_value(value: Any) -> str:
    try:
        formatted = json.dumps(value, ensure_ascii=False)
    except TypeError:
        formatted = repr(value)
    if len(formatted) > 180:
        return formatted[:177] + "..."
    return formatted


def _friendly_value(sample: AutoFixSample, *, before: bool) -> str:
    value = sample.original_value if before else sample.normalized_value
    code = sample.code
    path = sample.path

    if code == "base.missing_tags":
        return "No tags found." if before else "Empty tag list added."
    if code == "base.tags_not_list":
        return "Tags are not stored as a list." if before else "Empty tag list added."
    if code == "base.invalid_tag_value":
        return (
            f"Invalid tag value: {_format_inline_value(value)}"
            if before
            else "Invalid tag value removed."
        )
    if code == "base.empty_tag":
        return "Empty tag value." if before else "Empty tag value removed."
    if code == "chatml.role_canonicalization":
        return f"Role: {_format_inline_value(value)}"
    if code == "chatml.content_whitespace":
        return (
            "Text has extra leading or trailing spaces."
            if before
            else f"Trimmed text: {_format_inline_value(value)}"
        )
    if path and path[-1] == "role":
        return f"Role: {_format_inline_value(value)}"
    if path and path[-1] == "content":
        return f"Message text: {_format_inline_value(value)}"
    return _format_inline_value(value)


def _format_inline_value(value: Any) -> str:
    if value is None:
        return "None"
    if value == "":
        return "Blank text"
    if value == []:
        return "Empty list"
    text = str(value)
    return text if len(text) <= 120 else text[:117] + "..."
