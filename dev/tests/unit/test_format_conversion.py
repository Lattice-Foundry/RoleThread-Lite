from core.format_conversion import (
    FORMAT_CHATML,
    FORMAT_SHAREGPT,
    FORMAT_UNKNOWN,
    SHAREGPT_INTERNAL_SYSTEM_PROMPT,
    chatml_to_sharegpt_entry,
    convert_chatml_to_format,
    convert_records_to_chatml,
    detect_record_format,
    detect_records_format,
    sharegpt_to_chatml_entry,
)


def _chatml_entry():
    return {
        "messages": [
            {"role": "system", "content": "System"},
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello"},
        ],
        "tags": ["greeting"],
        "source": "manual",
    }


def _sharegpt_entry():
    return {
        "conversations": [
            {"from": "system", "value": "System"},
            {"from": "human", "value": "Hi"},
            {"from": "gpt", "value": "Hello"},
        ],
        "tags": ["greeting"],
        "source": "sharegpt",
    }


def test_detect_record_format_identifies_chatml_sharegpt_and_unknown():
    assert detect_record_format(_chatml_entry()) == FORMAT_CHATML
    assert detect_record_format(_sharegpt_entry()) == FORMAT_SHAREGPT
    assert detect_record_format({"text": "not a dataset entry"}) == FORMAT_UNKNOWN
    assert detect_record_format({"messages": [], "conversations": []}) == FORMAT_UNKNOWN


def test_detect_records_format_uses_majority_with_confidence():
    summary = detect_records_format([
        _sharegpt_entry(),
        _sharegpt_entry(),
        _chatml_entry(),
        {"unknown": True},
    ])

    assert summary.format == FORMAT_SHAREGPT
    assert summary.counts == {
        FORMAT_CHATML: 1,
        FORMAT_SHAREGPT: 2,
        FORMAT_UNKNOWN: 1,
    }
    assert summary.total == 4
    assert summary.confidence == 0.5


def test_detect_records_format_returns_unknown_for_ties_and_empty_lists():
    tie = detect_records_format([_sharegpt_entry(), _chatml_entry()])
    empty = detect_records_format([])

    assert tie.format == FORMAT_UNKNOWN
    assert tie.confidence == 0.5
    assert empty.format == FORMAT_UNKNOWN
    assert empty.confidence == 0.0


def test_sharegpt_to_chatml_maps_roles_and_fields():
    result = sharegpt_to_chatml_entry(
        {
            "conversations": [
                {"from": "SYSTEM", "value": "ShareGPT system"},
                {"from": "human", "value": "Hi"},
                {"from": "USER", "value": "Followup"},
                {"from": "gpt", "value": "Hello"},
                {"from": "Assistant", "value": "Sure"},
                {"from": "bot", "value": "Bot reply"},
                {"from": "model", "value": "Model reply"},
            ]
        }
    )

    assert result.entry["messages"] == [
        {"role": "system", "content": "ShareGPT system"},
        {"role": "user", "content": "Hi"},
        {"role": "user", "content": "Followup"},
        {"role": "assistant", "content": "Hello"},
        {"role": "assistant", "content": "Sure"},
        {"role": "assistant", "content": "Bot reply"},
        {"role": "assistant", "content": "Model reply"},
    ]
    assert result.diagnostics.mapped_roles["human"] == "user"
    assert result.diagnostics.mapped_roles["gpt"] == "assistant"


def test_sharegpt_to_chatml_handles_role_content_field_variants():
    result = sharegpt_to_chatml_entry(
        {
            "conversations": [
                {"role": "user", "content": "Hi"},
                {"role": "assistant", "content": "Hello"},
                {"speaker": "bot", "text": "Variant"},
            ]
        }
    )

    assert result.entry["messages"] == [
        {"role": "system", "content": SHAREGPT_INTERNAL_SYSTEM_PROMPT},
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "Hello"},
        {"role": "assistant", "content": "Variant"},
    ]
    assert "No ShareGPT system turn found; default system prompt injected." in (
        result.diagnostics.warnings
    )


def test_sharegpt_to_chatml_injects_system_prompt_and_preserves_metadata():
    source = {
        "conversations": [
            {"from": "human", "value": "Hi"},
            {"from": "gpt", "value": "Hello"},
        ],
        "tags": ["slow_burn"],
        "id": "row-1",
    }

    result = sharegpt_to_chatml_entry(source)

    assert result.entry["messages"][0] == {
        "role": "system",
        "content": SHAREGPT_INTERNAL_SYSTEM_PROMPT,
    }
    assert result.entry["tags"] == ["slow_burn"]
    assert result.entry["id"] == "row-1"
    assert "conversations" not in result.entry


def test_sharegpt_to_chatml_merges_multiple_system_turns():
    result = sharegpt_to_chatml_entry(
        {
            "conversations": [
                {"from": "system", "value": "One"},
                {"from": "system", "value": "Two"},
                {"from": "human", "value": "Hi"},
            ]
        }
    )

    assert result.entry["messages"][0]["content"] == "One\n\nTwo"
    assert "Multiple ShareGPT system turns were merged." in result.diagnostics.warnings


def test_sharegpt_to_chatml_reports_empty_missing_and_unknown_turns():
    result = sharegpt_to_chatml_entry(
        {
            "conversations": [
                "bad",
                {"from": "critic", "value": "Nope"},
                {"from": "human"},
                {"value": "Missing role"},
            ]
        }
    )

    assert result.entry["messages"] == [
        {"role": "system", "content": SHAREGPT_INTERNAL_SYSTEM_PROMPT},
        {"role": "user", "content": ""},
    ]
    warnings = "\n".join(result.diagnostics.warnings)
    assert "not an object" in warnings
    assert "unknown role" in warnings
    assert "missing a content field" in warnings
    assert "missing a role field" in warnings


def test_sharegpt_to_chatml_reports_empty_conversations():
    result = sharegpt_to_chatml_entry({"conversations": []})

    assert result.entry["messages"] == [
        {"role": "system", "content": SHAREGPT_INTERNAL_SYSTEM_PROMPT}
    ]
    assert "ShareGPT record contains no conversation turns." in result.diagnostics.warnings


def test_chatml_to_sharegpt_maps_roles_fields_and_preserves_metadata():
    result = chatml_to_sharegpt_entry(_chatml_entry())

    assert result.entry == {
        "conversations": [
            {"from": "system", "value": "System"},
            {"from": "human", "value": "Hi"},
            {"from": "gpt", "value": "Hello"},
        ],
        "tags": ["greeting"],
        "source": "manual",
    }


def test_chatml_to_sharegpt_strips_injected_system_prompt():
    result = chatml_to_sharegpt_entry(
        {
            "messages": [
                {"role": "system", "content": SHAREGPT_INTERNAL_SYSTEM_PROMPT},
                {"role": "user", "content": "Hi"},
                {"role": "assistant", "content": "Hello"},
            ],
            "tags": ["greeting"],
        }
    )

    assert result.entry["conversations"] == [
        {"from": "human", "value": "Hi"},
        {"from": "gpt", "value": "Hello"},
    ]


def test_chatml_to_sharegpt_can_strip_metadata_for_clean_export():
    result = chatml_to_sharegpt_entry(_chatml_entry(), include_metadata=False)

    assert result.entry == {
        "conversations": [
            {"from": "system", "value": "System"},
            {"from": "human", "value": "Hi"},
            {"from": "gpt", "value": "Hello"},
        ]
    }


def test_chatml_to_sharegpt_reports_missing_messages_and_unknown_roles():
    result = chatml_to_sharegpt_entry(
        {
            "messages": [
                {"role": "tool", "content": "Nope"},
                {"role": "user"},
                {"content": "Missing role"},
                "bad",
            ]
        }
    )

    assert result.entry["conversations"] == [{"from": "human", "value": ""}]
    warnings = "\n".join(result.diagnostics.warnings)
    assert "unknown role" in warnings
    assert "missing a content field" in warnings
    assert "missing a role field" in warnings
    assert "not an object" in warnings


def test_sharegpt_import_export_roundtrip_strips_injected_system_and_keeps_metadata():
    imported = sharegpt_to_chatml_entry(
        {
            "conversations": [
                {"from": "human", "value": "Hi"},
                {"from": "gpt", "value": "Hello"},
            ],
            "tags": ["greeting"],
            "source": "sharegpt",
        }
    ).entry

    exported = chatml_to_sharegpt_entry(imported).entry

    assert exported == {
        "conversations": [
            {"from": "human", "value": "Hi"},
            {"from": "gpt", "value": "Hello"},
        ],
        "tags": ["greeting"],
        "source": "sharegpt",
    }


def test_convert_records_to_chatml_batch_handles_chatml_and_sharegpt():
    chatml = convert_records_to_chatml([_chatml_entry()], source_format=FORMAT_CHATML)
    sharegpt = convert_records_to_chatml([_sharegpt_entry()], source_format=FORMAT_SHAREGPT)

    assert chatml.entries == [_chatml_entry()]
    assert chatml.already_target_count == 1
    assert sharegpt.entries[0]["messages"][1:] == [
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "Hello"},
    ]
    assert sharegpt.converted_count == 1


def test_convert_records_to_chatml_reports_unsupported_source_format():
    result = convert_records_to_chatml(
        [{"anything": True}],
        source_format=FORMAT_UNKNOWN,
    )

    assert result.entries == [{"anything": True}]
    assert result.warnings == [f"Unsupported source format: {FORMAT_UNKNOWN}"]


def test_convert_chatml_to_format_batch_handles_chatml_sharegpt_and_unknown():
    chatml = convert_chatml_to_format([_chatml_entry()], target_format=FORMAT_CHATML)
    sharegpt = convert_chatml_to_format(
        [_chatml_entry()],
        target_format=FORMAT_SHAREGPT,
        include_metadata=False,
    )
    unknown = convert_chatml_to_format([_chatml_entry()], target_format=FORMAT_UNKNOWN)

    assert chatml.entries == [_chatml_entry()]
    assert chatml.already_target_count == 1
    assert sharegpt.entries == [
        {
            "conversations": [
                {"from": "system", "value": "System"},
                {"from": "human", "value": "Hi"},
                {"from": "gpt", "value": "Hello"},
            ]
        }
    ]
    assert sharegpt.converted_count == 1
    assert unknown.warnings == [f"Unsupported target format: {FORMAT_UNKNOWN}"]
