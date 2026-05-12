from ui.entry_edit_helpers import (
    has_entry_notification_issue,
    requires_full_edit_for_quick_edit,
)


def _entry(messages=None, tags=None):
    return {
        "messages": messages
        if messages is not None
        else [
            {"role": "system", "content": "System"},
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello"},
        ],
        "tags": [] if tags is None else tags,
    }


def test_quick_edit_requires_full_edit_for_insufficient_messages():
    entry = _entry(messages=[
        {"role": "system", "content": "System"},
        {"role": "user", "content": "Hi"},
    ])

    assert requires_full_edit_for_quick_edit(entry) is True


def test_quick_edit_requires_full_edit_for_empty_system_prompt():
    entry = _entry(messages=[
        {"role": "system", "content": "   "},
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "Hello"},
    ])

    assert requires_full_edit_for_quick_edit(entry) is True


def test_quick_edit_requires_full_edit_for_missing_tags():
    entry = {"messages": _entry()["messages"]}

    assert requires_full_edit_for_quick_edit(entry) is True


def test_quick_edit_allowed_for_dirty_tags():
    assert requires_full_edit_for_quick_edit(_entry(tags=["good", 7, ""])) is False


def test_quick_edit_allowed_for_known_role_variants():
    entry = _entry(messages=[
        {"role": "System", "content": "System"},
        {"role": "human", "content": "Hi"},
        {"role": "GPT", "content": "Hello"},
    ])

    assert requires_full_edit_for_quick_edit(entry) is False


def test_quick_edit_requires_full_edit_for_wrong_system_position_role():
    entry = _entry(messages=[
        {"role": "GPT", "content": "System-ish"},
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "Hello"},
    ])

    assert requires_full_edit_for_quick_edit(entry) is True


def test_quick_edit_allows_system_case_variant():
    entry = _entry(messages=[
        {"role": "System", "content": "System"},
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "Hello"},
    ])

    assert requires_full_edit_for_quick_edit(entry) is False


def test_quick_edit_requires_full_edit_for_missing_messages():
    assert requires_full_edit_for_quick_edit({"tags": []}) is True


def test_quick_edit_requires_full_edit_for_malformed_messages():
    assert requires_full_edit_for_quick_edit({"messages": "bad", "tags": []}) is True


def test_quick_edit_requires_full_edit_for_empty_messages():
    assert requires_full_edit_for_quick_edit({"messages": [], "tags": []}) is True


def test_quick_edit_allows_custom_roles_for_editor_visibility():
    entry = _entry(messages=[
        {"role": "system", "content": "System"},
        {"role": "narrator", "content": "Hi"},
        {"role": "assistant", "content": "Hello"},
    ])

    assert requires_full_edit_for_quick_edit(entry) is False


def test_notification_issue_detects_auto_fixable_role_variants():
    entry = _entry(messages=[
        {"role": "System", "content": "System"},
        {"role": "User", "content": "Hi"},
        {"role": "Assistant", "content": "Hello"},
    ])

    assert has_entry_notification_issue(entry, errors=[]) is True


def test_notification_issue_detects_validation_errors():
    assert has_entry_notification_issue({"tags": []}, errors=["Missing messages"]) is True
