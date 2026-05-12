"""Pure entry analysis result types and format-agnostic checks."""
from copy import deepcopy
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Any, ClassVar

from core.loreforge_meta import LOREFORGE_META_KEY
from core.role_normalization import is_known_role_variant, normalize_role


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
CHATML_ROLE_CANONICALIZATION = "chatml.role_canonicalization"
CHATML_CONTENT_WHITESPACE = "chatml.content_whitespace"

SHAREGPT_MISSING_CONVERSATIONS = "sharegpt.missing_conversations"
SHAREGPT_CONVERSATIONS_NOT_LIST = "sharegpt.conversations_not_list"
SHAREGPT_EMPTY_CONVERSATIONS = "sharegpt.empty_conversations"
SHAREGPT_TURN_NOT_DICT = "sharegpt.turn_not_dict"
SHAREGPT_MISSING_ROLE_FIELD = "sharegpt.missing_role_field"
SHAREGPT_MISSING_CONTENT_FIELD = "sharegpt.missing_content_field"
SHAREGPT_ROLE_VARIANT = "sharegpt.role_variant"
SHAREGPT_UNKNOWN_ROLE = "sharegpt.unknown_role"
SHAREGPT_EMPTY_CONTENT = "sharegpt.empty_content"
SHAREGPT_MULTIPLE_SYSTEM_TURNS = "sharegpt.multiple_system_turns"
SHAREGPT_NO_SYSTEM_TURN = "sharegpt.no_system_turn"


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


@dataclass(frozen=True)
class RepairResult:
    """Result of applying deterministic entry repairs."""

    entry: dict
    repairs_applied: tuple[EntryDiagnostic, ...]
    changed: bool


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
        LOREFORGE_META_KEY,
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

    def plan_repairs(self, result: EntryAnalysisResult) -> list[EntryDiagnostic]:
        """Return automatic diagnostics that can be applied deterministically."""
        return [
            diagnostic
            for diagnostic in result.diagnostics
            if diagnostic.fixable and diagnostic.repair_kind == RepairKind.AUTOMATIC
        ]

    def apply_repairs(
        self,
        entry: dict,
        repair_plan: list[EntryDiagnostic],
    ) -> RepairResult:
        """Apply deterministic repairs to a copy of the entry."""
        repaired_entry = deepcopy(entry)
        applied: list[EntryDiagnostic] = []
        for diagnostic in self._ordered_repair_plan(repair_plan):
            if self._apply_single_repair(repaired_entry, diagnostic):
                applied.append(diagnostic)
        return RepairResult(
            entry=repaired_entry,
            repairs_applied=tuple(applied),
            changed=repaired_entry != entry,
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

    def _ordered_repair_plan(
        self,
        repair_plan: list[EntryDiagnostic],
    ) -> list[EntryDiagnostic]:
        tag_item_repairs = [
            diagnostic
            for diagnostic in repair_plan
            if diagnostic.code in {BASE_INVALID_TAG_VALUE, BASE_EMPTY_TAG}
        ]
        other_repairs = [
            diagnostic
            for diagnostic in repair_plan
            if diagnostic.code not in {BASE_INVALID_TAG_VALUE, BASE_EMPTY_TAG}
        ]
        tag_item_repairs.sort(
            key=lambda diagnostic: (
                diagnostic.path[1]
                if len(diagnostic.path) > 1 and isinstance(diagnostic.path[1], int)
                else -1
            ),
            reverse=True,
        )
        return other_repairs + tag_item_repairs

    def _apply_single_repair(
        self,
        entry: dict,
        diagnostic: EntryDiagnostic,
    ) -> bool:
        if diagnostic.code == BASE_MISSING_TAGS:
            if "tags" not in entry:
                entry["tags"] = []
                return True
            return False

        if diagnostic.code == BASE_TAGS_NOT_LIST:
            if not isinstance(entry.get("tags"), list):
                entry["tags"] = []
                return True
            return False

        if diagnostic.code == BASE_INVALID_TAG_VALUE:
            return self._drop_tag_at_path(
                entry,
                diagnostic,
                should_drop=lambda tag: not isinstance(tag, str),
            )

        if diagnostic.code == BASE_EMPTY_TAG:
            return self._drop_tag_at_path(
                entry,
                diagnostic,
                should_drop=lambda tag: isinstance(tag, str) and not tag.strip(),
            )

        return False

    def _drop_tag_at_path(
        self,
        entry: dict,
        diagnostic: EntryDiagnostic,
        *,
        should_drop,
    ) -> bool:
        if len(diagnostic.path) != 2 or diagnostic.path[0] != "tags":
            return False
        index = diagnostic.path[1]
        tags = entry.get("tags")
        if not isinstance(index, int) or not isinstance(tags, list):
            return False
        if index < 0 or index >= len(tags):
            return False
        if not should_drop(tags[index]):
            return False
        del tags[index]
        return True

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
            BASE_INVALID_TAG_VALUE: (
                "Tags contain non-text values, like numbers. "
                "These will be removed when you save."
            ),
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
                    repair_kind=RepairKind.MANUAL,
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
                    repair_kind=RepairKind.MANUAL,
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
                    repair_kind=RepairKind.MANUAL,
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
                    repair_kind=RepairKind.MANUAL,
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
                    message="First message must be a system prompt object.",
                    path=("messages", 0),
                    repair_kind=RepairKind.MANUAL,
                    original_value=system_message,
                )
            )
            return tuple(diagnostics)

        system_role = system_message.get("role")
        normalized_system_role = self._canonical_role(system_role)
        if normalized_system_role == "system" and system_role != "system":
            diagnostics.append(
                self._role_canonicalization_diagnostic(
                    index=0,
                    original_value=system_role,
                    normalized_value="system",
                )
            )
        elif system_role != "system":
            diagnostics.extend(
                self._role_whitespace_diagnostic(system_role, 0, expected_role="system")
            )
            diagnostics.append(
                EntryDiagnostic(
                    code=CHATML_MISSING_SYSTEM_ROLE,
                    severity=AnalysisSeverity.ERROR,
                    message=self._wrong_role_message(
                        role=system_role,
                        expected_role="system",
                        index=0,
                        system_position=True,
                    ),
                    path=("messages", 0, "role"),
                    repair_kind=RepairKind.MANUAL,
                    original_value=system_role,
                    normalized_value="system",
                )
            )
        diagnostics.extend(self._content_whitespace_diagnostic(system_message, 0))
        if not system_message.get("content", "").strip():
            diagnostics.append(
                EntryDiagnostic(
                    code=CHATML_EMPTY_SYSTEM_CONTENT,
                    severity=AnalysisSeverity.ERROR,
                    message="First system prompt is empty.",
                    path=("messages", 0, "content"),
                    fixable=True,
                    repair_kind=RepairKind.SUGGESTED,
                    suggested_repair="Review and add an appropriate system prompt.",
                    original_value=system_message.get("content", ""),
                )
            )

        expected_role = "user"
        reported_custom_roles: set[str] = set()
        for index, message in enumerate(messages[1:], 1):
            if not isinstance(message, dict):
                diagnostics.append(
                    EntryDiagnostic(
                        code=CHATML_MESSAGE_NOT_DICT,
                        severity=AnalysisSeverity.ERROR,
                        message=f"Message {index + 1} is not a valid message object.",
                        path=("messages", index),
                        repair_kind=RepairKind.MANUAL,
                        original_value=message,
                    )
                )
                expected_role = "assistant" if expected_role == "user" else "user"
                continue

            actual_role = message.get("role")
            normalized_role = self._canonical_role(actual_role)
            if normalized_role == expected_role and actual_role != expected_role:
                diagnostics.append(
                    self._role_canonicalization_diagnostic(
                        index=index,
                        original_value=actual_role,
                        normalized_value=expected_role,
                )
            )
            elif actual_role != expected_role:
                diagnostics.extend(
                    self._role_whitespace_diagnostic(
                        actual_role,
                        index,
                        expected_role=expected_role,
                    )
                )
                if not self._is_duplicate_custom_role(
                    actual_role,
                    reported_custom_roles,
                ):
                    diagnostics.append(
                        EntryDiagnostic(
                            code=CHATML_WRONG_ROLE,
                            severity=AnalysisSeverity.ERROR,
                            message=self._wrong_role_message(
                                role=actual_role,
                                expected_role=expected_role,
                                index=index,
                            ),
                            path=("messages", index, "role"),
                            repair_kind=RepairKind.MANUAL,
                            original_value=actual_role,
                            normalized_value=expected_role,
                        )
                    )
            diagnostics.extend(self._content_whitespace_diagnostic(message, index))
            if not message.get("content", "").strip():
                diagnostics.append(
                    EntryDiagnostic(
                        code=CHATML_EMPTY_CONTENT,
                        severity=AnalysisSeverity.ERROR,
                        message=f"Message {index + 1} ({expected_role}) is empty.",
                        path=("messages", index, "content"),
                        repair_kind=RepairKind.MANUAL,
                        original_value=message.get("content", ""),
                    )
                )
            expected_role = "assistant" if expected_role == "user" else "user"

        return tuple(diagnostics)

    def _role_article(self, role: str) -> str:
        if role == "user":
            return "a"
        return "an" if role[:1].lower() in {"a", "e", "i", "o", "u"} else "a"

    def _canonical_role(self, role: object) -> str | None:
        if not isinstance(role, str):
            return None
        if not is_known_role_variant(role):
            return None
        return normalize_role(role)[0]

    def _wrong_role_message(
        self,
        *,
        role: object,
        expected_role: str,
        index: int,
        system_position: bool = False,
    ) -> str:
        if isinstance(role, str) and not is_known_role_variant(role):
            return (
                f"Custom role name '{role}' detected. LoreForge needs canonical "
                "user/assistant/system roles; the character system will preserve "
                "identity metadata."
            )
        if system_position:
            return (
                "First message must be a system prompt, "
                f"but found role '{role}'."
            )
        return (
            f"Message {index + 1} should be "
            f"{self._role_article(expected_role)} {expected_role} turn, "
            f"but found role '{role}'."
        )

    def _is_duplicate_custom_role(
        self,
        role: object,
        reported_custom_roles: set[str],
    ) -> bool:
        if not isinstance(role, str) or is_known_role_variant(role):
            return False
        key = role.strip().casefold()
        if not key:
            return False
        if key in reported_custom_roles:
            return True
        reported_custom_roles.add(key)
        return False

    def _role_whitespace_diagnostic(
        self,
        role: object,
        index: int,
        *,
        expected_role: str,
    ) -> tuple[EntryDiagnostic, ...]:
        if not isinstance(role, str):
            return ()
        normalized_role, changed = normalize_role(role)
        if not changed or normalized_role != expected_role:
            return ()
        return (
            self._role_canonicalization_diagnostic(
                index=index,
                original_value=role,
                normalized_value=normalized_role,
            ),
        )

    def _apply_single_repair(
        self,
        entry: dict,
        diagnostic: EntryDiagnostic,
    ) -> bool:
        if diagnostic.code == CHATML_ROLE_CANONICALIZATION:
            return self._set_message_field_from_diagnostic(
                entry,
                diagnostic,
                field="role",
            )

        if diagnostic.code == CHATML_CONTENT_WHITESPACE:
            return self._set_message_field_from_diagnostic(
                entry,
                diagnostic,
                field="content",
            )

        return super()._apply_single_repair(entry, diagnostic)

    def _set_message_field_from_diagnostic(
        self,
        entry: dict,
        diagnostic: EntryDiagnostic,
        *,
        field: str,
    ) -> bool:
        if (
            len(diagnostic.path) != 3
            or diagnostic.path[0] != "messages"
            or diagnostic.path[2] != field
        ):
            return False
        index = diagnostic.path[1]
        messages = entry.get("messages")
        if not isinstance(index, int) or not isinstance(messages, list):
            return False
        if index < 0 or index >= len(messages):
            return False
        message = messages[index]
        if not isinstance(message, dict):
            return False
        if message.get(field) != diagnostic.original_value:
            return False
        message[field] = diagnostic.normalized_value
        return True

    def _role_canonicalization_diagnostic(
        self,
        *,
        index: int,
        original_value: object,
        normalized_value: str,
    ) -> EntryDiagnostic:
        return EntryDiagnostic(
            code=CHATML_ROLE_CANONICALIZATION,
            severity=AnalysisSeverity.WARNING,
            message=(
                f"Role '{original_value}' will be normalized to "
                f"'{normalized_value}' on save."
            ),
            path=("messages", index, "role"),
            fixable=True,
            repair_kind=RepairKind.AUTOMATIC,
            suggested_repair="Normalize role to canonical ChatML value.",
            original_value=original_value,
            normalized_value=normalized_value,
        )

    def _content_whitespace_diagnostic(
        self,
        message: dict,
        index: int,
    ) -> tuple[EntryDiagnostic, ...]:
        content = message.get("content")
        if not isinstance(content, str):
            return ()
        stripped = content.strip()
        if stripped == content:
            return ()
        return (
            EntryDiagnostic(
                code=CHATML_CONTENT_WHITESPACE,
                severity=AnalysisSeverity.WARNING,
                message=(
                    f"Message {index + 1} has extra spaces at the beginning "
                    "or end of its text."
                ),
                path=("messages", index, "content"),
                fixable=True,
                repair_kind=RepairKind.AUTOMATIC,
                suggested_repair="Trim leading and trailing whitespace.",
                original_value=content,
                normalized_value=stripped,
            ),
        )


class ShareGPTAnalyzer(BaseEntryAnalyzer):
    """Analyze ShareGPT import structure with lenient import diagnostics."""

    FORMAT = "sharegpt"
    KNOWN_TOP_LEVEL_KEYS: ClassVar[frozenset[str]] = (
        BaseEntryAnalyzer.KNOWN_TOP_LEVEL_KEYS
        | frozenset({
            "conversations",
            "conversation",
            "id",
            "title",
            "source",
            "model",
        })
    )
    ROLE_FIELD_KEYS: ClassVar[tuple[str, ...]] = ("from", "role", "speaker")
    CONTENT_FIELD_KEYS: ClassVar[tuple[str, ...]] = ("value", "content", "text")
    CANONICAL_ROLE_VALUES: ClassVar[dict[str, str]] = {
        "user": "human",
        "assistant": "gpt",
        "system": "system",
    }

    def analyze(self, entry: object, *, entry_index: int | None = None) -> EntryAnalysisResult:
        """Run base and ShareGPT-specific checks."""
        diagnostics = list(self._analyze_base(entry))
        if isinstance(entry, dict):
            diagnostics.extend(self._analyze_sharegpt(entry))
        return self._result(
            entry_index=entry_index,
            diagnostics=tuple(diagnostics),
        )

    def _analyze_sharegpt(self, entry: dict) -> tuple[EntryDiagnostic, ...]:
        if "conversations" not in entry:
            return (
                EntryDiagnostic(
                    code=SHAREGPT_MISSING_CONVERSATIONS,
                    severity=AnalysisSeverity.ERROR,
                    message="Missing 'conversations' key",
                    path=("conversations",),
                    repair_kind=RepairKind.MANUAL,
                ),
            )

        conversations = entry["conversations"]
        if not isinstance(conversations, list):
            return (
                EntryDiagnostic(
                    code=SHAREGPT_CONVERSATIONS_NOT_LIST,
                    severity=AnalysisSeverity.ERROR,
                    message="'conversations' must be a list",
                    path=("conversations",),
                    repair_kind=RepairKind.MANUAL,
                    original_value=conversations,
                ),
            )

        if not conversations:
            return (
                EntryDiagnostic(
                    code=SHAREGPT_EMPTY_CONVERSATIONS,
                    severity=AnalysisSeverity.ERROR,
                    message="'conversations' must contain at least one turn",
                    path=("conversations",),
                    repair_kind=RepairKind.MANUAL,
                    original_value=0,
                ),
            )

        diagnostics: list[EntryDiagnostic] = []
        system_turn_count = 0
        for index, turn in enumerate(conversations):
            if not isinstance(turn, dict):
                diagnostics.append(
                    EntryDiagnostic(
                        code=SHAREGPT_TURN_NOT_DICT,
                        severity=AnalysisSeverity.ERROR,
                        message=(
                            f"Conversation turn {index + 1} is not a valid "
                            "conversation object."
                        ),
                        path=("conversations", index),
                        repair_kind=RepairKind.MANUAL,
                        original_value=turn,
                    )
                )
                continue

            role_key, raw_role = self._first_present(turn, self.ROLE_FIELD_KEYS)
            content_key, raw_content = self._first_present(turn, self.CONTENT_FIELD_KEYS)

            if role_key is None:
                diagnostics.append(
                    EntryDiagnostic(
                        code=SHAREGPT_MISSING_ROLE_FIELD,
                        severity=AnalysisSeverity.ERROR,
                        message=f"Conversation turn {index + 1} is missing a role field.",
                        path=("conversations", index),
                        repair_kind=RepairKind.MANUAL,
                    )
                )
            else:
                mapped_role = self._map_role(raw_role)
                if mapped_role is None:
                    diagnostics.append(
                        EntryDiagnostic(
                            code=SHAREGPT_UNKNOWN_ROLE,
                            severity=AnalysisSeverity.WARNING,
                            message=(
                                f"Conversation turn {index + 1} has non-standard "
                                f"role '{raw_role}'."
                            ),
                            path=("conversations", index, role_key),
                            repair_kind=RepairKind.MANUAL,
                            original_value=raw_role,
                        )
                    )
                else:
                    canonical_role = self.CANONICAL_ROLE_VALUES[mapped_role]
                    if str(raw_role).strip() != canonical_role:
                        diagnostics.append(
                            EntryDiagnostic(
                                code=SHAREGPT_ROLE_VARIANT,
                                severity=AnalysisSeverity.INFO,
                                message=(
                                    f"Conversation turn {index} uses role variant "
                                    f"'{raw_role}' for '{canonical_role}'."
                                ),
                                path=("conversations", index, role_key),
                                fixable=True,
                                repair_kind=RepairKind.AUTOMATIC,
                                suggested_repair=(
                                    f"Replace role value with '{canonical_role}'."
                                ),
                                original_value=raw_role,
                                normalized_value=canonical_role,
                            )
                        )
                    if mapped_role == "system":
                        system_turn_count += 1

            if content_key is None:
                diagnostics.append(
                    EntryDiagnostic(
                        code=SHAREGPT_MISSING_CONTENT_FIELD,
                        severity=AnalysisSeverity.ERROR,
                        message=(
                            f"Conversation turn {index + 1} is missing a message "
                            "content field."
                        ),
                        path=("conversations", index),
                        repair_kind=RepairKind.MANUAL,
                    )
                )
            elif not str(raw_content).strip():
                diagnostics.append(
                    EntryDiagnostic(
                        code=SHAREGPT_EMPTY_CONTENT,
                        severity=AnalysisSeverity.WARNING,
                        message=f"Conversation turn {index + 1} has empty content.",
                        path=("conversations", index, content_key),
                        fixable=True,
                        repair_kind=RepairKind.SUGGESTED,
                        suggested_repair="Review whether this empty turn should be filled or removed.",
                        original_value=raw_content,
                    )
                )

        if system_turn_count > 1:
            diagnostics.append(
                EntryDiagnostic(
                    code=SHAREGPT_MULTIPLE_SYSTEM_TURNS,
                    severity=AnalysisSeverity.INFO,
                    message="ShareGPT entry contains multiple system turns.",
                    path=("conversations",),
                    fixable=True,
                    repair_kind=RepairKind.SUGGESTED,
                    suggested_repair="Review and merge system turns before conversion.",
                    original_value=system_turn_count,
                )
            )
        elif system_turn_count == 0:
            diagnostics.append(
                EntryDiagnostic(
                    code=SHAREGPT_NO_SYSTEM_TURN,
                    severity=AnalysisSeverity.INFO,
                    message="ShareGPT entry has no system turn; LoreForge can inject one during conversion.",
                    path=("conversations",),
                    fixable=True,
                    repair_kind=RepairKind.SUGGESTED,
                    suggested_repair="Inject LoreForge's internal ShareGPT import system prompt.",
                )
            )

        return tuple(diagnostics)

    def _apply_single_repair(
        self,
        entry: dict,
        diagnostic: EntryDiagnostic,
    ) -> bool:
        if super()._apply_single_repair(entry, diagnostic):
            return True

        if diagnostic.code != SHAREGPT_ROLE_VARIANT:
            return False
        if len(diagnostic.path) != 3 or diagnostic.path[0] != "conversations":
            return False
        index = diagnostic.path[1]
        role_key = diagnostic.path[2]
        conversations = entry.get("conversations")
        if (
            not isinstance(index, int)
            or not isinstance(role_key, str)
            or not isinstance(conversations, list)
            or index < 0
            or index >= len(conversations)
            or not isinstance(conversations[index], dict)
            or role_key not in conversations[index]
            or diagnostic.normalized_value is None
        ):
            return False
        if conversations[index][role_key] == diagnostic.normalized_value:
            return False
        conversations[index][role_key] = diagnostic.normalized_value
        return True

    def _first_present(
        self,
        turn: dict,
        keys: tuple[str, ...],
    ) -> tuple[str | None, object | None]:
        for key in keys:
            if key in turn:
                return key, turn[key]
        return None, None

    def _map_role(self, raw_role: object) -> str | None:
        role, changed = normalize_role(str(raw_role))
        if changed or role in {"user", "assistant", "system"}:
            return role
        return None
