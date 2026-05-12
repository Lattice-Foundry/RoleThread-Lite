from ui.entry_edit_helpers import requires_full_edit_for_quick_edit


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


def test_quick_edit_allowed_for_content_only_issues():
    entry = _entry(messages=[
        {"role": "system", "content": "System"},
        {"role": "user", "content": "Hi"},
    ])

    assert requires_full_edit_for_quick_edit(entry) is False


def test_quick_edit_requires_full_edit_for_missing_messages():
    assert requires_full_edit_for_quick_edit({"tags": []}) is True


def test_quick_edit_requires_full_edit_for_malformed_messages():
    assert requires_full_edit_for_quick_edit({"messages": "bad", "tags": []}) is True


def test_quick_edit_requires_full_edit_for_non_text_tags():
    assert requires_full_edit_for_quick_edit(_entry(tags=["good", 7])) is True


def test_quick_edit_requires_full_edit_for_wrong_roles():
    entry = _entry(messages=[
        {"role": "system", "content": "System"},
        {"role": "narrator", "content": "Hi"},
        {"role": "assistant", "content": "Hello"},
    ])

    assert requires_full_edit_for_quick_edit(entry) is True
