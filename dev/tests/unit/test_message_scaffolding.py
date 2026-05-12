from ui.message_scaffolding import (
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
