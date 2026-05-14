"""Service-layer load finalization orchestration."""
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
    canonicalize_entry_tag_aliases,
    normalize_dataset_entries,
    summarize_entry_analysis,
)
from core.load_pipeline import (
    build_pending_tag_trust,
    build_tag_normalization_summary,
    prepare_foreign_working_copy,
    sidecar_error_summary,
)
from core.loreforge_meta import ensure_entry_uuid
from core.registry_sidecar import read_sidecar, sidecar_path_for_dataset
from core.tag_registry import ensure_tags_exist_for_dataset
from core.tag_resolution import resolve_tag_lifecycle
from services.registry_sidecar_service import import_registry_sidecar


@dataclass(frozen=True)
class LoadPipelineResult:
    """Outputs from finalizing loaded entries for UI/session adoption."""

    entries: list[dict]
    effective_dataset_path: str | None
    dataset_source_format: str
    dataset_is_native: bool
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
    """Run service-level load-finalization stages after parse/detect/convert/normalize.

    Pipeline order:
    1. Use the provided load summary or normalize the given entries.
    2. Assign stable entry UUIDs without changing native/trust status.
    3. Create a protected working copy for foreign source files.
    4. Locate, read, and import a sibling registry sidecar.
    5. Canonicalize stale tag aliases in loaded entries.
    6. Apply trusted character-role mappings already known to the DB.
    7. Persist trusted character turn mappings created during normalization.
    8. Collect remaining custom-role character candidates.
    9. Refresh typed diagnostics if entries changed after core load analysis.
    10. Adopt unknown dataset tags into the registry/archive.
    11. Build the pending tag-trust map for imported archived tags.
    12. Return entries, effective path, summaries, candidates, and trust data.
    """

    normalization = normalization_summary or normalize_dataset_entries(entries)
    entries_changed_after_analysis = normalization_summary is None
    normalization.entries = [
        ensure_entry_uuid(entry) if isinstance(entry, dict) else entry
        for entry in normalization.entries
    ]

    working_copy_summary, effective_dataset_path = prepare_foreign_working_copy(
        dataset_path,
        dataset_is_native=normalization.dataset_is_native,
    )
    sidecar_summary, sidecar_tags, sidecar_categories = _import_sibling_sidecar(
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


def _import_sibling_sidecar(
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
            sidecar_error_summary(
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
            sidecar_error_summary(
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
