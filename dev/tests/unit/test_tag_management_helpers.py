from ui.tag_management_helpers import (
    selected_assignable_archived_slugs,
    validate_pending_archived_assignment,
    validate_pending_category_delete,
    validate_pending_category_rename,
    validate_pending_tag_delete,
    validate_pending_tag_edit,
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


def test_pending_tag_edit_is_valid_only_for_current_custom_row_and_category():
    pending = {
        "old_slug": "followup_question",
        "old_display_name": "Followup Question",
        "new_slug": "follow_up_question",
        "new_display_name": "Follow Up Question",
        "category_slug": "behavior",
    }

    assert validate_pending_tag_edit(
        pending_edit=pending,
        current_edit_slug="followup_question",
        active_custom_slugs={"followup_question"},
        active_category_slugs={"behavior"},
    ) == pending
    assert validate_pending_tag_edit(
        pending_edit=pending,
        current_edit_slug=None,
        active_custom_slugs={"followup_question"},
        active_category_slugs={"behavior"},
    ) is None
    assert validate_pending_tag_edit(
        pending_edit=pending,
        current_edit_slug="other_tag",
        active_custom_slugs={"followup_question"},
        active_category_slugs={"behavior"},
    ) is None
    assert validate_pending_tag_edit(
        pending_edit=pending,
        current_edit_slug="followup_question",
        active_custom_slugs=set(),
        active_category_slugs={"behavior"},
    ) is None
    assert validate_pending_tag_edit(
        pending_edit=pending,
        current_edit_slug="followup_question",
        active_custom_slugs={"followup_question"},
        active_category_slugs={"scene"},
    ) is None


def test_pending_category_rename_is_valid_only_for_current_custom_category():
    pending = {
        "old_slug": "story_shape",
        "old_display_name": "Story Shape",
        "new_slug": "narrative_shape",
        "new_display_name": "Narrative Shape",
    }

    assert validate_pending_category_rename(
        pending_rename=pending,
        current_rename_slug="story_shape",
        active_custom_category_slugs={"story_shape"},
    ) == pending
    assert validate_pending_category_rename(
        pending_rename=pending,
        current_rename_slug=None,
        active_custom_category_slugs={"story_shape"},
    ) is None
    assert validate_pending_category_rename(
        pending_rename=pending,
        current_rename_slug="other",
        active_custom_category_slugs={"story_shape"},
    ) is None
    assert validate_pending_category_rename(
        pending_rename=pending,
        current_rename_slug="story_shape",
        active_custom_category_slugs=set(),
    ) is None


def test_pending_category_delete_is_valid_only_for_current_empty_custom_category():
    pending = {
        "category_slug": "story_shape",
        "display_name": "Story Shape",
    }

    assert validate_pending_category_delete(
        pending_delete=pending,
        active_empty_custom_category_slugs={"story_shape"},
    ) == pending
    assert validate_pending_category_delete(
        pending_delete=pending,
        active_empty_custom_category_slugs=set(),
    ) is None
    assert validate_pending_category_delete(
        pending_delete={"category_slug": "story_shape"},
        active_empty_custom_category_slugs={"story_shape"},
    ) is None


def test_pending_tag_delete_is_valid_only_for_current_custom_tag():
    pending = {
        "tag_slug": "slow_burn",
        "display_name": "Slow Burn",
        "usage_count": 2,
    }

    assert validate_pending_tag_delete(
        pending_delete=pending,
        active_custom_slugs={"slow_burn"},
    ) == pending
    assert validate_pending_tag_delete(
        pending_delete=pending,
        active_custom_slugs=set(),
    ) is None
    assert validate_pending_tag_delete(
        pending_delete={"tag_slug": "slow_burn"},
        active_custom_slugs={"slow_burn"},
    ) is None
