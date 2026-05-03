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


# ── Per-entry helpers ──────────────────────────────────────────────────────────

def count_exchanges(entry: dict) -> int:
    """Count complete user/assistant pairs after the system message.
    Safe against malformed entries — never raises."""
    try:
        msgs = entry.get("messages") or []
        non_system = [m for m in msgs if isinstance(m, dict) and m.get("role") != "system"]
        return len(non_system) // 2
    except Exception:
        return 0


def get_entry_messages(entry: dict) -> list[dict]:
    """Safely return entry['messages'] if it is a list, else []."""
    try:
        msgs = entry.get("messages")
        return msgs if isinstance(msgs, list) else []
    except Exception:
        return []


def get_role_messages(entry: dict, role: str) -> list[str]:
    """Return content strings for all messages with the given role."""
    try:
        return [
            m.get("content", "")
            for m in get_entry_messages(entry)
            if isinstance(m, dict) and m.get("role") == role
        ]
    except Exception:
        return []


def entry_text_length(entry: dict) -> int:
    """Total character count across all message contents in an entry."""
    try:
        return sum(
            len(m.get("content", ""))
            for m in get_entry_messages(entry)
            if isinstance(m, dict)
        )
    except Exception:
        return 0


def build_dataset_stats(entries: list[dict]) -> dict:
    """Compute aggregate statistics for a list of dataset entries.

    Returns a plain dict — no Streamlit or pandas dependency here.
    All values are safe to render directly; nothing mutates the input entries.
    """
    total = len(entries)

    # ── Exchange counts ────────────────────────────────────────────────────────
    exchange_counts = [count_exchanges(e) for e in entries]
    total_exchanges = sum(exchange_counts)
    avg_exchanges = total_exchanges / total if total else 0.0
    single_turn = sum(1 for c in exchange_counts if c == 1)
    multi_turn = sum(1 for c in exchange_counts if c > 1)

    exchange_dist: dict[int, int] = {}
    for c in exchange_counts:
        exchange_dist[c] = exchange_dist.get(c, 0) + 1

    # ── Validation ────────────────────────────────────────────────────────────
    invalid_rows: list[dict] = []
    for i, entry in enumerate(entries):
        errs = validate_entry(entry)
        if errs:
            invalid_rows.append({
                "entry": i + 1,
                "error_count": len(errs),
                "errors": errs,
            })
    invalid_count = len(invalid_rows)
    valid_count = total - invalid_count

    # ── Tags ──────────────────────────────────────────────────────────────────
    tag_to_category: dict[str, str] = {
        tag: cat for cat, tags in TAGS.items() for tag in tags
    }

    all_tags: list[str] = []
    untagged_count = 0
    for entry in entries:
        tags = entry.get("tags") or []
        if tags:
            all_tags.extend(tags)
        else:
            untagged_count += 1

    tag_counts: dict[str, int] = {}
    for tag in all_tags:
        tag_counts[tag] = tag_counts.get(tag, 0) + 1

    tag_category_counts: dict[str, int] = {}
    for tag in all_tags:
        cat = tag_to_category.get(tag, "Unknown")
        tag_category_counts[cat] = tag_category_counts.get(cat, 0) + 1

    unique_tags = len(tag_counts)

    # ── Message lengths ───────────────────────────────────────────────────────
    user_lengths: list[int] = []
    asst_lengths: list[int] = []
    entry_lengths: list[int] = []

    for entry in entries:
        for content in get_role_messages(entry, "user"):
            user_lengths.append(len(content))
        for content in get_role_messages(entry, "assistant"):
            asst_lengths.append(len(content))
        entry_lengths.append(entry_text_length(entry))

    avg_user_len = sum(user_lengths) / len(user_lengths) if user_lengths else 0.0
    avg_asst_len = sum(asst_lengths) / len(asst_lengths) if asst_lengths else 0.0
    avg_entry_len = sum(entry_lengths) / len(entry_lengths) if entry_lengths else 0.0
    min_asst_len = min(asst_lengths) if asst_lengths else 0
    max_asst_len = max(asst_lengths) if asst_lengths else 0

    return {
        # Summary
        "total": total,
        "total_exchanges": total_exchanges,
        "avg_exchanges": avg_exchanges,
        "single_turn": single_turn,
        "multi_turn": multi_turn,
        # Validation
        "valid_count": valid_count,
        "invalid_count": invalid_count,
        "invalid_rows": invalid_rows,
        # Tags
        "untagged_count": untagged_count,
        "unique_tags": unique_tags,
        "tag_counts": tag_counts,
        "tag_category_counts": tag_category_counts,
        # Message lengths
        "avg_user_len": avg_user_len,
        "avg_asst_len": avg_asst_len,
        "avg_entry_len": avg_entry_len,
        "min_asst_len": min_asst_len,
        "max_asst_len": max_asst_len,
        # Raw series (chart-ready)
        "exchange_counts": exchange_counts,
        "exchange_dist": exchange_dist,
        "entry_lengths": entry_lengths,
    }


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
