"""Pure helpers for canonical role typo and variant normalization."""
from __future__ import annotations

from copy import deepcopy

STANDARD_ROLE_USER = "user"
STANDARD_ROLE_ASSISTANT = "assistant"
STANDARD_ROLE_SYSTEM = "system"

ROLE_VARIANTS: dict[str, str] = {
    "user": STANDARD_ROLE_USER,
    "usr": STANDARD_ROLE_USER,
    "uesr": STANDARD_ROLE_USER,
    "useer": STANDARD_ROLE_USER,
    "human": STANDARD_ROLE_USER,
    "humans": STANDARD_ROLE_USER,
    "person": STANDARD_ROLE_USER,
    "player": STANDARD_ROLE_USER,
    "input": STANDARD_ROLE_USER,
    "prompt": STANDARD_ROLE_USER,
    "instruction": STANDARD_ROLE_USER,
    "assistant": STANDARD_ROLE_ASSISTANT,
    "assistnt": STANDARD_ROLE_ASSISTANT,
    "assitant": STANDARD_ROLE_ASSISTANT,
    "assitstant": STANDARD_ROLE_ASSISTANT,
    "asistant": STANDARD_ROLE_ASSISTANT,
    "asst": STANDARD_ROLE_ASSISTANT,
    "bot": STANDARD_ROLE_ASSISTANT,
    "chatbot": STANDARD_ROLE_ASSISTANT,
    "gpt": STANDARD_ROLE_ASSISTANT,
    "model": STANDARD_ROLE_ASSISTANT,
    "ai": STANDARD_ROLE_ASSISTANT,
    "completion": STANDARD_ROLE_ASSISTANT,
    "response": STANDARD_ROLE_ASSISTANT,
    "output": STANDARD_ROLE_ASSISTANT,
    "system": STANDARD_ROLE_SYSTEM,
    "sys": STANDARD_ROLE_SYSTEM,
    "sytem": STANDARD_ROLE_SYSTEM,
    "systm": STANDARD_ROLE_SYSTEM,
    "system_prompt": STANDARD_ROLE_SYSTEM,
    "context": STANDARD_ROLE_SYSTEM,
}


def normalize_role(role: str) -> tuple[str, bool]:
    """Return the canonical role for known variants, otherwise the original."""

    normalized = ROLE_VARIANTS.get(role.strip().lower())
    if normalized is None:
        return role, False
    return normalized, normalized != role


def is_known_role_variant(role: str) -> bool:
    """Return True when role is a known standard-role spelling or typo."""

    return role.strip().lower() in ROLE_VARIANTS


def normalize_entry_roles(entry: dict) -> tuple[dict, bool]:
    """Normalize recognized message roles in a deep-copied entry."""

    normalized_entry = deepcopy(entry)
    messages = (
        normalized_entry.get("messages")
        if isinstance(normalized_entry, dict)
        else None
    )
    if not isinstance(messages, list):
        return normalized_entry, False

    changed = False
    for message in messages:
        if not isinstance(message, dict):
            continue
        role = message.get("role")
        if not isinstance(role, str):
            continue
        normalized_role, role_changed = normalize_role(role)
        if role_changed:
            message["role"] = normalized_role
            changed = True
    return normalized_entry, changed
