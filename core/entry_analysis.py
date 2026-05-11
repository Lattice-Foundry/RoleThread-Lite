"""Pure entry analysis result types and format-agnostic checks."""
from dataclasses import dataclass, replace
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

CHATML_MISSING_MESSAGES = "chatml.missing_messages"
CHATML_MESSAGES_NOT_LIST = "chatml.messages_not_list"
CHATML_INSUFFICIENT_MESSAGES = "chatml.insufficient_messages"
CHATML_INCOMPLETE_EXCHANGES = "chatml.incomplete_exchanges"
CHATML_SYSTEM_NOT_DICT = "chatml.system_not_dict"
CHATML_MISSING_SYSTEM_ROLE = "chatml.missing_system_role"
CHATML_EMPTY_SYSTEM_CONTENT = "chatml.empty_system_content"
CHATML_MESSAGE_NOT_DICT = "chatml.message_not_dict"
CHATML_WRONG_ROLE = "chatml.wrong_role"
CHATML_EMPTY_CONTENT = "chatml.empty_content"


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


class ChatMLAnalyzer(BaseEntryAnalyzer):
    """Analyze ChatML entry structure using the current validation contract."""

    FORMAT = "chatml"
    KNOWN_TOP_LEVEL_KEYS: ClassVar[frozenset[str]] = (
        BaseEntryAnalyzer.KNOWN_TOP_LEVEL_KEYS | frozenset({"messages"})
    )

    def analyze(self, entry: object, *, entry_index: int | None = None) -> EntryAnalysisResult:
        """Run base and ChatML-specific checks."""
        diagnostics = list(
            self._align_base_diagnostics_with_legacy_validator(
                self._analyze_base(entry)
            )
        )
        if isinstance(entry, dict):
            diagnostics.extend(self._analyze_chatml(entry))
        return self._result(
            entry_index=entry_index,
            diagnostics=tuple(diagnostics),
        )

    def _align_base_diagnostics_with_legacy_validator(
        self,
        diagnostics: tuple[EntryDiagnostic, ...],
    ) -> tuple[EntryDiagnostic, ...]:
        """Preserve validate_entry validity while keeping base analyzer repair metadata."""
        legacy_messages = {
            BASE_MISSING_TAGS: "Missing 'tags' key",
            BASE_TAGS_NOT_LIST: "'tags' must be a list",
            BASE_INVALID_TAG_VALUE: "Each tag must be a string",
        }
        return tuple(
            replace(
                diagnostic,
                severity=AnalysisSeverity.ERROR,
                message=legacy_messages[diagnostic.code],
            )
            if diagnostic.code in legacy_messages
            else diagnostic
            for diagnostic in diagnostics
        )

    def _analyze_chatml(self, entry: dict) -> tuple[EntryDiagnostic, ...]:
        if "messages" not in entry:
            return (
                EntryDiagnostic(
                    code=CHATML_MISSING_MESSAGES,
                    severity=AnalysisSeverity.ERROR,
                    message="Missing 'messages' key",
                    path=("messages",),
                ),
            )

        messages = entry["messages"]
        if not isinstance(messages, list):
            return (
                EntryDiagnostic(
                    code=CHATML_MESSAGES_NOT_LIST,
                    severity=AnalysisSeverity.ERROR,
                    message="'messages' must be a list",
                    path=("messages",),
                    original_value=messages,
                ),
            )

        diagnostics: list[EntryDiagnostic] = []
        if len(messages) < 3:
            diagnostics.append(
                EntryDiagnostic(
                    code=CHATML_INSUFFICIENT_MESSAGES,
                    severity=AnalysisSeverity.ERROR,
                    message="'messages' must have at least 3 items (system + one user/assistant exchange)",
                    path=("messages",),
                    original_value=len(messages),
                )
            )
            return tuple(diagnostics)

        if (len(messages) - 1) % 2 != 0:
            diagnostics.append(
                EntryDiagnostic(
                    code=CHATML_INCOMPLETE_EXCHANGES,
                    severity=AnalysisSeverity.ERROR,
                    message="Messages must contain complete user/assistant exchanges",
                    path=("messages",),
                    original_value=len(messages),
                )
            )
            return tuple(diagnostics)

        system_message = messages[0]
        if not isinstance(system_message, dict):
            diagnostics.append(
                EntryDiagnostic(
                    code=CHATML_SYSTEM_NOT_DICT,
                    severity=AnalysisSeverity.ERROR,
                    message="Message 0 is not a dict",
                    path=("messages", 0),
                    original_value=system_message,
                )
            )
            return tuple(diagnostics)

        system_role = system_message.get("role")
        if system_role != "system":
            diagnostics.append(
                EntryDiagnostic(
                    code=CHATML_MISSING_SYSTEM_ROLE,
                    severity=AnalysisSeverity.ERROR,
                    message=f"Message 0: expected role 'system', got '{system_role}'",
                    path=("messages", 0, "role"),
                    original_value=system_role,
                    normalized_value="system",
                )
            )
        if not system_message.get("content", "").strip():
            diagnostics.append(
                EntryDiagnostic(
                    code=CHATML_EMPTY_SYSTEM_CONTENT,
                    severity=AnalysisSeverity.ERROR,
                    message="Message 0 (system) has empty content",
                    path=("messages", 0, "content"),
                    original_value=system_message.get("content", ""),
                )
            )

        expected_role = "user"
        for index, message in enumerate(messages[1:], 1):
            if not isinstance(message, dict):
                diagnostics.append(
                    EntryDiagnostic(
                        code=CHATML_MESSAGE_NOT_DICT,
                        severity=AnalysisSeverity.ERROR,
                        message=f"Message {index} is not a dict",
                        path=("messages", index),
                        original_value=message,
                    )
                )
                expected_role = "assistant" if expected_role == "user" else "user"
                continue

            actual_role = message.get("role")
            if actual_role != expected_role:
                diagnostics.append(
                    EntryDiagnostic(
                        code=CHATML_WRONG_ROLE,
                        severity=AnalysisSeverity.ERROR,
                        message=f"Message {index}: expected role '{expected_role}', got '{actual_role}'",
                        path=("messages", index, "role"),
                        original_value=actual_role,
                        normalized_value=expected_role,
                    )
                )
            if not message.get("content", "").strip():
                diagnostics.append(
                    EntryDiagnostic(
                        code=CHATML_EMPTY_CONTENT,
                        severity=AnalysisSeverity.ERROR,
                        message=f"Message {index} ({expected_role}) has empty content",
                        path=("messages", index, "content"),
                        original_value=message.get("content", ""),
                    )
                )
            expected_role = "assistant" if expected_role == "user" else "user"

        return tuple(diagnostics)
