from ui.browser_helpers import (
    SHOW_ALL,
    build_filter_tag_state,
    calculate_pagination,
    format_browser_status_caption,
    format_entry_summary_label,
    normalize_untagged_selection,
    slice_visible_pairs,
)


def _entry(*, tags=None, messages=None):
    return {
        "messages": messages
        or [
            {"role": "system", "content": "System prompt"},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ],
        "tags": tags or [],
    }


def test_calculate_pagination_first_page():
    result = calculate_pagination(
        total_items=55,
        requested_page=0,
        per_page_setting=25,
    )

    assert result.page == 0
    assert result.total_pages == 3
    assert result.per_page == 25
    assert result.start == 0
    assert result.end == 25
    assert result.is_show_all is False


def test_calculate_pagination_clamps_high_page_to_last_page():
    result = calculate_pagination(
        total_items=55,
        requested_page=99,
        per_page_setting=25,
    )

    assert result.page == 2
    assert result.start == 50
    assert result.end == 55


def test_calculate_pagination_clamps_negative_page_to_zero():
    result = calculate_pagination(
        total_items=55,
        requested_page=-4,
        per_page_setting=25,
    )

    assert result.page == 0
    assert result.start == 0
    assert result.end == 25


def test_calculate_pagination_show_all_returns_full_range():
    result = calculate_pagination(
        total_items=55,
        requested_page=3,
        per_page_setting=SHOW_ALL,
    )

    assert result.page == 0
    assert result.total_pages == 1
    assert result.per_page == 55
    assert result.start == 0
    assert result.end == 55
    assert result.is_show_all is True


def test_calculate_pagination_zero_items_is_safe():
    result = calculate_pagination(
        total_items=0,
        requested_page=2,
        per_page_setting=25,
    )

    assert result.page == 0
    assert result.total_pages == 1
    assert result.start == 0
    assert result.end == 0


def test_slice_visible_pairs_returns_page_subset():
    pairs = [(f"id-{index}", {"value": index}) for index in range(10)]
    pagination = calculate_pagination(
        total_items=len(pairs),
        requested_page=1,
        per_page_setting=4,
    )

    visible = slice_visible_pairs(pairs, pagination)

    assert visible == pairs[4:8]


def test_format_browser_status_caption_unfiltered_without_selection():
    caption = format_browser_status_caption(
        start=0,
        end=25,
        total_filtered=300,
        total_all=300,
        filtered=False,
    )

    assert caption == "Showing 1\u201325 of 300 entries"


def test_format_browser_status_caption_filtered_without_selection():
    caption = format_browser_status_caption(
        start=0,
        end=25,
        total_filtered=140,
        total_all=300,
        filtered=True,
    )

    assert caption == "Showing 1\u201325 of 140 filtered entries (300 total)"


def test_format_browser_status_caption_unfiltered_with_selection():
    caption = format_browser_status_caption(
        start=0,
        end=25,
        total_filtered=300,
        total_all=300,
        filtered=False,
        selected_count=3,
    )

    assert caption == "Showing 1\u201325 of 300 entries | 3 of 300 selected"


def test_format_browser_status_caption_filtered_with_selection():
    caption = format_browser_status_caption(
        start=0,
        end=25,
        total_filtered=140,
        total_all=300,
        filtered=True,
        selected_count=3,
    )

    assert (
        caption
        == "Showing 1\u201325 of 140 filtered entries (300 total) | 3 of 140 selected"
    )


def test_normalize_untagged_selection_strips_untagged_from_select_all():
    selected = normalize_untagged_selection(
        selected_tags=["alpha", "beta", "__untagged__"],
        available_tags=["alpha", "beta", "__untagged__"],
    )

    assert selected == ["alpha", "beta"]


def test_normalize_untagged_selection_keeps_untagged_alone():
    selected = normalize_untagged_selection(
        selected_tags=["__untagged__"],
        available_tags=["alpha", "beta", "__untagged__"],
    )

    assert selected == ["__untagged__"]


def test_normalize_untagged_selection_keeps_partial_real_tags_with_untagged():
    selected = normalize_untagged_selection(
        selected_tags=["alpha", "__untagged__"],
        available_tags=["alpha", "beta", "__untagged__"],
    )

    assert selected == ["alpha", "__untagged__"]


def test_build_filter_tag_state_clamps_stale_selected_tags():
    state = build_filter_tag_state(
        entries=[_entry(tags=["alpha"])],
        selected_tags=["alpha", "stale"],
        only_used_tags=False,
        all_known_tags=["alpha", "beta"],
    )

    assert state.available_tags == ["alpha", "beta", "__untagged__"]
    assert state.clamped_selected_tags == ["alpha"]
    assert state.selected_tags_changed is True


def test_build_filter_tag_state_preserves_unknown_used_tags_when_only_used():
    state = build_filter_tag_state(
        entries=[
            _entry(tags=["alpha"]),
            _entry(tags=["mystery"]),
            _entry(tags=[]),
        ],
        selected_tags=["alpha", "mystery"],
        only_used_tags=True,
        all_known_tags=["alpha", "beta"],
    )

    assert state.available_tags == ["alpha", "mystery", "__untagged__"]
    assert state.clamped_selected_tags == ["alpha", "mystery"]
    assert state.selected_tags_changed is False


def test_format_entry_summary_label_for_tagged_entry():
    label = format_entry_summary_label(
        display_index=2,
        entry=_entry(tags=["alpha", "beta"]),
        dataset_format="chatml",
    )

    assert label == "Entry 3 | FORMAT: chatml | TAGS: alpha, beta | EXCHANGES: 1"


def test_format_entry_summary_label_for_untagged_entry():
    label = format_entry_summary_label(
        display_index=0,
        entry=_entry(tags=[]),
        dataset_format="sharegpt",
    )

    assert label == "Entry 1 | FORMAT: sharegpt | TAGS: untagged | EXCHANGES: 1"


def test_format_entry_summary_label_appends_warning_marker_for_errors():
    label = format_entry_summary_label(
        display_index=0,
        entry=_entry(tags=["alpha"]),
        dataset_format="chatml",
        errors=["Missing assistant message"],
    )

    assert label.endswith(" \u26a0\ufe0f")
