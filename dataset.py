import json
import random
from pathlib import Path


DEFAULT_SYSTEM_PROMPT = (
    "You are a creative, engaging roleplay assistant. Stay in character, "
    "be descriptive, and always follow the user's lead."
)

TAGS: dict[str, list[str]] = {
    "Behavior": ["pacing", "boundaries", "no_user_control", "followup_question", "emotional_awareness"],
    "Scene": ["greeting", "medical", "comfort", "tension", "assessment", "aftercare"],
    "Style": ["dialogue", "narration", "descriptive", "subtle", "grounded"],
    "Source & Status": ["manual", "ai_generated", "reviewed", "needs_edit"],
}


def make_entry(turns: list[dict], system_prompt: str, tags: list[str] | None = None) -> dict:
    """Build a dataset entry from a list of {role, content} turn dicts.

    Empty turns are stripped so trailing blank pairs do not produce invalid messages.
    """
    clean = [t for t in turns if t.get("content", "").strip()]
    return {
        "messages": [{"role": "system", "content": system_prompt}] + [
            {"role": t["role"], "content": t["content"].strip()} for t in clean
        ],
        "tags": tags if tags is not None else [],
    }


def validate_entry(entry: dict) -> list[str]:
    errors = []
    if "messages" not in entry:
        errors.append("Missing 'messages' key")
        return errors
    msgs = entry["messages"]
    if not isinstance(msgs, list):
        errors.append("'messages' must be a list")
        return errors
    if len(msgs) < 3:
        errors.append("'messages' must have at least 3 items (system + one user/assistant exchange)")
        return errors
    if (len(msgs) - 1) % 2 != 0:
        errors.append("Messages must contain complete user/assistant exchanges")
        return errors
    # System message
    if not isinstance(msgs[0], dict):
        errors.append("Message 0 is not a dict")
        return errors
    if msgs[0].get("role") != "system":
        errors.append(f"Message 0: expected role 'system', got '{msgs[0].get('role')}'")
    if not msgs[0].get("content", "").strip():
        errors.append("Message 0 (system) has empty content")
    # Alternating user / assistant after system
    expected = "user"
    for i, msg in enumerate(msgs[1:], 1):
        if not isinstance(msg, dict):
            errors.append(f"Message {i} is not a dict")
            expected = "assistant" if expected == "user" else "user"
            continue
        if msg.get("role") != expected:
            errors.append(f"Message {i}: expected role '{expected}', got '{msg.get('role')}'")
        if not msg.get("content", "").strip():
            errors.append(f"Message {i} ({expected}) has empty content")
        expected = "assistant" if expected == "user" else "user"
    if "tags" not in entry:
        errors.append("Missing 'tags' key")
    elif not isinstance(entry["tags"], list):
        errors.append("'tags' must be a list")
    elif not all(isinstance(t, str) for t in entry["tags"]):
        errors.append("Each tag must be a string")
    return errors


def load_dataset(path: str) -> tuple[list[dict], list[str]]:
    entries, parse_errors = [], []
    p = Path(path)
    if not p.exists():
        return [], [f"File not found: {path}"]
    with p.open("r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                if "tags" not in entry:
                    entry["tags"] = []
                entries.append(entry)
            except json.JSONDecodeError as e:
                parse_errors.append(f"Line {line_num}: {e}")
    return entries, parse_errors


def save_dataset(path: str, entries: list[dict]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def append_to_dataset(path: str, entry: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def merge_datasets(paths: list[str], shuffle: bool = True) -> tuple[list[dict], dict]:
    seen, merged = set(), []
    stats = {"total_loaded": 0, "duplicates_removed": 0, "parse_errors": []}

    for path in paths:
        entries, errors = load_dataset(path)
        stats["parse_errors"].extend(errors)
        for entry in entries:
            stats["total_loaded"] += 1
            msgs = {m["role"]: m["content"] for m in entry.get("messages", []) if m.get("role") in ("user", "assistant")}
            key = json.dumps(msgs, sort_keys=True)
            if key in seen:
                stats["duplicates_removed"] += 1
            else:
                seen.add(key)
                merged.append(entry)

    if shuffle:
        random.shuffle(merged)

    return merged, stats
