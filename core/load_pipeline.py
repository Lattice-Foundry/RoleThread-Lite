"""Core-safe helpers for load finalization."""
from __future__ import annotations

from pathlib import Path

from core.character_registry import CharacterCandidateReport
from core.dataset import (
    TagNormalizationSummary,
    get_entry_tags,
)
from core.tag_metadata import get_current_tag_lifecycle_metadata
from core.tag_constants import ARCHIVE_ORIGIN_IMPORTED, TAG_STATUS_ARCHIVED
from core.tag_registry import (
    get_tag_by_slug_any_status,
    prettify_tag_name,
)
from core.working_copy import create_dataset_working_copy


def prepare_foreign_working_copy(
    dataset_path: str | None,
    *,
    dataset_is_native: bool,
) -> tuple[dict | None, str | None]:
    """Create a protected working copy for foreign source files."""

    if not dataset_path:
        return None, dataset_path
    if dataset_is_native:
        return None, dataset_path
    if not Path(dataset_path).exists():
        return None, dataset_path

    result = create_dataset_working_copy(dataset_path)
    if not result.created:
        return None, result.working_path
    return (
        {
            "original_path": result.original_path,
            "working_path": result.working_path,
            "sidecar_copied": result.sidecar_copied,
            "sidecar_path": result.sidecar_path,
        },
        result.working_path,
    )


def build_pending_tag_trust(
    entries: list[dict],
    *,
    sidecar_tags: dict,
    sidecar_categories: dict,
) -> dict[str, dict]:
    """Build pending trust data for imported archived tags still in entries."""

    entry_indices_by_slug: dict[str, list[int]] = {}
    for index, entry in enumerate(entries):
        for slug in get_entry_tags(entry):
            entry_indices_by_slug.setdefault(slug, []).append(index)

    pending: dict[str, dict] = {}
    for slug, entry_indices in sorted(entry_indices_by_slug.items()):
        tag = get_tag_by_slug_any_status(slug)
        if tag is None or tag.status != TAG_STATUS_ARCHIVED:
            continue

        metadata = get_current_tag_lifecycle_metadata(slug)
        archive_origin = metadata.get("archive_origin")
        if archive_origin is None and getattr(tag, "category_id", None) is None:
            archive_origin = ARCHIVE_ORIGIN_IMPORTED
        if archive_origin != ARCHIVE_ORIGIN_IMPORTED:
            continue

        sidecar_tag = sidecar_tags.get(slug)
        sidecar_category = (
            sidecar_categories.get(sidecar_tag.category_slug)
            if sidecar_tag and sidecar_tag.category_slug
            else None
        )
        pending[slug] = {
            "display_name": getattr(tag, "name", None) or prettify_tag_name(slug),
            "entry_indices": entry_indices,
            "usage_count": len(entry_indices),
            "registry_status": getattr(tag, "status", TAG_STATUS_ARCHIVED),
            "archive_origin": archive_origin,
            "sidecar_category_slug": sidecar_tag.category_slug if sidecar_tag else None,
            "sidecar_category_name": sidecar_category.name if sidecar_category else None,
            "sidecar_status": sidecar_tag.status if sidecar_tag else None,
            "resolution": "sidecar_hint" if sidecar_tag else "no_hint",
            "status": "pending",
        }
    return pending


def build_tag_normalization_summary(
    *,
    normalization: TagNormalizationSummary,
    adoption,
    working_copy_summary: dict | None,
    sidecar_summary: dict | None,
    pending_trust: dict[str, dict],
    character_candidates: CharacterCandidateReport,
) -> dict:
    """Build the session-facing load summary dict."""

    return {
        "changed_entries": normalization.changed_entries,
        "changed_tags": normalization.changed_tags,
        "structural_changed_entries": normalization.structural_changed_entries,
        "tag_metadata_added_count": normalization.tag_metadata_added_count,
        "role_values_normalized": normalization.role_values_normalized,
        "message_content_trimmed": normalization.message_content_trimmed,
        "dropped_tags": normalization.dropped_tags,
        "source_format": normalization.source_format,
        "format_counts": normalization.format_counts,
        "format_confidence": normalization.format_confidence,
        "format_converted_count": normalization.format_converted_count,
        "format_already_target_count": normalization.format_already_target_count,
        "format_warnings": normalization.format_warnings,
        "diagnostics": {
            "entries_analyzed": normalization.diagnostics.entries_analyzed,
            "valid_entries": normalization.diagnostics.valid_entries,
            "entries_with_errors": normalization.diagnostics.entries_with_errors,
            "entries_with_warnings": normalization.diagnostics.entries_with_warnings,
            "entries_with_info": normalization.diagnostics.entries_with_info,
            "error_count": normalization.diagnostics.error_count,
            "warning_count": normalization.diagnostics.warning_count,
            "info_count": normalization.diagnostics.info_count,
            "auto_repairable_count": normalization.diagnostics.auto_repairable_count,
        },
        "adopted_count": adoption.created_count,
        "adopted_slugs": adoption.created_slugs or [],
        "sidecar_import": sidecar_summary,
        "pending_trust_count": len(pending_trust),
        "dataset_is_native": normalization.dataset_is_native,
        "working_copy": working_copy_summary,
        "alias_rewrites": normalization.alias_rewrites,
        "alias_rewrite_count": normalization.alias_rewrite_count,
        "alias_rewritten_entries": normalization.alias_rewritten_entries,
        "character_candidate_count": len(character_candidates.candidates),
        "character_candidate_labels": [
            candidate.source_role_label
            for candidate in character_candidates.candidates
        ],
        "character_candidate_pattern": character_candidates.pattern_summary,
    }


def sidecar_error_summary(path: Path, *, message: str, error: str) -> dict:
    return {
        "found": True,
        "ok": False,
        "path": str(path),
        "message": message,
        "categories_created": [],
        "tags_created": [],
        "tags_promoted": [],
        "aliases_imported": [],
        "characters_created": [],
        "character_mappings_imported": [],
        "conflicts": [],
        "warnings": [],
        "errors": [error],
    }
