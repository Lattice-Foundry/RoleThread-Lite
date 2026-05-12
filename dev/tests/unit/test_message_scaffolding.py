from ui.message_scaffolding import (
    canonical_editor_role,
    scaffold_editable_messages,
    scaffold_user_assistant_turns,
)


def test_scaffold_user_assistant_turns_adds_missing_assistant():
    turns = [{"role": "user", "content": "Hi"}]

    scaffolded = scaffold_user_assistant_turns(turns)

    assert scaffolded == [
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": ""},
    ]


def test_scaffold_user_assistant_turns_adds_missing_user_before_assistant():
    turns = [{"role": "assistant", "content": "Hello"}]

    scaffolded = scaffold_user_assistant_turns(turns)

    assert scaffolded == [
        {"role": "user", "content": ""},
        {"role": "assistant", "content": "Hello"},
    ]


def test_scaffold_editable_messages_preserves_system_and_inserts_missing_turn():
    messages = [
        {"role": "system", "content": "System"},
        {"role": "user", "content": "Question"},
    ]

    scaffolded = scaffold_editable_messages(messages)

    assert scaffolded == [
        {"role": "system", "content": "System"},
        {"role": "user", "content": "Question"},
        {"role": "assistant", "content": ""},
    ]


def test_scaffold_editable_messages_maps_known_role_variants():
    messages = [
        {"role": "System", "content": "System"},
        {"role": "human", "content": "Hi"},
        {"role": "GPT", "content": "Hello"},
        {"role": "Bot", "content": "Again"},
    ]

    scaffolded = scaffold_editable_messages(messages)

    assert scaffolded == [
        {"role": "system", "content": "System"},
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "Hello"},
        {"role": "user", "content": ""},
        {"role": "assistant", "content": "Again"},
    ]


def test_scaffold_editable_messages_preserves_custom_roles():
    messages = [
        {"role": "system", "content": "System"},
        {"role": "Scott", "content": "Hi"},
        {"role": "Emma", "content": "Hello"},
    ]

    scaffolded = scaffold_editable_messages(messages)

    assert scaffolded == [
        {"role": "system", "content": "System"},
        {"role": "Scott", "content": "Hi"},
        {"role": "Emma", "content": "Hello"},
    ]


def test_canonical_editor_role_maps_synonyms():
    assert canonical_editor_role(" Human ") == "user"
    assert canonical_editor_role("BOT") == "assistant"
    assert canonical_editor_role("System") == "system"
    assert canonical_editor_role("Scott") is None
