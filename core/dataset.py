"""Pure dataset helpers for JSONL entries.

This module owns entry validation, JSONL persistence, tag helpers, temporary
entry registries, statistics, and merge logic. It must stay Streamlit-free.
"""
import hashlib
import json
import os
import random
import tempfile
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path

from core.format_conversion import (
    FORMAT_CHATML,
    FORMAT_SHAREGPT,
    FORMAT_UNKNOWN,
    convert_records_to_chatml,
    detect_records_format,
)
from core.loreforge_meta import is_native_dataset
from core.role_normalization import normalize_role
from core.entry_analysis import (
    AnalysisSeverity,
    BASE_EMPTY_TAG,
    BASE_INVALID_TAG_VALUE,
    BASE_MISSING_TAGS,
    BASE_TAGS_NOT_LIST,
    ChatMLAnalyzer,
    EntryAnalysisResult,
    RepairKind,
)
from core.tag_normalization import normalize_tag
from core.text_helpers import count_phrase


DEFAULT_SYSTEM_PROMPT = (
    "You are a creative, engaging roleplay assistant. Stay in character, "
    "be descriptive, and always follow the user's lead."
)

TAGS: dict[str, list[str]] = {
    "Behavior": ["pacing", "boundaries", "no_user_control", "followup_question", "emotional_awareness"],
    "Scene": ["greeting", "medical", "comfort", "tension", "assessment", "aftercare"],
    "Style": ["dialogue", "narration", "descriptive", "subtle", "grounded"],
    "Source": ["manual", "ai_generated"],
    "Status": ["needs_review", "needs_edit"],
}

SUPPORTED_DATASET_EXTENSIONS = {".jsonl", ".json", ".txt"}
_TRAINING_OBJECT_KEYS = {"messages", "conversations", "instruction", "output"}


@dataclass
class DatasetDiagnosticSummary:
    """Aggregate entry diagnostics collected during dataset load."""

    entries_analyzed: int = 0
    valid_entries: int = 0
    entries_with_errors: int = 0
    entries_with_warnings: int = 0
    entries_with_info: int = 0
    error_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    auto_repairable_count: int = 0


@dataclass
class TagNormalizationSummary:
    """Result of normalizing dataset entry tags."""

    entries: list[dict]
    changed_entries: int = 0
    changed_tags: int = 0
    structural_changed_entries: int = 0
    tag_metadata_added_count: int = 0
    role_values_normalized: int = 0
    message_content_trimmed: int = 0
    normalized_slugs: set[str] = field(default_factory=set)
    dropped_tags: list[str] = field(default_factory=list)
    source_format: str = FORMAT_CHATML
    format_counts: dict[str, int] = field(default_factory=dict)
    format_confidence: float = 0.0
    format_converted_count: int = 0
    format_already_target_count: int = 0
    format_warnings: list[str] = field(default_factory=list)
    source_line_count: int = 0
    parsed_entry_count: int = 0
    parse_error_count: int = 0
    dataset_is_native: bool = False
    diagnostics: DatasetDiagnosticSummary = field(default_factory=DatasetDiagnosticSummary)
    alias_rewrites: dict[str, str] = field(default_factory=dict)
    alias_rewrite_count: int = 0
    alias_rewritten_entries: int = 0


_CHATML_ANALYZER = ChatMLAnalyzer()
_VALIDATE_ENTRY_CACHE: dict[str, EntryAnalysisResult] = {}
_METADATA_DIAGNOSTIC_CODES = {
    BASE_MISSING_TAGS,
    BASE_TAGS_NOT_LIST,
    BASE_INVALID_TAG_VALUE,
    BASE_EMPTY_TAG,
}


def clear_validate_entry_cache() -> None:
    """Clear per-render entry validation memoization."""

    _VALIDATE_ENTRY_CACHE.clear()


def make_entry(turns: list[dict], system_prompt: str, tags: list[str] | None = None) -> dict:
    """Build a dataset entry from a list of {role, content} turn dicts.

    Empty turns are stripped so trailing blank pairs do not produce invalid messages.
    """
    clean = [t for t in turns if t.get("content", "").strip()]
    return {
        "messages": [{"role": "system", "content": system_prompt}] + [
            {"role": t["role"], "content": t["content"].strip()} for t in clean
        ],
        "tags": tags if tags is not None else [],
    }


def validate_entry(entry: dict) -> list[str]:
    """Return validation errors for one ChatML-style dataset entry."""

    result = analyze_entry(entry)
    return [
        diagnostic.message
        for diagnostic in result.diagnostics
        if diagnostic.severity == AnalysisSeverity.ERROR
    ]


def analyze_entry(entry: dict) -> EntryAnalysisResult:
    """Return typed ChatML analysis diagnostics for one dataset entry."""

    cache_key = _entry_validation_cache_key(entry)
    if cache_key is None:
        return _analyze_entry_uncached(entry)
    if cache_key not in _VALIDATE_ENTRY_CACHE:
        _VALIDATE_ENTRY_CACHE[cache_key] = _analyze_entry_uncached(entry)
    return _VALIDATE_ENTRY_CACHE[cache_key]


def _entry_validation_cache_key(entry: dict) -> str | None:
    try:
        payload = json.dumps(
            entry,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError):
        return None
    return hashlib.blake2b(payload.encode("utf-8"), digest_size=16).hexdigest()


def _analyze_entry_uncached(entry: dict) -> EntryAnalysisResult:
    """Return typed diagnostics without consulting the memoization cache."""

    return _CHATML_ANALYZER.analyze(entry)


def load_dataset(path: str) -> tuple[list[dict], list[str]]:
    """Load JSONL entries and return parse errors without raising."""
    summary, parse_errors = load_dataset_with_summary(path)
    return summary.entries, parse_errors


def load_dataset_with_summary(
    path: str,
    *,
    auto_normalize: bool = True,
) -> tuple[TagNormalizationSummary, list[str]]:
    """Load JSONL entries and return normalization details plus parse errors."""

    p = Path(path)
    if not p.exists():
        return TagNormalizationSummary(
            entries=[],
            source_format=FORMAT_UNKNOWN,
        ), [f"File not found: {path}"]

    extension = p.suffix.lower()
    if extension not in SUPPORTED_DATASET_EXTENSIONS:
        return TagNormalizationSummary(
            entries=[],
            source_format=FORMAT_UNKNOWN,
        ), [
            f"Unsupported file type: {extension or '<none>'}. "
            "LoreForge supports .jsonl, .json, and .txt files."
        ]

    try:
        content = p.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return TagNormalizationSummary(
            entries=[],
            source_format=FORMAT_UNKNOWN,
        ), ["File is not valid UTF-8 text and cannot be loaded as a dataset."]

    entries, parse_errors, source_line_count, parse_error_count = _parse_dataset_entries(
        content,
        extension,
    )

    detection = detect_records_format(entries)
    dataset_is_native = is_native_dataset(entries)
    conversion_entries = entries
    converted_count = 0
    already_target_count = len(entries) if detection.format == FORMAT_CHATML else 0
    format_warnings: list[str] = []
    if detection.format == FORMAT_SHAREGPT:
        conversion = convert_records_to_chatml(
            entries,
            source_format=detection.format,
        )
        conversion_entries = conversion.entries
        converted_count = conversion.converted_count
        already_target_count = conversion.already_target_count
        format_warnings = conversion.warnings

    summary = (
        normalize_dataset_entries(conversion_entries)
        if auto_normalize
        else TagNormalizationSummary(entries=conversion_entries)
    )
    summary.source_format = detection.format
    summary.format_counts = detection.counts
    summary.format_confidence = detection.confidence
    summary.format_converted_count = converted_count
    summary.format_already_target_count = already_target_count
    summary.format_warnings = format_warnings
    summary.source_line_count = source_line_count
    summary.parsed_entry_count = len(entries)
    summary.parse_error_count = parse_error_count
    summary.dataset_is_native = dataset_is_native
    summary.diagnostics = summarize_entry_analysis(
        summary.entries,
        metadata_errors_block_validity=False,
    )
    return summary, parse_errors


def _parse_dataset_entries(
    content: str,
    extension: str,
) -> tuple[list[dict], list[str], int, int]:
    stripped = content.strip()
    source_line_count = sum(1 for line in content.splitlines() if line.strip())
    if not stripped:
        return [], [], 0, 0

    if stripped.startswith("["):
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            pass
        else:
            if not isinstance(parsed, list):
                return [], ["JSON array file detected but root value is not a list."], source_line_count, 0
            if not all(isinstance(item, dict) for item in parsed):
                return [], ["JSON array file detected but contains non-object items."], source_line_count, 0
            return list(parsed), [], source_line_count, 0

    if extension == ".json" and stripped.startswith("{"):
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            pass
        else:
            if not isinstance(parsed, dict):
                return [], ["JSON file root value must be an object or array."], source_line_count, 0
            if not (_TRAINING_OBJECT_KEYS & set(parsed)):
                return (
                    [],
                    [
                        "File contains a valid JSON object but it does not appear "
                        "to be a training dataset entry."
                    ],
                    source_line_count,
                    0,
                )
            return [parsed], [], source_line_count, 0

    entries: list[dict] = []
    parse_errors: list[str] = []
    for line_num, line in enumerate(content.splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
            entries.append(entry)
        except json.JSONDecodeError as e:
            parse_errors.append(f"Line {line_num}: {e}")

    if not entries and parse_errors:
        parse_errors.append(
            "No valid entries could be loaded. "
            f"{count_phrase(len(parse_errors), 'line')} had parse errors."
        )
    return entries, parse_errors, source_line_count, len(parse_errors) - (1 if not entries and parse_errors else 0)


def summarize_entry_analysis(
    entries: list[dict],
    *,
    metadata_errors_block_validity: bool = True,
) -> DatasetDiagnosticSummary:
    """Analyze loaded entries and return aggregate typed diagnostic counts."""

    summary = DatasetDiagnosticSummary(entries_analyzed=len(entries))
    for entry in entries:
        result = analyze_entry(entry)
        issue_diagnostics = [
            diagnostic
            for diagnostic in result.diagnostics
            if diagnostic.severity in {AnalysisSeverity.ERROR, AnalysisSeverity.WARNING}
        ]
        reportable_diagnostics = [
            diagnostic
            for diagnostic in result.diagnostics
            if metadata_errors_block_validity
            or diagnostic.code not in _METADATA_DIAGNOSTIC_CODES
        ]
        blocking_diagnostics = [
            diagnostic
            for diagnostic in reportable_diagnostics
            if diagnostic.severity == AnalysisSeverity.ERROR
        ]
        severities = {
            diagnostic.severity
            for diagnostic in reportable_diagnostics
        }
        if not issue_diagnostics:
            summary.valid_entries += 1
        if blocking_diagnostics:
            summary.entries_with_errors += 1
        if AnalysisSeverity.WARNING in severities:
            summary.entries_with_warnings += 1
        if AnalysisSeverity.INFO in severities:
            summary.entries_with_info += 1

        for diagnostic in result.diagnostics:
            if diagnostic.severity == AnalysisSeverity.ERROR:
                summary.error_count += 1
            elif diagnostic.severity == AnalysisSeverity.WARNING:
                summary.warning_count += 1
            elif diagnostic.severity == AnalysisSeverity.INFO:
                summary.info_count += 1

            if diagnostic.fixable and diagnostic.repair_kind == RepairKind.AUTOMATIC:
                summary.auto_repairable_count += 1

    return summary


def save_dataset(path: str, entries: list[dict]) -> None:
    """Atomically rewrite a JSONL dataset."""

    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        # Write beside the target so os.replace() stays atomic on the same filesystem.
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=p.parent,
            delete=False,
        ) as f:
            temp_path = Path(f.name)
            for entry in entries:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_path, p)
    except Exception:
        if temp_path is not None and temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass
        raise


def append_to_dataset(path: str, entry: dict) -> None:
    """Append one JSONL entry and fsync before returning."""

    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(entry, ensure_ascii=False) + "\n"
    with p.open("a", encoding="utf-8") as f:
        f.write(line)
        f.flush()
        os.fsync(f.fileno())


# ── Per-entry helpers ──────────────────────────────────────────────────────────

def count_exchanges(entry: dict) -> int:
    """Count complete user/assistant pairs after the system message.
    Safe against malformed entries — never raises."""
    try:
        msgs = entry.get("messages") or []
        non_system = [m for m in msgs if isinstance(m, dict) and m.get("role") != "system"]
        return len(non_system) // 2
    except Exception:
        return 0


def get_entry_messages(entry: dict) -> list[dict]:
    """Safely return entry['messages'] if it is a list, else []."""
    try:
        msgs = entry.get("messages")
        return msgs if isinstance(msgs, list) else []
    except Exception:
        return []


def get_role_messages(entry: dict, role: str) -> list[str]:
    """Return content strings for all messages with the given role."""
    try:
        return [
            m.get("content", "")
            for m in get_entry_messages(entry)
            if isinstance(m, dict) and m.get("role") == role
        ]
    except Exception:
        return []


def entry_text_length(entry: dict) -> int:
    """Total character count across all message contents in an entry."""
    try:
        return sum(
            len(m.get("content", ""))
            for m in get_entry_messages(entry)
            if isinstance(m, dict)
        )
    except Exception:
        return 0


# ── Entry mutation helpers ────────────────────────────────────────────────────

def set_entry_system_prompt(entry: dict, system_prompt: str) -> dict:
    """Replace or insert the system prompt message in an entry.

    If the first message has role 'system' its content is replaced in-place.
    Otherwise a new system message is inserted at index 0.
    Tags and user/assistant messages are not modified.
    Returns the entry.
    """
    if "messages" not in entry or not isinstance(entry["messages"], list):
        entry["messages"] = []
    msgs = entry["messages"]
    if msgs and isinstance(msgs[0], dict) and msgs[0].get("role") == "system":
        msgs[0]["content"] = system_prompt
    else:
        msgs.insert(0, {"role": "system", "content": system_prompt})
    return entry


# ── Tag helpers ───────────────────────────────────────────────────────────────

def get_all_tags() -> list[str]:
    """Return a flat list of all tags from TAGS in category order."""
    return [tag for tags in TAGS.values() for tag in tags]


def get_tag_category_map() -> dict[str, str]:
    """Return {tag: category} for all known tags."""
    return {tag: cat for cat, tags in TAGS.items() for tag in tags}


def get_tag_label_map(
    include_untagged: bool = True,
    untagged_key: str = "__untagged__",
) -> dict[str, str]:
    """Return display labels: {"pacing": "Behavior / pacing", "__untagged__": "Untagged", …}."""
    result: dict[str, str] = {}
    if include_untagged:
        result[untagged_key] = "Untagged"
    for cat, tags in TAGS.items():
        for tag in tags:
            result[tag] = f"{cat} / {tag}"
    return result


def get_entry_tags(entry: dict) -> list[str]:
    """Safely return entry["tags"] if it is a non-empty list of strings, else []."""
    try:
        tags = entry.get("tags")
        if isinstance(tags, list) and all(isinstance(t, str) for t in tags):
            return tags
        return []
    except Exception:
        return []


def canonicalize_entry_tag_aliases(entries: list[dict], resolve_fn) -> tuple[list[dict], dict]:
    """Return entries with stale alias tag slugs rewritten to resolver targets."""

    canonical_entries = deepcopy(entries)
    rewrites: dict[str, str] = {}
    rewrite_count = 0
    changed_entries = 0

    for entry in canonical_entries:
        if not isinstance(entry, dict):
            continue
        tags = entry.get("tags")
        if not isinstance(tags, list) or not all(isinstance(tag, str) for tag in tags):
            continue

        resolved_tags: list[str] = []
        entry_changed = False
        for tag in tags:
            resolved_tag = tag
            resolution = resolve_fn(tag)
            if (
                getattr(resolution, "should_rewrite_slug", False)
                and getattr(resolution, "resolved_slug", "")
            ):
                resolved_tag = resolution.resolved_slug
                if resolved_tag != tag:
                    rewrites[tag] = resolved_tag
                    rewrite_count += 1
                    entry_changed = True

            resolved_tags.append(resolved_tag)

        if entry_changed:
            rewritten_tags: list[str] = []
            seen: set[str] = set()
            for resolved_tag in resolved_tags:
                if resolved_tag in seen:
                    continue
                seen.add(resolved_tag)
                rewritten_tags.append(resolved_tag)
            entry["tags"] = rewritten_tags
            changed_entries += 1

    return canonical_entries, {
        "rewrites": rewrites,
        "rewrite_count": rewrite_count,
        "changed_entries": changed_entries,
    }


def normalize_entry_tags(entry: dict) -> tuple[dict, bool]:
    """Return a copy of entry with canonical, deduplicated tag slugs."""
    normalized_entry = deepcopy(entry)
    original_tags = normalized_entry.get("tags")
    if not isinstance(original_tags, list):
        normalized_entry["tags"] = []
        return normalized_entry, original_tags != []

    seen: set[str] = set()
    clean_tags: list[str] = []
    dropped_or_duplicate = False
    for raw_tag in original_tags:
        normalized = normalize_tag(raw_tag)
        if not normalized.slug:
            dropped_or_duplicate = True
            continue
        if normalized.slug in seen:
            dropped_or_duplicate = True
            continue
        seen.add(normalized.slug)
        clean_tags.append(normalized.slug)

    changed = clean_tags != original_tags or dropped_or_duplicate
    normalized_entry["tags"] = clean_tags
    return normalized_entry, changed


def normalize_dataset_tags(entries: list[dict]) -> TagNormalizationSummary:
    """Normalize tags across a dataset without mutating the input entries."""
    normalized_entries: list[dict] = []
    changed_entries = 0
    changed_tags = 0
    structural_changed_entries = 0
    tag_metadata_added_count = 0
    normalized_slugs: set[str] = set()
    dropped_tags: list[str] = []

    for entry in entries:
        original_tags = entry.get("tags") if isinstance(entry, dict) else []
        original_list = original_tags if isinstance(original_tags, list) else []
        tag_metadata_missing = not isinstance(original_tags, list)
        normalized_entry, changed = normalize_entry_tags(entry)
        clean_tags = get_entry_tags(normalized_entry)
        normalized_entries.append(normalized_entry)
        normalized_slugs.update(clean_tags)

        if changed:
            changed_entries += 1
        if tag_metadata_missing:
            structural_changed_entries += 1
            tag_metadata_added_count += 1

        seen_for_count: set[str] = set()
        for raw_tag in original_list:
            normalized = normalize_tag(raw_tag)
            if not normalized.slug:
                dropped_tags.append(raw_tag if isinstance(raw_tag, str) else repr(raw_tag))
                changed_tags += 1
                continue
            if normalized.slug in seen_for_count:
                changed_tags += 1
                continue
            seen_for_count.add(normalized.slug)
            if normalized.slug != raw_tag:
                changed_tags += 1

    return TagNormalizationSummary(
        entries=normalized_entries,
        changed_entries=changed_entries,
        changed_tags=changed_tags,
        structural_changed_entries=structural_changed_entries,
        tag_metadata_added_count=tag_metadata_added_count,
        normalized_slugs=normalized_slugs,
        dropped_tags=dropped_tags,
    )


def normalize_dataset_entries(entries: list[dict]) -> TagNormalizationSummary:
    """Run deterministic, no-judgment dataset normalization."""

    tag_summary = normalize_dataset_tags(entries)
    normalized_entries: list[dict] = []
    message_changed_indices: set[int] = set()
    role_values_normalized = 0
    message_content_trimmed = 0

    for index, entry in enumerate(tag_summary.entries):
        normalized_entry, message_changed, role_count, content_count = (
            normalize_entry_message_fields(entry)
        )
        normalized_entries.append(normalized_entry)
        if message_changed:
            message_changed_indices.add(index)
        role_values_normalized += role_count
        message_content_trimmed += content_count

    tag_changed_indices = {
        index
        for index, (original, normalized) in enumerate(zip(entries, tag_summary.entries))
        if original != normalized
    }
    return TagNormalizationSummary(
        entries=normalized_entries,
        changed_entries=len(tag_changed_indices | message_changed_indices),
        changed_tags=tag_summary.changed_tags,
        structural_changed_entries=tag_summary.structural_changed_entries,
        tag_metadata_added_count=tag_summary.tag_metadata_added_count,
        role_values_normalized=role_values_normalized,
        message_content_trimmed=message_content_trimmed,
        normalized_slugs=tag_summary.normalized_slugs,
        dropped_tags=tag_summary.dropped_tags,
    )


def normalize_entry_message_fields(entry: dict) -> tuple[dict, bool, int, int]:
    """Normalize known role synonyms and trim message content/role whitespace."""

    normalized_entry = deepcopy(entry)
    messages = normalized_entry.get("messages") if isinstance(normalized_entry, dict) else None
    if not isinstance(messages, list):
        return normalized_entry, False, 0, 0

    changed = False
    role_values_normalized = 0
    message_content_trimmed = 0
    for message in messages:
        if not isinstance(message, dict):
            continue

        role = message.get("role")
        if isinstance(role, str):
            normalized_role, role_changed = normalize_role(role)
            if role_changed:
                message["role"] = normalized_role
                role_values_normalized += 1
                changed = True

        content = message.get("content")
        if isinstance(content, str):
            stripped_content = content.strip()
            if stripped_content != content:
                message["content"] = stripped_content
                message_content_trimmed += 1
                changed = True

    return normalized_entry, changed, role_values_normalized, message_content_trimmed


def set_entry_tags(entry: dict, tags: list[str]) -> dict:
    """Set entry["tags"] to a deduplicated, order-preserving list of strings. Returns entry."""
    seen: set[str] = set()
    clean: list[str] = []
    for t in tags:
        if isinstance(t, str) and t not in seen:
            seen.add(t)
            clean.append(t)
    entry["tags"] = clean
    return entry


def add_tags_to_entry(entry: dict, tags: list[str]) -> dict:
    """Append tags to existing entry tags (no duplicates, order-preserving). Returns entry."""
    return set_entry_tags(entry, get_entry_tags(entry) + tags)


def remove_tags_from_entry(entry: dict, tags: list[str]) -> dict:
    """Remove the supplied tags from the entry. Returns entry."""
    remove_set = set(tags)
    return set_entry_tags(entry, [t for t in get_entry_tags(entry) if t not in remove_set])


def replace_entry_tags(entry: dict, tags: list[str]) -> dict:
    """Replace all tags with the supplied list (deduplicated). Returns entry."""
    return set_entry_tags(entry, tags)


def entry_is_untagged(entry: dict) -> bool:
    """Return True if the entry has no tags."""
    return len(get_entry_tags(entry)) == 0


def get_used_tags(entries: list[dict]) -> set[str]:
    """Return the set of all tags appearing in any entry."""
    result: set[str] = set()
    for entry in entries:
        result.update(get_entry_tags(entry))
    return result


def has_untagged_entries(entries: list[dict]) -> bool:
    """Return True if any entry has no tags."""
    return any(entry_is_untagged(e) for e in entries)


def get_available_filter_tags(
    entries: list[dict],
    only_used: bool,
    include_untagged: bool = True,
    untagged_key: str = "__untagged__",
    all_known_tags: list[str] | None = None,
) -> list[str]:
    """Return ordered tag options for filters, preserving unknown used tags."""
    all_flat = all_known_tags if all_known_tags is not None else get_all_tags()
    if only_used:
        used = get_used_tags(entries)
        result = [t for t in all_flat if t in used]
        # Append unknown used tags (in entries but absent from all_flat)
        _known_set = set(all_flat)
        result.extend(t for t in sorted(used) if t not in _known_set)
        if include_untagged and has_untagged_entries(entries):
            result.append(untagged_key)
    else:
        result = all_flat[:]
        if include_untagged:
            result.append(untagged_key)
    return result


def entry_matches_tags(
    entry: dict,
    selected_tags: list[str],
    match_mode: str,
    untagged_key: str = "__untagged__",
) -> bool:
    """Return True if entry passes the tag filter.

    Reproduces the existing filtering logic exactly:
    - No selected_tags → always True.
    - Untagged entries handled separately from tagged ones.
    - match_mode: "Any selected tags" | "All selected tags" | "Exact match"
    """
    if not selected_tags:
        return True

    normal_tags = [t for t in selected_tags if t != untagged_key]
    include_untagged = untagged_key in selected_tags
    normal_set = set(normal_tags)

    entry_tags = get_entry_tags(entry)
    is_untagged = len(entry_tags) == 0

    if is_untagged:
        if include_untagged and not normal_tags:
            return True
        if include_untagged and match_mode == "Exact match":
            return True
        return False

    # Tagged entry — normal_tags must be non-empty to match
    if not normal_tags:
        return False
    entry_set = set(entry_tags)
    if match_mode == "All selected tags":
        return normal_set.issubset(entry_set)
    if match_mode == "Exact match":
        return entry_set == normal_set
    # "Any selected tags"
    return bool(normal_set.intersection(entry_set))


def filter_entries_by_tags(
    entries: list[dict],
    selected_tags: list[str],
    match_mode: str,
    untagged_key: str = "__untagged__",
) -> list[dict]:
    """Return only entries that pass the tag filter."""
    if not selected_tags:
        return entries
    return [e for e in entries if entry_matches_tags(e, selected_tags, match_mode, untagged_key)]


def filter_entry_pairs_by_tags(
    pairs: list[tuple[str, dict]],
    selected_tags: list[str],
    match_mode: str,
    untagged_key: str = "__untagged__",
) -> list[tuple[str, dict]]:
    """Return only (entry_id, entry) pairs that pass the tag filter."""
    if not selected_tags:
        return pairs
    return [
        (eid, e) for eid, e in pairs
        if entry_matches_tags(e, selected_tags, match_mode, untagged_key)
    ]


# ── Temp-ID registry helpers ───────────────────────────────────────────────────

def make_temp_entry_id(n: int) -> str:
    """Return a zero-padded temp ID string, e.g. make_temp_entry_id(1) → 'tmp_000001'."""
    return f"tmp_{n:06d}"


def build_entry_registry(entries: list[dict]) -> dict:
    """Build a fresh registry for a list of entries.

    Returns:
        {
            "ids":          ["tmp_000001", ...],
            "id_to_index":  {"tmp_000001": 0, ...},
            "next_id":      int   # next unused counter value
        }
    """
    ids = [make_temp_entry_id(i + 1) for i in range(len(entries))]
    return {
        "ids": ids,
        "id_to_index": {eid: i for i, eid in enumerate(ids)},
        "next_id": len(entries) + 1,
    }


def rebuild_id_to_index(ids: list[str]) -> dict:
    """Reconstruct id_to_index from the current ordered IDs list."""
    return {eid: i for i, eid in enumerate(ids)}


def registry_is_valid(registry: dict, entries: list[dict]) -> bool:
    """Return True only when registry is internally consistent with entries.

    Returns False (triggering a silent rebuild) if anything looks wrong.
    """
    if not isinstance(registry, dict):
        return False
    ids = registry.get("ids")
    if not isinstance(ids, list):
        return False
    if len(ids) != len(entries):
        return False
    if len(set(ids)) != len(ids):          # IDs must be unique
        return False
    id_to_index = registry.get("id_to_index")
    if not isinstance(id_to_index, dict):
        return False
    if id_to_index != {eid: i for i, eid in enumerate(ids)}:
        return False
    next_id = registry.get("next_id")
    if not isinstance(next_id, int) or next_id < 1:
        return False
    return True


def append_registry_id(registry: dict) -> str:
    """Append one new temp ID, update id_to_index and next_id. Returns the new ID."""
    new_id = make_temp_entry_id(registry["next_id"])
    registry["ids"].append(new_id)
    registry["id_to_index"][new_id] = len(registry["ids"]) - 1
    registry["next_id"] += 1
    return new_id


def remove_registry_id(registry: dict, entry_id: str) -> bool:
    """Remove entry_id from the registry and rebuild id_to_index.

    Returns True if the ID was found and removed, False otherwise.
    """
    if entry_id not in registry.get("id_to_index", {}):
        return False
    registry["ids"].remove(entry_id)
    registry["id_to_index"] = rebuild_id_to_index(registry["ids"])
    return True


def get_index_for_entry_id(registry: dict, entry_id: str) -> int | None:
    """Return the source list index for a temp ID, or None if not found."""
    return registry.get("id_to_index", {}).get(entry_id)


def get_entry_pairs(entries: list[dict], registry: dict) -> list[tuple[str, dict]]:
    """Return [(entry_id, entry), ...] in source order."""
    return list(zip(registry["ids"], entries))


def build_dataset_stats(
    entries: list[dict],
    tag_category_map: dict[str, str] | None = None,
) -> dict:
    """Compute aggregate statistics for a list of dataset entries.

    Returns a plain dict — no Streamlit or pandas dependency here.
    All values are safe to render directly; nothing mutates the input entries.
    """
    total = len(entries)

    # ── Exchange counts ────────────────────────────────────────────────────────
    exchange_counts = [count_exchanges(e) for e in entries]
    total_exchanges = sum(exchange_counts)
    avg_exchanges = total_exchanges / total if total else 0.0
    single_turn = sum(1 for c in exchange_counts if c == 1)
    multi_turn = sum(1 for c in exchange_counts if c > 1)

    exchange_dist: dict[int, int] = {}
    for c in exchange_counts:
        exchange_dist[c] = exchange_dist.get(c, 0) + 1

    # ── Validation ────────────────────────────────────────────────────────────
    invalid_rows: list[dict] = []
    for i, entry in enumerate(entries):
        errs = validate_entry(entry)
        if errs:
            invalid_rows.append({
                "entry": i + 1,
                "error_count": len(errs),
                "errors": errs,
            })
    invalid_count = len(invalid_rows)
    valid_count = total - invalid_count

    # ── Tags ──────────────────────────────────────────────────────────────────
    # Accept a pre-built DB-backed map from the caller; fall back to TAGS.
    tag_to_category = tag_category_map if tag_category_map is not None else get_tag_category_map()

    all_tags: list[str] = []
    untagged_count = 0
    for entry in entries:
        tags = get_entry_tags(entry)
        if tags:
            all_tags.extend(tags)
        else:
            untagged_count += 1

    tag_counts: dict[str, int] = {}
    for tag in all_tags:
        tag_counts[tag] = tag_counts.get(tag, 0) + 1

    tag_category_counts: dict[str, int] = {}
    for tag in all_tags:
        cat = tag_to_category.get(tag, "Unknown")
        tag_category_counts[cat] = tag_category_counts.get(cat, 0) + 1

    unique_tags = len(tag_counts)

    # ── Message lengths ───────────────────────────────────────────────────────
    user_lengths: list[int] = []
    asst_lengths: list[int] = []
    entry_lengths: list[int] = []

    for entry in entries:
        for content in get_role_messages(entry, "user"):
            user_lengths.append(len(content))
        for content in get_role_messages(entry, "assistant"):
            asst_lengths.append(len(content))
        entry_lengths.append(entry_text_length(entry))

    avg_user_len = sum(user_lengths) / len(user_lengths) if user_lengths else 0.0
    avg_asst_len = sum(asst_lengths) / len(asst_lengths) if asst_lengths else 0.0
    avg_entry_len = sum(entry_lengths) / len(entry_lengths) if entry_lengths else 0.0
    min_asst_len = min(asst_lengths) if asst_lengths else 0
    max_asst_len = max(asst_lengths) if asst_lengths else 0

    return {
        # Summary
        "total": total,
        "total_exchanges": total_exchanges,
        "avg_exchanges": avg_exchanges,
        "single_turn": single_turn,
        "multi_turn": multi_turn,
        # Validation
        "valid_count": valid_count,
        "invalid_count": invalid_count,
        "invalid_rows": invalid_rows,
        # Tags
        "untagged_count": untagged_count,
        "unique_tags": unique_tags,
        "tag_counts": tag_counts,
        "tag_category_counts": tag_category_counts,
        # Message lengths
        "avg_user_len": avg_user_len,
        "avg_asst_len": avg_asst_len,
        "avg_entry_len": avg_entry_len,
        "min_asst_len": min_asst_len,
        "max_asst_len": max_asst_len,
        # Raw series (chart-ready)
        "exchange_counts": exchange_counts,
        "exchange_dist": exchange_dist,
        "entry_lengths": entry_lengths,
    }


def merge_datasets(paths: list[str], shuffle: bool = True) -> tuple[list[dict], dict]:
    """Merge JSONL datasets while removing duplicate user/assistant exchanges."""

    seen, merged = set(), []
    stats = {"total_loaded": 0, "duplicates_removed": 0, "parse_errors": []}

    for path in paths:
        entries, errors = load_dataset(path)
        stats["parse_errors"].extend(errors)
        for entry in entries:
            stats["total_loaded"] += 1
            msgs = [
                {"role": m["role"], "content": m.get("content", "")}
                for m in entry.get("messages", [])
                if isinstance(m, dict) and m.get("role") in ("user", "assistant")
            ]
            key = json.dumps(msgs, ensure_ascii=False, sort_keys=True)
            if key in seen:
                stats["duplicates_removed"] += 1
            else:
                seen.add(key)
                merged.append(entry)

    if shuffle:
        random.shuffle(merged)

    return merged, stats
