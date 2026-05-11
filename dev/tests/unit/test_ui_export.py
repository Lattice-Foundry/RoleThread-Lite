from core.format_conversion import (
    FORMAT_CHATML,
    FORMAT_SHAREGPT,
    SHAREGPT_INTERNAL_SYSTEM_PROMPT,
)
from core.loreforge_meta import LOREFORGE_META_KEY
from ui.ui_export import _prepare_export_entries


def _entry():
    return {
        "messages": [
            {"role": "system", "content": SHAREGPT_INTERNAL_SYSTEM_PROMPT},
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello"},
        ],
        "tags": ["slow_burn"],
        "source": "fixture",
    }


def test_prepare_export_entries_preserves_chatml_behavior():
    entries = [_entry()]

    exported = _prepare_export_entries(
        entries,
        export_format=FORMAT_CHATML,
        clean_export=False,
    )

    assert exported is entries
    assert exported == entries


def test_prepare_export_entries_cleans_chatml_metadata():
    exported = _prepare_export_entries(
        [_entry()],
        export_format=FORMAT_CHATML,
        clean_export=True,
    )

    assert exported == [{"messages": _entry()["messages"]}]


def test_prepare_export_entries_clean_export_strips_loreforge_metadata():
    entry = {
        **_entry(),
        LOREFORGE_META_KEY: {
            "version": "0.1.0",
            "native": True,
            "validated_at": "2026-05-11T12:00:00Z",
        },
    }

    chatml = _prepare_export_entries(
        [entry],
        export_format=FORMAT_CHATML,
        clean_export=True,
    )
    sharegpt = _prepare_export_entries(
        [entry],
        export_format=FORMAT_SHAREGPT,
        clean_export=True,
    )

    assert LOREFORGE_META_KEY not in chatml[0]
    assert LOREFORGE_META_KEY not in sharegpt[0]


def test_prepare_export_entries_converts_sharegpt_with_metadata():
    exported = _prepare_export_entries(
        [_entry()],
        export_format=FORMAT_SHAREGPT,
        clean_export=False,
    )

    assert exported == [
        {
            "conversations": [
                {"from": "human", "value": "Hi"},
                {"from": "gpt", "value": "Hello"},
            ],
            "tags": ["slow_burn"],
            "source": "fixture",
        }
    ]


def test_prepare_export_entries_cleans_sharegpt_metadata():
    exported = _prepare_export_entries(
        [_entry()],
        export_format=FORMAT_SHAREGPT,
        clean_export=True,
    )

    assert exported == [
        {
            "conversations": [
                {"from": "human", "value": "Hi"},
                {"from": "gpt", "value": "Hello"},
            ],
        }
    ]
