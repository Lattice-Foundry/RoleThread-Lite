"""Framework-independent dataset mutation services.

Services accept plain Python values and return DatasetOperationResult.
They must not import Streamlit or touch session state.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from pathlib import Path

from core.backups import create_dataset_backup
from core.dataset import (
    append_to_dataset,
    normalize_dataset_tags,
    normalize_entry_tags,
    replace_entry_tags,
    save_dataset,
    set_entry_system_prompt,
    validate_entry,
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


def _copy_entries(entries: list[dict]) -> list[dict]:
    return copy.deepcopy(entries)


def _normalize_entries(entries: list[dict]) -> list[dict]:
    return normalize_dataset_tags(entries).entries


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
            errors=["Each tag must be a string"],
        )

    edited_entry = copy.deepcopy(entries[entry_index])
    replace_entry_tags(edited_entry, tags)

    proposed_entries = _normalize_entries(
        _replace_entry_at_index(entries, entry_index, edited_entry)
    )
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
    """Replace tags for selected entries."""

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
    proposed_entries = _normalize_entries(proposed_entries)

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
        message=f"System prompt updated for {len(normalized_indices)} entries.",
        entries=proposed_entries,
        backup_path=backup_path,
        affected_count=len(normalized_indices),
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
        message=f"Deleted {len(normalized_indices)} entries.",
        entries=proposed_entries,
        backup_path=backup_path,
        affected_count=len(normalized_indices),
    )


def save_merged_entries_service(
    *,
    dataset_path: str,
    entries: list[dict],
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

    proposed_entries = _normalize_entries(entries)
    backup_path: str | None = None
    target = Path(dataset_path)

    if backup_enabled and target.exists():
        try:
            created_backup = create_dataset_backup(dataset_path, backup_reason)
        except Exception as exc:
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

    try:
        save_dataset(dataset_path, proposed_entries)
    except Exception as exc:
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
    )


def normalize_dataset_service(
    *,
    dataset_path: str,
    entries: list[dict],
    backup_reason: str = "before_normalize_data",
) -> DatasetOperationResult:
    """Persist normalized dataset structure to disk."""

    errors = _validate_dataset_path(dataset_path)
    if not isinstance(entries, list):
        errors.append("Loaded entries must be a list.")
    if errors:
        return DatasetOperationResult(
            ok=False,
            message="Could not normalize dataset.",
            errors=errors,
        )

    proposed_entries = _normalize_entries(entries)
    try:
        backup_path = _create_backup_if_enabled(dataset_path, True, backup_reason)
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
            message=f"Failed to save normalized dataset: {exc}",
        )

    return DatasetOperationResult(
        ok=True,
        message="Dataset normalized.",
        entries=proposed_entries,
        backup_path=backup_path,
        affected_count=len(proposed_entries),
    )


def create_entry_service(
    *,
    dataset_path: str,
    entries: list[dict],
    new_entry: dict,
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

    errors = validate_entry(new_entry)
    if errors:
        return DatasetOperationResult(
            ok=False,
            message="Entry is not valid.",
            errors=errors,
        )

    entry_to_append, _ = normalize_entry_tags(new_entry)
    try:
        append_to_dataset(dataset_path, entry_to_append)
    except Exception as exc:
        return DatasetOperationResult(
            ok=False,
            message=f"Failed to save: {exc}",
        )

    proposed_entries = _copy_entries(entries)
    proposed_entries.append(entry_to_append)
    proposed_entries = _normalize_entries(proposed_entries)
    return DatasetOperationResult(
        ok=True,
        message="Entry appended.",
        entries=proposed_entries,
        affected_count=1,
    )
