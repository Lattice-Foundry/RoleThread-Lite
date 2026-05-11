"""Pure helpers for dataset browser pages.

These helpers support Manage Dataset and Edit Entries browser mechanics without
importing Streamlit or owning page-specific selection/edit behavior.
"""
from dataclasses import dataclass

from core.dataset import count_exchanges, get_available_filter_tags, get_entry_tags
from core.tag_normalization import normalize_tag

SHOW_ALL = "Show All"
SHOW_ALL_MAX_ENTRIES = 1000
DEFAULT_PAGE_SIZE = 25
PAGE_SIZE_OPTIONS = [10, DEFAULT_PAGE_SIZE, 50, 100, 500, SHOW_ALL]
MATCH_MODE_ANY = "Any selected tags"
MATCH_MODE_ALL = "All selected tags"
MATCH_MODE_EXACT = "Exact match"
MATCH_MODE_OPTIONS = [
    MATCH_MODE_ANY,
    MATCH_MODE_ALL,
    MATCH_MODE_EXACT,
]


@dataclass(frozen=True)
class PaginationResult:
    """Calculated pagination state for a filtered browser list."""

    total_items: int
    page: int
    total_pages: int
    per_page: int
    start: int
    end: int
    is_show_all: bool

    @property
    def last_page(self) -> int:
        """Return the zero-based final page index."""
        return max(0, self.total_pages - 1)

    @property
    def is_show_all_capped(self) -> bool:
        """Return True when Show All is capped below the filtered total."""
        return self.is_show_all and self.end < self.total_items


@dataclass(frozen=True)
class FilterTagState:
    """Prepared tag filter options and clamped selection."""

    available_tags: list[str]
    clamped_selected_tags: list[str]
    selected_tags_changed: bool


def calculate_pagination(
    *,
    total_items: int,
    requested_page: int,
    per_page_setting: int | str,
) -> PaginationResult:
    """Return clamped pagination indexes for a filtered list."""
    total_items = max(0, total_items)
    is_show_all = per_page_setting == SHOW_ALL

    if is_show_all:
        per_page = min(total_items, SHOW_ALL_MAX_ENTRIES)
        total_pages = 1
        page = 0
        return PaginationResult(
            total_items=total_items,
            page=page,
            total_pages=total_pages,
            per_page=per_page,
            start=0,
            end=per_page,
            is_show_all=True,
        )

    per_page = per_page_setting if isinstance(per_page_setting, int) else DEFAULT_PAGE_SIZE
    per_page = max(1, per_page)
    total_pages = max(1, (total_items + per_page - 1) // per_page)
    page = min(max(0, requested_page), total_pages - 1)
    start = page * per_page
    end = min(start + per_page, total_items)
    return PaginationResult(
        total_items=total_items,
        page=page,
        total_pages=total_pages,
        per_page=per_page,
        start=start,
        end=end,
        is_show_all=False,
    )


def slice_visible_pairs(
    filtered_pairs: list[tuple[str, dict]],
    pagination: PaginationResult,
) -> list[tuple[str, dict]]:
    """Return the current visible pair slice."""
    return filtered_pairs[pagination.start:pagination.end]


def format_entry_summary_label(
    *,
    display_index: int,
    entry: dict,
    errors: list[str] | None = None,
    tag_label_map: dict[str, str] | None = None,
) -> str:
    """Format the browser expander label for one entry."""
    entry_tags = get_entry_tags(entry)
    tag_part = (
        ", ".join(_format_tag_display_name(tag, tag_label_map) for tag in entry_tags)
        if entry_tags
        else "Untagged"
    )
    exchange_count = count_exchanges(entry)
    label = (
        f"Entry {display_index + 1} | TAGS: {tag_part} | "
        f"EXCHANGES: {exchange_count}"
    )
    if errors:
        label += " \u26a0\ufe0f"
    return label


def _format_tag_display_name(
    tag_slug: str,
    tag_label_map: dict[str, str] | None,
) -> str:
    """Return a human-readable tag label for browser summaries."""
    if tag_label_map and tag_slug in tag_label_map:
        mapped = tag_label_map[tag_slug]
        if " / " in mapped:
            return mapped.rsplit(" / ", 1)[-1]
        return mapped
    return normalize_tag(tag_slug).display_name


def format_browser_status_caption(
    *,
    start: int,
    end: int,
    total_filtered: int,
    total_all: int,
    filtered: bool,
    selected_count: int | None = None,
) -> str:
    """Format the browser status caption text."""
    display_start = 0 if total_filtered == 0 else start + 1
    if filtered:
        caption = (
            f"Showing {display_start}\u2013{end} of {total_filtered} "
            f"filtered entries ({total_all} total)"
        )
        selected_total = total_filtered
    else:
        caption = f"Showing {display_start}\u2013{end} of {total_all} entries"
        selected_total = total_all

    if selected_count is not None:
        caption += f" | {selected_count} of {selected_total} selected"
    return caption


def build_filter_tag_state(
    *,
    entries: list[dict],
    selected_tags: list[str],
    only_used_tags: bool,
    all_known_tags: list[str],
    untagged_key: str = "__untagged__",
) -> FilterTagState:
    """Return available filter tags and selected tags clamped to those options."""
    available_tags = get_available_filter_tags(
        entries,
        only_used=only_used_tags,
        untagged_key=untagged_key,
        all_known_tags=all_known_tags,
    )
    clamped_selected_tags = [tag for tag in selected_tags if tag in available_tags]
    return FilterTagState(
        available_tags=available_tags,
        clamped_selected_tags=clamped_selected_tags,
        selected_tags_changed=clamped_selected_tags != selected_tags,
    )


def normalize_untagged_selection(
    *,
    selected_tags: list[str],
    available_tags: list[str],
    untagged_key: str = "__untagged__",
) -> list[str]:
    """Strip untagged when select-all includes every real tag."""
    available_real = [tag for tag in available_tags if tag != untagged_key]
    selected_real = [tag for tag in selected_tags if tag != untagged_key]
    if (
        untagged_key in selected_tags
        and available_real
        and set(selected_real) == set(available_real)
    ):
        return selected_real
    return selected_tags
