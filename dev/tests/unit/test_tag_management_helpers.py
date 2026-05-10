from ui.tag_management_helpers import (
    selected_assignable_archived_slugs,
    validate_pending_archived_assignment,
    validate_pending_tag_rename,
)


def test_selected_assignable_archived_slugs_filters_stale_and_deleted_rows():
    archived_tags = [
        {"slug": "anal_plugs", "can_assign_to_category": True},
        {"slug": "deleted_tag", "can_assign_to_category": False},
    ]

    selected = selected_assignable_archived_slugs(
        archived_tags=archived_tags,
        selected_by_slug={
            "anal_plugs": True,
            "deleted_tag": True,
            "stale_tag": True,
        },
    )

    assert selected == ["anal_plugs"]


def test_pending_assignment_is_valid_only_while_selection_and_category_match():
    pending = {
        "tag_slugs": ["anal_plugs"],
        "category_slug": "behavior",
        "category_name": "Behavior",
    }

    assert validate_pending_archived_assignment(
        pending_assignment=pending,
        selected_slugs=["anal_plugs"],
        category_slugs={"behavior"},
    ) == pending
    assert validate_pending_archived_assignment(
        pending_assignment=pending,
        selected_slugs=[],
        category_slugs={"behavior"},
    ) is None
    assert validate_pending_archived_assignment(
        pending_assignment=pending,
        selected_slugs=["other_tag"],
        category_slugs={"behavior"},
    ) is None
    assert validate_pending_archived_assignment(
        pending_assignment=pending,
        selected_slugs=["anal_plugs"],
        category_slugs={"tone"},
    ) is None


def test_pending_tag_rename_is_valid_only_for_current_custom_row():
    pending = {
        "old_slug": "followup_question",
        "old_display_name": "Followup Question",
        "new_slug": "follow_up_question",
        "new_display_name": "Follow Up Question",
    }

    assert validate_pending_tag_rename(
        pending_rename=pending,
        current_rename_slug="followup_question",
        active_custom_slugs={"followup_question"},
    ) == pending
    assert validate_pending_tag_rename(
        pending_rename=pending,
        current_rename_slug=None,
        active_custom_slugs={"followup_question"},
    ) is None
    assert validate_pending_tag_rename(
        pending_rename=pending,
        current_rename_slug="other_tag",
        active_custom_slugs={"followup_question"},
    ) is None
    assert validate_pending_tag_rename(
        pending_rename=pending,
        current_rename_slug="followup_question",
        active_custom_slugs=set(),
    ) is None
