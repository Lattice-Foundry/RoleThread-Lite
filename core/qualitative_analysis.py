"""Deterministic dataset quality scoring and qualitative insights."""

from __future__ import annotations

from collections import Counter, OrderedDict
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import re
from statistics import median
from typing import TYPE_CHECKING, Any

from core.dataset import analyze_entry, count_exchanges, get_entry_messages, get_entry_tags, validate_entry
from core.entry_analysis import (
    CHATML_AI_REFUSAL_LANGUAGE,
    CHATML_DUPLICATE_SYSTEM_MESSAGE,
    CHATML_FORMATTING_LEAKAGE,
    CHATML_SPLIT_CANDIDATE,
)
from core.rolethread_meta import (
    get_dataset_uuid_for_entries,
    get_entry_uuid,
    is_native_entry,
)
from core.registry_sidecar import SidecarValidationError, read_sidecar, sidecar_path_for_dataset

if TYPE_CHECKING:
    from core.tag_registry import TagRegistrySnapshot


_WORD_RE = re.compile(r"\b[\w']+\b", re.UNICODE)
_QUOTE_CONTENT_RE = re.compile(r'(?:\\"|")([^"\\]*(?:\\.[^"\\]*)*)(?:\\"|")')
_PLACEHOLDER_PATTERNS = (
    "test",
    "testing",
    "asdf",
    "placeholder",
    "todo",
    "tbd",
    "lorem ipsum",
    "[insert",
    "<insert",
    "n/a",
)
_STRUCTURE_FLAG_DIAGNOSTIC_CODES = {
    CHATML_DUPLICATE_SYSTEM_MESSAGE,
    CHATML_AI_REFUSAL_LANGUAGE,
    CHATML_SPLIT_CANDIDATE,
    CHATML_FORMATTING_LEAKAGE,
}
_ANALYSIS_CACHE_MAX_SIZE = 8
_ANALYSIS_CACHE: "OrderedDict[str, DatasetQualityReport]" = OrderedDict()
_NEAR_DUPLICATE_THRESHOLD = 0.9
_SIMHASH_BAND_BITS = 16
_SIMHASH_BAND_MASK = (1 << _SIMHASH_BAND_BITS) - 1
_SIMHASH_BAND_SHIFTS = (0, 16, 32, 48)


@dataclass(frozen=True)
class ResponseQualityScore:
    score: float
    avg_response_length: float
    median_response_length: float
    short_response_count: int
    empty_response_count: int
    placeholder_count: int
    user_assistant_length_ratio: float
    flagged_entry_uuids: tuple[str, ...]


@dataclass(frozen=True)
class DiversityScore:
    score: float
    unique_system_prompts: int
    total_entries: int
    system_prompt_diversity_ratio: float
    tag_coverage_percent: float
    tag_entropy: float
    category_coverage_count: int
    near_duplicate_count: int
    near_duplicate_pairs: tuple[tuple[str, str], ...]
    flagged_entry_uuids: tuple[str, ...]


@dataclass(frozen=True)
class StructureScore:
    score: float
    validation_pass_rate: float
    invalid_entry_count: int
    avg_exchange_count: float
    exchange_count_distribution: dict[str, int]
    in_optimal_range_percent: float
    short_system_prompt_count: int
    missing_system_prompt_count: int
    flagged_entry_uuids: tuple[str, ...]


@dataclass(frozen=True)
class MetadataIntegrityScore:
    score: float
    native_stamp_percent: float
    tagged_entry_percent: float
    character_mapping_percent: float
    sidecar_present: bool
    sidecar_current: bool
    flagged_entry_uuids: tuple[str, ...]


@dataclass(frozen=True)
class NarrativeInsight:
    dialogue_ratio: float
    spectrum_label: str
    spectrum_description: str
    per_entry_ratios: tuple[float, ...]


@dataclass(frozen=True)
class DatasetQualityReport:
    composite_score: float
    grade: str
    response_quality: ResponseQualityScore
    diversity: DiversityScore
    structure: StructureScore
    metadata_integrity: MetadataIntegrityScore
    narrative_insight: NarrativeInsight
    exchange_depth_distribution: dict[int, int]
    response_length_distribution: tuple[int, ...]
    system_prompt_concentration: dict[str, int]
    total_entries: int
    total_messages: int


@dataclass(frozen=True)
class _TokenProfile:
    index: int
    tokens: frozenset[str]
    token_count: int
    simhash: int


def analyze_dataset_quality(
    entries: list[dict],
    dataset_path: Path | None = None,
    sidecar_path: Path | None = None,
    tag_snapshot: "TagRegistrySnapshot | None" = None,
) -> DatasetQualityReport:
    """Return the full deterministic quality report for loaded entries."""

    safe_entries = [entry for entry in entries if isinstance(entry, dict)]
    cache_key = _analysis_cache_key(
        safe_entries,
        dataset_path=dataset_path,
        sidecar_path=sidecar_path,
        tag_snapshot=tag_snapshot,
    )
    cached = _ANALYSIS_CACHE.get(cache_key)
    if cached is not None:
        _ANALYSIS_CACHE.move_to_end(cache_key)
        return deepcopy(cached)

    report = _analyze_dataset_quality_uncached(
        safe_entries,
        dataset_path=dataset_path,
        sidecar_path=sidecar_path,
        tag_snapshot=tag_snapshot,
    )
    _ANALYSIS_CACHE[cache_key] = report
    if len(_ANALYSIS_CACHE) > _ANALYSIS_CACHE_MAX_SIZE:
        _ANALYSIS_CACHE.popitem(last=False)
    return deepcopy(report)


def clear_dataset_quality_cache() -> None:
    """Clear the bounded in-process dataset quality analysis cache."""

    _ANALYSIS_CACHE.clear()


def _analyze_dataset_quality_uncached(
    safe_entries: list[dict],
    *,
    dataset_path: Path | None,
    sidecar_path: Path | None,
    tag_snapshot: "TagRegistrySnapshot | None",
) -> DatasetQualityReport:
    response_quality = _score_response_quality(safe_entries)
    diversity = _score_diversity(safe_entries, tag_snapshot)
    structure = _score_structure(safe_entries)
    metadata_integrity = _score_metadata_integrity(
        safe_entries,
        dataset_path=dataset_path,
        sidecar_path=sidecar_path,
        tag_snapshot=tag_snapshot,
    )
    composite_score = _round_composite_score(
        response_quality.score
        + diversity.score
        + structure.score
        + metadata_integrity.score
    )

    return DatasetQualityReport(
        composite_score=composite_score,
        grade=_grade_for_score(composite_score),
        response_quality=response_quality,
        diversity=diversity,
        structure=structure,
        metadata_integrity=metadata_integrity,
        narrative_insight=_build_narrative_insight(safe_entries),
        exchange_depth_distribution=_exchange_depth_distribution(safe_entries),
        response_length_distribution=tuple(
            _word_count(content)
            for entry in safe_entries
            for content in _role_contents(entry, "assistant")
        ),
        system_prompt_concentration=_system_prompt_concentration(safe_entries),
        total_entries=len(safe_entries),
        total_messages=sum(len(get_entry_messages(entry)) for entry in safe_entries),
    )


def _analysis_cache_key(
    safe_entries: list[dict],
    *,
    dataset_path: Path | None,
    sidecar_path: Path | None,
    tag_snapshot: "TagRegistrySnapshot | None",
) -> str:
    entries_digest = hashlib.blake2b(
        json.dumps(
            safe_entries,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8"),
        digest_size=16,
    ).hexdigest()
    resolved_sidecar_path = sidecar_path
    if resolved_sidecar_path is None and dataset_path is not None:
        resolved_sidecar_path = sidecar_path_for_dataset(Path(dataset_path))
    parts = (
        f"entries={entries_digest}",
        f"count={len(safe_entries)}",
        f"dataset={_path_cache_marker(dataset_path)}",
        f"sidecar={_path_cache_marker(resolved_sidecar_path)}",
        f"tags={_tag_snapshot_cache_marker(tag_snapshot)}",
    )
    return "|".join(parts)


def _path_cache_marker(path: Path | None) -> str:
    if path is None:
        return "<none>"
    try:
        resolved = Path(path).expanduser().resolve()
    except OSError:
        resolved = Path(path).expanduser()
    try:
        stat = resolved.stat()
    except OSError:
        return f"{resolved}|missing"
    return f"{resolved}|{stat.st_mtime_ns}|{stat.st_size}"


def _tag_snapshot_cache_marker(tag_snapshot: "TagRegistrySnapshot | None") -> str:
    if tag_snapshot is None:
        return "<none>"
    payload = {
        "active_tag_slugs": sorted(getattr(tag_snapshot, "active_tag_slug_set", set())),
        "tag_category_map": sorted(
            getattr(tag_snapshot, "tag_category_map", {}).items()
        ),
    }
    return hashlib.blake2b(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8"),
        digest_size=12,
    ).hexdigest()


def _score_response_quality(entries: list[dict]) -> ResponseQualityScore:
    assistant_counts: list[int] = []
    user_counts: list[int] = []
    short_response_count = 0
    empty_response_count = 0
    placeholder_count = 0
    flagged: list[str] = []

    for index, entry in enumerate(entries):
        entry_flagged = False
        for content in _role_contents(entry, "assistant"):
            count = _word_count(content)
            assistant_counts.append(count)
            if count == 0:
                empty_response_count += 1
                entry_flagged = True
            if count < 20:
                short_response_count += 1
                entry_flagged = True
            if _is_placeholder_response(content, count):
                placeholder_count += 1
                entry_flagged = True

        user_counts.extend(_word_count(content) for content in _role_contents(entry, "user"))
        if _entry_has_extreme_length_ratio(entry):
            entry_flagged = True
        if entry_flagged:
            flagged.append(_entry_identifier(entry, index))

    avg_response_length = _mean(assistant_counts)
    median_response_length = float(median(assistant_counts)) if assistant_counts else 0.0
    assistant_message_count = len(assistant_counts)
    avg_user_length = _mean(user_counts)
    user_assistant_length_ratio = (
        avg_user_length / avg_response_length
        if avg_response_length > 0
        else 0.0
    )

    if not entries or assistant_message_count == 0:
        score = 0.0
    else:
        length_points = 15.0 * min(avg_response_length / 300.0, 1.0)
        empty_rate = empty_response_count / assistant_message_count
        placeholder_rate = placeholder_count / assistant_message_count
        short_rate = short_response_count / assistant_message_count
        content_points = 5.0 * (1.0 - min(empty_rate + placeholder_rate, 1.0))
        ratio_points = _ratio_points(user_assistant_length_ratio)
        score = length_points + content_points + ratio_points - (5.0 * short_rate)

    return ResponseQualityScore(
        score=_round_score(score),
        avg_response_length=round(avg_response_length, 2),
        median_response_length=round(median_response_length, 2),
        short_response_count=short_response_count,
        empty_response_count=empty_response_count,
        placeholder_count=placeholder_count,
        user_assistant_length_ratio=round(user_assistant_length_ratio, 3),
        flagged_entry_uuids=_dedupe_preserving_order(flagged),
    )


def _score_diversity(
    entries: list[dict],
    tag_snapshot: "TagRegistrySnapshot | None",
) -> DiversityScore:
    total_entries = len(entries)
    prompts = [_normalize_text(_system_prompt(entry)) for entry in entries]
    unique_prompts = {prompt for prompt in prompts if prompt}
    used_tag_counts = Counter(
        tag
        for entry in entries
        for tag in _active_or_known_entry_tags(entry, tag_snapshot)
    )
    tagged_entry_count = sum(
        1
        for entry in entries
        if _active_or_known_entry_tags(entry, tag_snapshot)
    )
    unresolved_tag_entries = [
        _entry_identifier(entry, index)
        for index, entry in enumerate(entries)
        if tag_snapshot is not None
        and any(tag not in tag_snapshot.active_tag_slug_set for tag in get_entry_tags(entry))
    ]
    tag_coverage_percent = _percent(tagged_entry_count, total_entries)
    tag_entropy = _normalized_entropy(used_tag_counts)
    category_coverage_count = _category_coverage_count(used_tag_counts, tag_snapshot)
    near_duplicate_pairs = _near_duplicate_pairs(entries)
    near_duplicate_entry_ids = _dedupe_preserving_order(
        [
            entry_uuid
            for pair in near_duplicate_pairs
            for entry_uuid in pair
        ]
    )
    duplicate_rate = (
        len(near_duplicate_entry_ids) / total_entries
        if total_entries
        else 0.0
    )
    system_prompt_diversity_ratio = (
        len(unique_prompts) / total_entries
        if total_entries
        else 0.0
    )

    if not entries:
        score = 0.0
    else:
        system_points = 8.0 * min(len(unique_prompts) / min(total_entries, 10), 1.0)
        tag_coverage_points = 6.0 * (tag_coverage_percent / 100.0)
        entropy_points = 5.0 * tag_entropy
        category_points = 3.0 * min(category_coverage_count / 4.0, 1.0)
        duplicate_points = 3.0 * (1.0 - min(duplicate_rate / 0.25, 1.0))
        unresolved_penalty = min(len(unresolved_tag_entries) / total_entries, 1.0) * 2.0
        score = (
            system_points
            + tag_coverage_points
            + entropy_points
            + category_points
            + duplicate_points
            - unresolved_penalty
        )

    return DiversityScore(
        score=_round_score(score),
        unique_system_prompts=len(unique_prompts),
        total_entries=total_entries,
        system_prompt_diversity_ratio=round(system_prompt_diversity_ratio, 3),
        tag_coverage_percent=round(tag_coverage_percent, 2),
        tag_entropy=round(tag_entropy, 3),
        category_coverage_count=category_coverage_count,
        near_duplicate_count=len(near_duplicate_pairs),
        near_duplicate_pairs=near_duplicate_pairs,
        flagged_entry_uuids=_dedupe_preserving_order(
            list(near_duplicate_entry_ids) + unresolved_tag_entries
        ),
    )


def _score_structure(entries: list[dict]) -> StructureScore:
    total_entries = len(entries)
    invalid_ids: list[str] = []
    exchange_counts: list[int] = []
    short_system_ids: list[str] = []
    missing_system_ids: list[str] = []
    diagnostic_flag_ids: list[str] = []

    for index, entry in enumerate(entries):
        entry_id = _entry_identifier(entry, index)
        if validate_entry(entry):
            invalid_ids.append(entry_id)
        analysis = analyze_entry(entry)
        if any(
            diagnostic.code in _STRUCTURE_FLAG_DIAGNOSTIC_CODES
            for diagnostic in analysis.diagnostics
        ):
            diagnostic_flag_ids.append(entry_id)
        exchanges = count_exchanges(entry)
        exchange_counts.append(exchanges)
        system_prompt = _system_prompt(entry)
        if not system_prompt.strip():
            missing_system_ids.append(entry_id)
        elif len(system_prompt.strip()) < 50:
            short_system_ids.append(entry_id)

    valid_count = total_entries - len(invalid_ids)
    validation_pass_rate = _percent(valid_count, total_entries)
    optimal_count = sum(1 for count in exchange_counts if 3 <= count <= 7)
    in_optimal_range_percent = _percent(optimal_count, total_entries)
    present_system_count = total_entries - len(missing_system_ids)
    adequate_system_count = total_entries - len(missing_system_ids) - len(short_system_ids)

    if not entries:
        score = 0.0
    else:
        validation_points = 10.0 * (validation_pass_rate / 100.0)
        exchange_points = 8.0 * (in_optimal_range_percent / 100.0)
        system_points = (
            3.0 * (present_system_count / total_entries)
            + 4.0 * max(adequate_system_count, 0) / total_entries
        )
        score = validation_points + exchange_points + system_points

    return StructureScore(
        score=_round_score(score),
        validation_pass_rate=round(validation_pass_rate, 2),
        invalid_entry_count=len(invalid_ids),
        avg_exchange_count=round(_mean(exchange_counts), 2),
        exchange_count_distribution=_exchange_bucket_distribution(exchange_counts),
        in_optimal_range_percent=round(in_optimal_range_percent, 2),
        short_system_prompt_count=len(short_system_ids),
        missing_system_prompt_count=len(missing_system_ids),
        flagged_entry_uuids=_dedupe_preserving_order(
            invalid_ids + short_system_ids + missing_system_ids + diagnostic_flag_ids
        ),
    )


def _score_metadata_integrity(
    entries: list[dict],
    *,
    dataset_path: Path | None,
    sidecar_path: Path | None,
    tag_snapshot: "TagRegistrySnapshot | None",
) -> MetadataIntegrityScore:
    total_entries = len(entries)
    sidecar_present, sidecar = _load_sidecar_status(dataset_path, sidecar_path)
    sidecar_current = _sidecar_current_for_entries(sidecar, entries)
    if not entries:
        return MetadataIntegrityScore(
            score=0.0,
            native_stamp_percent=0.0,
            tagged_entry_percent=0.0,
            character_mapping_percent=0.0,
            sidecar_present=sidecar_present,
            sidecar_current=sidecar_current,
            flagged_entry_uuids=(),
        )

    native_ids = [
        _entry_identifier(entry, index)
        for index, entry in enumerate(entries)
        if is_native_entry(entry)
    ]
    tagged_ids = [
        _entry_identifier(entry, index)
        for index, entry in enumerate(entries)
        if _active_or_known_entry_tags(entry, tag_snapshot)
    ]
    mapped_entry_uuids = {
        mapping.entry_uuid
        for mapping in sidecar.entry_character_mappings
    } if sidecar else set()
    entry_uuids = {
        uuid
        for entry in entries
        if (uuid := get_entry_uuid(entry))
    }
    mappings_apply = bool(mapped_entry_uuids)
    mapped_present_uuids = mapped_entry_uuids & entry_uuids
    character_mapping_percent = (
        _percent(len(mapped_present_uuids), total_entries)
        if mappings_apply
        else 100.0
    )

    native_stamp_percent = _percent(len(native_ids), total_entries)
    tagged_entry_percent = _percent(len(tagged_ids), total_entries)
    missing_native_ids = [
        _entry_identifier(entry, index)
        for index, entry in enumerate(entries)
        if not is_native_entry(entry)
    ]
    missing_tag_ids = [
        _entry_identifier(entry, index)
        for index, entry in enumerate(entries)
        if not _active_or_known_entry_tags(entry, tag_snapshot)
    ]
    missing_mapping_ids = [
        _entry_identifier(entry, index)
        for index, entry in enumerate(entries)
        if mappings_apply and get_entry_uuid(entry) not in mapped_present_uuids
    ]

    score = (
        8.0 * (native_stamp_percent / 100.0)
        + 7.0 * (tagged_entry_percent / 100.0)
        + 5.0 * (character_mapping_percent / 100.0)
        + (2.0 if sidecar_present else 0.0)
        + (3.0 if sidecar_current else 0.0)
    )

    return MetadataIntegrityScore(
        score=_round_score(score),
        native_stamp_percent=round(native_stamp_percent, 2),
        tagged_entry_percent=round(tagged_entry_percent, 2),
        character_mapping_percent=round(character_mapping_percent, 2),
        sidecar_present=sidecar_present,
        sidecar_current=sidecar_current,
        flagged_entry_uuids=_dedupe_preserving_order(
            missing_native_ids + missing_tag_ids + missing_mapping_ids
        ),
    )


def _build_narrative_insight(entries: list[dict]) -> NarrativeInsight:
    ratios = tuple(_entry_dialogue_ratio(entry) for entry in entries)
    dialogue_ratio = _mean(ratios)
    label, description = _narrative_label_and_description(dialogue_ratio)
    return NarrativeInsight(
        dialogue_ratio=round(dialogue_ratio, 3),
        spectrum_label=label,
        spectrum_description=description,
        per_entry_ratios=tuple(round(ratio, 3) for ratio in ratios),
    )


def _role_contents(entry: dict, role: str) -> list[str]:
    return [
        str(message.get("content", ""))
        for message in get_entry_messages(entry)
        if isinstance(message, dict) and message.get("role") == role
    ]


def _system_prompt(entry: dict) -> str:
    messages = get_entry_messages(entry)
    if not messages:
        return ""
    first = messages[0]
    if isinstance(first, dict) and first.get("role") == "system":
        return str(first.get("content", ""))
    return ""


def _word_count(text: str) -> int:
    return len(_WORD_RE.findall(text or ""))


def _word_set(text: str) -> set[str]:
    return {match.group(0).lower() for match in _WORD_RE.finditer(text or "")}


def _entry_text(entry: dict) -> str:
    return " ".join(
        str(message.get("content", ""))
        for message in get_entry_messages(entry)
        if isinstance(message, dict)
    )


def _normalize_text(text: str) -> str:
    return " ".join((text or "").casefold().split())


def _is_placeholder_response(content: str, word_count: int) -> bool:
    normalized = _normalize_text(content)
    if not normalized:
        return False
    if word_count == 1:
        return True
    return any(pattern in normalized for pattern in _PLACEHOLDER_PATTERNS)


def _entry_has_extreme_length_ratio(entry: dict) -> bool:
    user_words = sum(_word_count(content) for content in _role_contents(entry, "user"))
    assistant_words = sum(_word_count(content) for content in _role_contents(entry, "assistant"))
    if user_words == 0 or assistant_words == 0:
        return True
    ratio = user_words / assistant_words
    return ratio < 0.1 or ratio > 5.0


def _ratio_points(ratio: float) -> float:
    if 0.2 <= ratio <= 2.0:
        return 5.0
    if 0.1 <= ratio <= 5.0:
        return 3.0
    return 0.0


def _active_or_known_entry_tags(
    entry: dict,
    tag_snapshot: "TagRegistrySnapshot | None",
) -> list[str]:
    tags = get_entry_tags(entry)
    if tag_snapshot is None:
        return tags
    return [tag for tag in tags if tag in tag_snapshot.active_tag_slug_set]


def _normalized_entropy(counts: Counter[str]) -> float:
    total = sum(counts.values())
    if total == 0 or len(counts) <= 1:
        return 0.0
    entropy = -sum((count / total) * math.log2(count / total) for count in counts.values())
    return entropy / math.log2(len(counts))


def _category_coverage_count(
    used_tag_counts: Counter[str],
    tag_snapshot: "TagRegistrySnapshot | None",
) -> int:
    if tag_snapshot is None:
        return 0
    return len(
        {
            category
            for tag in used_tag_counts
            if (category := tag_snapshot.tag_category_map.get(tag))
        }
    )


def _near_duplicate_pairs(entries: list[dict]) -> tuple[tuple[str, str], ...]:
    profiles: list[_TokenProfile] = []
    exact_buckets: dict[frozenset[str], list[_TokenProfile]] = {}
    band_buckets: dict[tuple[int, int], list[_TokenProfile]] = {}

    for index, entry in enumerate(entries):
        tokens = frozenset(_word_set(_entry_text(entry)))
        if not tokens:
            continue
        profile = _TokenProfile(
            index=index,
            tokens=tokens,
            token_count=len(tokens),
            simhash=_token_simhash(tokens),
        )
        profiles.append(profile)
        exact_buckets.setdefault(tokens, []).append(profile)
        for band_key in _simhash_band_keys(profile.simhash):
            band_buckets.setdefault(band_key, []).append(profile)

    candidate_pairs: set[tuple[int, int]] = set()
    for bucket in exact_buckets.values():
        _add_candidate_pairs(candidate_pairs, bucket)
    for bucket in band_buckets.values():
        _add_candidate_pairs(candidate_pairs, bucket)

    profile_by_index = {profile.index: profile for profile in profiles}
    pairs: list[tuple[str, str]] = []
    for left_index, right_index in sorted(candidate_pairs):
        left = profile_by_index[left_index]
        right = profile_by_index[right_index]
        if not _near_duplicate_size_possible(left.token_count, right.token_count):
            continue
        overlap = len(left.tokens & right.tokens) / max(len(left.tokens | right.tokens), 1)
        if overlap > _NEAR_DUPLICATE_THRESHOLD:
            pairs.append(
                (
                    _entry_identifier(entries[left_index], left_index),
                    _entry_identifier(entries[right_index], right_index),
                )
            )
    return tuple(pairs)


def _token_simhash(tokens: frozenset[str]) -> int:
    vector = [0] * 64
    for token in tokens:
        token_hash = int(hashlib.blake2b(token.encode("utf-8"), digest_size=8).hexdigest(), 16)
        for bit in range(64):
            vector[bit] += 1 if token_hash & (1 << bit) else -1
    fingerprint = 0
    for bit, value in enumerate(vector):
        if value >= 0:
            fingerprint |= 1 << bit
    return fingerprint


def _simhash_band_keys(fingerprint: int) -> tuple[tuple[int, int], ...]:
    return tuple(
        (shift, (fingerprint >> shift) & _SIMHASH_BAND_MASK)
        for shift in _SIMHASH_BAND_SHIFTS
    )


def _add_candidate_pairs(
    candidate_pairs: set[tuple[int, int]],
    bucket: list[_TokenProfile],
) -> None:
    if len(bucket) < 2:
        return
    for left_offset, left in enumerate(bucket):
        for right in bucket[left_offset + 1:]:
            if left.index == right.index:
                continue
            pair = (
                min(left.index, right.index),
                max(left.index, right.index),
            )
            candidate_pairs.add(pair)


def _near_duplicate_size_possible(left_count: int, right_count: int) -> bool:
    smaller = min(left_count, right_count)
    larger = max(left_count, right_count)
    return larger > 0 and (smaller / larger) > _NEAR_DUPLICATE_THRESHOLD


def _exchange_bucket_distribution(exchange_counts: list[int]) -> dict[str, int]:
    buckets = {"1": 0, "2": 0, "3-7": 0, "8+": 0}
    for count in exchange_counts:
        if count <= 1:
            buckets["1"] += 1
        elif count == 2:
            buckets["2"] += 1
        elif 3 <= count <= 7:
            buckets["3-7"] += 1
        else:
            buckets["8+"] += 1
    return buckets


def _exchange_depth_distribution(entries: list[dict]) -> dict[int, int]:
    counts = Counter(count_exchanges(entry) for entry in entries)
    return dict(sorted(counts.items()))


def _system_prompt_concentration(entries: list[dict]) -> dict[str, int]:
    concentration: Counter[str] = Counter()
    for entry in entries:
        prompt = _normalize_text(_system_prompt(entry))
        if not prompt:
            continue
        digest = hashlib.sha1(prompt.encode("utf-8")).hexdigest()[:12]
        concentration[digest] += 1
    return dict(concentration)


def _entry_dialogue_ratio(entry: dict) -> float:
    assistant_text = "\n".join(_role_contents(entry, "assistant"))
    total_length = len(assistant_text.strip())
    if total_length == 0:
        return 0.0
    quoted_length = sum(len(match.group(1)) for match in _QUOTE_CONTENT_RE.finditer(assistant_text))
    if quoted_length == 0 and '\\"' in assistant_text:
        quoted_length = assistant_text.count('\\"') * 2
    return min(quoted_length / total_length, 1.0)


def _narrative_label_and_description(dialogue_ratio: float) -> tuple[str, str]:
    if dialogue_ratio < 0.2:
        return (
            "Heavy Narrative",
            "Your model will likely narrate extensively, describe scenes in detail, "
            "and may control the user's actions.",
        )
    if dialogue_ratio < 0.4:
        return (
            "Narrative-Leaning",
            "Your model will blend scene-setting with character interaction and may "
            "take narrative liberties.",
        )
    if dialogue_ratio < 0.6:
        return (
            "Balanced",
            "Your model will mix dialogue and narration naturally while maintaining "
            "scene awareness.",
        )
    if dialogue_ratio < 0.8:
        return (
            "Dialogue-Leaning",
            "Your model will primarily respond through direct speech with minimal "
            "scene description.",
        )
    return (
        "Heavy Dialogue",
        "Your model will almost exclusively use direct speech and stay responsive "
        "in first-person character.",
    )


def _load_sidecar_status(dataset_path: Path | None, sidecar_path: Path | None):
    resolved_path = sidecar_path
    if resolved_path is None and dataset_path is not None:
        resolved_path = sidecar_path_for_dataset(dataset_path)
    if resolved_path is None or not resolved_path.exists():
        return False, None
    try:
        return True, read_sidecar(resolved_path)
    except (OSError, ValueError, SidecarValidationError):
        return True, None


def _sidecar_current_for_entries(sidecar: Any, entries: list[dict]) -> bool:
    if sidecar is None:
        return False
    if sidecar.dataset_info.entry_count != len(entries):
        return False
    dataset_uuid = get_dataset_uuid_for_entries(entries)
    if dataset_uuid and sidecar.dataset_info.dataset_uuid != dataset_uuid:
        return False
    return True


def _entry_identifier(entry: dict, index: int) -> str:
    return get_entry_uuid(entry) or f"entry_index:{index}"


def _dedupe_preserving_order(values: list[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return tuple(deduped)


def _mean(values) -> float:
    values = list(values)
    return sum(values) / len(values) if values else 0.0


def _percent(part: int, whole: int) -> float:
    return (part / whole * 100.0) if whole else 0.0


def _round_score(value: float) -> float:
    return round(max(0.0, min(float(value), 25.0)), 2)


def _round_composite_score(value: float) -> float:
    return round(max(0.0, min(float(value), 100.0)), 2)


def _grade_for_score(score: float) -> str:
    if score >= 90:
        return "Excellent"
    if score >= 70:
        return "Good"
    if score >= 50:
        return "Fair"
    if score >= 30:
        return "Needs Attention"
    return "Significant Issues"

