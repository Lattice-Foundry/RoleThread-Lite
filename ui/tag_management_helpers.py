"""Pure helpers for Tag Management UI state."""


def selected_assignable_archived_slugs(
    *,
    archived_tags: list[dict],
    selected_by_slug: dict[str, bool],
) -> list[str]:
    """Return selected slugs that are still assignable archived rows."""
    assignable_slugs = {
        tag["slug"] for tag in archived_tags if tag.get("can_assign_to_category")
    }
    return [
        slug
        for slug, selected in selected_by_slug.items()
        if selected and slug in assignable_slugs
    ]


def validate_pending_archived_assignment(
    *,
    pending_assignment: dict | None,
    selected_slugs: list[str],
    category_slugs: set[str],
) -> dict | None:
    """Return pending assignment only while current UI state still matches it."""
    if not pending_assignment:
        return None

    pending_slugs = pending_assignment.get("tag_slugs")
    pending_category = pending_assignment.get("category_slug")
    if not isinstance(pending_slugs, list) or not pending_slugs:
        return None
    if pending_slugs != selected_slugs:
        return None
    if pending_category not in category_slugs:
        return None

    return pending_assignment
