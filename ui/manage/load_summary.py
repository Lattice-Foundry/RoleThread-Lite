"""Load, sidecar, and validation summary rendering for Manage Dataset."""
import streamlit as st

from core.dataset import analyze_entry
from core.format_conversion import FORMAT_CHATML, FORMAT_SHAREGPT, FORMAT_UNKNOWN
from core.text_helpers import count_phrase
from ui.guidance import render_recommended_action


def format_source_format(source_format: str) -> str:
    """Return a user-facing label for a detected source format."""

    labels = {
        FORMAT_CHATML: "ChatML",
        FORMAT_SHAREGPT: "ShareGPT",
        FORMAT_UNKNOWN: "Unknown",
    }
    return labels.get(source_format, source_format or "Unknown")


def render_load_format_summary(
    normalization,
    *,
    loaded_dataset_path: str | None = None,
    loaded_entry_count: int | None = None,
    correction_saved: bool = False,
    correction_failed: bool = False,
    normalized_entries: int = 0,
) -> None:
    """Render format, load, normalization, and follow-up notices."""

    source_format = normalization.source_format
    if source_format == FORMAT_SHAREGPT:
        st.info(
            "Detected format: ShareGPT. "
            "Export as ShareGPT to preserve the original format."
        )
    else:
        st.info(f"Detected format: {format_source_format(source_format)}.")

    if loaded_dataset_path is not None and loaded_entry_count is not None:
        diagnostics = normalization.diagnostics
        issue_entries = max(0, diagnostics.entries_analyzed - diagnostics.valid_entries)
        st.success(
            f"Loaded {count_phrase(loaded_entry_count, 'entry', 'entries')} "
            f"from `{loaded_dataset_path}`. "
            f"({diagnostics.valid_entries} valid, {issue_entries} with issues)."
        )
        if issue_entries:
            render_recommended_action(
                f"{count_phrase(issue_entries, 'entry', 'entries')} have validation issues.",
                button_label="Go to Validation →",
                target_page="Validation",
                key="guidance_load_validation",
            )
        untagged_entries = _count_untagged_entries(normalization.entries)
        if untagged_entries:
            render_recommended_action(
                f"{count_phrase(untagged_entries, 'entry', 'entries')} are untagged.",
                button_label="Tag them in Manage Dataset →",
                target_page="Manage Dataset",
                key="guidance_load_untagged",
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

    render_sidecar_summary()
    render_pending_trust_summary()


def render_sidecar_summary() -> None:
    """Render sibling sidecar import results when they are user-visible."""

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


def render_pending_trust_summary() -> None:
    """Render archived/imported tag notices after dataset load."""

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


def render_load_errors(normalization, errors: list[str], entries: list[dict]) -> bool:
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


def render_entry_issue_summary(entries: list[dict]) -> None:
    """Render the Manage Dataset validation issue count for loaded entries."""

    invalid_count = sum(1 for entry in entries if _entry_has_reportable_diagnostics(entry))
    if invalid_count:
        st.warning(
            f"{count_phrase(invalid_count, 'entry', 'entries')} "
            "have validation issues."
        )
    else:
        st.success("All entries are valid.")


def _entry_has_reportable_diagnostics(entry: dict) -> bool:
    result = analyze_entry(entry)
    return any(
        diagnostic.severity.value in {"error", "warning"}
        or (diagnostic.fixable and diagnostic.repair_kind.value == "automatic")
        for diagnostic in result.diagnostics
    )


def _count_untagged_entries(entries: list[dict]) -> int:
    return sum(
        1
        for entry in entries
        if not (
            isinstance(entry, dict)
            and isinstance(entry.get("tags"), list)
            and any(isinstance(tag, str) and tag.strip() for tag in entry["tags"])
        )
    )
