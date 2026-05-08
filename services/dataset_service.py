"""Framework-independent dataset mutation workflows."""
from __future__ import annotations

import copy
from dataclasses import dataclass, field

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
