from core.dataset import analyze_entry, clear_validate_entry_cache
from core.entry_analysis import (
    BASE_INVALID_TAG_VALUE,
    BASE_MISSING_TAGS,
    CHATML_CONTENT_WHITESPACE,
    CHATML_ROLE_CANONICALIZATION,
    RepairKind,
)
from core.validation_actions import (
    apply_all_auto_repairs,
    apply_group_repairs,
    collect_auto_fixable_groups,
)


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


def _auto_diagnostic_codes(entry):
    result = analyze_entry(entry)
    return {
        diagnostic.code
        for diagnostic in result.diagnostics
        if diagnostic.fixable and diagnostic.repair_kind == RepairKind.AUTOMATIC
    }


def test_collect_auto_fixable_groups_returns_group_counts_and_samples():
    entries = [
        {"messages": _entry()["messages"]},
        _entry(tags=["slow_burn", 7]),
        _entry(messages=[
            {"role": "SYSTEM", "content": " System "},
            {"role": "Human", "content": "Hi"},
            {"role": "GPT", "content": "Hello"},
        ]),
        _entry(),
    ]

    groups = collect_auto_fixable_groups(entries)
    groups_by_code = {group.code: group for group in groups}

    assert [group.code for group in groups[:2]] == [
        BASE_INVALID_TAG_VALUE,
        BASE_MISSING_TAGS,
    ]
    assert groups[2].code == CHATML_ROLE_CANONICALIZATION
    assert groups_by_code[CHATML_ROLE_CANONICALIZATION].count == 3
    assert groups_by_code[CHATML_ROLE_CANONICALIZATION].entry_indices == (2,)
    assert groups_by_code[CHATML_CONTENT_WHITESPACE].count == 1
    assert groups_by_code[CHATML_CONTENT_WHITESPACE].sample_entries[0].path == (
        "messages",
        0,
        "content",
    )
    assert groups_by_code[BASE_MISSING_TAGS].title == "Missing Tags"
    assert groups_by_code[BASE_INVALID_TAG_VALUE].sample_entries[0].entry_index == 1


def test_collect_auto_fixable_groups_returns_empty_for_clean_entries():
    assert collect_auto_fixable_groups([_entry(), _entry(tags=["slow_burn"])]) == []


def test_apply_group_repairs_applies_only_selected_diagnostic_code():
    entry = _entry(messages=[
        {"role": "SYSTEM", "content": " System "},
        {"role": "Human", "content": " Hi "},
        {"role": "GPT", "content": " Hello "},
    ])

    repaired_entries, changed_indices = apply_group_repairs(
        [entry],
        CHATML_ROLE_CANONICALIZATION,
    )

    assert changed_indices == [0]
    assert repaired_entries[0]["messages"] == [
        {"role": "system", "content": " System "},
        {"role": "user", "content": " Hi "},
        {"role": "assistant", "content": " Hello "},
    ]
    assert entry["messages"][0]["role"] == "SYSTEM"
    assert CHATML_CONTENT_WHITESPACE in _auto_diagnostic_codes(repaired_entries[0])
    assert CHATML_ROLE_CANONICALIZATION not in _auto_diagnostic_codes(repaired_entries[0])


def test_apply_group_repairs_passes_untouched_entries_through():
    clean = _entry()
    dirty = {"messages": _entry()["messages"]}
    repaired_entries, changed_indices = apply_group_repairs(
        [clean, dirty],
        BASE_MISSING_TAGS,
    )

    assert changed_indices == [1]
    assert repaired_entries[0] is clean
    assert repaired_entries[1] is not dirty
    assert repaired_entries[1]["tags"] == []


def test_apply_all_auto_repairs_removes_all_auto_fixable_diagnostics():
    entries = [
        {"messages": _entry()["messages"]},
        _entry(tags=["slow_burn", 7, ""]),
        _entry(messages=[
            {"role": "SYSTEM", "content": " System "},
            {"role": "Human", "content": " Hi "},
            {"role": "GPT", "content": " Hello "},
        ]),
    ]

    repaired_entries, changed_indices = apply_all_auto_repairs(entries)

    assert changed_indices == [0, 1, 2]
    assert repaired_entries[0]["tags"] == []
    assert repaired_entries[1]["tags"] == ["slow_burn"]
    assert repaired_entries[2]["messages"] == [
        {"role": "system", "content": "System"},
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "Hello"},
    ]
    assert collect_auto_fixable_groups(repaired_entries) == []


def test_cache_clearing_after_repair_allows_fresh_analysis():
    entry = {"messages": _entry()["messages"]}
    assert BASE_MISSING_TAGS in _auto_diagnostic_codes(entry)

    repaired_entries, changed_indices = apply_all_auto_repairs([entry])
    assert changed_indices == [0]
    clear_validate_entry_cache()

    assert _auto_diagnostic_codes(repaired_entries[0]) == set()
