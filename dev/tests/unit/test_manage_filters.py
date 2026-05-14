from core.entry_search import (
    EntrySearchOptions,
    SEARCH_MATCH_CONTAINS,
    SEARCH_SCOPE_ASSISTANT,
    SEARCH_SCOPE_USER,
)
from ui.browser_helpers import MATCH_MODE_ANY, MATCH_MODE_EXACT, calculate_pagination, slice_visible_pairs
from ui.manage.filters import apply_manage_entry_filters, apply_stats_uuid_filter


def _entry(*, tags=None, user="", assistant=""):
    return {
        "messages": [
            {"role": "system", "content": "System"},
            {"role": "user", "content": user},
            {"role": "assistant", "content": assistant},
        ],
        "tags": tags or [],
    }


def test_manage_search_applies_after_tag_filtering():
    pairs = [
        ("alpha-no-hit", _entry(tags=["alpha"], user="plain text")),
        ("beta-hit", _entry(tags=["beta"], user="lantern text")),
        ("alpha-hit", _entry(tags=["alpha"], user="lantern text")),
    ]

    matches = apply_manage_entry_filters(
        pairs,
        filter_tags=["alpha"],
        tag_match_mode=MATCH_MODE_ANY,
        search_query="lantern",
        search_options=EntrySearchOptions(),
    )

    assert [entry_uuid for entry_uuid, _entry in matches] == ["alpha-hit"]


def test_manage_blank_search_preserves_existing_tag_filter_behavior():
    pairs = [
        ("alpha", _entry(tags=["alpha"], user="first")),
        ("beta", _entry(tags=["beta"], user="second")),
        ("both", _entry(tags=["alpha", "beta"], user="third")),
    ]

    matches = apply_manage_entry_filters(
        pairs,
        filter_tags=["alpha"],
        tag_match_mode=MATCH_MODE_ANY,
        search_query=" ",
        search_options=EntrySearchOptions(),
    )

    assert [entry_uuid for entry_uuid, _entry in matches] == ["alpha", "both"]


def test_manage_whitespace_search_is_inactive_even_with_no_scopes():
    pairs = [
        ("alpha", _entry(tags=["alpha"], user="first")),
        ("beta", _entry(tags=["beta"], user="second")),
    ]

    matches = apply_manage_entry_filters(
        pairs,
        filter_tags=["alpha"],
        tag_match_mode=MATCH_MODE_ANY,
        search_query="   ",
        search_options=EntrySearchOptions(scopes=()),
    )

    assert [entry_uuid for entry_uuid, _entry in matches] == ["alpha"]


def test_manage_active_search_with_all_scopes_disabled_matches_nothing():
    pairs = [("entry", _entry(user="needle"))]

    matches = apply_manage_entry_filters(
        pairs,
        filter_tags=[],
        tag_match_mode=MATCH_MODE_ANY,
        search_query="needle",
        search_options=EntrySearchOptions(scopes=()),
    )

    assert matches == []


def test_manage_search_preserves_tag_exact_match_mode():
    pairs = [
        ("alpha", _entry(tags=["alpha"], user="lantern")),
        ("alpha-beta", _entry(tags=["alpha", "beta"], user="lantern")),
    ]

    matches = apply_manage_entry_filters(
        pairs,
        filter_tags=["alpha"],
        tag_match_mode=MATCH_MODE_EXACT,
        search_query="lantern",
        search_options=EntrySearchOptions(),
    )

    assert [entry_uuid for entry_uuid, _entry in matches] == ["alpha"]


def test_manage_pagination_applies_after_search():
    pairs = [
        (f"entry-{index}", _entry(user=f"needle {index}" if index >= 5 else "plain"))
        for index in range(12)
    ]

    matches = apply_manage_entry_filters(
        pairs,
        filter_tags=[],
        tag_match_mode=MATCH_MODE_ANY,
        search_query="needle",
        search_options=EntrySearchOptions(),
    )
    pagination = calculate_pagination(
        total_items=len(matches),
        requested_page=1,
        per_page_setting=3,
    )
    visible = slice_visible_pairs(matches, pagination)

    assert len(matches) == 7
    assert [entry_uuid for entry_uuid, _entry in visible] == [
        "entry-8",
        "entry-9",
        "entry-10",
    ]


def test_manage_search_scans_entries_outside_current_page():
    pairs = [
        (f"entry-{index}", _entry(user="needle" if index == 29 else "plain"))
        for index in range(30)
    ]

    matches = apply_manage_entry_filters(
        pairs,
        filter_tags=[],
        tag_match_mode=MATCH_MODE_ANY,
        search_query="needle",
        search_options=EntrySearchOptions(),
    )

    assert [entry_uuid for entry_uuid, _entry in matches] == ["entry-29"]


def test_manage_search_preserves_input_order():
    pairs = [
        ("third", _entry(user="needle three")),
        ("first", _entry(user="needle one")),
        ("skip", _entry(user="plain")),
        ("second", _entry(assistant="needle two")),
    ]

    matches = apply_manage_entry_filters(
        pairs,
        filter_tags=[],
        tag_match_mode=MATCH_MODE_ANY,
        search_query="needle",
        search_options=EntrySearchOptions(
            scopes=(SEARCH_SCOPE_USER, SEARCH_SCOPE_ASSISTANT),
            match_mode=SEARCH_MATCH_CONTAINS,
        ),
    )

    assert [entry_uuid for entry_uuid, _entry in matches] == [
        "third",
        "first",
        "second",
    ]


def test_manage_search_no_results_is_safe():
    pairs = [("entry", _entry(tags=["alpha"], user="plain"))]

    matches = apply_manage_entry_filters(
        pairs,
        filter_tags=["alpha"],
        tag_match_mode=MATCH_MODE_ANY,
        search_query="missing",
        search_options=EntrySearchOptions(),
    )

    assert matches == []


def test_stats_uuid_filter_limits_entries_and_preserves_order():
    pairs = [
        ("first", _entry(user="one")),
        ("second", _entry(user="two")),
        ("third", _entry(user="three")),
    ]

    matches = apply_stats_uuid_filter(pairs, {"third", "first"})

    assert [entry_uuid for entry_uuid, _entry in matches] == ["first", "third"]


def test_stats_uuid_filter_composes_after_tag_and_search_filters():
    pairs = [
        ("alpha-hit", _entry(tags=["alpha"], user="needle")),
        ("alpha-other", _entry(tags=["alpha"], user="needle")),
        ("beta-hit", _entry(tags=["beta"], user="needle")),
    ]

    matches = apply_manage_entry_filters(
        pairs,
        filter_tags=["alpha"],
        tag_match_mode=MATCH_MODE_ANY,
        search_query="needle",
        search_options=EntrySearchOptions(),
        stats_filter_uuids={"alpha-other", "beta-hit"},
    )

    assert [entry_uuid for entry_uuid, _entry in matches] == ["alpha-other"]
