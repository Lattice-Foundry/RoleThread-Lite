"""Framework-independent services for character role mapping."""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
import traceback

from core.character_registry import (
    bulk_set_character_mappings,
    create_character,
    get_character_by_slug,
    normalize_character_name,
)
from core.rolethread_meta import ensure_entry_uuid, get_entry_uuid
from services.dataset_service import DatasetOperationResult, save_repaired_entries_service

_TRAINING_ROLES = {"user", "assistant"}


@dataclass
class CharacterMappingResult:
    """Structured result returned by the character mapping workflow."""

    ok: bool
    message: str
    entries: list[dict] | None = None
    errors: list[str] = field(default_factory=list)
    backup_path: str | None = None
    dataset_path: str | None = None
    characters_created: list[str] = field(default_factory=list)
    mapped_entries: int = 0
    mapped_turns: int = 0


def apply_character_mapping_service(
    *,
    dataset_path: str,
    entries: list[dict],
    role_mappings: dict[str, str],
) -> CharacterMappingResult:
    """Normalize selected custom role labels and persist character mappings."""

    errors = _validate_inputs(dataset_path, entries, role_mappings)
    if errors:
        return CharacterMappingResult(
            ok=False,
            message="Could not apply character mapping.",
            errors=errors,
        )

    try:
        proposed_entries, mapping_payload = _build_mapped_entries(
            entries,
            role_mappings,
        )
    except Exception as exc:
        traceback.print_exc()
        return CharacterMappingResult(
            ok=False,
            message=f"Could not prepare character mapping: {exc}",
            errors=[str(exc)],
        )

    mapped_turns = sum(len(mapping["turns"]) for mapping in mapping_payload)
    if mapped_turns == 0:
        return CharacterMappingResult(
            ok=False,
            message="Could not apply character mapping.",
            errors=["No matching custom role turns were found."],
        )

    save_result = save_repaired_entries_service(
        dataset_path=dataset_path,
        repaired_entries=proposed_entries,
        backup_reason="before_character_mapping",
    )
    if not save_result.ok:
        return _from_dataset_result(save_result)

    persisted_entries = save_result.entries or proposed_entries
    try:
        created_characters = _ensure_characters(role_mappings)
        mapping_counts = bulk_set_character_mappings(mapping_payload)
        _write_sidecar_after_mapping(save_result.dataset_path or dataset_path, persisted_entries)
    except Exception as exc:
        traceback.print_exc()
        return CharacterMappingResult(
            ok=False,
            message=f"Saved entries, but could not store character mappings: {exc}",
            entries=persisted_entries,
            errors=[str(exc)],
            backup_path=save_result.backup_path,
            dataset_path=save_result.dataset_path,
            mapped_entries=len(mapping_payload),
            mapped_turns=mapped_turns,
        )

    return CharacterMappingResult(
        ok=True,
        message=(
            f"Mapped {mapping_counts['turns']} character turns across "
            f"{mapping_counts['entries']} entries."
        ),
        entries=persisted_entries,
        backup_path=save_result.backup_path,
        dataset_path=save_result.dataset_path,
        characters_created=created_characters,
        mapped_entries=mapping_counts["entries"],
        mapped_turns=mapping_counts["turns"],
    )


def _validate_inputs(
    dataset_path: str,
    entries: list[dict],
    role_mappings: dict[str, str],
) -> list[str]:
    errors: list[str] = []
    if not dataset_path:
        errors.append("No dataset loaded. Please load a dataset before mapping characters.")
    if not isinstance(entries, list):
        errors.append("Loaded entries must be a list.")
    if not isinstance(role_mappings, dict) or not role_mappings:
        errors.append("No character roles were selected.")

    for label, training_role in (role_mappings or {}).items():
        if not isinstance(label, str) or not label.strip():
            errors.append("Character role labels must be text.")
        if training_role not in _TRAINING_ROLES:
            errors.append(f"Invalid training role for '{label}': {training_role}")
    return errors


def _build_mapped_entries(
    entries: list[dict],
    role_mappings: dict[str, str],
) -> tuple[list[dict], list[dict]]:
    cleaned_mappings = {
        source_label.strip(): training_role
        for source_label, training_role in role_mappings.items()
        if isinstance(source_label, str)
    }
    proposed_entries: list[dict] = []
    mapping_by_entry: dict[str, list[dict]] = {}

    for entry in entries:
        if not isinstance(entry, dict):
            proposed_entries.append(copy.deepcopy(entry))
            continue

        proposed_entry = ensure_entry_uuid(entry)
        entry_uuid = get_entry_uuid(proposed_entry)
        messages = proposed_entry.get("messages")
        if not entry_uuid or not isinstance(messages, list):
            proposed_entries.append(proposed_entry)
            continue

        for turn_index, message in enumerate(messages):
            if not isinstance(message, dict):
                continue
            raw_role = message.get("role")
            if raw_role is None:
                continue
            source_label = str(raw_role).strip()
            training_role = cleaned_mappings.get(source_label)
            if training_role is None:
                continue

            character_slug, _display_name = normalize_character_name(source_label)
            if not character_slug:
                continue
            message["role"] = training_role
            mapping_by_entry.setdefault(entry_uuid, []).append({
                "turn_index": turn_index,
                "character_slug": character_slug,
                "training_role": training_role,
                "source_role_label": source_label,
            })

        proposed_entries.append(proposed_entry)

    mapping_payload = [
        {"entry_uuid": entry_uuid, "turns": turns}
        for entry_uuid, turns in mapping_by_entry.items()
    ]
    return proposed_entries, mapping_payload


def _ensure_characters(role_mappings: dict[str, str]) -> list[str]:
    created: list[str] = []
    seen_slugs: set[str] = set()
    for source_label in role_mappings:
        character_slug, _display_name = normalize_character_name(source_label)
        if not character_slug or character_slug in seen_slugs:
            continue
        seen_slugs.add(character_slug)
        if get_character_by_slug(character_slug) is not None:
            continue
        create_character(source_label)
        created.append(character_slug)
    return created


def _write_sidecar_after_mapping(dataset_path: str, entries: list[dict]) -> None:
    try:
        # Lazy import keeps character mapping independent from registry sidecar setup.
        from services.registry_sidecar_service import export_registry_sidecar

        result = export_registry_sidecar(dataset_path=dataset_path, entries=entries)
        if not result.ok:
            print(result.message)
    except Exception:
        traceback.print_exc()


def _from_dataset_result(result: DatasetOperationResult) -> CharacterMappingResult:
    return CharacterMappingResult(
        ok=False,
        message=result.message,
        entries=result.entries,
        errors=list(result.errors),
        backup_path=result.backup_path,
        dataset_path=result.dataset_path,
    )

