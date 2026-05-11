import dataclasses

import pytest

from core.entry_analysis import (
    BASE_EMPTY_TAG,
    BASE_INVALID_TAG_VALUE,
    BASE_MISSING_TAGS,
    BASE_NOT_DICT,
    BASE_TAGS_NOT_LIST,
    BASE_UNKNOWN_TOP_LEVEL_KEY,
    AnalysisSeverity,
    BaseEntryAnalyzer,
    EntryAnalysisResult,
    EntryDiagnostic,
    RepairKind,
)


def _diagnostic_by_code(result: EntryAnalysisResult, code: str) -> EntryDiagnostic:
    matches = [diagnostic for diagnostic in result.diagnostics if diagnostic.code == code]
    assert len(matches) == 1
    return matches[0]


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
