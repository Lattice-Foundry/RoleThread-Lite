from core.format_conversion import (
    FORMAT_CHATML,
    FORMAT_SHAREGPT,
    SHAREGPT_INTERNAL_SYSTEM_PROMPT,
)
from core.loreforge_meta import LOREFORGE_META_KEY
from ui.export_scope import scoped_export_pairs
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
            "version": "0.10.0",
            "native": True,
            "validated_at": "2026-05-11T12:00:00Z",
            "entry_uuid": "entry-uuid-1",
            "dataset_uuid": "dataset-uuid-1",
        },
        "character_notes": {"scott": "speaker metadata"},
        "custom_metadata": "remove me",
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
    assert chatml == [{"messages": entry["messages"]}]
    assert sharegpt == [
        {
            "conversations": [
                {"from": "human", "value": "Hi"},
                {"from": "gpt", "value": "Hello"},
            ],
        }
    ]


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


def test_scoped_export_pairs_prefers_selected_entries_in_dataset_order():
    pairs = [
        ("first", {"id": 1}),
        ("second", {"id": 2}),
        ("third", {"id": 3}),
    ]

    scoped, label = scoped_export_pairs(
        pairs,
        selected_uuids={"third", "first"},
        filtered_pairs=[("second", {"id": 2})],
        filters_active=True,
    )

    assert scoped == [("first", {"id": 1}), ("third", {"id": 3})]
    assert label == "selected entries"


def test_scoped_export_pairs_uses_filtered_entries_when_no_selection():
    pairs = [
        ("first", {"id": 1}),
        ("second", {"id": 2}),
    ]

    scoped, label = scoped_export_pairs(
        pairs,
        selected_uuids=set(),
        filtered_pairs=[("second", {"id": 2})],
        filters_active=True,
    )

    assert scoped == [("second", {"id": 2})]
    assert label == "filtered entries"
