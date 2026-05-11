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


def validate_pending_tag_edit(
    *,
    pending_edit: dict | None,
    current_edit_slug: str | None,
    active_custom_slugs: set[str],
    active_category_slugs: set[str],
) -> dict | None:
    """Return pending edit only while it still matches the active edit row."""
    if not pending_edit:
        return None

    old_slug = pending_edit.get("old_slug")
    new_slug = pending_edit.get("new_slug")
    new_display_name = pending_edit.get("new_display_name")
    category_slug = pending_edit.get("category_slug")
    required_values = [old_slug, new_slug, new_display_name, category_slug]
    if not all(isinstance(value, str) and value for value in required_values):
        return None
    if old_slug != current_edit_slug:
        return None
    if old_slug not in active_custom_slugs:
        return None
    if category_slug not in active_category_slugs:
        return None

    return pending_edit


validate_pending_tag_rename = validate_pending_tag_edit


def validate_pending_tag_delete(
    *,
    pending_delete: dict | None,
    active_custom_slugs: set[str],
) -> dict | None:
    """Return pending delete only while its custom active tag still exists."""
    if not pending_delete:
        return None

    tag_slug = pending_delete.get("tag_slug")
    display_name = pending_delete.get("display_name")
    if not isinstance(tag_slug, str) or not tag_slug:
        return None
    if not isinstance(display_name, str) or not display_name:
        return None
    if tag_slug not in active_custom_slugs:
        return None

    return pending_delete


def validate_pending_category_rename(
    *,
    pending_rename: dict | None,
    current_rename_slug: str | None,
    active_custom_category_slugs: set[str],
) -> dict | None:
    """Return pending category rename only while its custom category still exists."""
    if not pending_rename:
        return None

    old_slug = pending_rename.get("old_slug")
    new_slug = pending_rename.get("new_slug")
    new_display_name = pending_rename.get("new_display_name")
    required_values = [old_slug, new_slug, new_display_name]
    if not all(isinstance(value, str) and value for value in required_values):
        return None
    if old_slug != current_rename_slug:
        return None
    if old_slug not in active_custom_category_slugs:
        return None

    return pending_rename
