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
from core.rolethread_meta import ensure_entry_uuid, get_dataset_uuid_for_entries
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
    """Run the service-level load finalization contract.

    This function begins after the core file loader has already parsed records,
    detected source format, converted ShareGPT records to ChatML, run baseline
    normalization, and determined trusted/untrusted dataset state. The order is
    intentionally stable because later stages depend on earlier identity and
    registry decisions:

    1. Accept the loader summary, or normalize entries when called directly.
    2. Ensure every loaded entry has an entry UUID, without adding trust stamps.
    3. Create a protected working copy for untrusted source files.
    4. Resolve the effective dataset path after any working-copy creation.
    5. Validate the sibling sidecar dataset UUID before importing it.
    6. Keep sidecar import failures as load summaries, not hard crashes.
    7. Canonicalize stale tag aliases before registry adoption.
    8. Preserve alias rewrite counts for the session/load summary.
    9. Normalize known custom character roles into user/assistant turns.
    10. Persist trusted character mappings produced by known-role normalization.
    11. Collect unresolved custom-role candidates for user review.
    12. Refresh typed diagnostics only when finalization mutated entries.
    13. Adopt unknown dataset tags into archived/imported registry state.
    14. Build pending trust state for imported archived tags still in entries.
    15. Build the session-facing normalization and sidecar summary payload.
    16. Preserve the source format/native-state facts from the loader summary.
    17. Return entries and effective path for safe UI session publication.
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

    mismatch_summary = _sidecar_dataset_uuid_mismatch(
        sidecar_path,
        registry,
        entries,
    )
    if mismatch_summary is not None:
        return mismatch_summary, {}, {}

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


def _sidecar_dataset_uuid_mismatch(
    sidecar_path: Path,
    registry,
    entries: list[dict] | None,
) -> dict | None:
    """Return a load summary when a sibling sidecar belongs to another dataset."""

    if entries is None:
        return None
    entry_dataset_uuid = get_dataset_uuid_for_entries(entries)
    dataset_info = getattr(registry, "dataset_info", None)
    sidecar_dataset_uuid = getattr(dataset_info, "dataset_uuid", None)
    if (
        entry_dataset_uuid
        and sidecar_dataset_uuid
        and sidecar_dataset_uuid != entry_dataset_uuid
    ):
        error = (
            "Sidecar dataset UUID does not match the loaded dataset "
            f"({sidecar_dataset_uuid} != {entry_dataset_uuid})."
        )
        return sidecar_error_summary(
            sidecar_path,
            message="Registry sidecar belongs to a different dataset; sidecar import skipped.",
            error=error,
        )
    return None

