"""Helpers for showing editable user/assistant slots for malformed entries."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from core.role_normalization import is_known_role_variant, normalize_role


def scaffold_user_assistant_turns(turns: list[dict]) -> list[dict]:
    """Return turns with missing user/assistant partners inserted as blanks."""

    scaffolded: list[dict] = []
    expected_role = "user"
    for turn in turns:
        role = canonical_editor_role(turn.get("role")) or turn.get("role")
        editable_turn = {**turn, "role": role}
        while role in {"user", "assistant"} and role != expected_role:
            scaffolded.append({"role": expected_role, "content": ""})
            expected_role = _next_role(expected_role)
        scaffolded.append(editable_turn)
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
        if not isinstance(message, dict):
            flush_run()
            scaffolded.append(deepcopy(message))
            continue

        canonical_role = canonical_editor_role(message.get("role"))
        if canonical_role == "system":
            flush_run()
            scaffolded.append({**message, "role": "system"})
            continue
        if canonical_role in {"user", "assistant"}:
            editable_run.append({**message, "role": canonical_role})
            continue
        if isinstance(message.get("role"), str):
            editable_run.append(dict(message))
            continue
        flush_run()
        scaffolded.append(deepcopy(message))
    flush_run()
    return scaffolded


def _next_role(role: str) -> str:
    return "assistant" if role == "user" else "user"


def canonical_editor_role(role: object) -> str | None:
    """Map known role variants to editor roles."""

    if not isinstance(role, str):
        return None
    if not is_known_role_variant(role):
        return None
    return normalize_role(role)[0]
