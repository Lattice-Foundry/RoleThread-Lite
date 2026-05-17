"""Framework-independent dataset mutation services.

Services accept plain Python values and return DatasetOperationResult.
They must not import Streamlit or touch session state.
"""
from __future__ import annotations

import copy
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
import traceback
from uuid import uuid4

from core.backups import create_dataset_backup
from core.character_registry import (
    delete_entry_character_turns,
    get_entry_character_turns,
    set_entry_character_turns,
)
from core.dataset import (
    canonicalize_entry_tag_aliases,
    load_dataset,
    normalize_dataset_entries,
    normalize_dataset_tags,
    normalize_entry_tags,
    replace_entry_tags,
    save_dataset,
    set_entry_system_prompt,
    validate_entry,
)
from core.rolethread_meta import (
    ROLETHREAD_META_KEY,
    ensure_entry_uuid,
    get_dataset_uuid_for_entries,
    get_entry_uuid,
    stamp_entries,
)
from core.registry_sidecar import read_sidecar, sidecar_path_for_dataset
from core.role_normalization import normalize_entry_roles
from core.working_copy import (
    canonical_training_dataset_path,
    migrate_training_dataset_to_subfolder,
)


@dataclass
class DatasetOperationResult:
    """Structured result returned by dataset mutation services."""

    ok: bool
    message: str
    entries: list[dict] | None = None
    errors: list[str] = field(default_factory=list)
    backup_path: str | None = None
    affected_count: int = 0
    dataset_path: str | None = None
    sidecar_ok: bool = True
    sidecar_message: str | None = None
    warnings: list[str] = field(default_factory=list)
    source_sidecar_summary: "SourceSidecarImportSummary | None" = None


@dataclass
class DatasetSaveResult:
    """Internal result for a JSONL save plus best-effort sidecar refresh."""

    dataset_path: str
    entries: list[dict]
    sidecar_ok: bool = True
    sidecar_message: str | None = None


@dataclass
class SourceSidecarImportSummary:
    """Summary of source sidecars discovered during merge."""

    source_count: int = 0
    found_count: int = 0
    imported_count: int = 0
    missing_paths: list[str] = field(default_factory=list)
    imported_paths: list[str] = field(default_factory=list)
    failed_paths: list[str] = field(default_factory=list)
    categories_created: list[str] = field(default_factory=list)
    tags_created: list[str] = field(default_factory=list)
    tags_promoted: list[str] = field(default_factory=list)
    aliases_imported: list[str] = field(default_factory=list)
    characters_created: list[str] = field(default_factory=list)
    character_mappings_imported: list[str] = field(default_factory=list)
    character_slugs: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class _DatasetMutationWrite:
    """Internal result for the common backup-then-save mutation path."""

    backup_path: str | None
    save_result: DatasetSaveResult
    warnings: tuple[str, ...] = ()


def _copy_entries(entries: list[dict]) -> list[dict]:
    return copy.deepcopy(entries)


def _normalize_entries(entries: list[dict]) -> list[dict]:
    normalized_entries = normalize_dataset_tags(entries).entries
    return _canonicalize_alias_tags(normalized_entries)


def _canonicalize_alias_tags(entries: list[dict]) -> list[dict]:
    # Lazy import keeps dataset mutation services independent from registry setup at import time.
    from core.tag_resolution import resolve_tag_lifecycle

    canonical_entries, _summary = canonicalize_entry_tag_aliases(
        entries,
        resolve_tag_lifecycle,
    )
    return canonical_entries


def _save_dataset_with_sidecar(
    dataset_path: str,
    entries: list[dict],
    *,
    dataset_uuid: str | None = None,
    extra_character_slugs: set[str] | None = None,
) -> DatasetSaveResult:
    target_path = _prepare_dataset_save_path(dataset_path)
    resolved_dataset_uuid = dataset_uuid or _dataset_uuid_for_save(target_path, entries)
    stamped_entries = stamp_entries(entries, dataset_uuid=resolved_dataset_uuid)
    save_dataset(target_path, stamped_entries)
    sidecar_ok = True
    sidecar_message = None
    try:
        if extra_character_slugs:
            sidecar_status = _write_registry_sidecar(
                target_path,
                stamped_entries,
                extra_character_slugs=extra_character_slugs,
            )
        else:
            sidecar_status = _write_registry_sidecar(target_path, stamped_entries)
        if sidecar_status is not None:
            sidecar_ok, sidecar_message = sidecar_status
    except Exception:
        traceback.print_exc()
        sidecar_ok = False
        sidecar_message = "Registry sidecar could not be updated."
    return DatasetSaveResult(
        dataset_path=target_path,
        entries=stamped_entries,
        sidecar_ok=sidecar_ok,
        sidecar_message=sidecar_message,
    )


def _prepare_dataset_save_path(dataset_path: str) -> str:
    source = Path(dataset_path)
    if source.exists():
        return migrate_training_dataset_to_subfolder(source).working_path
    return str(canonical_training_dataset_path(source))


def _write_registry_sidecar(
    dataset_path: str,
    entries: list[dict],
    *,
    extra_character_slugs: set[str] | None = None,
) -> tuple[bool, str | None]:
    try:
        # Lazy import avoids making every dataset service import initialize sidecar/registry queries.
        from services.registry_sidecar_service import export_registry_sidecar

        result = export_registry_sidecar(
            dataset_path=dataset_path,
            entries=entries,
            dataset_uuid=get_dataset_uuid_for_entries(entries),
            extra_character_slugs=extra_character_slugs,
        )
    except Exception:
        traceback.print_exc()
        return False, "Registry sidecar could not be updated."
    if not result.ok:
        print(result.message)
        return False, result.message
    return True, None


def _dataset_uuid_for_save(dataset_path: str, entries: list[dict]) -> str | None:
    dataset_uuid = get_dataset_uuid_for_entries(entries)
    if dataset_uuid:
        return dataset_uuid
    sidecar_path = sidecar_path_for_dataset(Path(dataset_path))
    if not sidecar_path.exists():
        return None
    try:
        return read_sidecar(sidecar_path).dataset_info.dataset_uuid
    except Exception:
        return None


def _sidecar_result_fields(save_result: DatasetSaveResult) -> dict:
    return {
        "sidecar_ok": save_result.sidecar_ok,
        "sidecar_message": save_result.sidecar_message,
    }


def _apply_character_turn_update(
    save_result: DatasetSaveResult,
    *,
    entry_uuid: str | None,
    character_turns: list[dict] | None = None,
    clear_character_mappings: bool = False,
) -> tuple[DatasetSaveResult, list[str]]:
    """Apply best-effort entry character mappings after a dataset save."""

    if character_turns is None and not clear_character_mappings:
        return save_result, []

    warnings: list[str] = []
    if not entry_uuid:
        warnings.append("Character mappings could not be updated because the entry UUID is missing.")
        return save_result, warnings

    try:
        if clear_character_mappings:
            delete_entry_character_turns(entry_uuid)
        else:
            set_entry_character_turns(entry_uuid, character_turns or [])
    except Exception as exc:
        traceback.print_exc()
        warnings.append(f"Character mappings could not be updated: {exc}")
        return save_result, warnings

    sidecar_ok, sidecar_message = _write_registry_sidecar(
        save_result.dataset_path,
        save_result.entries,
    )
    if not sidecar_ok:
        save_result.sidecar_ok = False
        save_result.sidecar_message = sidecar_message
    return save_result, warnings


def _import_source_sidecars(
    source_paths: list[str] | None,
    *,
    surviving_entry_uuids: set[str] | None = None,
) -> SourceSidecarImportSummary:
    summary = SourceSidecarImportSummary(source_count=len(source_paths or []))
    if not source_paths:
        return summary

    for raw_path in source_paths:
        source_path = Path(raw_path)
        source_sidecar_path = sidecar_path_for_dataset(source_path)
        if not source_sidecar_path.exists():
            summary.missing_paths.append(str(source_sidecar_path))
            continue

        summary.found_count += 1
        entries, parse_errors = load_dataset(str(source_path))
        if parse_errors:
            summary.warnings.append(
                f"Source sidecar {source_sidecar_path} was imported without "
                f"dataset UUID validation because source parse warnings were present."
            )
        try:
            registry = read_sidecar(source_sidecar_path)
            import_result = _import_registry_sidecar(
                registry=registry,
                entries=entries if entries else None,
                include_entry_character_mappings=True,
                valid_entry_uuids=surviving_entry_uuids,
            )
        except Exception as exc:
            traceback.print_exc()
            summary.failed_paths.append(str(source_sidecar_path))
            summary.errors.append(f"{source_sidecar_path}: {exc}")
            continue

        if import_result.ok:
            summary.imported_count += 1
            summary.imported_paths.append(str(source_sidecar_path))
            summary.character_slugs.extend(
                character.slug for character in registry.characters
            )
            summary.categories_created.extend(import_result.categories_created)
            summary.tags_created.extend(import_result.tags_created)
            summary.tags_promoted.extend(import_result.tags_promoted)
            summary.aliases_imported.extend(import_result.aliases_imported)
            summary.characters_created.extend(import_result.characters_created)
            summary.character_mappings_imported.extend(
                import_result.character_mappings_imported
            )
            summary.conflicts.extend(import_result.conflicts)
            summary.warnings.extend(import_result.warnings)
        else:
            summary.failed_paths.append(str(source_sidecar_path))
            summary.errors.extend(
                f"{source_sidecar_path}: {error}"
                for error in (import_result.errors or [import_result.message])
            )

    return summary


def _import_registry_sidecar(**kwargs):
    from services.registry_sidecar_service import import_registry_sidecar

    return import_registry_sidecar(**kwargs)


def _valid_index(entries: list[dict], index: int) -> bool:
    return 0 <= index < len(entries)


def _normalized_indices(entry_indices: list[int], entries: list[dict]) -> tuple[list[int], list[str]]:
    errors: list[str] = []
    if not entry_indices:
        errors.append("No entries selected.")
        return [], errors

    normalized: list[int] = []
    seen: set[int] = set()
    for index in entry_indices:
        if not isinstance(index, int) or not _valid_index(entries, index):
            errors.append(f"Invalid entry index: {index}")
            continue
        if index not in seen:
            seen.add(index)
            normalized.append(index)
    return normalized, errors


def _validate_dataset_path(dataset_path: str) -> list[str]:
    if not dataset_path:
        return ["No dataset loaded. Please load or create a dataset before saving."]
    if not Path(dataset_path).is_file():
        return ["Dataset file was not found."]
    return []


def _replace_entry_at_index(
    entries: list[dict],
    index: int,
    new_entry: dict,
) -> list[dict]:
    proposed_entries = _copy_entries(entries)
    proposed_entries[index] = copy.deepcopy(new_entry)
    return proposed_entries


def _entry_with_fresh_uuid(entry: dict) -> dict:
    """Return a copy of entry with a new entry UUID and no dataset identity drift."""

    proposed = copy.deepcopy(entry)
    metadata = proposed.get(ROLETHREAD_META_KEY)
    if not isinstance(metadata, dict):
        metadata = {}
    metadata = dict(metadata)
    metadata.pop("dataset_uuid", None)
    metadata["entry_uuid"] = str(uuid4())
    proposed[ROLETHREAD_META_KEY] = metadata
    return ensure_entry_uuid(proposed)


def _non_system_messages(entry: dict) -> list[dict]:
    messages = entry.get("messages") if isinstance(entry, dict) else None
    if not isinstance(messages, list):
        return []
    return [
        copy.deepcopy(message)
        for message in messages
        if isinstance(message, dict) and message.get("role") != "system"
    ]


def _system_message(entry: dict) -> dict:
    messages = entry.get("messages") if isinstance(entry, dict) else None
    if isinstance(messages, list):
        for message in messages:
            if isinstance(message, dict) and message.get("role") == "system":
                return copy.deepcopy(message)
    return {"role": "system", "content": ""}


def _dedupe_tags_preserving_order(entries: list[dict]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for entry in entries:
        tags = entry.get("tags") if isinstance(entry, dict) else None
        if not isinstance(tags, list):
            continue
        for tag in tags:
            if isinstance(tag, str) and tag not in seen:
                seen.add(tag)
                merged.append(tag)
    return merged


def _mapping_to_dict(mapping, *, turn_index: int) -> dict | None:
    character = getattr(mapping, "character", None)
    character_slug = getattr(character, "slug", None)
    if not character_slug:
        return None
    return {
        "turn_index": turn_index,
        "character_slug": character_slug,
        "training_role": getattr(mapping, "training_role", "") or "",
        "source_role_label": getattr(mapping, "source_role_label", None),
    }


def _apply_character_mapping_replacements(
    save_result: DatasetSaveResult,
    replacements: list[tuple[str, list[dict]]],
) -> tuple[DatasetSaveResult, list[str]]:
    warnings: list[str] = []
    if not replacements:
        return save_result, warnings

    try:
        for entry_uuid, turns in replacements:
            set_entry_character_turns(entry_uuid, turns)
    except Exception as exc:
        traceback.print_exc()
        warnings.append(f"Character mappings could not be updated: {exc}")
        return save_result, warnings

    sidecar_ok, sidecar_message = _write_registry_sidecar(
        save_result.dataset_path,
        save_result.entries,
    )
    if not sidecar_ok:
        save_result.sidecar_ok = False
        save_result.sidecar_message = sidecar_message
    return save_result, warnings


def _create_backup_if_enabled(
    dataset_path: str,
    backup_enabled: bool,
    backup_reason: str,
) -> str | None:
    if not backup_enabled:
        return None
    backup_path = create_dataset_backup(dataset_path, backup_reason)
    if backup_path is None:
        raise FileNotFoundError(
            "Could not create dataset backup because the dataset file was not found."
        )
    return str(backup_path)


def _save_entries_with_backup(
    *,
    dataset_path: str,
    entries: list[dict],
    backup_enabled: bool,
    backup_reason: str,
    backup_error_prefix: str = "Failed to create dataset backup",
    save_error_prefix: str = "Failed to save dataset",
) -> tuple[_DatasetMutationWrite | None, DatasetOperationResult | None]:
    """Run the common backup/save/sidecar refresh path for dataset mutations."""

    try:
        backup_path = _create_backup_if_enabled(dataset_path, backup_enabled, backup_reason)
    except Exception as exc:
        traceback.print_exc()
        return None, DatasetOperationResult(
            ok=False,
            message=f"{backup_error_prefix}: {exc}",
        )

    try:
        save_result = _save_dataset_with_sidecar(dataset_path, entries)
    except Exception as exc:
        traceback.print_exc()
        return None, DatasetOperationResult(
            ok=False,
            message=f"{save_error_prefix}: {exc}",
        )

    return _DatasetMutationWrite(backup_path=backup_path, save_result=save_result), None


def _dataset_mutation_pipeline(
    *,
    dataset_path: str,
    entries: list[dict],
    backup_enabled: bool,
    backup_reason: str,
    backup_error_prefix: str = "Failed to create dataset backup",
    save_error_prefix: str = "Failed to save dataset",
    after_save: Callable[
        [DatasetSaveResult],
        tuple[DatasetSaveResult, list[str]],
    ] | None = None,
) -> tuple[_DatasetMutationWrite | None, DatasetOperationResult | None]:
    """Run the shared dataset mutation write path with optional post-save metadata work."""

    write, error_result = _save_entries_with_backup(
        dataset_path=dataset_path,
        entries=entries,
        backup_enabled=backup_enabled,
        backup_reason=backup_reason,
        backup_error_prefix=backup_error_prefix,
        save_error_prefix=save_error_prefix,
    )
    if error_result is not None or write is None:
        return None, error_result
    if after_save is None:
        return write, None

    try:
        save_result, warnings = after_save(write.save_result)
    except Exception as exc:
        traceback.print_exc()
        return None, DatasetOperationResult(
            ok=False,
            message=f"{save_error_prefix}: {exc}",
        )

    return _DatasetMutationWrite(
        backup_path=write.backup_path,
        save_result=save_result,
        warnings=tuple(warnings),
    ), None


def save_quick_edit_service(
    *,
    dataset_path: str,
    entries: list[dict],
    entry_index: int,
    updated_messages: list[dict],
    backup_enabled: bool = True,
    backup_reason: str = "before_quick_edit",
) -> DatasetOperationResult:
    """Persist user/assistant message edits for one entry."""

    if not dataset_path:
        return DatasetOperationResult(
            ok=False,
            message="No dataset loaded. Please load or create a dataset before saving.",
        )
    if not _valid_index(entries, entry_index):
        return DatasetOperationResult(
            ok=False,
            message="Could not find the selected entry.",
        )

    edited_entry = copy.deepcopy(entries[entry_index])
    edited_entry["messages"] = copy.deepcopy(updated_messages)
    edited_entry, _ = normalize_entry_roles(edited_entry)
    normalized = normalize_dataset_entries([edited_entry])
    edited_entry = normalized.entries[0] if normalized.entries else edited_entry

    errors = validate_entry(edited_entry)
    if errors:
        return DatasetOperationResult(
            ok=False,
            message="Entry validation failed.",
            errors=errors,
        )

    proposed_entries = _normalize_entries(
        _replace_entry_at_index(entries, entry_index, edited_entry)
    )
    write, error_result = _dataset_mutation_pipeline(
        dataset_path=dataset_path,
        entries=proposed_entries,
        backup_enabled=backup_enabled,
        backup_reason=backup_reason,
    )
    if error_result is not None:
        return error_result
    save_result = write.save_result
    backup_path = write.backup_path
    saved_path = save_result.dataset_path
    proposed_entries = save_result.entries

    return DatasetOperationResult(
        ok=True,
        message="Entry updated.",
        entries=proposed_entries,
        backup_path=backup_path,
        affected_count=1,
        dataset_path=saved_path,
        **_sidecar_result_fields(save_result),
    )


def save_full_edit_service(
    *,
    dataset_path: str,
    entries: list[dict],
    entry_index: int,
    updated_entry: dict,
    character_turns: list[dict] | None = None,
    clear_character_mappings: bool = False,
    backup_enabled: bool = True,
    backup_reason: str = "before_full_edit",
) -> DatasetOperationResult:
    """Persist a fully edited replacement entry."""

    if not dataset_path:
        return DatasetOperationResult(
            ok=False,
            message="No dataset loaded. Please load or create a dataset before saving.",
        )
    if not _valid_index(entries, entry_index):
        return DatasetOperationResult(
            ok=False,
            message="Could not find the selected entry.",
        )

    edited_entry = copy.deepcopy(updated_entry)
    if ROLETHREAD_META_KEY not in edited_entry:
        existing_meta = entries[entry_index].get(ROLETHREAD_META_KEY)
        if isinstance(existing_meta, dict):
            edited_entry[ROLETHREAD_META_KEY] = copy.deepcopy(existing_meta)
    edited_entry, _ = normalize_entry_roles(edited_entry)
    errors = validate_entry(edited_entry)
    if errors:
        return DatasetOperationResult(
            ok=False,
            message="Entry validation failed.",
            errors=errors,
        )

    proposed_entries = _normalize_entries(
        _replace_entry_at_index(entries, entry_index, edited_entry)
    )
    def after_save(save_result: DatasetSaveResult) -> tuple[DatasetSaveResult, list[str]]:
        saved_entries = save_result.entries
        entry_uuid = get_entry_uuid(saved_entries[entry_index])
        return _apply_character_turn_update(
            save_result,
            entry_uuid=entry_uuid,
            character_turns=character_turns,
            clear_character_mappings=clear_character_mappings,
        )

    write, error_result = _dataset_mutation_pipeline(
        dataset_path=dataset_path,
        entries=proposed_entries,
        backup_enabled=backup_enabled,
        backup_reason=backup_reason,
        after_save=after_save,
    )
    if error_result is not None:
        return error_result
    save_result = write.save_result
    backup_path = write.backup_path
    saved_path = save_result.dataset_path
    proposed_entries = save_result.entries

    return DatasetOperationResult(
        ok=True,
        message="Entry updated.",
        entries=proposed_entries,
        backup_path=backup_path,
        affected_count=1,
        dataset_path=saved_path,
        warnings=list(write.warnings),
        **_sidecar_result_fields(save_result),
    )


def replace_single_entry_tags_service(
    *,
    dataset_path: str,
    entries: list[dict],
    entry_index: int,
    tags: list[str],
    backup_enabled: bool = True,
    backup_reason: str = "before_single_tag_edit",
) -> DatasetOperationResult:
    """Replace tags for one entry."""

    if not dataset_path:
        return DatasetOperationResult(
            ok=False,
            message="No dataset loaded. Please load or create a dataset before saving.",
        )
    if not _valid_index(entries, entry_index):
        return DatasetOperationResult(
            ok=False,
            message="Could not find the selected entry.",
        )

    if not all(isinstance(tag, str) for tag in tags):
        return DatasetOperationResult(
            ok=False,
            message="Tag validation failed.",
            errors=[
                "Tags contain non-text values, like numbers. "
                "These will be removed when you save."
            ],
        )

    edited_entry = copy.deepcopy(entries[entry_index])
    replace_entry_tags(edited_entry, tags)

    proposed_entries = _normalize_entries(
        _replace_entry_at_index(entries, entry_index, edited_entry)
    )
    write, error_result = _dataset_mutation_pipeline(
        dataset_path=dataset_path,
        entries=proposed_entries,
        backup_enabled=backup_enabled,
        backup_reason=backup_reason,
    )
    if error_result is not None:
        return error_result
    save_result = write.save_result
    backup_path = write.backup_path
    saved_path = save_result.dataset_path
    proposed_entries = save_result.entries

    return DatasetOperationResult(
        ok=True,
        message="Tags updated for selected entry.",
        entries=proposed_entries,
        backup_path=backup_path,
        affected_count=1,
        dataset_path=saved_path,
        **_sidecar_result_fields(save_result),
    )


def replace_tags_bulk_service(
    *,
    dataset_path: str,
    entries: list[dict],
    entry_indices: list[int],
    tags: list[str],
    backup_enabled: bool = True,
    backup_reason: str = "before_bulk_tag_replace",
) -> DatasetOperationResult:
    """Replace tags for selected entries."""

    errors = _validate_dataset_path(dataset_path)
    normalized_indices, index_errors = _normalized_indices(entry_indices, entries)
    errors.extend(index_errors)
    if not all(isinstance(tag, str) for tag in tags):
        errors.append(
            "Tags contain non-text values, like numbers. "
            "These will be removed when you save."
        )
    if errors:
        return DatasetOperationResult(
            ok=False,
            message="Could not replace tags.",
            errors=errors,
        )

    proposed_entries = _copy_entries(entries)
    for index in normalized_indices:
        replace_entry_tags(proposed_entries[index], tags)
    proposed_entries = _normalize_entries(proposed_entries)

    write, error_result = _dataset_mutation_pipeline(
        dataset_path=dataset_path,
        entries=proposed_entries,
        backup_enabled=backup_enabled,
        backup_reason=backup_reason,
    )
    if error_result is not None:
        return error_result
    save_result = write.save_result
    backup_path = write.backup_path
    saved_path = save_result.dataset_path
    proposed_entries = save_result.entries

    return DatasetOperationResult(
        ok=True,
        message=f"Tags replaced for {len(normalized_indices)} entries.",
        entries=proposed_entries,
        backup_path=backup_path,
        affected_count=len(normalized_indices),
        dataset_path=saved_path,
        **_sidecar_result_fields(save_result),
    )


def clear_tags_bulk_service(
    *,
    dataset_path: str,
    entries: list[dict],
    entry_indices: list[int],
    backup_enabled: bool = True,
    backup_reason: str = "before_bulk_tag_clear",
) -> DatasetOperationResult:
    """Clear tags for selected entries."""

    errors = _validate_dataset_path(dataset_path)
    normalized_indices, index_errors = _normalized_indices(entry_indices, entries)
    errors.extend(index_errors)
    if errors:
        return DatasetOperationResult(
            ok=False,
            message="Could not clear tags.",
            errors=errors,
        )

    proposed_entries = _copy_entries(entries)
    for index in normalized_indices:
        replace_entry_tags(proposed_entries[index], [])
    proposed_entries = _normalize_entries(proposed_entries)

    write, error_result = _dataset_mutation_pipeline(
        dataset_path=dataset_path,
        entries=proposed_entries,
        backup_enabled=backup_enabled,
        backup_reason=backup_reason,
    )
    if error_result is not None:
        return error_result
    save_result = write.save_result
    backup_path = write.backup_path
    saved_path = save_result.dataset_path
    proposed_entries = save_result.entries

    return DatasetOperationResult(
        ok=True,
        message=f"Tags cleared for {len(normalized_indices)} entries.",
        entries=proposed_entries,
        backup_path=backup_path,
        affected_count=len(normalized_indices),
        dataset_path=saved_path,
        **_sidecar_result_fields(save_result),
    )


def replace_system_prompt_bulk_service(
    *,
    dataset_path: str,
    entries: list[dict],
    entry_indices: list[int],
    system_prompt: str,
    backup_enabled: bool = True,
    backup_reason: str = "before_bulk_system_prompt_replace",
) -> DatasetOperationResult:
    """Replace the system prompt for selected entries."""

    errors = _validate_dataset_path(dataset_path)
    normalized_indices, index_errors = _normalized_indices(entry_indices, entries)
    errors.extend(index_errors)
    if not isinstance(system_prompt, str):
        errors.append("System prompt must be a string")
    if errors:
        return DatasetOperationResult(
            ok=False,
            message="Could not update system prompt.",
            errors=errors,
        )

    proposed_entries = _copy_entries(entries)
    for index in normalized_indices:
        set_entry_system_prompt(proposed_entries[index], system_prompt)
    proposed_entries = _normalize_entries(proposed_entries)

    write, error_result = _dataset_mutation_pipeline(
        dataset_path=dataset_path,
        entries=proposed_entries,
        backup_enabled=backup_enabled,
        backup_reason=backup_reason,
    )
    if error_result is not None:
        return error_result
    save_result = write.save_result
    backup_path = write.backup_path
    saved_path = save_result.dataset_path
    proposed_entries = save_result.entries

    return DatasetOperationResult(
        ok=True,
        message=f"System prompt updated for {len(normalized_indices)} entries.",
        entries=proposed_entries,
        backup_path=backup_path,
        affected_count=len(normalized_indices),
        dataset_path=saved_path,
        **_sidecar_result_fields(save_result),
    )


def delete_entries_service(
    *,
    dataset_path: str,
    entries: list[dict],
    entry_indices: list[int],
    backup_enabled: bool = True,
    backup_reason: str = "before_delete_selected",
) -> DatasetOperationResult:
    """Delete selected entries by source index."""

    errors = _validate_dataset_path(dataset_path)
    normalized_indices, index_errors = _normalized_indices(entry_indices, entries)
    errors.extend(index_errors)
    if errors:
        return DatasetOperationResult(
            ok=False,
            message="Could not delete selected entries.",
            errors=errors,
        )

    delete_indices = set(normalized_indices)
    proposed_entries = [
        copy.deepcopy(entry)
        for index, entry in enumerate(entries)
        if index not in delete_indices
    ]
    proposed_entries = _normalize_entries(proposed_entries)

    write, error_result = _dataset_mutation_pipeline(
        dataset_path=dataset_path,
        entries=proposed_entries,
        backup_enabled=backup_enabled,
        backup_reason=backup_reason,
    )
    if error_result is not None:
        return error_result
    save_result = write.save_result
    backup_path = write.backup_path
    saved_path = save_result.dataset_path
    proposed_entries = save_result.entries

    return DatasetOperationResult(
        ok=True,
        message=f"Deleted {len(normalized_indices)} entries.",
        entries=proposed_entries,
        backup_path=backup_path,
        affected_count=len(normalized_indices),
        dataset_path=saved_path,
        **_sidecar_result_fields(save_result),
    )


def split_entry_service(
    *,
    dataset_path: str,
    entry_uuid: str,
    split_points: list[int],
    entries: list[dict],
    backup_enabled: bool = True,
    backup_reason: str = "before_entry_split",
) -> DatasetOperationResult:
    """Replace one entry with multiple entries split at exchange boundaries."""

    errors = _validate_dataset_path(dataset_path)
    if not entry_uuid:
        errors.append("No entry selected for splitting.")
    entry_index = None
    for index, entry in enumerate(entries):
        if get_entry_uuid(entry) == entry_uuid:
            entry_index = index
            break
    if entry_index is None:
        errors.append("Could not find the selected entry.")
    if not split_points:
        errors.append("Choose at least one split point.")
    if errors:
        return DatasetOperationResult(
            ok=False,
            message="Could not split entry.",
            errors=errors,
        )

    original_entry = entries[entry_index]
    turns = _non_system_messages(original_entry)
    if len(turns) < 4 or len(turns) % 2 != 0:
        return DatasetOperationResult(
            ok=False,
            message="Could not split entry.",
            errors=["Entry must contain at least two complete exchanges to split."],
        )

    exchange_count = len(turns) // 2
    boundaries = sorted({point for point in split_points if isinstance(point, int)})
    invalid_points = [
        point for point in boundaries if point <= 0 or point >= exchange_count
    ]
    if invalid_points:
        return DatasetOperationResult(
            ok=False,
            message="Could not split entry.",
            errors=[f"Invalid split point: {invalid_points[0]}"],
        )

    system_message = _system_message(original_entry)
    tags = copy.deepcopy(original_entry.get("tags", []))
    turn_boundaries = [0] + [point * 2 for point in boundaries] + [len(turns)]
    existing_mappings = get_entry_character_turns(entry_uuid)
    mappings_by_original_index = {
        getattr(mapping, "turn_index", -1): mapping
        for mapping in existing_mappings
    }

    split_entries: list[dict] = []
    pending_mappings_by_segment: list[list[dict]] = []
    for segment_index in range(len(turn_boundaries) - 1):
        start_offset = turn_boundaries[segment_index]
        end_offset = turn_boundaries[segment_index + 1]
        segment_turns = copy.deepcopy(turns[start_offset:end_offset])
        segment_entry = _entry_with_fresh_uuid({
            "messages": [copy.deepcopy(system_message)] + segment_turns,
            "tags": copy.deepcopy(tags),
        })
        validation_errors = validate_entry(segment_entry)
        if validation_errors:
            return DatasetOperationResult(
                ok=False,
                message="Split entry validation failed.",
                errors=validation_errors,
            )
        split_entries.append(segment_entry)

        segment_mappings: list[dict] = []
        for local_offset in range(end_offset - start_offset):
            original_turn_index = 1 + start_offset + local_offset
            mapping = mappings_by_original_index.get(original_turn_index)
            if mapping is None:
                continue
            mapping_dict = _mapping_to_dict(mapping, turn_index=1 + local_offset)
            if mapping_dict is not None:
                segment_mappings.append(mapping_dict)
        pending_mappings_by_segment.append(segment_mappings)

    proposed_entries = _copy_entries(entries)
    proposed_entries[entry_index:entry_index + 1] = split_entries
    proposed_entries = _normalize_entries(proposed_entries)

    def after_save(save_result: DatasetSaveResult) -> tuple[DatasetSaveResult, list[str]]:
        saved_entries = save_result.entries
        replacements = []
        for offset, turns_for_segment in enumerate(pending_mappings_by_segment):
            saved_entry_uuid = get_entry_uuid(saved_entries[entry_index + offset])
            if saved_entry_uuid:
                replacements.append((saved_entry_uuid, turns_for_segment))
        save_result, warnings = _apply_character_mapping_replacements(
            save_result,
            replacements,
        )
        try:
            delete_entry_character_turns(entry_uuid)
        except Exception as exc:
            warnings.append(f"Original character mappings could not be cleared: {exc}")
        return save_result, warnings

    write, error_result = _dataset_mutation_pipeline(
        dataset_path=dataset_path,
        entries=proposed_entries,
        backup_enabled=backup_enabled,
        backup_reason=backup_reason,
        save_error_prefix="Failed to save split entries",
        after_save=after_save,
    )
    if error_result is not None:
        return error_result
    save_result = write.save_result
    backup_path = write.backup_path
    saved_path = save_result.dataset_path
    proposed_entries = save_result.entries

    return DatasetOperationResult(
        ok=True,
        message=f"Split entry into {len(split_entries)} entries.",
        entries=proposed_entries,
        backup_path=backup_path,
        affected_count=len(split_entries),
        dataset_path=saved_path,
        warnings=list(write.warnings),
        **_sidecar_result_fields(save_result),
    )


def join_entries_service(
    *,
    dataset_path: str,
    entry_uuids: list[str],
    entries: list[dict],
    backup_enabled: bool = True,
    backup_reason: str = "before_entry_join",
) -> DatasetOperationResult:
    """Replace selected entries with one joined multi-turn conversation."""

    errors = _validate_dataset_path(dataset_path)
    if len(entry_uuids or []) < 2:
        errors.append("Select at least two entries to join.")

    uuid_to_index = {
        entry_uuid: index
        for index, entry in enumerate(entries)
        if (entry_uuid := get_entry_uuid(entry))
    }
    selected_indices: list[int] = []
    seen_uuids: set[str] = set()
    for entry_uuid in entry_uuids or []:
        if entry_uuid in seen_uuids:
            continue
        seen_uuids.add(entry_uuid)
        index = uuid_to_index.get(entry_uuid)
        if index is None:
            errors.append(f"Could not find selected entry: {entry_uuid}")
        else:
            selected_indices.append(index)
    if errors:
        return DatasetOperationResult(
            ok=False,
            message="Could not join entries.",
            errors=errors,
        )

    selected_entries = [entries[index] for index in selected_indices]
    system_message = _system_message(selected_entries[0])
    joined_turns: list[dict] = []
    pending_mappings: list[dict] = []
    next_turn_index = 1
    system_prompts_differ = False
    first_system_content = system_message.get("content", "")

    for selected_entry in selected_entries:
        if _system_message(selected_entry).get("content", "") != first_system_content:
            system_prompts_differ = True
        entry_uuid = get_entry_uuid(selected_entry)
        mappings_by_original_index = {
            getattr(mapping, "turn_index", -1): mapping
            for mapping in get_entry_character_turns(entry_uuid or "")
        }
        turns = _non_system_messages(selected_entry)
        for local_offset, turn in enumerate(turns):
            joined_turns.append(copy.deepcopy(turn))
            mapping = mappings_by_original_index.get(1 + local_offset)
            if mapping is not None:
                mapping_dict = _mapping_to_dict(mapping, turn_index=next_turn_index)
                if mapping_dict is not None:
                    pending_mappings.append(mapping_dict)
            next_turn_index += 1

    joined_entry = _entry_with_fresh_uuid({
        "messages": [copy.deepcopy(system_message)] + joined_turns,
        "tags": _dedupe_tags_preserving_order(selected_entries),
    })
    validation_errors = validate_entry(joined_entry)
    if validation_errors:
        return DatasetOperationResult(
            ok=False,
            message="Joined entry validation failed.",
            errors=validation_errors,
        )

    first_selected_index = min(selected_indices)
    selected_index_set = set(selected_indices)
    proposed_entries: list[dict] = []
    inserted_joined_entry = False
    for index, entry in enumerate(entries):
        if index == first_selected_index:
            proposed_entries.append(joined_entry)
            inserted_joined_entry = True
        if index in selected_index_set:
            continue
        proposed_entries.append(copy.deepcopy(entry))
    if not inserted_joined_entry:
        proposed_entries.append(joined_entry)
    proposed_entries = _normalize_entries(proposed_entries)

    def after_save(save_result: DatasetSaveResult) -> tuple[DatasetSaveResult, list[str]]:
        saved_entries = save_result.entries
        joined_uuid = get_entry_uuid(saved_entries[first_selected_index])
        replacements = [(joined_uuid, pending_mappings)] if joined_uuid else []
        save_result, mapping_warnings = _apply_character_mapping_replacements(
            save_result,
            replacements,
        )
        warnings = list(mapping_warnings)
        for removed_uuid in seen_uuids:
            try:
                delete_entry_character_turns(removed_uuid)
            except Exception as exc:
                warnings.append(f"Old character mappings could not be cleared: {exc}")
        return save_result, warnings

    write, error_result = _dataset_mutation_pipeline(
        dataset_path=dataset_path,
        entries=proposed_entries,
        backup_enabled=backup_enabled,
        backup_reason=backup_reason,
        save_error_prefix="Failed to save joined entry",
        after_save=after_save,
    )
    if error_result is not None:
        return error_result
    save_result = write.save_result
    backup_path = write.backup_path
    saved_path = save_result.dataset_path
    proposed_entries = save_result.entries
    warnings = list(write.warnings)

    if system_prompts_differ:
        warnings.append("System prompts differed; the first selected system prompt was used.")

    return DatasetOperationResult(
        ok=True,
        message=f"Joined {len(selected_indices)} entries.",
        entries=proposed_entries,
        backup_path=backup_path,
        affected_count=1,
        dataset_path=saved_path,
        warnings=warnings,
        **_sidecar_result_fields(save_result),
    )


def save_merged_entries_service(
    *,
    dataset_path: str,
    entries: list[dict],
    source_paths: list[str] | None = None,
    backup_enabled: bool = True,
    backup_reason: str = "before_merge_save",
) -> DatasetOperationResult:
    """Persist the final result of a dataset merge."""

    if not dataset_path:
        return DatasetOperationResult(
            ok=False,
            message="No merge output path selected.",
        )
    if not isinstance(entries, list):
        return DatasetOperationResult(
            ok=False,
            message="Merged entries must be a list.",
        )

    proposed_entries = normalize_dataset_entries(entries).entries
    backup_path: str | None = None
    target = Path(dataset_path)

    if backup_enabled and target.exists():
        try:
            created_backup = create_dataset_backup(dataset_path, backup_reason)
        except Exception as exc:
            traceback.print_exc()
            return DatasetOperationResult(
                ok=False,
                message=f"Failed to create merge output backup: {exc}",
            )
        if created_backup is None:
            return DatasetOperationResult(
                ok=False,
                message="Could not create backup for existing merge output.",
            )
        backup_path = str(created_backup)

    surviving_entry_uuids = {
        entry_uuid
        for entry in proposed_entries
        if (entry_uuid := get_entry_uuid(entry))
    }
    source_sidecar_summary = _import_source_sidecars(
        source_paths,
        surviving_entry_uuids=surviving_entry_uuids,
    )
    proposed_entries = _canonicalize_alias_tags(proposed_entries)

    try:
        save_result = _save_dataset_with_sidecar(
            dataset_path,
            proposed_entries,
            dataset_uuid=str(uuid4()),
            extra_character_slugs=set(source_sidecar_summary.character_slugs),
        )
        saved_path = save_result.dataset_path
        proposed_entries = save_result.entries
    except Exception as exc:
        traceback.print_exc()
        return DatasetOperationResult(
            ok=False,
            message=f"Failed to save merged dataset: {exc}",
        )

    return DatasetOperationResult(
        ok=True,
        message="Merged dataset saved.",
        entries=proposed_entries,
        backup_path=backup_path,
        affected_count=len(proposed_entries),
        dataset_path=saved_path,
        source_sidecar_summary=source_sidecar_summary,
        **_sidecar_result_fields(save_result),
    )


def save_repaired_entries_service(
    *,
    dataset_path: str,
    repaired_entries: list[dict],
    backup_reason: str = "before_validation_repair",
) -> DatasetOperationResult:
    """Persist exact validation-repaired entries with a dataset backup."""

    errors = _validate_dataset_path(dataset_path)
    if not isinstance(repaired_entries, list):
        errors.append("Repaired entries must be a list.")
    if errors:
        return DatasetOperationResult(
            ok=False,
            message="Could not save repaired entries.",
            errors=errors,
        )

    proposed_entries = [
        normalize_entry_roles(entry)[0] if isinstance(entry, dict) else copy.deepcopy(entry)
        for entry in repaired_entries
    ]
    proposed_entries = _canonicalize_alias_tags(proposed_entries)
    write, error_result = _dataset_mutation_pipeline(
        dataset_path=dataset_path,
        entries=proposed_entries,
        backup_enabled=True,
        backup_reason=backup_reason,
        save_error_prefix="Failed to save repaired entries",
    )
    if error_result is not None:
        return error_result
    save_result = write.save_result
    backup_path = write.backup_path
    saved_path = save_result.dataset_path
    proposed_entries = save_result.entries

    return DatasetOperationResult(
        ok=True,
        message="Repaired entries saved.",
        entries=proposed_entries,
        backup_path=backup_path,
        affected_count=len(proposed_entries),
        dataset_path=saved_path,
        **_sidecar_result_fields(save_result),
    )


def create_entry_service(
    *,
    dataset_path: str,
    entries: list[dict],
    new_entry: dict,
    character_turns: list[dict] | None = None,
    backup_enabled: bool = True,
    backup_reason: str = "before_create_entry",
) -> DatasetOperationResult:
    """Validate and append one newly created entry."""

    if not dataset_path:
        return DatasetOperationResult(
            ok=False,
            message="No dataset loaded. Please load or create a dataset before saving an exchange.",
        )
    if not isinstance(entries, list):
        return DatasetOperationResult(
            ok=False,
            message="Loaded entries must be a list.",
        )
    if not isinstance(new_entry, dict):
        return DatasetOperationResult(
            ok=False,
            message="New entry must be a dictionary.",
        )

    new_entry, _ = normalize_entry_roles(new_entry)
    errors = validate_entry(new_entry)
    if errors:
        return DatasetOperationResult(
            ok=False,
            message="Entry is not valid.",
            errors=errors,
        )

    proposed_entries = _copy_entries(entries)
    entry_to_append, _ = normalize_entry_tags(new_entry)
    proposed_entries.append(entry_to_append)
    proposed_entries = _normalize_entries(proposed_entries)

    def after_save(save_result: DatasetSaveResult) -> tuple[DatasetSaveResult, list[str]]:
        saved_entries = save_result.entries
        entry_uuid = get_entry_uuid(saved_entries[-1]) if saved_entries else None
        return _apply_character_turn_update(
            save_result,
            entry_uuid=entry_uuid,
            character_turns=character_turns,
        )

    write, error_result = _dataset_mutation_pipeline(
        dataset_path=dataset_path,
        entries=proposed_entries,
        backup_enabled=backup_enabled,
        backup_reason=backup_reason,
        save_error_prefix="Failed to save",
        after_save=after_save,
    )
    if error_result is not None:
        return error_result
    save_result = write.save_result
    backup_path = write.backup_path
    saved_path = save_result.dataset_path
    proposed_entries = save_result.entries

    return DatasetOperationResult(
        ok=True,
        message="Entry appended.",
        entries=proposed_entries,
        backup_path=backup_path,
        affected_count=1,
        dataset_path=saved_path,
        warnings=list(write.warnings),
        **_sidecar_result_fields(save_result),
    )


def duplicate_entry_service(
    *,
    dataset_path: str,
    entries: list[dict],
    entry_index: int,
    backup_enabled: bool = True,
) -> DatasetOperationResult:
    """Append a duplicate of one existing entry with a fresh entry UUID."""

    errors = _validate_dataset_path(dataset_path)
    if errors:
        return DatasetOperationResult(ok=False, message=errors[0], errors=errors)
    if not isinstance(entries, list):
        return DatasetOperationResult(
            ok=False,
            message="Loaded entries must be a list.",
        )
    if not _valid_index(entries, entry_index):
        return DatasetOperationResult(
            ok=False,
            message="Could not find the selected entry.",
        )

    source_entry = entries[entry_index]
    if not isinstance(source_entry, dict):
        return DatasetOperationResult(
            ok=False,
            message="Selected entry is not a dictionary.",
        )

    duplicate_entry = _entry_with_fresh_uuid(source_entry)
    duplicate_entry, _ = normalize_entry_tags(duplicate_entry)
    duplicate_entry, _ = normalize_entry_roles(duplicate_entry)
    validation_errors = validate_entry(duplicate_entry)
    if validation_errors:
        return DatasetOperationResult(
            ok=False,
            message="Duplicated entry is not valid.",
            errors=validation_errors,
        )

    proposed_entries = _copy_entries(entries)
    proposed_entries.append(duplicate_entry)
    proposed_entries = _normalize_entries(proposed_entries)

    def after_save(save_result: DatasetSaveResult) -> tuple[DatasetSaveResult, list[str]]:
        saved_entries = save_result.entries
        source_uuid = get_entry_uuid(source_entry)
        new_uuid = get_entry_uuid(saved_entries[-1]) if saved_entries else None
        character_turns = _character_turn_payloads(source_uuid)
        return _apply_character_turn_update(
            save_result,
            entry_uuid=new_uuid,
            character_turns=character_turns,
        )

    write, error_result = _dataset_mutation_pipeline(
        dataset_path=dataset_path,
        entries=proposed_entries,
        backup_enabled=backup_enabled,
        backup_reason="before_duplicate_entry",
        save_error_prefix="Failed to duplicate entry",
        after_save=after_save,
    )
    if error_result is not None:
        return error_result
    save_result = write.save_result
    backup_path = write.backup_path
    saved_path = save_result.dataset_path
    proposed_entries = save_result.entries

    return DatasetOperationResult(
        ok=True,
        message="Entry duplicated.",
        entries=proposed_entries,
        backup_path=backup_path,
        affected_count=1,
        dataset_path=saved_path,
        warnings=list(write.warnings),
        **_sidecar_result_fields(save_result),
    )


def _character_turn_payloads(entry_uuid: str | None) -> list[dict] | None:
    if not entry_uuid:
        return None
    payloads: list[dict] = []
    for mapping in get_entry_character_turns(entry_uuid):
        character = getattr(mapping, "character", None)
        character_slug = getattr(character, "slug", None) or getattr(
            mapping,
            "character_slug",
            None,
        )
        if not character_slug:
            continue
        payloads.append({
            "turn_index": mapping.turn_index,
            "character_slug": character_slug,
            "training_role": mapping.training_role,
            "source_role_label": mapping.source_role_label,
        })
    return payloads

