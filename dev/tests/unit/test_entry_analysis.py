import dataclasses

import pytest

from core.dataset import validate_entry
from core.entry_analysis import (
    BASE_EMPTY_TAG,
    BASE_INVALID_TAG_VALUE,
    BASE_MISSING_TAGS,
    BASE_NOT_DICT,
    BASE_TAGS_NOT_LIST,
    BASE_UNKNOWN_TOP_LEVEL_KEY,
    CHATML_EMPTY_CONTENT,
    CHATML_EMPTY_SYSTEM_CONTENT,
    CHATML_INCOMPLETE_EXCHANGES,
    CHATML_INSUFFICIENT_MESSAGES,
    CHATML_MESSAGE_NOT_DICT,
    CHATML_MESSAGES_NOT_LIST,
    CHATML_MISSING_MESSAGES,
    CHATML_MISSING_SYSTEM_ROLE,
    CHATML_SYSTEM_NOT_DICT,
    CHATML_WRONG_ROLE,
    SHAREGPT_CONVERSATIONS_NOT_LIST,
    SHAREGPT_EMPTY_CONTENT,
    SHAREGPT_EMPTY_CONVERSATIONS,
    SHAREGPT_MISSING_CONTENT_FIELD,
    SHAREGPT_MISSING_CONVERSATIONS,
    SHAREGPT_MISSING_ROLE_FIELD,
    SHAREGPT_MULTIPLE_SYSTEM_TURNS,
    SHAREGPT_NO_SYSTEM_TURN,
    SHAREGPT_TURN_NOT_DICT,
    SHAREGPT_UNKNOWN_ROLE,
    AnalysisSeverity,
    BaseEntryAnalyzer,
    ChatMLAnalyzer,
    EntryAnalysisResult,
    EntryDiagnostic,
    RepairKind,
    ShareGPTAnalyzer,
)


def _diagnostic_by_code(result: EntryAnalysisResult, code: str) -> EntryDiagnostic:
    matches = [diagnostic for diagnostic in result.diagnostics if diagnostic.code == code]
    assert len(matches) == 1
    return matches[0]


def _entry(*, messages=None, tags=None):
    return {
        "messages": messages
        or [
            {"role": "system", "content": "System"},
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello"},
        ],
        "tags": [] if tags is None else tags,
    }


def _sharegpt_entry(*, conversations=None, tags=None):
    return {
        "conversations": conversations
        or [
            {"from": "system", "value": "System"},
            {"from": "human", "value": "Hi"},
            {"from": "gpt", "value": "Hello"},
        ],
        "tags": [] if tags is None else tags,
    }


def test_base_analyzer_accepts_known_top_level_keys_without_diagnostics():
    analyzer = BaseEntryAnalyzer(format_name="base")
    entry = {
        "messages": [],
        "conversations": [],
        "tags": [],
        "metadata": {},
        "source": "fixture",
        "id": "entry-1",
    }

    result = analyzer.analyze(entry, entry_index=7)

    assert result.format == "base"
    assert result.entry_index == 7
    assert result.is_valid is True
    assert result.diagnostics == ()
    assert result.repaired_entry is None
    assert result.changed is False


def test_base_analyzer_reports_non_dict_entry_as_error():
    result = BaseEntryAnalyzer().analyze(["not", "a", "dict"])

    diagnostic = _diagnostic_by_code(result, BASE_NOT_DICT)

    assert result.is_valid is False
    assert diagnostic.severity == AnalysisSeverity.ERROR
    assert diagnostic.message == "Entry must be a JSON object."
    assert diagnostic.path == ()
    assert diagnostic.fixable is False
    assert diagnostic.repair_kind == RepairKind.NONE
    assert diagnostic.original_value == ["not", "a", "dict"]


def test_base_analyzer_reports_unknown_top_level_keys_as_info():
    result = BaseEntryAnalyzer().analyze({
        "messages": [],
        "tags": [],
        "mystery": "kept",
    })

    diagnostic = _diagnostic_by_code(result, BASE_UNKNOWN_TOP_LEVEL_KEY)

    assert result.is_valid is True
    assert diagnostic.severity == AnalysisSeverity.INFO
    assert diagnostic.message == "Unknown top-level key preserved: mystery"
    assert diagnostic.path == ("mystery",)
    assert diagnostic.fixable is False
    assert diagnostic.original_value == "kept"


def test_base_analyzer_reports_missing_tags_as_auto_fixable_warning():
    result = BaseEntryAnalyzer().analyze({"messages": []})

    diagnostic = _diagnostic_by_code(result, BASE_MISSING_TAGS)

    assert result.is_valid is True
    assert diagnostic.severity == AnalysisSeverity.WARNING
    assert diagnostic.path == ("tags",)
    assert diagnostic.fixable is True
    assert diagnostic.repair_kind == RepairKind.AUTOMATIC
    assert diagnostic.suggested_repair == "Add tags: []."
    assert diagnostic.normalized_value == []


def test_base_analyzer_reports_tags_not_list_as_auto_fixable_warning():
    result = BaseEntryAnalyzer().analyze({
        "messages": [],
        "tags": "slow_burn",
    })

    diagnostic = _diagnostic_by_code(result, BASE_TAGS_NOT_LIST)

    assert result.is_valid is True
    assert diagnostic.severity == AnalysisSeverity.WARNING
    assert diagnostic.path == ("tags",)
    assert diagnostic.fixable is True
    assert diagnostic.repair_kind == RepairKind.AUTOMATIC
    assert diagnostic.suggested_repair == "Replace tags with []."
    assert diagnostic.original_value == "slow_burn"
    assert diagnostic.normalized_value == []


def test_base_analyzer_reports_non_string_and_empty_tags():
    result = BaseEntryAnalyzer().analyze({
        "messages": [],
        "tags": ["slow_burn", 7, "   "],
    })

    invalid = _diagnostic_by_code(result, BASE_INVALID_TAG_VALUE)
    empty = _diagnostic_by_code(result, BASE_EMPTY_TAG)

    assert result.is_valid is True
    assert invalid.severity == AnalysisSeverity.WARNING
    assert invalid.path == ("tags", 1)
    assert invalid.fixable is True
    assert invalid.repair_kind == RepairKind.AUTOMATIC
    assert invalid.original_value == 7
    assert empty.severity == AnalysisSeverity.INFO
    assert empty.path == ("tags", 2)
    assert empty.fixable is True
    assert empty.repair_kind == RepairKind.AUTOMATIC
    assert empty.original_value == "   "


def test_analysis_result_validity_depends_only_on_error_severity():
    analyzer = BaseEntryAnalyzer()
    warning = EntryDiagnostic(
        code=BASE_MISSING_TAGS,
        severity=AnalysisSeverity.WARNING,
        message="warning",
    )
    info = EntryDiagnostic(
        code=BASE_UNKNOWN_TOP_LEVEL_KEY,
        severity=AnalysisSeverity.INFO,
        message="info",
    )
    error = EntryDiagnostic(
        code=BASE_NOT_DICT,
        severity=AnalysisSeverity.ERROR,
        message="error",
    )

    non_blocking = analyzer._result(entry_index=None, diagnostics=(warning, info))
    blocking = analyzer._result(entry_index=None, diagnostics=(warning, error))

    assert non_blocking.is_valid is True
    assert blocking.is_valid is False


def test_analysis_dataclasses_are_frozen():
    diagnostic = EntryDiagnostic(
        code=BASE_MISSING_TAGS,
        severity=AnalysisSeverity.WARNING,
        message="Missing tags.",
    )
    result = EntryAnalysisResult(
        format="unknown",
        entry_index=None,
        is_valid=True,
        diagnostics=(diagnostic,),
    )

    with pytest.raises(dataclasses.FrozenInstanceError):
        diagnostic.message = "changed"
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.is_valid = False


def test_severity_and_repair_enums_have_stable_values():
    assert AnalysisSeverity.INFO.value == "info"
    assert AnalysisSeverity.WARNING.value == "warning"
    assert AnalysisSeverity.ERROR.value == "error"
    assert RepairKind.NONE.value == "none"
    assert RepairKind.AUTOMATIC.value == "automatic"
    assert RepairKind.SUGGESTED.value == "suggested"
    assert RepairKind.MANUAL.value == "manual"


def test_chatml_analyzer_reports_missing_messages_key():
    result = ChatMLAnalyzer().analyze({"tags": []})

    diagnostic = _diagnostic_by_code(result, CHATML_MISSING_MESSAGES)

    assert result.is_valid is False
    assert diagnostic.severity == AnalysisSeverity.ERROR
    assert diagnostic.message == "Missing 'messages' key"
    assert diagnostic.path == ("messages",)


def test_chatml_analyzer_reports_messages_not_list():
    result = ChatMLAnalyzer().analyze({"messages": "bad", "tags": []})

    diagnostic = _diagnostic_by_code(result, CHATML_MESSAGES_NOT_LIST)

    assert result.is_valid is False
    assert diagnostic.severity == AnalysisSeverity.ERROR
    assert diagnostic.message == "'messages' must be a list"
    assert diagnostic.path == ("messages",)


def test_chatml_analyzer_reports_insufficient_messages():
    result = ChatMLAnalyzer().analyze({
        "messages": [
            {"role": "system", "content": "System"},
            {"role": "user", "content": "Hi"},
        ],
        "tags": [],
    })

    diagnostic = _diagnostic_by_code(result, CHATML_INSUFFICIENT_MESSAGES)

    assert result.is_valid is False
    assert diagnostic.severity == AnalysisSeverity.ERROR
    assert "at least 3" in diagnostic.message
    assert diagnostic.path == ("messages",)


def test_chatml_analyzer_reports_incomplete_exchanges():
    result = ChatMLAnalyzer().analyze({
        "messages": [
            {"role": "system", "content": "System"},
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello"},
            {"role": "user", "content": "Again"},
        ],
        "tags": [],
    })

    diagnostic = _diagnostic_by_code(result, CHATML_INCOMPLETE_EXCHANGES)

    assert result.is_valid is False
    assert diagnostic.severity == AnalysisSeverity.ERROR
    assert diagnostic.message == "Messages must contain complete user/assistant exchanges"
    assert diagnostic.path == ("messages",)


def test_chatml_analyzer_reports_system_not_dict():
    result = ChatMLAnalyzer().analyze({
        "messages": [
            "not dict",
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello"},
        ],
        "tags": [],
    })

    diagnostic = _diagnostic_by_code(result, CHATML_SYSTEM_NOT_DICT)

    assert result.is_valid is False
    assert diagnostic.severity == AnalysisSeverity.ERROR
    assert diagnostic.message == "Message 0 is not a dict"
    assert diagnostic.path == ("messages", 0)


def test_chatml_analyzer_reports_wrong_system_role_and_empty_content():
    result = ChatMLAnalyzer().analyze({
        "messages": [
            {"role": "user", "content": " "},
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello"},
        ],
        "tags": [],
    })

    role = _diagnostic_by_code(result, CHATML_MISSING_SYSTEM_ROLE)
    content = _diagnostic_by_code(result, CHATML_EMPTY_SYSTEM_CONTENT)

    assert result.is_valid is False
    assert role.severity == AnalysisSeverity.ERROR
    assert role.message == "Message 0: expected role 'system', got 'user'"
    assert role.path == ("messages", 0, "role")
    assert role.original_value == "user"
    assert role.normalized_value == "system"
    assert content.severity == AnalysisSeverity.ERROR
    assert content.message == "Message 0 (system) has empty content"
    assert content.path == ("messages", 0, "content")


def test_chatml_analyzer_reports_message_not_dict_with_indexed_path():
    result = ChatMLAnalyzer().analyze({
        "messages": [
            {"role": "system", "content": "System"},
            "bad",
            {"role": "user", "content": "Hi"},
        ],
        "tags": [],
    })

    diagnostic = _diagnostic_by_code(result, CHATML_MESSAGE_NOT_DICT)

    assert result.is_valid is False
    assert diagnostic.severity == AnalysisSeverity.ERROR
    assert diagnostic.message == "Message 1 is not a dict"
    assert diagnostic.path == ("messages", 1)


def test_chatml_analyzer_reports_wrong_role_and_empty_content_with_indexed_paths():
    result = ChatMLAnalyzer().analyze({
        "messages": [
            {"role": "system", "content": "System"},
            {"role": "assistant", "content": ""},
            {"role": "assistant", "content": "Hi"},
        ],
        "tags": [],
    })

    wrong_role = _diagnostic_by_code(result, CHATML_WRONG_ROLE)
    empty_content = _diagnostic_by_code(result, CHATML_EMPTY_CONTENT)

    assert result.is_valid is False
    assert wrong_role.severity == AnalysisSeverity.ERROR
    assert wrong_role.message == "Message 1: expected role 'user', got 'assistant'"
    assert wrong_role.path == ("messages", 1, "role")
    assert wrong_role.original_value == "assistant"
    assert wrong_role.normalized_value == "user"
    assert empty_content.severity == AnalysisSeverity.ERROR
    assert empty_content.message == "Message 1 (user) has empty content"
    assert empty_content.path == ("messages", 1, "content")


def test_chatml_analyzer_runs_base_checks_alongside_chatml_checks():
    result = ChatMLAnalyzer().analyze({"tags": "bad"})

    codes = {diagnostic.code for diagnostic in result.diagnostics}

    assert result.is_valid is False
    assert codes == {BASE_TAGS_NOT_LIST, CHATML_MISSING_MESSAGES}
    assert _diagnostic_by_code(result, BASE_TAGS_NOT_LIST).severity == (
        AnalysisSeverity.ERROR
    )
    assert _diagnostic_by_code(result, BASE_TAGS_NOT_LIST).message == (
        "'tags' must be a list"
    )
    assert _diagnostic_by_code(result, CHATML_MISSING_MESSAGES).severity == (
        AnalysisSeverity.ERROR
    )


@pytest.mark.parametrize(
    "entry",
    [
        _entry(tags=["greeting"]),
        {"tags": []},
        {"messages": "not a list", "tags": []},
        {
            "messages": [
                {"role": "system", "content": "System"},
                {"role": "user", "content": "Hi"},
            ],
            "tags": [],
        },
        {
            "messages": [
                {"role": "system", "content": "System"},
                {"role": "user", "content": "Hi"},
                {"role": "assistant", "content": "Hello"},
                {"role": "user", "content": "Again"},
            ],
            "tags": [],
        },
        {
            "messages": [
                "not dict",
                {"role": "user", "content": "Hi"},
                {"role": "assistant", "content": "Hello"},
            ],
            "tags": [],
        },
        {
            "messages": [
                {"role": "user", "content": "System-ish"},
                {"role": "user", "content": "Hi"},
                {"role": "assistant", "content": "Hello"},
            ],
            "tags": [],
        },
        {
            "messages": [
                {"role": "system", "content": "   "},
                {"role": "user", "content": "Hi"},
                {"role": "assistant", "content": "Hello"},
            ],
            "tags": [],
        },
        {
            "messages": [
                {"role": "system", "content": "System"},
                {"role": "assistant", "content": "Hello"},
                {"role": "user", "content": "Hi"},
            ],
            "tags": [],
        },
        {
            "messages": [
                {"role": "system", "content": "System"},
                {"role": "user", "content": ""},
                {"role": "assistant", "content": "   "},
            ],
            "tags": [],
        },
        {
            "messages": [
                {"role": "system", "content": "System"},
                {"role": "user", "content": "Hi"},
                {"role": "assistant", "content": "Hello"},
            ],
        },
        _entry(tags="greeting"),
        _entry(tags=["greeting", 7]),
        _entry(tags=[""]),
    ],
)
def test_chatml_analyzer_validity_matches_validate_entry(entry):
    result = ChatMLAnalyzer().analyze(entry)

    assert result.is_valid == (validate_entry(entry) == [])


def test_chatml_analyzer_error_messages_match_validate_entry_for_representative_entries():
    entries = [
        {"tags": []},
        {"messages": "not a list", "tags": []},
        {
            "messages": [
                {"role": "user", "content": "System-ish"},
                {"role": "assistant", "content": ""},
                {"role": "user", "content": "Hi"},
            ],
            "tags": [],
        },
        _entry(tags="greeting"),
        _entry(tags=["greeting", 7]),
    ]

    for entry in entries:
        result_messages = [
            diagnostic.message
            for diagnostic in ChatMLAnalyzer().analyze(entry).diagnostics
            if diagnostic.severity == AnalysisSeverity.ERROR
        ]
        assert result_messages == validate_entry(entry)


def test_sharegpt_analyzer_accepts_valid_entry_without_diagnostics():
    result = ShareGPTAnalyzer().analyze(_sharegpt_entry())

    assert result.format == "sharegpt"
    assert result.is_valid is True
    assert result.diagnostics == ()


def test_sharegpt_analyzer_reports_missing_conversations_key():
    result = ShareGPTAnalyzer().analyze({"tags": []})

    diagnostic = _diagnostic_by_code(result, SHAREGPT_MISSING_CONVERSATIONS)

    assert result.is_valid is False
    assert diagnostic.severity == AnalysisSeverity.ERROR
    assert diagnostic.message == "Missing 'conversations' key"
    assert diagnostic.path == ("conversations",)


def test_sharegpt_analyzer_reports_conversations_not_list():
    result = ShareGPTAnalyzer().analyze({"conversations": "bad", "tags": []})

    diagnostic = _diagnostic_by_code(result, SHAREGPT_CONVERSATIONS_NOT_LIST)

    assert result.is_valid is False
    assert diagnostic.severity == AnalysisSeverity.ERROR
    assert diagnostic.message == "'conversations' must be a list"
    assert diagnostic.path == ("conversations",)
    assert diagnostic.original_value == "bad"


def test_sharegpt_analyzer_reports_empty_conversations():
    result = ShareGPTAnalyzer().analyze({"conversations": [], "tags": []})

    diagnostic = _diagnostic_by_code(result, SHAREGPT_EMPTY_CONVERSATIONS)

    assert result.is_valid is False
    assert diagnostic.severity == AnalysisSeverity.ERROR
    assert diagnostic.message == "'conversations' must contain at least one turn"
    assert diagnostic.path == ("conversations",)
    assert diagnostic.original_value == 0


def test_sharegpt_analyzer_reports_turn_not_dict_with_indexed_path():
    result = ShareGPTAnalyzer().analyze(_sharegpt_entry(conversations=[
        {"from": "system", "value": "System"},
        "bad",
    ]))

    diagnostic = _diagnostic_by_code(result, SHAREGPT_TURN_NOT_DICT)

    assert result.is_valid is False
    assert diagnostic.severity == AnalysisSeverity.ERROR
    assert diagnostic.message == "Conversation turn 1 is not a dict"
    assert diagnostic.path == ("conversations", 1)
    assert diagnostic.original_value == "bad"


def test_sharegpt_analyzer_reports_missing_role_field():
    result = ShareGPTAnalyzer().analyze(_sharegpt_entry(conversations=[
        {"from": "system", "value": "System"},
        {"value": "Hi"},
    ]))

    diagnostic = _diagnostic_by_code(result, SHAREGPT_MISSING_ROLE_FIELD)

    assert result.is_valid is False
    assert diagnostic.severity == AnalysisSeverity.ERROR
    assert diagnostic.message == "Conversation turn 1 is missing a role field"
    assert diagnostic.path == ("conversations", 1)


def test_sharegpt_analyzer_reports_missing_content_field():
    result = ShareGPTAnalyzer().analyze(_sharegpt_entry(conversations=[
        {"from": "system", "value": "System"},
        {"from": "human"},
    ]))

    diagnostic = _diagnostic_by_code(result, SHAREGPT_MISSING_CONTENT_FIELD)

    assert result.is_valid is False
    assert diagnostic.severity == AnalysisSeverity.ERROR
    assert diagnostic.message == "Conversation turn 1 is missing a content field"
    assert diagnostic.path == ("conversations", 1)


def test_sharegpt_analyzer_reports_unknown_role_as_warning():
    result = ShareGPTAnalyzer().analyze(_sharegpt_entry(conversations=[
        {"from": "system", "value": "System"},
        {"from": "narrator", "value": "Hi"},
    ]))

    diagnostic = _diagnostic_by_code(result, SHAREGPT_UNKNOWN_ROLE)

    assert result.is_valid is True
    assert diagnostic.severity == AnalysisSeverity.WARNING
    assert diagnostic.message == "Conversation turn 1 has unknown role: narrator"
    assert diagnostic.path == ("conversations", 1, "from")
    assert diagnostic.original_value == "narrator"


def test_sharegpt_analyzer_reports_empty_content_as_warning():
    result = ShareGPTAnalyzer().analyze(_sharegpt_entry(conversations=[
        {"from": "system", "value": "System"},
        {"from": "human", "value": "   "},
    ]))

    diagnostic = _diagnostic_by_code(result, SHAREGPT_EMPTY_CONTENT)

    assert result.is_valid is True
    assert diagnostic.severity == AnalysisSeverity.WARNING
    assert diagnostic.message == "Conversation turn 1 has empty content"
    assert diagnostic.path == ("conversations", 1, "value")
    assert diagnostic.original_value == "   "


def test_sharegpt_analyzer_reports_multiple_system_turns_as_info():
    result = ShareGPTAnalyzer().analyze(_sharegpt_entry(conversations=[
        {"from": "system", "value": "System"},
        {"from": "system", "value": "More system"},
        {"from": "human", "value": "Hi"},
    ]))

    diagnostic = _diagnostic_by_code(result, SHAREGPT_MULTIPLE_SYSTEM_TURNS)

    assert result.is_valid is True
    assert diagnostic.severity == AnalysisSeverity.INFO
    assert diagnostic.message == "ShareGPT entry contains multiple system turns."
    assert diagnostic.path == ("conversations",)
    assert diagnostic.original_value == 2


def test_sharegpt_analyzer_reports_no_system_turn_as_info():
    result = ShareGPTAnalyzer().analyze(_sharegpt_entry(conversations=[
        {"from": "human", "value": "Hi"},
        {"from": "gpt", "value": "Hello"},
    ]))

    diagnostic = _diagnostic_by_code(result, SHAREGPT_NO_SYSTEM_TURN)

    assert result.is_valid is True
    assert diagnostic.severity == AnalysisSeverity.INFO
    assert diagnostic.path == ("conversations",)
    assert diagnostic.fixable is True
    assert diagnostic.repair_kind == RepairKind.AUTOMATIC


def test_sharegpt_analyzer_collects_multiple_simultaneous_issues():
    result = ShareGPTAnalyzer().analyze({
        "conversations": [
            {"from": "system", "value": "System"},
            "bad",
            {"from": "narrator"},
            {"value": ""},
        ],
        "tags": ["slow_burn", 7],
    })

    codes = {diagnostic.code for diagnostic in result.diagnostics}

    assert result.is_valid is False
    assert {
        BASE_INVALID_TAG_VALUE,
        SHAREGPT_TURN_NOT_DICT,
        SHAREGPT_UNKNOWN_ROLE,
        SHAREGPT_MISSING_CONTENT_FIELD,
        SHAREGPT_MISSING_ROLE_FIELD,
        SHAREGPT_EMPTY_CONTENT,
    }.issubset(codes)
    assert _diagnostic_by_code(result, BASE_INVALID_TAG_VALUE).severity == (
        AnalysisSeverity.WARNING
    )


def test_sharegpt_analyzer_runs_base_checks_alongside_sharegpt_checks():
    result = ShareGPTAnalyzer().analyze({"tags": "bad"})

    codes = {diagnostic.code for diagnostic in result.diagnostics}

    assert result.is_valid is False
    assert codes == {BASE_TAGS_NOT_LIST, SHAREGPT_MISSING_CONVERSATIONS}
    assert _diagnostic_by_code(result, BASE_TAGS_NOT_LIST).severity == (
        AnalysisSeverity.WARNING
    )
    assert _diagnostic_by_code(result, SHAREGPT_MISSING_CONVERSATIONS).severity == (
        AnalysisSeverity.ERROR
    )


@pytest.mark.parametrize("role_key", ["from", "role", "speaker"])
def test_sharegpt_analyzer_detects_role_field_variants(role_key):
    result = ShareGPTAnalyzer().analyze(_sharegpt_entry(conversations=[
        {"from": "system", "value": "System"},
        {role_key: "human", "value": "Hi"},
    ]))

    assert SHAREGPT_MISSING_ROLE_FIELD not in {
        diagnostic.code for diagnostic in result.diagnostics
    }
    assert SHAREGPT_UNKNOWN_ROLE not in {
        diagnostic.code for diagnostic in result.diagnostics
    }


@pytest.mark.parametrize("content_key", ["value", "content", "text"])
def test_sharegpt_analyzer_detects_content_field_variants(content_key):
    result = ShareGPTAnalyzer().analyze(_sharegpt_entry(conversations=[
        {"from": "system", "value": "System"},
        {"from": "human", content_key: "Hi"},
    ]))

    assert SHAREGPT_MISSING_CONTENT_FIELD not in {
        diagnostic.code for diagnostic in result.diagnostics
    }
    assert SHAREGPT_EMPTY_CONTENT not in {
        diagnostic.code for diagnostic in result.diagnostics
    }
