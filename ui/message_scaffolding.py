"""Helpers for showing editable user/assistant slots for malformed entries."""
from __future__ import annotations

from copy import deepcopy
from typing import Any


def scaffold_user_assistant_turns(turns: list[dict]) -> list[dict]:
    """Return turns with missing user/assistant partners inserted as blanks."""

    scaffolded: list[dict] = []
    expected_role = "user"
    for turn in turns:
        role = turn.get("role")
        while role in {"user", "assistant"} and role != expected_role:
            scaffolded.append({"role": expected_role, "content": ""})
            expected_role = _next_role(expected_role)
        scaffolded.append(dict(turn))
        if role in {"user", "assistant"}:
            expected_role = _next_role(role)

    if not scaffolded:
        return [
            {"role": "user", "content": ""},
            {"role": "assistant", "content": ""},
        ]
    if len(scaffolded) % 2:
        scaffolded.append({"role": expected_role, "content": ""})
    return scaffolded


def scaffold_editable_messages(messages: list[Any]) -> list[Any]:
    """Insert blank user/assistant messages into editable message runs."""

    scaffolded: list[Any] = []
    editable_run: list[dict] = []

    def flush_run() -> None:
        nonlocal editable_run
        if editable_run:
            scaffolded.extend(scaffold_user_assistant_turns(editable_run))
            editable_run = []

    for message in messages:
        if isinstance(message, dict) and message.get("role") in {"user", "assistant"}:
            editable_run.append(dict(message))
            continue
        flush_run()
        scaffolded.append(deepcopy(message))
    flush_run()
    return scaffolded


def _next_role(role: str) -> str:
    return "assistant" if role == "user" else "user"
