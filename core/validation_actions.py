"""Pure helpers for grouping and applying entry validation repairs."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from core.dataset import analyze_entry
from core.entry_analysis import (
    BASE_EMPTY_TAG,
    BASE_INVALID_TAG_VALUE,
    BASE_MISSING_TAGS,
    BASE_TAGS_NOT_LIST,
    CHATML_CONTENT_WHITESPACE,
    CHATML_ROLE_CANONICALIZATION,
    AnalysisSeverity,
    ChatMLAnalyzer,
    EntryDiagnostic,
    RepairKind,
)


@dataclass(frozen=True)
class AutoFixSample:
    """Preview data for one auto-fixable diagnostic."""

    entry_index: int
    code: str
    path: tuple[str | int, ...]
    message: str
    original_value: Any | None = None
    normalized_value: Any | None = None


@dataclass(frozen=True)
class AutoFixGroup:
    """Auto-fixable diagnostics grouped by diagnostic code."""

    code: str
    title: str
    description: str
    severity: AnalysisSeverity
    count: int
    entry_indices: tuple[int, ...]
    sample_entries: tuple[AutoFixSample, ...]


_ANALYZER = ChatMLAnalyzer()
_MAX_SAMPLES_PER_GROUP = 5
_SEVERITY_ORDER = {
    AnalysisSeverity.ERROR: 0,
    AnalysisSeverity.WARNING: 1,
    AnalysisSeverity.INFO: 2,
}
_GROUP_COPY = {
    BASE_MISSING_TAGS: (
        "Missing Tags",
        "Adds an empty tags list so LoreForge metadata is present.",
    ),
    BASE_TAGS_NOT_LIST: (
        "Invalid Tags Metadata",
        "Replaces malformed tags metadata with an empty tags list.",
    ),
    BASE_INVALID_TAG_VALUE: (
        "Invalid Tag Values",
        "Drops tag values that are not strings.",
    ),
    BASE_EMPTY_TAG: (
        "Empty Tags",
        "Drops empty or whitespace-only tag values.",
    ),
    CHATML_ROLE_CANONICALIZATION: (
        "Role Normalization",
        "Normalizes known role names and trims role whitespace.",
    ),
    CHATML_CONTENT_WHITESPACE: (
        "Message Whitespace",
        "Trims leading and trailing whitespace from message content.",
    ),
}


def collect_auto_fixable_groups(entries: list[dict]) -> list[AutoFixGroup]:
    """Return auto-fixable diagnostics grouped by diagnostic code."""

    grouped: dict[str, dict[str, Any]] = {}
    for entry_index, entry in enumerate(entries):
        result = analyze_entry(entry)
        for diagnostic in _automatic_diagnostics(result.diagnostics):
            group = grouped.setdefault(
                diagnostic.code,
                {
                    "diagnostics": [],
                    "entry_indices": set(),
                    "severity": diagnostic.severity,
                    "samples": [],
                },
            )
            group["diagnostics"].append(diagnostic)
            group["entry_indices"].add(entry_index)
            if len(group["samples"]) < _MAX_SAMPLES_PER_GROUP:
                group["samples"].append(_sample_for_diagnostic(entry_index, diagnostic))

    groups = [
        AutoFixGroup(
            code=code,
            title=_title_for_code(code),
            description=_description_for_code(code),
            severity=group["severity"],
            count=len(group["diagnostics"]),
            entry_indices=tuple(sorted(group["entry_indices"])),
            sample_entries=tuple(group["samples"]),
        )
        for code, group in grouped.items()
    ]
    return sorted(
        groups,
        key=lambda group: (
            _SEVERITY_ORDER.get(group.severity, 99),
            -group.count,
            group.code,
        ),
    )


def apply_group_repairs(
    entries: list[dict],
    diagnostic_code: str,
) -> tuple[list[dict], list[int]]:
    """Apply automatic repairs for one diagnostic code."""

    repaired_entries = list(entries)
    changed_indices: list[int] = []
    for index, entry in enumerate(entries):
        result = analyze_entry(entry)
        repair_plan = [
            diagnostic
            for diagnostic in _ANALYZER.plan_repairs(result)
            if diagnostic.code == diagnostic_code
        ]
        if not repair_plan:
            continue
        repair = _ANALYZER.apply_repairs(entry, repair_plan)
        if repair.changed:
            repaired_entries[index] = repair.entry
            changed_indices.append(index)
    return repaired_entries, changed_indices


def apply_all_auto_repairs(entries: list[dict]) -> tuple[list[dict], list[int]]:
    """Apply all automatic validation repairs."""

    repaired_entries = list(entries)
    changed_indices: list[int] = []
    for index, entry in enumerate(entries):
        result = analyze_entry(entry)
        repair_plan = _ANALYZER.plan_repairs(result)
        if not repair_plan:
            continue
        repair = _ANALYZER.apply_repairs(entry, repair_plan)
        if repair.changed:
            repaired_entries[index] = repair.entry
            changed_indices.append(index)
    return repaired_entries, changed_indices


def _automatic_diagnostics(
    diagnostics: tuple[EntryDiagnostic, ...],
) -> tuple[EntryDiagnostic, ...]:
    return tuple(
        diagnostic
        for diagnostic in diagnostics
        if diagnostic.fixable and diagnostic.repair_kind == RepairKind.AUTOMATIC
    )


def _sample_for_diagnostic(
    entry_index: int,
    diagnostic: EntryDiagnostic,
) -> AutoFixSample:
    return AutoFixSample(
        entry_index=entry_index,
        code=diagnostic.code,
        path=diagnostic.path,
        message=diagnostic.message,
        original_value=deepcopy(diagnostic.original_value),
        normalized_value=deepcopy(diagnostic.normalized_value),
    )


def _title_for_code(code: str) -> str:
    return _GROUP_COPY.get(code, (_fallback_title(code), ""))[0]


def _description_for_code(code: str) -> str:
    return _GROUP_COPY.get(code, ("", "Applies a deterministic validation repair."))[1]


def _fallback_title(code: str) -> str:
    return code.replace(".", " ").replace("_", " ").title()
