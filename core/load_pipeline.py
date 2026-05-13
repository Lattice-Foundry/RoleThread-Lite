"""Core load-finalization pipeline for parsed dataset entries."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from core.character_registry import (
    CharacterCandidateReport,
    collect_character_candidates,
    normalize_known_character_roles,
    upsert_character_mappings,
)
from core.dataset import (
    TagNormalizationSummary,
    build_entry_registry,
    canonicalize_entry_tag_aliases,
    get_entry_tags,
    normalize_dataset_entries,
    summarize_entry_analysis,
)
from core.registry_sidecar import read_sidecar, sidecar_path_for_dataset
from core.tag_metadata import get_current_tag_lifecycle_metadata
from core.tag_constants import ARCHIVE_ORIGIN_IMPORTED, TAG_STATUS_ARCHIVED
from core.tag_registry import (
    ensure_tags_exist_for_dataset,
    get_tag_by_slug_any_status,
    prettify_tag_name,
)
from core.tag_resolution import resolve_tag_lifecycle
from core.working_copy import create_dataset_working_copy
from services.registry_sidecar_service import import_registry_sidecar


@dataclass(frozen=True)
class LoadPipelineResult:
    """Outputs from finalizing loaded entries for UI/session adoption."""

    entries: list[dict]
    effective_dataset_path: str | None
    dataset_source_format: str
    dataset_is_native: bool
    entry_registry: dict
    tag_normalization_summary: dict
    normalization_pending: bool
    working_copy_summary: dict | None
    sidecar_import_summary: dict | None
    pending_tag_trust: dict[str, dict]
    character_candidates: CharacterCandidateReport | None
    normalization: TagNormalizationSummary


def finalize_loaded_entries(
    entries: list[dict],
    *,
    dataset_path: str | None = None,
    normalization_summary: TagNormalizationSummary | None = None,
) -> LoadPipelineResult:
    """Run core load-finalization stages after parse/detect/convert/normalize.

    Pipeline order:
    1. Use the provided load summary or normalize the given entries.
    2. Create a protected working copy for foreign source files.
    3. Locate, read, and import a sibling registry sidecar.
    4. Canonicalize stale tag aliases in loaded entries.
    5. Apply trusted character-role mappings already known to the DB.
    6. Persist trusted character turn mappings created during normalization.
    7. Collect remaining custom-role character candidates.
    8. Refresh typed diagnostics if entries changed after core load analysis.
    9. Adopt unknown dataset tags into the registry/archive.
    10. Build the pending tag-trust map for imported archived tags.
    11. Return entries, effective path, summaries, candidates, and trust data.
    """

    normalization = normalization_summary or normalize_dataset_entries(entries)
    entries_changed_after_analysis = normalization_summary is None

    working_copy_summary, effective_dataset_path = prepare_foreign_working_copy(
        dataset_path,
        dataset_is_native=normalization.dataset_is_native,
    )
    sidecar_summary, sidecar_tags, sidecar_categories = import_sibling_sidecar(
        effective_dataset_path,
        normalization.entries,
    )

    alias_canonical_entries, alias_summary = canonicalize_entry_tag_aliases(
        normalization.entries,
        resolve_tag_lifecycle,
    )
    if alias_summary.get("rewrite_count"):
        entries_changed_after_analysis = True
        normalization.entries = alias_canonical_entries
        normalization.alias_rewrites = dict(alias_summary.get("rewrites", {}))
        normalization.alias_rewrite_count = int(alias_summary.get("rewrite_count", 0))
        normalization.alias_rewritten_entries = int(alias_summary.get("changed_entries", 0))
        normalization.changed_entries += normalization.alias_rewritten_entries

    known_character_result = normalize_known_character_roles(normalization.entries)
    if known_character_result.changed_turns:
        entries_changed_after_analysis = True
        normalization.entries = known_character_result.entries
        normalization.changed_entries += known_character_result.changed_entries
        normalization.role_values_normalized += known_character_result.changed_turns
        upsert_character_mappings(known_character_result.mapping_payload)

    character_candidates = collect_character_candidates(normalization.entries)
    if entries_changed_after_analysis:
        normalization.diagnostics = summarize_entry_analysis(
            normalization.entries,
            metadata_errors_block_validity=False,
        )

    adoption = ensure_tags_exist_for_dataset(normalization.entries)
    pending_trust = build_pending_tag_trust(
        normalization.entries,
        sidecar_tags=sidecar_tags,
        sidecar_categories=sidecar_categories,
    )
    tag_summary = build_tag_normalization_summary(
        normalization=normalization,
        adoption=adoption,
        working_copy_summary=working_copy_summary,
        sidecar_summary=sidecar_summary,
        pending_trust=pending_trust,
        character_candidates=character_candidates,
    )

    return LoadPipelineResult(
        entries=normalization.entries,
        effective_dataset_path=effective_dataset_path,
        dataset_source_format=normalization.source_format,
        dataset_is_native=normalization.dataset_is_native,
        entry_registry=build_entry_registry(normalization.entries),
        tag_normalization_summary=tag_summary,
        normalization_pending=normalization.changed_entries > 0,
        working_copy_summary=working_copy_summary,
        sidecar_import_summary=sidecar_summary,
        pending_tag_trust=pending_trust,
        character_candidates=(
            character_candidates if character_candidates.has_candidates else None
        ),
        normalization=normalization,
    )


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


def import_sibling_sidecar(
    dataset_path: str | None,
    entries: list[dict] | None = None,
) -> tuple[dict | None, dict, dict]:
    """Read and import a sibling registry sidecar if one exists."""

    if not dataset_path:
        return None, {}, {}

    sidecar_path = sidecar_path_for_dataset(Path(dataset_path))
    if not sidecar_path.exists():
        return None, {}, {}

    try:
        registry = read_sidecar(sidecar_path)
    except Exception as exc:
        return (
            _sidecar_error_summary(
                sidecar_path,
                message=f"Could not read registry sidecar: {exc}",
                error=str(exc),
            ),
            {},
            {},
        )

    try:
        result = import_registry_sidecar(registry=registry, entries=entries)
    except Exception as exc:
        return (
            _sidecar_error_summary(
                sidecar_path,
                message=f"Could not import registry sidecar: {exc}",
                error=str(exc),
            ),
            {tag.slug: tag for tag in registry.tags},
            {category.slug: category for category in registry.categories},
        )

    summary = {
        "found": True,
        "ok": result.ok,
        "path": str(sidecar_path),
        "message": result.message,
        "categories_created": list(result.categories_created),
        "tags_created": list(result.tags_created),
        "tags_promoted": list(result.tags_promoted),
        "aliases_imported": list(result.aliases_imported),
        "characters_created": list(getattr(result, "characters_created", [])),
        "character_mappings_imported": list(
            getattr(result, "character_mappings_imported", [])
        ),
        "conflicts": list(result.conflicts),
        "warnings": list(result.warnings),
        "errors": list(result.errors),
    }
    return (
        summary,
        {tag.slug: tag for tag in registry.tags},
        {category.slug: category for category in registry.categories},
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


def _sidecar_error_summary(path: Path, *, message: str, error: str) -> dict:
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
