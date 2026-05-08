"""Framework-independent dataset mutation workflows."""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from pathlib import Path

from core.backups import create_dataset_backup
from core.dataset import replace_entry_tags, save_dataset, validate_entry


@dataclass
class DatasetOperationResult:
    ok: bool
    message: str
    entries: list[dict] | None = None
    errors: list[str] = field(default_factory=list)
    backup_path: str | None = None
    affected_count: int = 0


def _copy_entries(entries: list[dict]) -> list[dict]:
    return copy.deepcopy(entries)


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


def save_quick_edit_service(
    *,
    dataset_path: str,
    entries: list[dict],
    entry_index: int,
    updated_messages: list[dict],
    backup_enabled: bool = True,
    backup_reason: str = "before_quick_edit",
) -> DatasetOperationResult:
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

    errors = validate_entry(edited_entry)
    if errors:
        return DatasetOperationResult(
            ok=False,
            message="Entry validation failed.",
            errors=errors,
        )

    proposed_entries = _replace_entry_at_index(entries, entry_index, edited_entry)
    try:
        backup_path = _create_backup_if_enabled(dataset_path, backup_enabled, backup_reason)
    except Exception as exc:
        return DatasetOperationResult(
            ok=False,
            message=f"Failed to create dataset backup: {exc}",
        )
    try:
        save_dataset(dataset_path, proposed_entries)
    except Exception as exc:
        return DatasetOperationResult(
            ok=False,
            message=f"Failed to save dataset: {exc}",
        )

    return DatasetOperationResult(
        ok=True,
        message="Entry updated.",
        entries=proposed_entries,
        backup_path=backup_path,
        affected_count=1,
    )


def save_full_edit_service(
    *,
    dataset_path: str,
    entries: list[dict],
    entry_index: int,
    updated_entry: dict,
    backup_enabled: bool = True,
    backup_reason: str = "before_full_edit",
) -> DatasetOperationResult:
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
    errors = validate_entry(edited_entry)
    if errors:
        return DatasetOperationResult(
            ok=False,
            message="Entry validation failed.",
            errors=errors,
        )

    proposed_entries = _replace_entry_at_index(entries, entry_index, edited_entry)
    try:
        backup_path = _create_backup_if_enabled(dataset_path, backup_enabled, backup_reason)
    except Exception as exc:
        return DatasetOperationResult(
            ok=False,
            message=f"Failed to create dataset backup: {exc}",
        )
    try:
        save_dataset(dataset_path, proposed_entries)
    except Exception as exc:
        return DatasetOperationResult(
            ok=False,
            message=f"Failed to save dataset: {exc}",
        )

    return DatasetOperationResult(
        ok=True,
        message="Entry updated.",
        entries=proposed_entries,
        backup_path=backup_path,
        affected_count=1,
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
            errors=["Each tag must be a string"],
        )

    edited_entry = copy.deepcopy(entries[entry_index])
    replace_entry_tags(edited_entry, tags)

    proposed_entries = _replace_entry_at_index(entries, entry_index, edited_entry)
    try:
        backup_path = _create_backup_if_enabled(dataset_path, backup_enabled, backup_reason)
    except Exception as exc:
        return DatasetOperationResult(
            ok=False,
            message=f"Failed to create dataset backup: {exc}",
        )
    try:
        save_dataset(dataset_path, proposed_entries)
    except Exception as exc:
        return DatasetOperationResult(
            ok=False,
            message=f"Failed to save dataset: {exc}",
        )

    return DatasetOperationResult(
        ok=True,
        message="Tags updated for selected entry.",
        entries=proposed_entries,
        backup_path=backup_path,
        affected_count=1,
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
    errors = _validate_dataset_path(dataset_path)
    normalized_indices, index_errors = _normalized_indices(entry_indices, entries)
    errors.extend(index_errors)
    if not all(isinstance(tag, str) for tag in tags):
        errors.append("Each tag must be a string")
    if errors:
        return DatasetOperationResult(
            ok=False,
            message="Could not replace tags.",
            errors=errors,
        )

    proposed_entries = _copy_entries(entries)
    for index in normalized_indices:
        replace_entry_tags(proposed_entries[index], tags)

    try:
        backup_path = _create_backup_if_enabled(dataset_path, backup_enabled, backup_reason)
    except Exception as exc:
        return DatasetOperationResult(
            ok=False,
            message=f"Failed to create dataset backup: {exc}",
        )
    try:
        save_dataset(dataset_path, proposed_entries)
    except Exception as exc:
        return DatasetOperationResult(
            ok=False,
            message=f"Failed to save dataset: {exc}",
        )

    return DatasetOperationResult(
        ok=True,
        message=f"Tags replaced for {len(normalized_indices)} entries.",
        entries=proposed_entries,
        backup_path=backup_path,
        affected_count=len(normalized_indices),
    )


def clear_tags_bulk_service(
    *,
    dataset_path: str,
    entries: list[dict],
    entry_indices: list[int],
    backup_enabled: bool = True,
    backup_reason: str = "before_bulk_tag_clear",
) -> DatasetOperationResult:
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

    try:
        backup_path = _create_backup_if_enabled(dataset_path, backup_enabled, backup_reason)
    except Exception as exc:
        return DatasetOperationResult(
            ok=False,
            message=f"Failed to create dataset backup: {exc}",
        )
    try:
        save_dataset(dataset_path, proposed_entries)
    except Exception as exc:
        return DatasetOperationResult(
            ok=False,
            message=f"Failed to save dataset: {exc}",
        )

    return DatasetOperationResult(
        ok=True,
        message=f"Tags cleared for {len(normalized_indices)} entries.",
        entries=proposed_entries,
        backup_path=backup_path,
        affected_count=len(normalized_indices),
    )
