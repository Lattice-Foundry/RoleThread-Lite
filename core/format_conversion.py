"""Pure dataset format detection and conversion helpers."""
from copy import deepcopy
from dataclasses import dataclass, field

from core.role_normalization import normalize_role


FORMAT_CHATML = "chatml"
FORMAT_SHAREGPT = "sharegpt"
FORMAT_UNKNOWN = "unknown"

SHAREGPT_INTERNAL_SYSTEM_PROMPT = (
    "This entry was imported from ShareGPT format. This system prompt is used "
    "internally by LoreForge and will not be included in ShareGPT exports."
)

_ROLE_FIELD_KEYS = ("from", "role", "speaker")
_CONTENT_FIELD_KEYS = ("value", "content", "text")


@dataclass(frozen=True)
class FormatDetectionSummary:
    """Dominant format detection result for a group of records."""

    format: str
    counts: dict[str, int]
    total: int
    confidence: float


@dataclass(frozen=True)
class ConversionDiagnostics:
    """Diagnostics produced while converting one entry."""

    detected_format: str
    mapped_roles: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class EntryConversionResult:
    """Converted entry plus diagnostics."""

    entry: dict
    diagnostics: ConversionDiagnostics


@dataclass(frozen=True)
class BatchConversionResult:
    """Converted entries plus aggregate conversion details."""

    entries: list[dict]
    source_format: str
    target_format: str
    converted_count: int = 0
    already_target_count: int = 0
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CustomRolePatternSummary:
    """Detected custom-role pattern and suggested standard mapping."""

    detected: bool = False
    roles: tuple[str, ...] = ()
    suggested_mapping: dict[str, str] = field(default_factory=dict)
    message: str | None = None


def detect_record_format(record: dict) -> str:
    """Return ``chatml``, ``sharegpt``, or ``unknown`` for one parsed record."""
    if not isinstance(record, dict):
        return FORMAT_UNKNOWN

    has_messages = isinstance(record.get("messages"), list)
    has_conversations = isinstance(record.get("conversations"), list)
    if has_messages and has_conversations:
        return FORMAT_UNKNOWN
    if has_messages:
        return FORMAT_CHATML
    if has_conversations:
        return FORMAT_SHAREGPT
    return FORMAT_UNKNOWN


def detect_records_format(records: list[dict]) -> FormatDetectionSummary:
    """Return the majority detected format for parsed records."""
    counts = {
        FORMAT_CHATML: 0,
        FORMAT_SHAREGPT: 0,
        FORMAT_UNKNOWN: 0,
    }
    for record in records:
        counts[detect_record_format(record)] += 1

    total = len(records)
    if total == 0:
        return FormatDetectionSummary(
            format=FORMAT_UNKNOWN,
            counts=counts,
            total=0,
            confidence=0.0,
        )

    ordered = sorted(counts.items(), key=lambda item: item[1], reverse=True)
    if len(ordered) > 1 and ordered[0][1] == ordered[1][1]:
        return FormatDetectionSummary(
            format=FORMAT_UNKNOWN,
            counts=counts,
            total=total,
            confidence=ordered[0][1] / total,
        )
    return FormatDetectionSummary(
        format=ordered[0][0],
        counts=counts,
        total=total,
        confidence=ordered[0][1] / total,
    )


def detect_custom_role_pattern(records: list[dict]) -> CustomRolePatternSummary:
    """Detect simple alternating custom-role patterns in ShareGPT records."""
    role_sequence: list[str] = []
    for record in records:
        conversations = record.get("conversations") if isinstance(record, dict) else None
        if not isinstance(conversations, list):
            continue
        for turn in conversations:
            if not isinstance(turn, dict):
                continue
            raw_role = _first_present(turn, _ROLE_FIELD_KEYS)
            if raw_role is None or _map_sharegpt_role(raw_role) is not None:
                continue
            role = str(raw_role).strip()
            if role:
                role_sequence.append(role)

    roles = tuple(dict.fromkeys(role_sequence))
    if len(roles) == 2 and _alternates(role_sequence, roles):
        mapping = {roles[0]: "user", roles[1]: "assistant"}
        return CustomRolePatternSummary(
            detected=True,
            roles=roles,
            suggested_mapping=mapping,
            message=_custom_role_mapping_message(mapping),
        )

    if len(roles) == 3 and role_sequence and role_sequence[0] == roles[0]:
        first_role_count = role_sequence.count(roles[0])
        remaining_roles = roles[1:]
        remaining_sequence = role_sequence[1:]
        if first_role_count == 1 and _alternates(remaining_sequence, remaining_roles):
            mapping = {
                roles[0]: "system",
                roles[1]: "user",
                roles[2]: "assistant",
            }
            return CustomRolePatternSummary(
                detected=True,
                roles=roles,
                suggested_mapping=mapping,
                message=_custom_role_mapping_message(mapping),
            )

    return CustomRolePatternSummary(roles=roles)


def sharegpt_to_chatml_entry(
    record: dict,
    *,
    default_system_prompt: str = SHAREGPT_INTERNAL_SYSTEM_PROMPT,
) -> EntryConversionResult:
    """Convert one ShareGPT-style record to canonical ChatML entry shape."""
    metadata = _top_level_metadata(record, exclude={"conversations", "messages"})
    warnings: list[str] = []
    mapped_roles: dict[str, str] = {}

    conversations = record.get("conversations") if isinstance(record, dict) else None
    if not isinstance(conversations, list):
        conversations = []
        warnings.append("ShareGPT record is missing a conversations list.")
    if not conversations:
        warnings.append("ShareGPT record contains no conversation turns.")

    system_parts: list[str] = []
    converted_messages: list[dict] = []
    for index, turn in enumerate(conversations):
        if not isinstance(turn, dict):
            warnings.append(f"Conversation turn {index} is not an object.")
            continue

        raw_role = _first_present(turn, _ROLE_FIELD_KEYS)
        raw_content = _first_present(turn, _CONTENT_FIELD_KEYS)
        if raw_role is None:
            warnings.append(f"Conversation turn {index} is missing a role field.")
            continue
        if raw_content is None:
            warnings.append(f"Conversation turn {index} is missing a content field.")
            raw_content = ""

        mapped_role = _map_sharegpt_role(raw_role)
        if mapped_role is None:
            warnings.append(
                f"Turn {index} has non-standard role '{raw_role}' - manual role mapping needed."
            )
            converted_messages.append({"role": str(raw_role), "content": str(raw_content)})
            continue

        mapped_roles[str(raw_role)] = mapped_role
        content = str(raw_content)
        if mapped_role == "system":
            system_parts.append(content)
        else:
            converted_messages.append({"role": mapped_role, "content": content})

    if system_parts:
        system_content = "\n\n".join(part for part in system_parts if part.strip())
        if not system_content.strip():
            system_content = default_system_prompt
            warnings.append("ShareGPT system turn was empty; default system prompt injected.")
        if len(system_parts) > 1:
            warnings.append("Multiple ShareGPT system turns were merged.")
    else:
        system_content = default_system_prompt
        warnings.append("No ShareGPT system turn found; default system prompt injected.")

    entry = {
        **metadata,
        "messages": [{"role": "system", "content": system_content}] + converted_messages,
    }
    return EntryConversionResult(
        entry=entry,
        diagnostics=ConversionDiagnostics(
            detected_format=FORMAT_SHAREGPT,
            mapped_roles=mapped_roles,
            warnings=warnings,
        ),
    )


def chatml_to_sharegpt_entry(
    entry: dict,
    *,
    include_metadata: bool = True,
) -> EntryConversionResult:
    """Convert one ChatML entry to ShareGPT-style record shape."""
    metadata = (
        _top_level_metadata(entry, exclude={"messages", "conversations"})
        if include_metadata
        else {}
    )
    warnings: list[str] = []
    mapped_roles: dict[str, str] = {}
    conversations: list[dict] = []

    messages = entry.get("messages") if isinstance(entry, dict) else None
    if not isinstance(messages, list):
        messages = []
        warnings.append("ChatML entry is missing a messages list.")
    if not messages:
        warnings.append("ChatML entry contains no messages.")

    for index, message in enumerate(messages):
        if not isinstance(message, dict):
            warnings.append(f"Message {index} is not an object.")
            continue
        raw_role = message.get("role")
        raw_content = message.get("content")
        if raw_role is None:
            warnings.append(f"Message {index} is missing a role field.")
            continue
        if raw_content is None:
            warnings.append(f"Message {index} is missing a content field.")
            raw_content = ""

        mapped_role = _map_chatml_role(raw_role)
        if mapped_role is None:
            warnings.append(f"Message {index} has unknown role: {raw_role}")
            continue
        if raw_role == "system" and str(raw_content) == SHAREGPT_INTERNAL_SYSTEM_PROMPT:
            mapped_roles[str(raw_role)] = mapped_role
            continue

        mapped_roles[str(raw_role)] = mapped_role
        conversations.append({"from": mapped_role, "value": str(raw_content)})

    return EntryConversionResult(
        entry={**metadata, "conversations": conversations},
        diagnostics=ConversionDiagnostics(
            detected_format=FORMAT_CHATML,
            mapped_roles=mapped_roles,
            warnings=warnings,
        ),
    )


def convert_records_to_chatml(
    records: list[dict],
    *,
    source_format: str,
    default_system_prompt: str = SHAREGPT_INTERNAL_SYSTEM_PROMPT,
) -> BatchConversionResult:
    """Convert parsed records to canonical ChatML entries."""
    if source_format == FORMAT_CHATML:
        return BatchConversionResult(
            entries=deepcopy(records),
            source_format=source_format,
            target_format=FORMAT_CHATML,
            already_target_count=len(records),
        )
    if source_format != FORMAT_SHAREGPT:
        return BatchConversionResult(
            entries=deepcopy(records),
            source_format=source_format,
            target_format=FORMAT_CHATML,
            warnings=[f"Unsupported source format: {source_format}"],
        )

    converted_entries: list[dict] = []
    warnings: list[str] = []
    role_pattern = detect_custom_role_pattern(records)
    if role_pattern.detected and role_pattern.message:
        warnings.append(role_pattern.message)
    for index, record in enumerate(records):
        result = sharegpt_to_chatml_entry(
            record,
            default_system_prompt=default_system_prompt,
        )
        converted_entries.append(result.entry)
        warnings.extend(f"Record {index}: {warning}" for warning in result.diagnostics.warnings)
    return BatchConversionResult(
        entries=converted_entries,
        source_format=source_format,
        target_format=FORMAT_CHATML,
        converted_count=len(converted_entries),
        warnings=warnings,
    )


def convert_chatml_to_format(
    entries: list[dict],
    *,
    target_format: str,
    include_metadata: bool = True,
) -> BatchConversionResult:
    """Convert ChatML entries to the requested export format."""
    if target_format == FORMAT_CHATML:
        return BatchConversionResult(
            entries=deepcopy(entries),
            source_format=FORMAT_CHATML,
            target_format=target_format,
            already_target_count=len(entries),
        )
    if target_format != FORMAT_SHAREGPT:
        return BatchConversionResult(
            entries=deepcopy(entries),
            source_format=FORMAT_CHATML,
            target_format=target_format,
            warnings=[f"Unsupported target format: {target_format}"],
        )

    converted_entries: list[dict] = []
    warnings: list[str] = []
    for index, entry in enumerate(entries):
        result = chatml_to_sharegpt_entry(
            entry,
            include_metadata=include_metadata,
        )
        converted_entries.append(result.entry)
        warnings.extend(f"Entry {index}: {warning}" for warning in result.diagnostics.warnings)
    return BatchConversionResult(
        entries=converted_entries,
        source_format=FORMAT_CHATML,
        target_format=target_format,
        converted_count=len(converted_entries),
        warnings=warnings,
    )


def _first_present(record: dict, keys: tuple[str, ...]) -> object | None:
    for key in keys:
        if key in record:
            return record[key]
    return None


def _map_sharegpt_role(raw_role: object) -> str | None:
    role, changed = normalize_role(str(raw_role))
    if changed or role in {"user", "assistant", "system"}:
        return role
    return None


def _map_chatml_role(raw_role: object) -> str | None:
    role, changed = normalize_role(str(raw_role))
    if not changed and role not in {"user", "assistant", "system"}:
        return None
    if role == "user":
        return "human"
    if role == "assistant":
        return "gpt"
    if role == "system":
        return "system"
    return None


def _alternates(sequence: list[str], roles: tuple[str, ...]) -> bool:
    if not sequence or len(roles) != 2:
        return False
    return all(role == roles[index % 2] for index, role in enumerate(sequence))


def _custom_role_mapping_message(mapping: dict[str, str]) -> str:
    pairs = ", ".join(f"{role} appears to be '{target}'" for role, target in mapping.items())
    return f"Custom role names detected - likely maps to standard roles: {pairs}."


def _top_level_metadata(record: dict, *, exclude: set[str]) -> dict:
    if not isinstance(record, dict):
        return {}
    return {
        key: deepcopy(value)
        for key, value in record.items()
        if key not in exclude
    }
