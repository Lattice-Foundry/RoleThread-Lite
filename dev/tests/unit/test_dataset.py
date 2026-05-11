import json

import pytest

import core.dataset as dataset
from core.dataset import (
    add_tags_to_entry,
    analyze_entry,
    append_registry_id,
    append_to_dataset,
    build_dataset_stats,
    build_entry_registry,
    clear_validate_entry_cache,
    count_exchanges,
    entry_is_untagged,
    entry_matches_tags,
    entry_text_length,
    filter_entries_by_tags,
    filter_entry_pairs_by_tags,
    get_available_filter_tags,
    get_entry_messages,
    get_entry_pairs,
    get_entry_tags,
    get_index_for_entry_id,
    get_role_messages,
    get_used_tags,
    has_untagged_entries,
    load_dataset,
    load_dataset_with_summary,
    make_entry,
    make_temp_entry_id,
    merge_datasets,
    normalize_dataset_tags,
    normalize_entry_tags,
    rebuild_id_to_index,
    registry_is_valid,
    remove_registry_id,
    remove_tags_from_entry,
    replace_entry_tags,
    save_dataset,
    set_entry_tags,
    validate_entry,
)
from core.entry_analysis import AnalysisSeverity, EntryAnalysisResult, EntryDiagnostic
from core.format_conversion import (
    FORMAT_CHATML,
    FORMAT_SHAREGPT,
    FORMAT_UNKNOWN,
    SHAREGPT_INTERNAL_SYSTEM_PROMPT,
)


def _entry(*, tags=None, messages=None):
    return {
        "messages": messages
        or [
            {"role": "system", "content": "System"},
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello"},
        ],
        "tags": tags or [],
    }


def _multi_turn_entry(*, tags=None):
    return _entry(
        tags=tags,
        messages=[
            {"role": "system", "content": "System"},
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello"},
            {"role": "user", "content": "How are you?"},
            {"role": "assistant", "content": "Doing well."},
        ],
    )


def _error_text(errors):
    return "\n".join(errors)


def test_validate_entry_accepts_valid_single_turn_entry():
    assert validate_entry(_entry(tags=["greeting"])) == []


def test_validate_entry_reports_missing_messages_key():
    errors = validate_entry({"tags": []})

    assert "messages" in _error_text(errors)


def test_validate_entry_reports_messages_not_list():
    errors = validate_entry({"messages": "not a list", "tags": []})

    assert "must be a list" in _error_text(errors)


def test_validate_entry_reports_too_few_messages():
    errors = validate_entry(
        {
            "messages": [
                {"role": "system", "content": "System"},
                {"role": "user", "content": "Hi"},
            ],
            "tags": [],
        }
    )

    assert "at least 3" in _error_text(errors)


def test_validate_entry_reports_missing_or_incorrect_system_role():
    errors = validate_entry(
        {
            "messages": [
                {"role": "user", "content": "System-ish"},
                {"role": "user", "content": "Hi"},
                {"role": "assistant", "content": "Hello"},
            ],
            "tags": [],
        }
    )

    assert "expected role 'system'" in _error_text(errors)


def test_validate_entry_reports_empty_system_content():
    errors = validate_entry(
        {
            "messages": [
                {"role": "system", "content": "   "},
                {"role": "user", "content": "Hi"},
                {"role": "assistant", "content": "Hello"},
            ],
            "tags": [],
        }
    )

    assert "system" in _error_text(errors)
    assert "empty content" in _error_text(errors)


def test_validate_entry_reports_broken_user_assistant_alternation():
    errors = validate_entry(
        {
            "messages": [
                {"role": "system", "content": "System"},
                {"role": "assistant", "content": "Hello"},
                {"role": "user", "content": "Hi"},
            ],
            "tags": [],
        }
    )

    assert "expected role 'user'" in _error_text(errors)
    assert "expected role 'assistant'" in _error_text(errors)


def test_validate_entry_reports_empty_user_or_assistant_content():
    errors = validate_entry(
        {
            "messages": [
                {"role": "system", "content": "System"},
                {"role": "user", "content": ""},
                {"role": "assistant", "content": "   "},
            ],
            "tags": [],
        }
    )

    assert "empty content" in _error_text(errors)


def test_validate_entry_reports_missing_tags():
    errors = validate_entry(
        {
            "messages": [
                {"role": "system", "content": "System"},
                {"role": "user", "content": "Hi"},
                {"role": "assistant", "content": "Hello"},
            ],
        }
    )

    assert "Missing 'tags'" in _error_text(errors)


def test_validate_entry_reports_tags_not_list():
    errors = validate_entry({**_entry(), "tags": "greeting"})

    assert "'tags' must be a list" in _error_text(errors)


def test_validate_entry_reports_non_string_tag():
    errors = validate_entry(_entry(tags=["greeting", 7]))

    assert "Each tag must be a string" in _error_text(errors)


def test_validate_entry_accepts_valid_multi_turn_entry():
    assert validate_entry(_multi_turn_entry(tags=["greeting"])) == []


def test_validate_entry_memoizes_by_content(monkeypatch):
    clear_validate_entry_cache()
    calls = []

    def fake_analyze(entry):
        calls.append(entry)
        return EntryAnalysisResult(
            format="chatml",
            entry_index=None,
            is_valid=False,
            diagnostics=(
                EntryDiagnostic(
                    code="test.cached",
                    severity=AnalysisSeverity.ERROR,
                    message="cached error",
                ),
            ),
        )

    monkeypatch.setattr(dataset, "_analyze_entry_uncached", fake_analyze)

    entry = _entry(tags=["greeting"])

    assert validate_entry(entry) == ["cached error"]
    assert validate_entry({**entry, "tags": ["greeting"]}) == ["cached error"]
    assert len(calls) == 1

    clear_validate_entry_cache()
    assert validate_entry(entry) == ["cached error"]
    assert len(calls) == 2
    clear_validate_entry_cache()


def test_validate_entry_returns_fresh_error_list_from_cache(monkeypatch):
    clear_validate_entry_cache()

    result = EntryAnalysisResult(
        format="chatml",
        entry_index=None,
        is_valid=False,
        diagnostics=(
            EntryDiagnostic(
                code="test.cached",
                severity=AnalysisSeverity.ERROR,
                message="cached error",
            ),
        ),
    )
    monkeypatch.setattr(dataset, "_analyze_entry_uncached", lambda entry: result)

    entry = _entry(tags=["greeting"])
    errors = validate_entry(entry)
    errors.append("mutated")

    assert validate_entry(entry) == ["cached error"]
    clear_validate_entry_cache()


def test_analyze_entry_returns_cached_typed_result(monkeypatch):
    clear_validate_entry_cache()
    calls = []

    def fake_analyze(entry):
        calls.append(entry)
        return EntryAnalysisResult(
            format="chatml",
            entry_index=None,
            is_valid=False,
            diagnostics=(
                EntryDiagnostic(
                    code="test.cached",
                    severity=AnalysisSeverity.ERROR,
                    message="typed cached error",
                ),
            ),
        )

    monkeypatch.setattr(dataset, "_analyze_entry_uncached", fake_analyze)

    entry = _entry(tags=["greeting"])

    first = analyze_entry(entry)
    second = analyze_entry({**entry, "tags": ["greeting"]})

    assert first is second
    assert first.diagnostics[0].message == "typed cached error"
    assert len(calls) == 1
    clear_validate_entry_cache()


def test_make_entry_creates_system_and_user_assistant_messages():
    entry = make_entry(
        [
            {"role": "user", "content": " Hi "},
            {"role": "assistant", "content": " Hello "},
        ],
        "System",
        ["greeting"],
    )

    assert entry == {
        "messages": [
            {"role": "system", "content": "System"},
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello"},
        ],
        "tags": ["greeting"],
    }


def test_make_entry_strips_empty_turns():
    entry = make_entry(
        [
            {"role": "user", "content": ""},
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "   "},
            {"role": "assistant", "content": "Hello"},
        ],
        "System",
    )

    assert entry["messages"] == [
        {"role": "system", "content": "System"},
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "Hello"},
    ]


def test_make_entry_preserves_provided_tags():
    tags = ["greeting", "reviewed"]
    entry = make_entry(
        [
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello"},
        ],
        "System",
        tags,
    )

    assert entry["tags"] is tags


def test_count_exchanges_handles_single_and_multi_turn_entries():
    assert count_exchanges(_entry()) == 1
    assert count_exchanges(_multi_turn_entry()) == 2


@pytest.mark.parametrize(
    "entry",
    [
        {},
        {"messages": "bad"},
        {"messages": [{"role": "system", "content": "Only system"}]},
        None,
    ],
)
def test_count_exchanges_safely_handles_malformed_entries(entry):
    assert count_exchanges(entry) == 0


def test_get_entry_messages_returns_empty_list_for_malformed_or_missing_messages():
    assert get_entry_messages({}) == []
    assert get_entry_messages({"messages": "bad"}) == []


def test_get_role_messages_returns_only_requested_role_contents():
    entry = _multi_turn_entry()

    assert get_role_messages(entry, "user") == ["Hi", "How are you?"]
    assert get_role_messages(entry, "assistant") == ["Hello", "Doing well."]


def test_entry_text_length_sums_message_content_lengths_and_handles_malformed():
    assert entry_text_length(_entry()) == len("SystemHiHello")
    assert entry_text_length({"messages": "bad"}) == 0


def test_get_entry_tags_returns_empty_list_for_missing_or_malformed_tags():
    assert get_entry_tags({}) == []
    assert get_entry_tags({"tags": "greeting"}) == []
    assert get_entry_tags({"tags": ["greeting", 7]}) == []


def test_normalize_entry_tags_canonicalizes_deduplicates_and_drops_invalid_tags():
    entry = _entry(tags=["sLow burn", "slow-burn", "  ", "AI Focus", "ai_focus"])
    entry["metadata"] = {"source": "import"}

    normalized, changed = normalize_entry_tags(entry)

    assert changed is True
    assert normalized["tags"] == ["slow_burn", "ai_focus"]
    assert normalized["metadata"] == {"source": "import"}
    assert entry["tags"] == ["sLow burn", "slow-burn", "  ", "AI Focus", "ai_focus"]


def test_normalize_dataset_tags_reports_changed_entries_and_slugs():
    entries = [
        _entry(tags=["slow burn", "slow-burn"]),
        _entry(tags=["reviewed"]),
    ]

    summary = normalize_dataset_tags(entries)

    assert [entry["tags"] for entry in summary.entries] == [
        ["slow_burn"],
        ["reviewed"],
    ]
    assert summary.changed_entries == 1
    assert summary.changed_tags == 2
    assert summary.structural_changed_entries == 0
    assert summary.tag_metadata_added_count == 0
    assert summary.normalized_slugs == {"slow_burn", "reviewed"}


def test_normalize_dataset_tags_reports_missing_tag_metadata():
    entries = [
        {"messages": _entry()["messages"]},
        _entry(tags=["reviewed"]),
    ]

    summary = normalize_dataset_tags(entries)

    assert summary.entries[0]["tags"] == []
    assert summary.structural_changed_entries == 1
    assert summary.tag_metadata_added_count == 1
    assert summary.changed_entries == 1


def test_set_entry_tags_deduplicates_while_preserving_order():
    entry = _entry(tags=["old"])

    set_entry_tags(entry, ["alpha", "beta", "alpha", "gamma"])

    assert entry["tags"] == ["alpha", "beta", "gamma"]


def test_add_tags_to_entry_preserves_existing_order_and_avoids_duplicates():
    entry = _entry(tags=["alpha", "beta"])

    add_tags_to_entry(entry, ["beta", "gamma"])

    assert entry["tags"] == ["alpha", "beta", "gamma"]


def test_remove_tags_from_entry_removes_selected_tags():
    entry = _entry(tags=["alpha", "beta", "gamma"])

    remove_tags_from_entry(entry, ["beta", "missing"])

    assert entry["tags"] == ["alpha", "gamma"]


def test_replace_entry_tags_replaces_all_tags():
    entry = _entry(tags=["alpha", "beta"])

    replace_entry_tags(entry, ["gamma", "gamma", "delta"])

    assert entry["tags"] == ["gamma", "delta"]


def test_entry_is_untagged_detects_empty_tags():
    assert entry_is_untagged(_entry(tags=[])) is True
    assert entry_is_untagged(_entry(tags=["alpha"])) is False


def test_get_used_tags_returns_tags_across_entries():
    entries = [_entry(tags=["alpha", "beta"]), _entry(tags=["beta", "gamma"])]

    assert get_used_tags(entries) == {"alpha", "beta", "gamma"}


def test_has_untagged_entries_detects_at_least_one_untagged_entry():
    assert has_untagged_entries([_entry(tags=["alpha"]), _entry(tags=[])]) is True
    assert has_untagged_entries([_entry(tags=["alpha"])]) is False


def test_get_available_filter_tags_only_used_mode_preserves_unknown_used_tags():
    entries = [_entry(tags=["alpha"]), _entry(tags=["mystery"]), _entry(tags=[])]

    tags = get_available_filter_tags(
        entries,
        only_used=True,
        all_known_tags=["alpha", "beta"],
    )

    assert tags == ["alpha", "mystery", "__untagged__"]


def test_get_available_filter_tags_all_known_mode_includes_untagged_sentinel():
    entries = [_entry(tags=["mystery"])]

    tags = get_available_filter_tags(
        entries,
        only_used=False,
        all_known_tags=["alpha", "beta"],
    )

    assert tags == ["alpha", "beta", "__untagged__"]


def test_entry_matches_tags_no_selected_tags_matches_all():
    assert entry_matches_tags(_entry(tags=[]), [], "Any selected tags") is True
    assert entry_matches_tags(_entry(tags=["alpha"]), [], "Any selected tags") is True


def test_entry_matches_tags_any_selected_tags():
    entry = _entry(tags=["alpha", "beta"])

    assert entry_matches_tags(entry, ["beta"], "Any selected tags") is True
    assert entry_matches_tags(entry, ["gamma"], "Any selected tags") is False


def test_entry_matches_tags_all_selected_tags():
    entry = _entry(tags=["alpha", "beta", "gamma"])

    assert entry_matches_tags(entry, ["alpha", "gamma"], "All selected tags") is True
    assert entry_matches_tags(entry, ["alpha", "missing"], "All selected tags") is False


def test_entry_matches_tags_exact_match():
    entry = _entry(tags=["alpha", "beta"])

    assert entry_matches_tags(entry, ["beta", "alpha"], "Exact match") is True
    assert entry_matches_tags(entry, ["alpha"], "Exact match") is False


def test_entry_matches_tags_untagged_only_selection():
    assert entry_matches_tags(_entry(tags=[]), ["__untagged__"], "Any selected tags") is True
    assert entry_matches_tags(_entry(tags=["alpha"]), ["__untagged__"], "Any selected tags") is False


def test_entry_matches_tags_untagged_and_exact_behavior():
    assert entry_matches_tags(
        _entry(tags=[]),
        ["alpha", "__untagged__"],
        "Exact match",
    ) is True
    assert entry_matches_tags(
        _entry(tags=["alpha"]),
        ["alpha", "__untagged__"],
        "Exact match",
    ) is True
    assert entry_matches_tags(
        _entry(tags=["alpha", "beta"]),
        ["alpha", "__untagged__"],
        "Exact match",
    ) is False


def test_filter_entries_by_tags_filters_correctly():
    entries = [_entry(tags=["alpha"]), _entry(tags=["beta"]), _entry(tags=[])]

    filtered = filter_entries_by_tags(entries, ["alpha"], "Any selected tags")

    assert filtered == [entries[0]]


def test_filter_entry_pairs_by_tags_preserves_entry_ids_and_order():
    entries = [_entry(tags=["alpha"]), _entry(tags=["beta"]), _entry(tags=["alpha"])]
    pairs = [("first", entries[0]), ("second", entries[1]), ("third", entries[2])]

    filtered = filter_entry_pairs_by_tags(pairs, ["alpha"], "Any selected tags")

    assert filtered == [("first", entries[0]), ("third", entries[2])]


def test_make_temp_entry_id_is_zero_padded_and_stable():
    assert make_temp_entry_id(1) == "tmp_000001"
    assert make_temp_entry_id(42) == "tmp_000042"


def test_build_entry_registry_length_and_id_to_index_match_entries():
    entries = [_entry(), _entry(), _entry()]
    registry = build_entry_registry(entries)

    assert registry["ids"] == ["tmp_000001", "tmp_000002", "tmp_000003"]
    assert registry["id_to_index"] == {
        "tmp_000001": 0,
        "tmp_000002": 1,
        "tmp_000003": 2,
    }
    assert registry["next_id"] == 4


def test_rebuild_id_to_index_maps_ids_to_source_indices():
    assert rebuild_id_to_index(["tmp_000002", "tmp_000004"]) == {
        "tmp_000002": 0,
        "tmp_000004": 1,
    }


def test_registry_is_valid_accepts_consistent_registry():
    entries = [_entry(), _entry()]
    registry = build_entry_registry(entries)

    assert registry_is_valid(registry, entries) is True


def test_registry_is_valid_rejects_wrong_length():
    entries = [_entry(), _entry()]
    registry = build_entry_registry(entries)
    registry["ids"].pop()
    registry["id_to_index"] = rebuild_id_to_index(registry["ids"])

    assert registry_is_valid(registry, entries) is False


def test_registry_is_valid_rejects_duplicate_ids():
    entries = [_entry(), _entry()]
    registry = {
        "ids": ["tmp_000001", "tmp_000001"],
        "id_to_index": {"tmp_000001": 1},
        "next_id": 2,
    }

    assert registry_is_valid(registry, entries) is False


def test_registry_is_valid_rejects_bad_id_to_index():
    entries = [_entry(), _entry()]
    registry = build_entry_registry(entries)
    registry["id_to_index"]["tmp_000001"] = 99

    assert registry_is_valid(registry, entries) is False


def test_registry_is_valid_rejects_missing_or_invalid_next_id():
    entries = [_entry()]
    registry = build_entry_registry(entries)
    registry["next_id"] = 0

    assert registry_is_valid(registry, entries) is False


def test_append_registry_id_increments_next_id_and_updates_mapping():
    registry = build_entry_registry([_entry()])

    new_id = append_registry_id(registry)

    assert new_id == "tmp_000002"
    assert registry["ids"] == ["tmp_000001", "tmp_000002"]
    assert registry["id_to_index"] == {"tmp_000001": 0, "tmp_000002": 1}
    assert registry["next_id"] == 3


def test_remove_registry_id_rebuilds_mapping():
    registry = build_entry_registry([_entry(), _entry(), _entry()])

    removed = remove_registry_id(registry, "tmp_000002")

    assert removed is True
    assert registry["ids"] == ["tmp_000001", "tmp_000003"]
    assert registry["id_to_index"] == {"tmp_000001": 0, "tmp_000003": 1}


def test_remove_registry_id_returns_false_for_missing_id():
    registry = build_entry_registry([_entry()])

    assert remove_registry_id(registry, "tmp_999999") is False


def test_get_index_for_entry_id_returns_index_or_none():
    registry = build_entry_registry([_entry(), _entry()])

    assert get_index_for_entry_id(registry, "tmp_000002") == 1
    assert get_index_for_entry_id(registry, "missing") is None


def test_get_entry_pairs_pairs_ids_with_entries_in_source_order():
    entries = [_entry(tags=["first"]), _entry(tags=["second"])]
    registry = build_entry_registry(entries)

    assert get_entry_pairs(entries, registry) == [
        ("tmp_000001", entries[0]),
        ("tmp_000002", entries[1]),
    ]


def test_save_then_load_dataset_roundtrip_preserves_entries(tmp_path):
    path = tmp_path / "nested" / "dataset.jsonl"
    entries = [_entry(tags=["greeting"]), _multi_turn_entry(tags=["story"])]

    save_dataset(str(path), entries)
    loaded, errors = load_dataset(str(path))

    assert errors == []
    assert loaded == entries


def test_load_dataset_missing_file_returns_error_and_empty_entries(tmp_path):
    loaded, errors = load_dataset(str(tmp_path / "missing.jsonl"))

    assert loaded == []
    assert len(errors) == 1
    assert "File not found" in errors[0]


def test_load_dataset_records_parse_errors_but_keeps_valid_lines(tmp_path):
    path = tmp_path / "bad.jsonl"
    valid = _entry(tags=["greeting"])
    path.write_text(
        json.dumps(valid, ensure_ascii=False) + "\n{not valid json}\n",
        encoding="utf-8",
    )

    loaded, errors = load_dataset(str(path))

    assert loaded == [valid]
    assert len(errors) == 1
    assert "Line 2" in errors[0]


def test_load_dataset_normalizes_missing_tags_to_empty_list(tmp_path):
    path = tmp_path / "missing_tags.jsonl"
    entry = {"messages": _entry()["messages"]}
    path.write_text(json.dumps(entry) + "\n", encoding="utf-8")

    loaded, errors = load_dataset(str(path))

    assert errors == []
    assert loaded[0]["tags"] == []


def test_load_dataset_with_summary_reports_missing_tag_metadata(tmp_path):
    path = tmp_path / "missing_tags.jsonl"
    entries = [
        {"messages": _entry()["messages"]},
        {"messages": _entry()["messages"]},
        {"messages": _entry()["messages"]},
    ]
    path.write_text(
        "\n".join(json.dumps(entry) for entry in entries) + "\n",
        encoding="utf-8",
    )

    summary, errors = load_dataset_with_summary(str(path))

    assert errors == []
    assert [entry["tags"] for entry in summary.entries] == [[], [], []]
    assert summary.structural_changed_entries == 3
    assert summary.tag_metadata_added_count == 3


def test_load_dataset_with_summary_reports_chatml_source_format(tmp_path):
    path = tmp_path / "chatml.jsonl"
    entry = _entry(tags=["greeting"])
    path.write_text(json.dumps(entry) + "\n", encoding="utf-8")

    summary, errors = load_dataset_with_summary(str(path))

    assert errors == []
    assert summary.entries == [entry]
    assert summary.source_format == FORMAT_CHATML
    assert summary.format_counts[FORMAT_CHATML] == 1
    assert summary.format_converted_count == 0
    assert summary.format_already_target_count == 1
    assert summary.format_warnings == []


def test_load_dataset_with_summary_converts_sharegpt_to_chatml(tmp_path):
    path = tmp_path / "sharegpt.jsonl"
    record = {
        "conversations": [
            {"from": "human", "value": "Hi"},
            {"from": "gpt", "value": "Hello"},
        ],
        "tags": ["sLow burn"],
        "source": "outside",
    }
    path.write_text(json.dumps(record) + "\n", encoding="utf-8")

    summary, errors = load_dataset_with_summary(str(path))

    assert errors == []
    assert summary.source_format == FORMAT_SHAREGPT
    assert summary.format_counts[FORMAT_SHAREGPT] == 1
    assert summary.format_converted_count == 1
    assert summary.entries == [
        {
            "messages": [
                {"role": "system", "content": SHAREGPT_INTERNAL_SYSTEM_PROMPT},
                {"role": "user", "content": "Hi"},
                {"role": "assistant", "content": "Hello"},
            ],
            "tags": ["slow_burn"],
            "source": "outside",
        }
    ]
    assert any("default system prompt" in warning for warning in summary.format_warnings)


def test_load_dataset_with_summary_keeps_unknown_format_loadable(tmp_path):
    path = tmp_path / "unknown.jsonl"
    record = {"prompt": "Hi", "completion": "Hello"}
    path.write_text(json.dumps(record) + "\n", encoding="utf-8")

    summary, errors = load_dataset_with_summary(str(path))

    assert errors == []
    assert summary.source_format == FORMAT_UNKNOWN
    assert summary.entries == [{"prompt": "Hi", "completion": "Hello", "tags": []}]
    assert summary.format_converted_count == 0
    assert summary.format_warnings == []


def test_load_dataset_normalizes_funky_tags_in_memory(tmp_path):
    path = tmp_path / "funky_tags.jsonl"
    path.write_text(
        json.dumps(_entry(tags=["sLow burn", "slow-burn", "!!!"])) + "\n",
        encoding="utf-8",
    )

    loaded, errors = load_dataset(str(path))

    assert errors == []
    assert loaded[0]["tags"] == ["slow_burn"]


def test_append_to_dataset_writes_one_entry_after_existing_entries(tmp_path):
    path = tmp_path / "dataset.jsonl"
    first = _entry(tags=["first"])
    second = _entry(tags=["second"])
    save_dataset(str(path), [first])

    append_to_dataset(str(path), second)
    loaded, errors = load_dataset(str(path))

    assert errors == []
    assert loaded == [first, second]


def test_save_dataset_creates_parent_directories(tmp_path):
    path = tmp_path / "new" / "deeper" / "dataset.jsonl"

    save_dataset(str(path), [_entry()])

    assert path.exists()


def test_save_dataset_outputs_newline_delimited_jsonl(tmp_path):
    path = tmp_path / "dataset.jsonl"
    entries = [_entry(tags=["first"]), _entry(tags=["second"])]

    save_dataset(str(path), entries)

    text = path.read_text(encoding="utf-8")
    assert text.endswith("\n")
    lines = text.splitlines()
    assert len(lines) == 2
    assert [json.loads(line) for line in lines] == entries


def test_merge_datasets_removes_duplicates_and_preserves_first_unique_entry(tmp_path):
    path_one = tmp_path / "one.jsonl"
    path_two = tmp_path / "two.jsonl"
    first = _entry(tags=["first"])
    duplicate = _entry(tags=["duplicate"])
    second = _entry(
        tags=["second"],
        messages=[
            {"role": "system", "content": "Different system"},
            {"role": "user", "content": "Different"},
            {"role": "assistant", "content": "Different answer"},
        ],
    )
    save_dataset(str(path_one), [first])
    save_dataset(str(path_two), [duplicate, second])

    merged, stats = merge_datasets([str(path_one), str(path_two)], shuffle=False)

    assert merged == [first, second]
    assert stats["total_loaded"] == 3
    assert stats["duplicates_removed"] == 1


def test_merge_datasets_collects_parse_errors_from_bad_input_files(tmp_path):
    valid_path = tmp_path / "valid.jsonl"
    bad_path = tmp_path / "bad.jsonl"
    entry = _entry(tags=["valid"])
    save_dataset(str(valid_path), [entry])
    bad_path.write_text("{bad json}\n", encoding="utf-8")

    merged, stats = merge_datasets([str(valid_path), str(bad_path)], shuffle=False)

    assert merged == [entry]
    assert stats["total_loaded"] == 1
    assert len(stats["parse_errors"]) == 1
    assert "Line 1" in stats["parse_errors"][0]


def test_merge_datasets_with_shuffle_false_preserves_deterministic_order(tmp_path):
    path_one = tmp_path / "one.jsonl"
    path_two = tmp_path / "two.jsonl"
    first = _entry(
        tags=["first"],
        messages=[
            {"role": "system", "content": "System"},
            {"role": "user", "content": "One"},
            {"role": "assistant", "content": "First"},
        ],
    )
    second = _entry(
        tags=["second"],
        messages=[
            {"role": "system", "content": "System"},
            {"role": "user", "content": "Two"},
            {"role": "assistant", "content": "Second"},
        ],
    )
    save_dataset(str(path_one), [first])
    save_dataset(str(path_two), [second])

    merged, _stats = merge_datasets([str(path_one), str(path_two)], shuffle=False)

    assert merged == [first, second]


def test_build_dataset_stats_reports_summary_validation_tags_and_lengths():
    valid = _multi_turn_entry(tags=["alpha", "beta"])
    untagged = _entry(tags=[])
    invalid = {"messages": [{"role": "system", "content": "Only system"}], "tags": ["alpha"]}

    stats = build_dataset_stats(
        [valid, untagged, invalid],
        tag_category_map={"alpha": "Known", "beta": "Known"},
    )

    assert stats["total"] == 3
    assert stats["valid_count"] == 2
    assert stats["invalid_count"] == 1
    assert stats["tag_counts"] == {"alpha": 2, "beta": 1}
    assert stats["tag_category_counts"] == {"Known": 3}
    assert stats["untagged_count"] == 1
    assert stats["exchange_dist"] == {2: 1, 1: 1, 0: 1}
    assert stats["total_exchanges"] == 3
    assert stats["avg_user_len"] > 0
    assert stats["avg_asst_len"] > 0
    assert stats["avg_entry_len"] > 0
