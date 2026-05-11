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
    CHATML_CONTENT_WHITESPACE,
    CHATML_ROLE_CANONICALIZATION,
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
    SHAREGPT_ROLE_VARIANT,
    SHAREGPT_TURN_NOT_DICT,
    SHAREGPT_UNKNOWN_ROLE,
    AnalysisSeverity,
    BaseEntryAnalyzer,
    ChatMLAnalyzer,
    EntryAnalysisResult,
    EntryDiagnostic,
    RepairKind,
    RepairResult,
    ShareGPTAnalyzer,
)
from core.loreforge_meta import LOREFORGE_META_KEY


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
        LOREFORGE_META_KEY: {"native": True},
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


def test_repair_result_dataclass_is_frozen():
    repair_result = RepairResult(entry={"tags": []}, repairs_applied=(), changed=False)

    with pytest.raises(dataclasses.FrozenInstanceError):
        repair_result.changed = True


def test_severity_and_repair_enums_have_stable_values():
    assert AnalysisSeverity.INFO.value == "info"
    assert AnalysisSeverity.WARNING.value == "warning"
    assert AnalysisSeverity.ERROR.value == "error"
    assert RepairKind.NONE.value == "none"
    assert RepairKind.AUTOMATIC.value == "automatic"
    assert RepairKind.SUGGESTED.value == "suggested"
    assert RepairKind.MANUAL.value == "manual"


def test_base_analyzer_repairs_missing_tags_without_mutating_original():
    analyzer = BaseEntryAnalyzer()
    entry = {"messages": []}

    result = analyzer.analyze(entry)
    repair = analyzer.apply_repairs(entry, analyzer.plan_repairs(result))

    assert repair.entry == {"messages": [], "tags": []}
    assert repair.changed is True
    assert [diagnostic.code for diagnostic in repair.repairs_applied] == [
        BASE_MISSING_TAGS
    ]
    assert entry == {"messages": []}


def test_base_analyzer_repairs_tags_not_list_without_mutating_original():
    analyzer = BaseEntryAnalyzer()
    entry = {"messages": [], "tags": "slow_burn"}

    result = analyzer.analyze(entry)
    repair = analyzer.apply_repairs(entry, analyzer.plan_repairs(result))

    assert repair.entry["tags"] == []
    assert repair.changed is True
    assert [diagnostic.code for diagnostic in repair.repairs_applied] == [
        BASE_TAGS_NOT_LIST
    ]
    assert entry["tags"] == "slow_burn"


def test_base_analyzer_repairs_invalid_and_empty_tag_values():
    analyzer = BaseEntryAnalyzer()
    entry = {"messages": [], "tags": ["slow_burn", 7, "   ", "comfort"]}

    result = analyzer.analyze(entry)
    repair = analyzer.apply_repairs(entry, analyzer.plan_repairs(result))

    assert repair.entry["tags"] == ["slow_burn", "comfort"]
    assert repair.changed is True
    assert [diagnostic.code for diagnostic in repair.repairs_applied] == [
        BASE_EMPTY_TAG,
        BASE_INVALID_TAG_VALUE,
    ]
    assert entry["tags"] == ["slow_burn", 7, "   ", "comfort"]


def test_base_repair_round_trip_removes_fixed_tag_diagnostics():
    analyzer = BaseEntryAnalyzer()
    entry = {"messages": [], "tags": ["slow_burn", 7, ""]}

    result = analyzer.analyze(entry)
    repair = analyzer.apply_repairs(entry, analyzer.plan_repairs(result))
    repaired_result = analyzer.analyze(repair.entry)

    assert {diagnostic.code for diagnostic in repaired_result.diagnostics} == set()


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
    assert content.fixable is True
    assert content.repair_kind == RepairKind.SUGGESTED


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


def test_chatml_structural_errors_are_not_automatic_repairs():
    analyzer = ChatMLAnalyzer()
    result = analyzer.analyze({"messages": "bad", "tags": []})

    diagnostic = _diagnostic_by_code(result, CHATML_MESSAGES_NOT_LIST)

    assert diagnostic.fixable is False
    assert diagnostic.repair_kind == RepairKind.MANUAL
    assert analyzer.plan_repairs(result) == []


def test_chatml_repair_plan_for_bad_tags_only_returns_tag_repairs():
    analyzer = ChatMLAnalyzer()
    entry = _entry(tags=["slow_burn", 7, ""])

    result = analyzer.analyze(entry)
    plan = analyzer.plan_repairs(result)
    repair = analyzer.apply_repairs(entry, plan)

    assert [diagnostic.code for diagnostic in plan] == [
        BASE_INVALID_TAG_VALUE,
        BASE_EMPTY_TAG,
    ]
    assert repair.entry["tags"] == ["slow_burn"]
    assert entry["tags"] == ["slow_burn", 7, ""]


def test_chatml_suggested_repairs_are_not_in_automatic_repair_plan():
    analyzer = ChatMLAnalyzer()
    result = analyzer.analyze(_entry(messages=[
        {"role": "system", "content": ""},
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "Hello"},
    ]))

    diagnostic = _diagnostic_by_code(result, CHATML_EMPTY_SYSTEM_CONTENT)

    assert diagnostic.fixable is True
    assert diagnostic.repair_kind == RepairKind.SUGGESTED
    assert analyzer.plan_repairs(result) == []


def test_chatml_analyzer_reports_known_role_synonyms_as_automatic_repairs():
    result = ChatMLAnalyzer().analyze(_entry(messages=[
        {"role": "System", "content": "System"},
        {"role": "Human", "content": "Hi"},
        {"role": "assistant", "content": "Hello"},
    ]))

    diagnostics = [
        diagnostic
        for diagnostic in result.diagnostics
        if diagnostic.code == CHATML_ROLE_CANONICALIZATION
    ]

    assert result.is_valid is True
    assert [(diagnostic.path, diagnostic.original_value, diagnostic.normalized_value)
            for diagnostic in diagnostics] == [
        (("messages", 0, "role"), "System", "system"),
        (("messages", 1, "role"), "Human", "user"),
    ]
    assert all(diagnostic.severity == AnalysisSeverity.WARNING for diagnostic in diagnostics)
    assert all(diagnostic.fixable for diagnostic in diagnostics)
    assert all(
        diagnostic.repair_kind == RepairKind.AUTOMATIC
        for diagnostic in diagnostics
    )


def test_chatml_analyzer_reports_content_whitespace_as_automatic_repair():
    result = ChatMLAnalyzer().analyze(_entry(messages=[
        {"role": "system", "content": "System"},
        {"role": "user", "content": "  Hi  "},
        {"role": "assistant", "content": "Hello"},
    ]))

    diagnostic = _diagnostic_by_code(result, CHATML_CONTENT_WHITESPACE)

    assert result.is_valid is True
    assert diagnostic.severity == AnalysisSeverity.WARNING
    assert diagnostic.path == ("messages", 1, "content")
    assert diagnostic.fixable is True
    assert diagnostic.repair_kind == RepairKind.AUTOMATIC
    assert diagnostic.original_value == "  Hi  "
    assert diagnostic.normalized_value == "Hi"


def test_chatml_analyzer_keeps_custom_character_roles_manual():
    result = ChatMLAnalyzer().analyze(_entry(messages=[
        {"role": "system", "content": "System"},
        {"role": "Scott", "content": "Hi"},
        {"role": "Emma", "content": "Hello"},
    ]))

    wrong_roles = [
        diagnostic
        for diagnostic in result.diagnostics
        if diagnostic.code == CHATML_WRONG_ROLE
    ]

    assert result.is_valid is False
    assert len(wrong_roles) == 2
    assert all(diagnostic.repair_kind == RepairKind.MANUAL for diagnostic in wrong_roles)
    assert CHATML_ROLE_CANONICALIZATION not in {
        diagnostic.code for diagnostic in result.diagnostics
    }


def test_chatml_analyzer_reports_custom_role_whitespace_without_mapping_it():
    result = ChatMLAnalyzer().analyze(_entry(messages=[
        {"role": "system", "content": "System"},
        {"role": " Scott ", "content": "Hi"},
        {"role": "assistant", "content": "Hello"},
    ]))

    whitespace = _diagnostic_by_code(result, CHATML_ROLE_CANONICALIZATION)
    wrong_role = _diagnostic_by_code(result, CHATML_WRONG_ROLE)

    assert result.is_valid is False
    assert whitespace.repair_kind == RepairKind.AUTOMATIC
    assert whitespace.original_value == " Scott "
    assert whitespace.normalized_value == "Scott"
    assert wrong_role.repair_kind == RepairKind.MANUAL
    assert wrong_role.original_value == " Scott "


def test_chatml_repairs_role_and_content_normalization_without_mutating_original():
    analyzer = ChatMLAnalyzer()
    entry = _entry(messages=[
        {"role": "SYSTEM", "content": " System "},
        {"role": "Human", "content": "  Hi"},
        {"role": "GPT", "content": "Hello  "},
    ])

    result = analyzer.analyze(entry)
    repair = analyzer.apply_repairs(entry, analyzer.plan_repairs(result))

    assert repair.changed is True
    assert repair.entry["messages"] == [
        {"role": "system", "content": "System"},
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "Hello"},
    ]
    assert entry["messages"][0] == {"role": "SYSTEM", "content": " System "}
    assert {diagnostic.code for diagnostic in repair.repairs_applied} == {
        CHATML_ROLE_CANONICALIZATION,
        CHATML_CONTENT_WHITESPACE,
    }
    assert ChatMLAnalyzer().analyze(repair.entry).diagnostics == ()


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
    assert diagnostic.repair_kind == RepairKind.SUGGESTED


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


def test_sharegpt_analyzer_reports_role_variant_as_automatic_repair():
    result = ShareGPTAnalyzer().analyze(_sharegpt_entry(conversations=[
        {"from": "system", "value": "System"},
        {"from": "user", "value": "Hi"},
        {"from": "assistant", "value": "Hello"},
    ]))

    diagnostics = [
        diagnostic
        for diagnostic in result.diagnostics
        if diagnostic.code == SHAREGPT_ROLE_VARIANT
    ]

    assert result.is_valid is True
    assert len(diagnostics) == 2
    assert diagnostics[0].path == ("conversations", 1, "from")
    assert diagnostics[0].original_value == "user"
    assert diagnostics[0].normalized_value == "human"
    assert diagnostics[0].fixable is True
    assert diagnostics[0].repair_kind == RepairKind.AUTOMATIC
    assert diagnostics[1].path == ("conversations", 2, "from")
    assert diagnostics[1].original_value == "assistant"
    assert diagnostics[1].normalized_value == "gpt"


def test_sharegpt_applies_automatic_role_variant_repairs_without_mutating_original():
    analyzer = ShareGPTAnalyzer()
    entry = _sharegpt_entry(conversations=[
        {"from": "system", "value": "System"},
        {"role": "user", "value": "Hi"},
        {"speaker": "assistant", "value": "Hello"},
    ])

    result = analyzer.analyze(entry)
    repair = analyzer.apply_repairs(entry, analyzer.plan_repairs(result))

    assert repair.changed is True
    assert [diagnostic.code for diagnostic in repair.repairs_applied] == [
        SHAREGPT_ROLE_VARIANT,
        SHAREGPT_ROLE_VARIANT,
    ]
    assert repair.entry["conversations"][1]["role"] == "human"
    assert repair.entry["conversations"][2]["speaker"] == "gpt"
    assert entry["conversations"][1]["role"] == "user"
    assert entry["conversations"][2]["speaker"] == "assistant"


def test_sharegpt_suggested_repairs_are_not_in_automatic_repair_plan():
    analyzer = ShareGPTAnalyzer()
    result = analyzer.analyze(_sharegpt_entry(conversations=[
        {"from": "human", "value": ""},
        {"from": "gpt", "value": "Hello"},
    ]))

    codes = {diagnostic.code for diagnostic in result.diagnostics}

    assert SHAREGPT_EMPTY_CONTENT in codes
    assert SHAREGPT_NO_SYSTEM_TURN in codes
    assert analyzer.plan_repairs(result) == []


def test_sharegpt_repair_round_trip_removes_fixed_role_variant_diagnostics():
    analyzer = ShareGPTAnalyzer()
    entry = _sharegpt_entry(conversations=[
        {"from": "system", "value": "System"},
        {"from": "user", "value": "Hi"},
        {"from": "assistant", "value": "Hello"},
    ])

    result = analyzer.analyze(entry)
    repair = analyzer.apply_repairs(entry, analyzer.plan_repairs(result))
    repaired_result = analyzer.analyze(repair.entry)

    assert SHAREGPT_ROLE_VARIANT not in {
        diagnostic.code for diagnostic in repaired_result.diagnostics
    }
