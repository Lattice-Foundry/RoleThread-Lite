import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import core.dataset as dataset
from core.dataset import (
    add_tags_to_entry,
    analyze_entry,
    build_dataset_stats,
    build_uuid_index,
    canonicalize_entry_tag_aliases,
    clear_validate_entry_cache,
    count_exchanges,
    entry_is_untagged,
    entry_matches_tags,
    entry_text_length,
    filter_entries_by_tags,
    filter_entry_pairs_by_tags,
    get_available_filter_tags,
    get_entry_messages,
    get_entry_tags,
    get_entry_by_uuid,
    get_entry_index_by_uuid,
    get_role_messages,
    get_used_tags,
    has_untagged_entries,
    load_dataset,
    load_dataset_with_summary,
    make_entry,
    merge_datasets,
    normalize_dataset_entries,
    normalize_dataset_tags,
    normalize_entry_message_fields,
    normalize_entry_tags,
    remove_tags_from_entry,
    replace_entry_tags,
    save_dataset,
    set_entry_tags,
    summarize_entry_analysis,
    validate_entry,
)
from core.loreforge_meta import LOREFORGE_META_KEY, get_entry_uuid, stamp_entries
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


def _resolution(slug, *, rewrite=False, resolved=None):
    return SimpleNamespace(
        should_rewrite_slug=rewrite,
        resolved_slug=resolved or slug,
    )


def test_canonicalize_entry_tag_aliases_rewrites_and_deduplicates_without_mutation():
    entries = [
        _entry(tags=["old_tag", "active_tag", "old_tag"]),
        _entry(tags=["untouched"]),
    ]
    original = json.loads(json.dumps(entries))

    def resolve(tag):
        if tag == "old_tag":
            return _resolution(tag, rewrite=True, resolved="active_tag")
        return _resolution(tag)

    canonical_entries, summary = canonicalize_entry_tag_aliases(entries, resolve)

    assert entries == original
    assert canonical_entries[0]["tags"] == ["active_tag"]
    assert canonical_entries[1]["tags"] == ["untouched"]
    assert summary == {
        "rewrites": {"old_tag": "active_tag"},
        "rewrite_count": 2,
        "changed_entries": 1,
    }


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

    assert "First message must be a system prompt" in _error_text(errors)


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
    assert "empty" in _error_text(errors)


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

    assert "should be a user turn" in _error_text(errors)
    assert "should be an assistant turn" in _error_text(errors)


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

    assert "empty" in _error_text(errors)


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

    assert "Tags contain non-text values" in _error_text(errors)


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


def test_validate_entry_cache_evicts_least_recently_used_entries(monkeypatch):
    clear_validate_entry_cache()
    monkeypatch.setattr(dataset, "_VALIDATE_ENTRY_CACHE_MAX_SIZE", 2)
    calls = []

    def fake_analyze(entry):
        calls.append(entry["tags"][0])
        return EntryAnalysisResult(
            format="chatml",
            entry_index=None,
            is_valid=False,
            diagnostics=(
                EntryDiagnostic(
                    code="test.cached",
                    severity=AnalysisSeverity.ERROR,
                    message=f"cached error {entry['tags'][0]}",
                ),
            ),
        )

    monkeypatch.setattr(dataset, "_analyze_entry_uncached", fake_analyze)

    validate_entry(_entry(tags=["one"]))
    validate_entry(_entry(tags=["two"]))
    validate_entry(_entry(tags=["one"]))
    validate_entry(_entry(tags=["three"]))
    validate_entry(_entry(tags=["one"]))
    validate_entry(_entry(tags=["two"]))

    assert calls == ["one", "two", "three", "two"]
    clear_validate_entry_cache()


def test_analyze_entry_cache_does_not_expose_mutable_repaired_entry(monkeypatch):
    clear_validate_entry_cache()
    repaired = {"messages": [{"role": "system", "content": "System"}], "tags": []}

    monkeypatch.setattr(
        dataset,
        "_analyze_entry_uncached",
        lambda entry: EntryAnalysisResult(
            format="chatml",
            entry_index=None,
            is_valid=True,
            diagnostics=(),
            repaired_entry=repaired,
            changed=True,
        ),
    )

    entry = _entry(tags=["greeting"])
    first = analyze_entry(entry)
    assert first.repaired_entry is not None
    first.repaired_entry["mutated"] = True

    second = analyze_entry(entry)

    assert second.repaired_entry is not None
    assert "mutated" not in second.repaired_entry
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


def test_normalize_entry_message_fields_canonicalizes_roles_and_trims_content():
    entry = {
        "messages": [
            {"role": " SYSTEM ", "content": " System "},
            {"role": "Human", "content": "  Hi"},
            {"role": "BOT", "content": "Hello  "},
            {"role": " Scott ", "content": " custom "},
        ],
        "tags": [],
    }

    normalized, changed, role_count, content_count = normalize_entry_message_fields(entry)

    assert changed is True
    assert role_count == 3
    assert content_count == 4
    assert normalized["messages"] == [
        {"role": "system", "content": "System"},
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "Hello"},
        {"role": " Scott ", "content": "custom"},
    ]
    assert entry["messages"][0]["role"] == " SYSTEM "


def test_normalize_dataset_entries_combines_tag_and_message_normalization():
    entries = [
        {
            "messages": [
                {"role": "SYSTEM", "content": "System"},
                {"role": "Human", "content": " Hi "},
                {"role": "GPT", "content": "Hello"},
            ],
            "tags": ["slow burn", 7, ""],
        }
    ]

    summary = normalize_dataset_entries(entries)

    assert summary.entries[0]["messages"] == [
        {"role": "system", "content": "System"},
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "Hello"},
    ]
    assert summary.entries[0]["tags"] == ["slow_burn"]
    assert summary.changed_entries == 1
    assert summary.changed_tags == 3
    assert summary.role_values_normalized == 3
    assert summary.message_content_trimmed == 1
    assert summary.normalized_slugs == {"slow_burn"}


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


def test_filter_entry_pairs_by_tags_preserves_entry_uuids_and_order():
    entries = [_entry(tags=["alpha"]), _entry(tags=["beta"]), _entry(tags=["alpha"])]
    pairs = [("first", entries[0]), ("second", entries[1]), ("third", entries[2])]

    filtered = filter_entry_pairs_by_tags(pairs, ["alpha"], "Any selected tags")

    assert filtered == [("first", entries[0]), ("third", entries[2])]


def test_build_uuid_index_maps_entry_uuids_to_source_indices():
    entries = [
        {**_entry(), LOREFORGE_META_KEY: {"entry_uuid": "entry-1"}},
        {**_entry(), LOREFORGE_META_KEY: {"entry_uuid": "entry-2"}},
        _entry(),
    ]

    assert build_uuid_index(entries) == {
        "entry-1": 0,
        "entry-2": 1,
    }


def test_build_uuid_index_ignores_missing_and_malformed_uuid_metadata():
    entries = [
        _entry(),
        {**_entry(), LOREFORGE_META_KEY: "bad"},
        {**_entry(), LOREFORGE_META_KEY: {"entry_uuid": ""}},
        {**_entry(), LOREFORGE_META_KEY: {"entry_uuid": "entry-4"}},
        "not an entry",
    ]

    assert build_uuid_index(entries) == {"entry-4": 3}


def test_uuid_lookup_helpers_return_entry_index_and_entry():
    entries = [
        {**_entry(tags=["first"]), LOREFORGE_META_KEY: {"entry_uuid": "entry-1"}},
        {**_entry(tags=["second"]), LOREFORGE_META_KEY: {"entry_uuid": "entry-2"}},
    ]

    assert get_entry_index_by_uuid(entries, "entry-2") == 1
    assert get_entry_by_uuid(entries, "entry-2") == entries[1]
    assert get_entry_index_by_uuid(entries, "missing") is None
    assert get_entry_by_uuid(entries, "missing") is None


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
    assert "column 2" in errors[0]


def test_load_dataset_with_summary_reports_parse_line_breakdown(tmp_path):
    path = tmp_path / "mixed.jsonl"
    valid = _entry(tags=["greeting"])
    path.write_text(
        json.dumps(valid, ensure_ascii=False) + "\n{not valid json}\n",
        encoding="utf-8",
    )

    summary, errors = load_dataset_with_summary(str(path))

    assert len(errors) == 1
    assert summary.source_line_count == 2
    assert summary.parsed_entry_count == 1
    assert summary.parse_error_count == 1


def test_load_dataset_rejects_unsupported_file_extension(tmp_path):
    path = tmp_path / "image.png"
    path.write_text(json.dumps(_entry()) + "\n", encoding="utf-8")

    loaded, errors = load_dataset(str(path))

    assert loaded == []
    assert errors == [
        "Unsupported file type: .png. LoreForge supports .jsonl, .json, and .txt files."
    ]


def test_load_dataset_rejects_non_utf8_text(tmp_path):
    path = tmp_path / "binary.jsonl"
    path.write_bytes(b"\xff\xfe\x00\x00not-json")

    loaded, errors = load_dataset(str(path))

    assert loaded == []
    assert errors == ["File is not valid UTF-8 text and cannot be loaded as a dataset."]


def test_load_dataset_expands_json_array_file(tmp_path):
    path = tmp_path / "dataset.json"
    entries = [_entry(tags=["greeting"]), _entry(tags=["slow burn"])]
    path.write_text(json.dumps(entries), encoding="utf-8")

    summary, errors = load_dataset_with_summary(str(path))

    assert errors == []
    assert len(summary.entries) == 2
    assert summary.entries[0]["tags"] == ["greeting"]
    assert summary.entries[1]["tags"] == ["slow_burn"]
    assert summary.source_format == FORMAT_CHATML


def test_load_dataset_rejects_json_array_with_non_object_items(tmp_path):
    path = tmp_path / "dataset.json"
    path.write_text(json.dumps([_entry(), "not an entry"]), encoding="utf-8")

    loaded, errors = load_dataset(str(path))

    assert loaded == []
    assert errors == ["JSON array file detected but contains non-object items."]


def test_load_dataset_rejects_single_non_training_json_object(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"editor.fontSize": 14}), encoding="utf-8")

    loaded, errors = load_dataset(str(path))

    assert loaded == []
    assert errors == [
        "File contains a valid JSON object but it does not appear to be a training dataset entry."
    ]


def test_load_dataset_loads_single_training_json_object(tmp_path):
    path = tmp_path / "entry.json"
    entry = _entry(tags=["slow burn"])
    path.write_text(json.dumps(entry), encoding="utf-8")

    summary, errors = load_dataset_with_summary(str(path))

    assert errors == []
    assert summary.entries == [_entry(tags=["slow_burn"])]
    assert summary.source_format == FORMAT_CHATML


def test_load_dataset_reports_zero_entries_when_all_lines_fail(tmp_path):
    path = tmp_path / "plain.jsonl"
    path.write_text("hello world\nstill not json\n", encoding="utf-8")

    loaded, errors = load_dataset(str(path))

    assert loaded == []
    assert len(errors) == 3
    assert "Line 1" in errors[0]
    assert "Line 2" in errors[1]
    assert errors[2] == "No valid entries could be loaded. 2 lines had parse errors."


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


def test_load_dataset_with_summary_auto_normalize_on_cleans_deterministic_issues(
    tmp_path,
):
    path = tmp_path / "normalize_on.jsonl"
    entry = {
        "messages": [
            {"role": "SYSTEM", "content": " System "},
            {"role": "Human", "content": " Hi "},
            {"role": "GPT", "content": " Hello "},
        ],
        "tags": ["slow burn", 7, ""],
    }
    path.write_text(json.dumps(entry) + "\n", encoding="utf-8")

    summary, errors = load_dataset_with_summary(str(path), auto_normalize=True)

    assert errors == []
    assert summary.entries == [
        {
            "messages": [
                {"role": "system", "content": "System"},
                {"role": "user", "content": "Hi"},
                {"role": "assistant", "content": "Hello"},
            ],
            "tags": ["slow_burn"],
        }
    ]
    assert summary.role_values_normalized == 3
    assert summary.message_content_trimmed == 3
    assert summary.diagnostics.valid_entries == 1
    assert summary.diagnostics.auto_repairable_count == 0


def test_load_dataset_with_summary_auto_normalize_off_preserves_issues_for_analysis(
    tmp_path,
):
    path = tmp_path / "normalize_off.jsonl"
    entry = {
        "messages": [
            {"role": "SYSTEM", "content": " System "},
            {"role": "Human", "content": " Hi "},
            {"role": "GPT", "content": " Hello "},
        ],
        "tags": ["slow burn", 7, ""],
    }
    path.write_text(json.dumps(entry) + "\n", encoding="utf-8")

    summary, errors = load_dataset_with_summary(str(path), auto_normalize=False)

    assert errors == []
    assert summary.entries == [
        {
            "messages": [
                {"role": "system", "content": "System"},
                {"role": "user", "content": "Hi"},
                {"role": "assistant", "content": "Hello"},
            ],
            "tags": ["slow burn"],
        }
    ]
    assert summary.changed_entries == 1
    assert summary.changed_tags == 2
    assert summary.role_values_normalized == 3
    assert summary.message_content_trimmed == 3
    assert summary.diagnostics.valid_entries == 1
    assert summary.diagnostics.entries_with_errors == 0
    assert summary.diagnostics.entries_with_warnings == 0
    assert summary.diagnostics.auto_repairable_count == 0


def test_load_dataset_summary_counts_auto_fixable_entries_as_issues(tmp_path):
    path = tmp_path / "dirty_auto_fixable.jsonl"
    records = [
        _entry(messages=[
            {"role": "System", "content": "System"},
            {"role": "User", "content": "Hi"},
            {"role": "Assistant", "content": "Hello"},
        ]),
        _entry(messages=[
            {"role": "SYSTEM", "content": "System"},
            {"role": "USER", "content": "Hi"},
            {"role": "ASSISTANT", "content": "Hello"},
        ]),
        _entry(messages=[
            {"role": "system", "content": "System"},
            {"role": "human", "content": "Hi"},
            {"role": "gpt", "content": "Hello"},
        ]),
        {"messages": [
            {"role": "system", "content": " System "},
            {"role": "user", "content": " Hi "},
            {"role": "assistant", "content": " Hello "},
        ]},
        _entry(tags=["good", "", 7, "also good"]),
        _entry(messages=[
            {"role": "GPT", "content": "System-ish"},
            {"role": "USER", "content": "Hi"},
            {"role": "Bot", "content": "Hello"},
        ]),
    ]
    path.write_text(
        "\n".join(json.dumps(record) for record in records) + "\n",
        encoding="utf-8",
    )

    summary, errors = load_dataset_with_summary(str(path), auto_normalize=False)

    assert errors == []
    assert summary.diagnostics.entries_analyzed == 6
    assert summary.diagnostics.valid_entries == 5
    assert (
        summary.diagnostics.entries_analyzed - summary.diagnostics.valid_entries
    ) == 1
    assert summary.diagnostics.auto_repairable_count == 0
    assert summary.diagnostics.entries_with_errors == 1


def test_load_dataset_with_summary_corrects_known_role_variants_from_dirty_fixture():
    path = Path("training_data/test_originals/dirty/02_dirty_auto_fixable.jsonl")

    summary, errors = load_dataset_with_summary(str(path), auto_normalize=False)

    assert errors == []
    assert len(summary.entries) == 6
    assert [
        [message["role"] for message in entry["messages"]]
        for entry in summary.entries
    ] == [
        ["system", "user", "assistant"],
        ["system", "user", "assistant"],
        ["system", "user", "assistant"],
        ["system", "user", "assistant"],
        ["system", "user", "assistant"],
        ["GPT", "user", "assistant"],
    ]
    assert summary.role_values_normalized == 7
    assert summary.message_content_trimmed == 3
    assert summary.changed_tags == 4
    assert summary.diagnostics.entries_analyzed == 6
    assert summary.diagnostics.valid_entries == 5


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
    assert summary.diagnostics.entries_analyzed == 1
    assert summary.diagnostics.valid_entries == 1
    assert summary.diagnostics.entries_with_errors == 0


def test_load_dataset_with_summary_reports_native_dataset_signature(tmp_path):
    path = tmp_path / "native.jsonl"
    entry = {
        **_entry(tags=["greeting"]),
        LOREFORGE_META_KEY: {
            "version": "0.1.0",
            "native": True,
            "validated_at": "2026-05-11T12:00:00Z",
            "dataset_uuid": "dataset-uuid-1",
        },
    }
    path.write_text(json.dumps(entry) + "\n", encoding="utf-8")

    summary, errors = load_dataset_with_summary(str(path))

    assert errors == []
    assert summary.dataset_is_native is True
    assert summary.entries[0][LOREFORGE_META_KEY]["native"] is True


def test_load_dataset_with_summary_treats_legacy_native_without_dataset_uuid_as_foreign(
    tmp_path,
):
    path = tmp_path / "legacy_native.jsonl"
    entry = {
        **_entry(tags=["greeting"]),
        LOREFORGE_META_KEY: {
            "version": "0.6.0",
            "native": True,
            "validated_at": "2026-05-11T12:00:00Z",
        },
    }
    path.write_text(json.dumps(entry) + "\n", encoding="utf-8")

    summary, errors = load_dataset_with_summary(str(path))

    assert errors == []
    assert summary.dataset_is_native is False


def test_load_dataset_with_summary_empty_file_is_safe_initialization(tmp_path):
    path = tmp_path / "empty.jsonl"
    path.write_text("", encoding="utf-8")

    summary, errors = load_dataset_with_summary(str(path))

    assert errors == []
    assert summary.entries == []
    assert summary.dataset_is_native is False
    assert summary.diagnostics.entries_analyzed == 0


def test_load_dataset_with_summary_reports_foreign_dataset_when_partially_stamped(tmp_path):
    path = tmp_path / "partial.jsonl"
    native_entry = {
        **_entry(tags=["greeting"]),
        LOREFORGE_META_KEY: {"native": True},
    }
    path.write_text(
        json.dumps(native_entry) + "\n" + json.dumps(_entry(tags=["slow burn"])) + "\n",
        encoding="utf-8",
    )

    summary, errors = load_dataset_with_summary(str(path))

    assert errors == []
    assert summary.dataset_is_native is False


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
    assert summary.diagnostics.entries_analyzed == 1
    assert summary.diagnostics.valid_entries == 1
    assert summary.diagnostics.error_count == 0


def test_load_dataset_with_summary_baseline_repairs_sharegpt_missing_tags(tmp_path):
    path = tmp_path / "sharegpt_no_tags.jsonl"
    records = [
        {
            "conversations": [
                {"from": "human", "value": "Hi"},
                {"from": "gpt", "value": "Hello"},
            ]
        },
        {
            "conversations": [
                {"from": "human", "value": "Question"},
                {"from": "gpt", "value": "Answer"},
            ]
        },
    ]
    path.write_text(
        "\n".join(json.dumps(record) for record in records) + "\n",
        encoding="utf-8",
    )

    summary, errors = load_dataset_with_summary(str(path), auto_normalize=False)

    assert errors == []
    assert summary.source_format == FORMAT_SHAREGPT
    assert summary.diagnostics.entries_analyzed == 2
    assert summary.diagnostics.valid_entries == 2
    assert summary.diagnostics.entries_with_errors == 0
    assert summary.diagnostics.auto_repairable_count == 0
    assert summary.tag_metadata_added_count == 2
    assert all(entry["tags"] == [] for entry in summary.entries)


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
    assert summary.diagnostics.entries_analyzed == 1
    assert summary.diagnostics.valid_entries == 0
    assert summary.diagnostics.entries_with_errors == 1
    assert summary.diagnostics.error_count == 1


def test_summarize_entry_analysis_counts_severity_and_auto_repairs():
    entries = [
        _entry(tags=["greeting"]),
        _entry(tags=["greeting", 7]),
        {"prompt": "Hi", "tags": []},
    ]

    summary = summarize_entry_analysis(entries)

    assert summary.entries_analyzed == 3
    assert summary.valid_entries == 1
    assert summary.entries_with_errors == 2
    assert summary.entries_with_warnings == 0
    assert summary.error_count == 2
    assert summary.warning_count == 0
    assert summary.auto_repairable_count == 1


def test_load_dataset_with_summary_collects_diagnostics_after_tag_normalization(tmp_path):
    path = tmp_path / "diagnostics.jsonl"
    records = [
        _entry(tags=["greeting"]),
        {"messages": "bad", "tags": ["slow burn"]},
        {"messages": _entry()["messages"], "tags": "slow burn"},
    ]
    path.write_text(
        "\n".join(json.dumps(record) for record in records) + "\n",
        encoding="utf-8",
    )

    summary, errors = load_dataset_with_summary(str(path))

    assert errors == []
    assert summary.entries[1]["tags"] == ["slow_burn"]
    assert summary.entries[2]["tags"] == []
    assert summary.diagnostics.entries_analyzed == 3
    assert summary.diagnostics.valid_entries == 2
    assert summary.diagnostics.entries_with_errors == 1
    assert summary.diagnostics.error_count == 1
    assert summary.diagnostics.warning_count == 0
    assert summary.diagnostics.auto_repairable_count == 0


def test_load_dataset_normalizes_funky_tags_in_memory(tmp_path):
    path = tmp_path / "funky_tags.jsonl"
    path.write_text(
        json.dumps(_entry(tags=["sLow burn", "slow-burn", "!!!"])) + "\n",
        encoding="utf-8",
    )

    loaded, errors = load_dataset(str(path))

    assert errors == []
    assert loaded[0]["tags"] == ["slow_burn"]


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

    expected_first = {**first, "tags": ["first", "duplicate"]}
    assert merged == [expected_first, second]
    assert stats["total_loaded"] == 3
    assert stats["duplicates_removed"] == 1


def test_merge_datasets_duplicate_entries_merge_tags_only_into_first_survivor(tmp_path):
    path_one = tmp_path / "one.jsonl"
    path_two = tmp_path / "two.jsonl"
    first = stamp_entries(
        [
            _entry(
                tags=["first", "shared"],
                messages=[
                    {"role": "system", "content": "First system"},
                    {"role": "user", "content": "Same user"},
                    {"role": "assistant", "content": "Same assistant"},
                ],
            )
        ],
        dataset_uuid="first-dataset",
    )[0]
    duplicate = stamp_entries(
        [
            _entry(
                tags=["shared", "duplicate", "first"],
                messages=[
                    {"role": "system", "content": "Different system"},
                    {"role": "user", "content": "Same user"},
                    {"role": "assistant", "content": "Same assistant"},
                ],
            )
        ],
        dataset_uuid="duplicate-dataset",
    )[0]
    first_uuid = get_entry_uuid(first)
    duplicate_uuid = get_entry_uuid(duplicate)
    save_dataset(str(path_one), [first])
    save_dataset(str(path_two), [duplicate])

    merged, stats = merge_datasets([str(path_one), str(path_two)], shuffle=False)

    assert len(merged) == 1
    assert stats["duplicates_removed"] == 1
    assert merged[0]["messages"] == first["messages"]
    assert get_entry_uuid(merged[0]) == first_uuid
    assert get_entry_uuid(merged[0]) != duplicate_uuid
    assert merged[0]["tags"] == ["first", "shared", "duplicate"]


def test_merge_datasets_collects_parse_errors_from_bad_input_files(tmp_path):
    valid_path = tmp_path / "valid.jsonl"
    bad_path = tmp_path / "bad.jsonl"
    entry = _entry(tags=["valid"])
    save_dataset(str(valid_path), [entry])
    bad_path.write_text("{bad json}\n", encoding="utf-8")

    merged, stats = merge_datasets([str(valid_path), str(bad_path)], shuffle=False)

    assert merged == [entry]
    assert stats["total_loaded"] == 1
    assert len(stats["parse_errors"]) == 2
    assert "Line 1" in stats["parse_errors"][0]
    assert stats["parse_errors"][1] == "No valid entries could be loaded. 1 line had parse errors."


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
