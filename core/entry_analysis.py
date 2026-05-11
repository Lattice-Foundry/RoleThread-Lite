"""Pure entry analysis result types and format-agnostic checks."""
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, ClassVar


class AnalysisSeverity(StrEnum):
    """Diagnostic severity levels."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class RepairKind(StrEnum):
    """How a diagnostic can be repaired."""

    NONE = "none"
    AUTOMATIC = "automatic"
    SUGGESTED = "suggested"
    MANUAL = "manual"


BASE_NOT_DICT = "base.not_dict"
BASE_UNKNOWN_TOP_LEVEL_KEY = "base.unknown_top_level_key"
BASE_MISSING_TAGS = "base.missing_tags"
BASE_TAGS_NOT_LIST = "base.tags_not_list"
BASE_INVALID_TAG_VALUE = "base.invalid_tag_value"
BASE_EMPTY_TAG = "base.empty_tag"


@dataclass(frozen=True)
class EntryDiagnostic:
    """One typed diagnostic produced while analyzing an entry."""

    code: str
    severity: AnalysisSeverity
    message: str
    path: tuple[str | int, ...] = ()
    fixable: bool = False
    repair_kind: RepairKind = RepairKind.NONE
    suggested_repair: str | None = None
    original_value: Any | None = None
    normalized_value: Any | None = None


@dataclass(frozen=True)
class EntryAnalysisResult:
    """Typed analysis result for one entry."""

    format: str
    entry_index: int | None
    is_valid: bool
    diagnostics: tuple[EntryDiagnostic, ...] = ()
    repaired_entry: dict | None = None
    changed: bool = False


class BaseEntryAnalyzer:
    """Analyze format-agnostic entry structure and metadata."""

    FORMAT = "unknown"
    KNOWN_TOP_LEVEL_KEYS: ClassVar[frozenset[str]] = frozenset({
        "messages",
        "conversations",
        "tags",
        "metadata",
        "source",
        "id",
    })

    def __init__(self, *, format_name: str | None = None):
        self.format = format_name or self.FORMAT

    def analyze(self, entry: object, *, entry_index: int | None = None) -> EntryAnalysisResult:
        """Run base checks and return typed diagnostics."""
        diagnostics = self._analyze_base(entry)
        return self._result(
            entry_index=entry_index,
            diagnostics=diagnostics,
        )

    def _analyze_base(self, entry: object) -> tuple[EntryDiagnostic, ...]:
        diagnostics: list[EntryDiagnostic] = []
        if not isinstance(entry, dict):
            diagnostics.append(
                EntryDiagnostic(
                    code=BASE_NOT_DICT,
                    severity=AnalysisSeverity.ERROR,
                    message="Entry must be a JSON object.",
                    path=(),
                    original_value=entry,
                )
            )
            return tuple(diagnostics)

        diagnostics.extend(self._analyze_unknown_top_level_keys(entry))
        diagnostics.extend(self._analyze_tags(entry))
        return tuple(diagnostics)

    def _analyze_unknown_top_level_keys(self, entry: dict) -> tuple[EntryDiagnostic, ...]:
        diagnostics: list[EntryDiagnostic] = []
        for key in sorted(entry):
            if key in self.KNOWN_TOP_LEVEL_KEYS:
                continue
            diagnostics.append(
                EntryDiagnostic(
                    code=BASE_UNKNOWN_TOP_LEVEL_KEY,
                    severity=AnalysisSeverity.INFO,
                    message=f"Unknown top-level key preserved: {key}",
                    path=(key,),
                    original_value=entry.get(key),
                )
            )
        return tuple(diagnostics)

    def _analyze_tags(self, entry: dict) -> tuple[EntryDiagnostic, ...]:
        if "tags" not in entry:
            return (
                EntryDiagnostic(
                    code=BASE_MISSING_TAGS,
                    severity=AnalysisSeverity.WARNING,
                    message="Missing 'tags' metadata; LoreForge can add tags: [].",
                    path=("tags",),
                    fixable=True,
                    repair_kind=RepairKind.AUTOMATIC,
                    suggested_repair="Add tags: [].",
                    normalized_value=[],
                ),
            )

        tags = entry.get("tags")
        if not isinstance(tags, list):
            return (
                EntryDiagnostic(
                    code=BASE_TAGS_NOT_LIST,
                    severity=AnalysisSeverity.WARNING,
                    message="'tags' metadata must be a list; LoreForge can replace it with [].",
                    path=("tags",),
                    fixable=True,
                    repair_kind=RepairKind.AUTOMATIC,
                    suggested_repair="Replace tags with [].",
                    original_value=tags,
                    normalized_value=[],
                ),
            )

        diagnostics: list[EntryDiagnostic] = []
        for index, tag in enumerate(tags):
            if not isinstance(tag, str):
                diagnostics.append(
                    EntryDiagnostic(
                        code=BASE_INVALID_TAG_VALUE,
                        severity=AnalysisSeverity.WARNING,
                        message="Tag values must be strings; LoreForge can drop this value.",
                        path=("tags", index),
                        fixable=True,
                        repair_kind=RepairKind.AUTOMATIC,
                        suggested_repair="Drop non-string tag value.",
                        original_value=tag,
                    )
                )
                continue
            if not tag.strip():
                diagnostics.append(
                    EntryDiagnostic(
                        code=BASE_EMPTY_TAG,
                        severity=AnalysisSeverity.INFO,
                        message="Empty tag value can be dropped.",
                        path=("tags", index),
                        fixable=True,
                        repair_kind=RepairKind.AUTOMATIC,
                        suggested_repair="Drop empty tag value.",
                        original_value=tag,
                    )
                )
        return tuple(diagnostics)

    def _result(
        self,
        *,
        entry_index: int | None,
        diagnostics: tuple[EntryDiagnostic, ...],
        repaired_entry: dict | None = None,
        changed: bool = False,
    ) -> EntryAnalysisResult:
        is_valid = not any(
            diagnostic.severity == AnalysisSeverity.ERROR
            for diagnostic in diagnostics
        )
        return EntryAnalysisResult(
            format=self.format,
            entry_index=entry_index,
            is_valid=is_valid,
            diagnostics=diagnostics,
            repaired_entry=repaired_entry,
            changed=changed,
        )
