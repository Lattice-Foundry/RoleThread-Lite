import json
import re
import tkinter as tk
from pathlib import Path
from tkinter import filedialog

import pandas as pd
import plotly.express as px
import streamlit as st

from dataset import (
    DEFAULT_SYSTEM_PROMPT,
    TAGS,
    append_registry_id,
    append_to_dataset,
    build_dataset_stats,
    build_entry_registry,
    count_exchanges,
    entry_text_length,
    get_entry_pairs,
    get_entry_messages,
    get_index_for_entry_id,
    get_role_messages,
    load_dataset,
    make_entry,
    merge_datasets,
    registry_is_valid,
    remove_registry_id,
    save_dataset,
    validate_entry,
)
from preferences import get_initial_dir, load_preferences, save_preferences

st.set_page_config(page_title="Roleplay Dataset Manager", layout="wide")

st.markdown(
    "<h1 style='color:#1a73e8'>Roleplay Dataset Manager</h1>",
    unsafe_allow_html=True,
)

st.markdown("""
<style>
/* Primary button — enabled state only (:not(:disabled) keeps disabled grey) */
button[data-testid="baseButton-primary"]:not(:disabled),
button[kind="primary"]:not(:disabled),
.stButton > button[type="submit"]:not(:disabled),
.stButton > button:not([kind="secondary"]):not([kind="tertiary"]):not(:disabled) {
    background-color: #1a73e8 !important;
    border-color: #1565c0 !important;
    color: white !important;
}
button[data-testid="baseButton-primary"]:not(:disabled):hover,
button[kind="primary"]:not(:disabled):hover,
.stButton > button[type="submit"]:not(:disabled):hover,
.stButton > button:not([kind="secondary"]):not([kind="tertiary"]):not(:disabled):hover {
    background-color: #1565c0 !important;
    border-color: #0d47a1 !important;
    color: white !important;
}
/* Active sidebar nav button — blue text, no background fill.
   More specific selector overrides the general primary-button rule above. */
section[data-testid="stSidebar"] button[data-testid="baseButton-primary"]:not(:disabled),
section[data-testid="stSidebar"] button[kind="primary"]:not(:disabled) {
    background-color: transparent !important;
    border-color: transparent !important;
    color: #1a73e8 !important;
    box-shadow: none !important;
}
section[data-testid="stSidebar"] button[data-testid="baseButton-primary"]:not(:disabled):hover,
section[data-testid="stSidebar"] button[kind="primary"]:not(:disabled):hover {
    background-color: rgba(26, 115, 232, 0.08) !important;
    border-color: transparent !important;
    color: #1565c0 !important;
}
</style>
""", unsafe_allow_html=True)

# ── Module-level constants ─────────────────────────────────────────────────────
JSONL_TYPES = [("JSONL files", "*.jsonl"), ("All files", "*.*")]

_ROLE_COLOR = {"user": "#1a73e8", "assistant": "#188038"}
_ROLE_PLACEHOLDER = {
    "user": "What the user says…",
    "assistant": "What the assistant replies…",
}

_UNTAGGED = "__untagged__"


# ── Preferences helpers ────────────────────────────────────────────────────────
def _update_prefs(updates: dict) -> None:
    st.session_state.prefs.update(updates)
    save_preferences(st.session_state.prefs)


# ── Tkinter helpers ────────────────────────────────────────────────────────────
def _tk_root():
    root = tk.Tk()
    root.withdraw()
    root.wm_attributes("-topmost", 1)
    return root


def browse_open_file(pending_key: str, pref_path_key: str = "last_loaded_dataset_path") -> None:
    prefs = st.session_state.prefs
    root = _tk_root()
    path = filedialog.askopenfilename(
        title="Select dataset file",
        filetypes=JSONL_TYPES,
        initialdir=get_initial_dir(prefs, path_key=pref_path_key, dir_key="last_open_directory"),
    )
    root.destroy()
    if path:
        st.session_state[pending_key] = path
        _update_prefs({
            pref_path_key: path,
            "last_open_directory": str(Path(path).parent),
        })
        st.rerun()


def browse_save_file(
    pending_key: str,
    default_name: str = "dataset.jsonl",
) -> None:
    prefs = st.session_state.prefs
    root = _tk_root()
    path = filedialog.asksaveasfilename(
        title="Save dataset as",
        defaultextension=".jsonl",
        initialfile=default_name,
        initialdir=get_initial_dir(prefs, dir_key="last_open_directory"),
        filetypes=JSONL_TYPES,
    )
    root.destroy()
    if path:
        st.session_state[pending_key] = path
        st.rerun()


def browse_export_file(pending_key: str) -> None:
    """Open a save-as dialog for the Export page.
    Does NOT update preferences — export is a one-off operation."""
    _default = Path(st.session_state.loaded_path).name if st.session_state.loaded_path else "dataset.jsonl"
    _initial_dir = (
        str(Path(st.session_state.loaded_path).parent)
        if st.session_state.loaded_path and Path(st.session_state.loaded_path).parent.exists()
        else None
    )
    root = _tk_root()
    path = filedialog.asksaveasfilename(
        title="Export dataset",
        defaultextension=".jsonl",
        initialfile=_default,
        initialdir=_initial_dir,
        filetypes=JSONL_TYPES,
    )
    root.destroy()
    if path:
        st.session_state[pending_key] = path
        st.rerun()


def browse_open_multiple(widget_key: str, pending_key: str) -> None:
    prefs = st.session_state.prefs
    root = _tk_root()
    paths = filedialog.askopenfilenames(
        title="Select dataset files to merge",
        filetypes=JSONL_TYPES,
        initialdir=get_initial_dir(prefs, dir_key="last_open_directory"),
    )
    root.destroy()
    if paths:
        existing = st.session_state.get(widget_key, "").strip()
        new_lines = "\n".join(paths)
        combined = (existing + "\n" + new_lines).strip() if existing else new_lines
        st.session_state[pending_key] = combined
        _update_prefs({"last_open_directory": str(Path(paths[0]).parent)})
        st.rerun()


# ── path_input widget ──────────────────────────────────────────────────────────
def path_input(label: str, state_key: str, browse_fn, browse_kwargs: dict, default: str = "") -> str:
    """Text input + Browse button. Uses pending-key pattern to update the field from browse."""
    pending_key = f"{state_key}_pending"

    if pending_key in st.session_state:
        st.session_state[state_key] = st.session_state.pop(pending_key)
    elif state_key not in st.session_state:
        st.session_state[state_key] = default

    col_input, col_btn = st.columns([5, 1])
    with col_input:
        value = st.text_input(label, key=state_key)
    with col_btn:
        st.write("")
        if st.button("Browse", key=f"browse_{state_key}"):
            browse_fn(pending_key, **browse_kwargs)
    return value


# ── Tag filtering helper ───────────────────────────────────────────────────────
def filter_entries_by_tags(
    entries: list[dict],
    selected_tags: list[str],
    match_mode: str,
) -> list[dict]:
    if not selected_tags:
        return entries

    normal_tags = [t for t in selected_tags if t != _UNTAGGED]
    include_untagged = _UNTAGGED in selected_tags
    normal_set = set(normal_tags)

    result = []
    for entry in entries:
        entry_tags = entry.get("tags") or []
        is_untagged = len(entry_tags) == 0

        if is_untagged:
            if include_untagged and not normal_tags:
                result.append(entry)
            elif include_untagged and match_mode == "Exact match":
                result.append(entry)
            continue

        # Tagged entry — normal_tags must be non-empty to match
        if not normal_tags:
            continue
        entry_set = set(entry_tags)
        if match_mode == "All selected tags":
            if normal_set.issubset(entry_set):
                result.append(entry)
        elif match_mode == "Exact match":
            if entry_set == normal_set:
                result.append(entry)
        else:  # Any selected tags
            if normal_set.intersection(entry_set):
                result.append(entry)

    return result


# ── Narration / dialogue formatter ────────────────────────────────────────────
def _format_preview_content(text: str) -> str:
    """Split content into dialogue (plain) and narration (orange italic).
    Text inside double-quotes is treated as dialogue and left unstyled.
    Everything else is narration and rendered orange + italic."""
    parts = re.split(r'(".*?")', text, flags=re.DOTALL)
    out = ""
    for part in parts:
        if not part:
            continue
        if part.startswith('"') and part.endswith('"') and len(part) >= 2:
            out += part  # dialogue — plain/default color
        else:
            out += f"<span style='color:#e67e22;font-style:italic'>{part}</span>"
    return out


# ── Session-state registry helpers ────────────────────────────────────────────

def ensure_entry_registry() -> None:
    """Ensure entry_registry exists and is consistent with loaded_entries.
    Rebuilds silently if missing or invalid — safe to call anywhere."""
    entries = st.session_state.get("loaded_entries", [])
    if not registry_is_valid(st.session_state.get("entry_registry"), entries):
        st.session_state.entry_registry = build_entry_registry(entries)


def set_loaded_entries(entries: list[dict]) -> None:
    """Replace loaded_entries and rebuild the registry from scratch."""
    st.session_state.loaded_entries = entries
    st.session_state.entry_registry = build_entry_registry(entries)


def append_loaded_entry(entry: dict) -> None:
    """Append one entry and add a matching temp ID to the registry."""
    ensure_entry_registry()
    st.session_state.loaded_entries.append(entry)
    append_registry_id(st.session_state.entry_registry)


def get_loaded_entry_by_id(entry_id: str) -> dict | None:
    """Return the entry for the given temp ID, or None if not found."""
    ensure_entry_registry()
    idx = get_index_for_entry_id(st.session_state.entry_registry, entry_id)
    if idx is None:
        return None
    entries = st.session_state.loaded_entries
    return entries[idx] if 0 <= idx < len(entries) else None


def replace_loaded_entry_by_id(entry_id: str, new_entry: dict) -> bool:
    """Overwrite the entry at entry_id in-place. Returns True on success."""
    ensure_entry_registry()
    idx = get_index_for_entry_id(st.session_state.entry_registry, entry_id)
    if idx is None:
        return False
    entries = st.session_state.loaded_entries
    if not (0 <= idx < len(entries)):
        return False
    st.session_state.loaded_entries[idx] = new_entry
    return True


def delete_loaded_entry_by_id(entry_id: str) -> bool:
    """Delete the entry at entry_id and remove it from the registry. Returns True on success."""
    ensure_entry_registry()
    idx = get_index_for_entry_id(st.session_state.entry_registry, entry_id)
    if idx is None:
        return False
    entries = st.session_state.loaded_entries
    if not (0 <= idx < len(entries)):
        return False
    del st.session_state.loaded_entries[idx]
    remove_registry_id(st.session_state.entry_registry, entry_id)
    return True


def get_all_entry_pairs() -> list[tuple[str, dict]]:
    """Return [(entry_id, entry), ...] for all loaded entries."""
    ensure_entry_registry()
    return get_entry_pairs(st.session_state.loaded_entries, st.session_state.entry_registry)


def filter_entry_pairs_by_tags(
    pairs: list[tuple[str, dict]],
    selected_tags: list[str],
    match_mode: str,
) -> list[tuple[str, dict]]:
    """Filter (entry_id, entry) pairs by tag selection — mirrors filter_entries_by_tags."""
    if not selected_tags:
        return pairs

    normal_tags = [t for t in selected_tags if t != _UNTAGGED]
    include_untagged = _UNTAGGED in selected_tags
    normal_set = set(normal_tags)

    result = []
    for entry_id, entry in pairs:
        entry_tags = entry.get("tags") or []
        is_untagged = len(entry_tags) == 0

        if is_untagged:
            if include_untagged and not normal_tags:
                result.append((entry_id, entry))
            elif include_untagged and match_mode == "Exact match":
                result.append((entry_id, entry))
            continue

        if not normal_tags:
            continue
        entry_set = set(entry_tags)
        if match_mode == "All selected tags":
            if normal_set.issubset(entry_set):
                result.append((entry_id, entry))
        elif match_mode == "Exact match":
            if entry_set == normal_set:
                result.append((entry_id, entry))
        else:  # Any selected tags
            if normal_set.intersection(entry_set):
                result.append((entry_id, entry))

    return result


# ── Editor functions ───────────────────────────────────────────────────────────
def init_editor_state(prefix: str) -> None:
    """Initialise session state keys for an entry editor instance.
    Safe to call multiple times — only sets keys that don't exist yet."""
    if f"{prefix}_turns" not in st.session_state:
        st.session_state[f"{prefix}_turns"] = [
            {"role": "user"}, {"role": "assistant"}
        ]
    if f"{prefix}_planned_exchanges" not in st.session_state:
        st.session_state[f"{prefix}_planned_exchanges"] = 1
    if f"{prefix}_clear" not in st.session_state:
        st.session_state[f"{prefix}_clear"] = False


def render_turn_builder(prefix: str) -> list[dict]:
    """Render the multi-turn conversation builder for an editor instance.

    Handles the pending-clear logic, tag-backup restore, planned-exchanges
    input, planning metrics, turn pair widgets, Add/Remove buttons, and the
    exchange-count caption.  Returns _turns_now — the list of
    {role, content} dicts reflecting the current widget values.
    """
    # ── Pending clear ──────────────────────────────────────────────────────────
    if st.session_state.pop(f"{prefix}_clear", False):
        _old_turn_count = len(st.session_state.get(f"{prefix}_turns", []))
        st.session_state[f"{prefix}_turns"] = [{"role": "user"}, {"role": "assistant"}]
        st.session_state[f"{prefix}_turn_0"] = ""
        st.session_state[f"{prefix}_turn_1"] = ""
        for _i in range(2, _old_turn_count):
            st.session_state.pop(f"{prefix}_turn_{_i}", None)
        for _cat in TAGS:
            st.session_state[f"{prefix}_tags_{_cat}"] = []

    # ── Tag backup restore ─────────────────────────────────────────────────────
    for _cat in TAGS:
        _bk = f"_{prefix}_tags_backup_{_cat}"
        if _bk in st.session_state:
            st.session_state[f"{prefix}_tags_{_cat}"] = st.session_state.pop(_bk)

    # ── _turns_now snapshot (read before widgets render) ──────────────────────
    _turns_now = [
        {"role": t["role"], "content": st.session_state.get(f"{prefix}_turn_{i}", "")}
        for i, t in enumerate(st.session_state[f"{prefix}_turns"])
    ]

    # ── Planned exchanges number input ────────────────────────────────────────
    st.number_input(
        "Planned exchanges",
        min_value=1,
        step=1,
        key=f"{prefix}_planned_exchanges",
    )

    # ── Planning metrics (recomputed every run) ────────────────────────────────
    # Only count an exchange as complete when BOTH turns are filled in.
    _current_exchanges = sum(
        1
        for _pi in range(0, len(_turns_now), 2)
        if (
            _pi + 1 < len(_turns_now)
            and _turns_now[_pi]["content"].strip()
            and _turns_now[_pi + 1]["content"].strip()
        )
    )
    _planned_exchanges = st.session_state[f"{prefix}_planned_exchanges"]
    _remaining = max(0, _planned_exchanges - len(_turns_now) // 2)
    _overage = max(0, _current_exchanges - _planned_exchanges)

    # ── Turn pair rendering loop ───────────────────────────────────────────────
    for _pair in range(0, len(st.session_state[f"{prefix}_turns"]), 2):
        _col_user, _col_asst = st.columns(2)
        for _col, _idx in ((_col_user, _pair), (_col_asst, _pair + 1)):
            if _idx >= len(st.session_state[f"{prefix}_turns"]):
                break
            _turn = st.session_state[f"{prefix}_turns"][_idx]
            _role = _turn["role"]
            _color = _ROLE_COLOR.get(_role, "#000")
            with _col:
                st.markdown(
                    f"<span style='color:{_color};font-weight:bold;text-transform:uppercase'>{_role}</span>",
                    unsafe_allow_html=True,
                )
                st.text_area(
                    label=f"{prefix}_turn_{_idx}",
                    placeholder=_ROLE_PLACEHOLDER.get(_role, ""),
                    key=f"{prefix}_turn_{_idx}",
                    height=150,
                    label_visibility="collapsed",
                )

    # ── Add / Remove Exchange buttons ─────────────────────────────────────────
    _add_label = (
        f"Add Exchange ({_remaining} Remaining)"
        if _remaining > 0 and _planned_exchanges >= 2
        else "Add Exchange"
    )
    _btn_add, _btn_remove = st.columns(2)
    with _btn_add:
        if st.button(_add_label, key=f"{prefix}_btn_add", width='stretch'):
            for _cat in TAGS:
                st.session_state[f"_{prefix}_tags_backup_{_cat}"] = list(
                    st.session_state.get(f"{prefix}_tags_{_cat}", [])
                )
            st.session_state[f"{prefix}_turns"] += [{"role": "user"}, {"role": "assistant"}]
            st.rerun()
    with _btn_remove:
        if st.button(
            "Remove Last Exchange",
            key=f"{prefix}_btn_remove",
            disabled=len(st.session_state[f"{prefix}_turns"]) <= 2,
            width='stretch',
        ):
            for _cat in TAGS:
                st.session_state[f"_{prefix}_tags_backup_{_cat}"] = list(
                    st.session_state.get(f"{prefix}_tags_{_cat}", [])
                )
            _n = len(st.session_state[f"{prefix}_turns"])
            st.session_state[f"{prefix}_turns"] = st.session_state[f"{prefix}_turns"][:-2]
            for _k in [f"{prefix}_turn_{_n - 2}", f"{prefix}_turn_{_n - 1}"]:
                st.session_state.pop(_k, None)
            st.rerun()

    # ── Exchange count caption ─────────────────────────────────────────────────
    st.caption(f"Current exchanges: {_current_exchanges} / Planned: {_planned_exchanges}")

    return _turns_now


def render_conversation_preview(turns_now: list[dict], prefix: str) -> None:  # noqa: ARG001
    """Render the read-only conversation preview for an editor instance.

    Iterates turns_now, applying narration/dialogue formatting via
    _format_preview_content and speaker labels from preferences.
    Shows an empty-state caption when no turns have content.

    prefix is reserved for future use (e.g. per-editor preview settings).
    """
    # prefix is intentionally unused — reserved for future per-editor settings
    _ = prefix

    _SPEAKER_LABEL = {
        "user": st.session_state.preview_user_name,
        "assistant": st.session_state.preview_assistant_name,
    }

    _preview_turns = [t for t in turns_now if t["content"].strip()]
    if not _preview_turns:
        st.caption("Your conversation will appear here as you write…")
        return

    for _pt in _preview_turns:
        _role = _pt["role"]
        _color = _ROLE_COLOR.get(_role, "#000")
        _name = _SPEAKER_LABEL.get(_role, _role.upper())
        _body = _format_preview_content(_pt["content"])
        st.markdown(
            f"<span style='color:{_color};font-weight:bold'>{_name.upper()}:</span> {_body}",
            unsafe_allow_html=True,
        )
        st.write("")


def render_entry_actions(
    turns_now: list[dict],
    prefix: str,
    mode: str,
    entry_index: int | None = None,
) -> None:
    """Render the tag selector, JSON preview, validation, planning warnings,
    and save button for an entry editor instance.

    mode — "create" appends to the dataset file;
           "edit"   overwrites loaded_entries[entry_index] in place.
    entry_index — required when mode == "edit"; ignored for "create".
    """
    st.divider()
    st.subheader("Tag & Complete Exchange")

    # ── Tag selectors ──────────────────────────────────────────────────────────
    selected_tags: list[str] = []
    tag_cols = st.columns(len(TAGS))
    for col, (category, options) in zip(tag_cols, TAGS.items()):
        with col:
            chosen = st.multiselect(
                f"{category} tags", options=options, key=f"{prefix}_tags_{category}"
            )
            selected_tags.extend(chosen)

    # ── Entry preview & validation ─────────────────────────────────────────────
    _has_content = any(t["content"].strip() for t in turns_now)

    entry_preview = None
    _entry_valid = False
    if _has_content:
        entry_preview = make_entry(
            turns=turns_now,
            system_prompt=st.session_state.system_prompt,
            tags=selected_tags,
        )
        errors = validate_entry(entry_preview)

        with st.expander("Preview JSON", expanded=False):
            st.code(json.dumps(entry_preview, ensure_ascii=False, indent=2), language="json")

        if errors:
            for err in errors:
                st.error(err)
        else:
            st.success("Entry looks valid.")
            _entry_valid = True

    # ── Planning warnings ──────────────────────────────────────────────────────
    _planned_exchanges = st.session_state.get(f"{prefix}_planned_exchanges", 1)
    _total_slots = len(turns_now) // 2
    _current_exchanges = sum(
        1
        for _pi in range(0, len(turns_now), 2)
        if (
            _pi + 1 < len(turns_now)
            and turns_now[_pi]["content"].strip()
            and turns_now[_pi + 1]["content"].strip()
        )
    )
    _overage = max(0, _total_slots - _planned_exchanges)
    _blank_pairs = sum(
        1
        for _pi in range(0, len(turns_now), 2)
        if _pi + 1 < len(turns_now) and (
            not turns_now[_pi]["content"].strip()
            or not turns_now[_pi + 1]["content"].strip()
        )
    )

    if _planned_exchanges > 1 and _current_exchanges < _planned_exchanges:
        st.warning("You have not reached your planned number of exchanges yet.")
    if _overage > 0:
        st.info(
            f"You are {_overage} exchange(s) over your planned count. "
            "You can still save this exchange."
        )
    if _planned_exchanges > 1 and _blank_pairs > 0:
        st.warning(
            f"{_blank_pairs} exchange pair(s) have empty fields and will not be saved. "
            "Fill them in or remove them before completing."
        )

    # ── Save button ────────────────────────────────────────────────────────────
    _btn_label = "Complete Exchange" if mode == "create" else "Save Changes"
    _complete_disabled = not _entry_valid or _current_exchanges < _planned_exchanges
    if st.button(_btn_label, disabled=_complete_disabled, type="primary", width='stretch'):
        save_path = st.session_state.get("loaded_path", "").strip()
        if not save_path:
            st.error("No dataset loaded. Please load or create a dataset before saving an exchange.")
        elif mode == "create":
            try:
                append_to_dataset(save_path, entry_preview)
                entries, _ = load_dataset(save_path)
                set_loaded_entries(entries)
                _update_prefs({
                    "last_loaded_dataset_path": save_path,
                })
                st.session_state["manage_load_path_pending"] = save_path
                st.session_state[f"{prefix}_clear"] = True
                st.success(f"Entry appended to `{Path(save_path).resolve()}`.")
                st.rerun()
            except Exception as exc:
                st.error(f"Failed to save: {exc}")
        elif mode == "edit":
            if entry_index is None:
                st.warning("edit mode requires entry_index — nothing saved.")
            else:
                try:
                    st.session_state.loaded_entries[entry_index] = entry_preview
                    save_dataset(save_path, st.session_state.loaded_entries)
                    st.success(f"Entry {entry_index + 1} updated.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Failed to save: {exc}")


# ── One-time session initialisation ───────────────────────────────────────────
if "prefs" not in st.session_state:
    prefs = load_preferences()
    st.session_state.prefs = prefs

    st.session_state.system_prompt = prefs.get("last_system_prompt") or DEFAULT_SYSTEM_PROMPT
    set_loaded_entries([])
    st.session_state.loaded_path = ""
    st.session_state.stale_last_path = ""
    st.session_state.entry_page = 0
    st.session_state.entries_per_page = 25
    st.session_state.filter_tags = []
    st.session_state.filter_only_used = True
    st.session_state.filter_match_mode = "Any selected tags"
    init_editor_state("create")
    st.session_state.preview_user_name = prefs.get("preview_user_name", "User")
    st.session_state.preview_assistant_name = prefs.get("preview_assistant_name", "Assistant")
    st.session_state.dataset_format = prefs.get("dataset_format", "ChatML")
    st.session_state.page = "Create Entry"

    last = prefs.get("last_loaded_dataset_path", "")
    if last:
        if Path(last).exists():
            entries, errors = load_dataset(last)
            set_loaded_entries(entries)
            st.session_state.loaded_path = last
        else:
            st.session_state.stale_last_path = last


# ── Sidebar navigation ─────────────────────────────────────────────────────────
if "page" not in st.session_state:
    st.session_state.page = "Create Entry"

_page = st.session_state.page

_NAV_SECTIONS = [
    ("Create", [
        ("New Entry",       "Create Entry"),
    ]),
    ("Dataset", [
        ("Manage",          "Manage Dataset"),
        ("Merge",           "Merge Datasets"),
        ("Edit Entries",    "Edit Entries"),
    ]),
    ("Tools", [
        ("Export",          "Export"),
        ("Validate",        "Validation"),
    ]),
    ("Analytics", [
        ("Statistics",      "Statistics"),
    ]),
    ("Settings", [
        ("Preferences",     "Settings"),
    ]),
]

for _sec_name, _sec_items in _NAV_SECTIONS:
    st.sidebar.markdown(f"**{_sec_name}**")
    for _display_label, _target in _sec_items:
        _btn_label = f"▶ {_display_label}" if _page == _target else _display_label
        if st.sidebar.button(_btn_label, key=f"_nav_{_target}", width="stretch",
                             type="primary" if _page == _target else "secondary"):
            st.session_state.page = _target
            st.rerun()

page = st.session_state.page


# ── Create Entry ───────────────────────────────────────────────────────────────
if page == "Create Entry":
    st.subheader("System Prompt")

    def _persist_system_prompt():
        _update_prefs({"last_system_prompt": st.session_state.sys_prompt_input})

    st.session_state.system_prompt = st.text_area(
        "Default system prompt (applied to every entry)",
        value=st.session_state.system_prompt,
        height=100,
        key="sys_prompt_input",
        on_change=_persist_system_prompt,
    )

    st.divider()
    st.subheader("New Entry")
    turns_now = render_turn_builder("create")

    # ── Conversation preview (full width, below Add/Remove buttons) ────────────
    st.subheader("Conversation Preview")
    render_conversation_preview(turns_now, "create")

    render_entry_actions(turns_now, "create", mode="create")


# ── Manage Dataset ─────────────────────────────────────────────────────────────
elif page == "Manage Dataset":
    ensure_entry_registry()
    if st.session_state.stale_last_path and not st.session_state.loaded_path:
        st.warning(
            f"Last dataset `{st.session_state.stale_last_path}` no longer exists. "
            "Please load or create a dataset."
        )

    st.subheader("Load Dataset")

    load_path = path_input(
        "File path",
        state_key="manage_load_path",
        browse_fn=browse_open_file,
        browse_kwargs={"pref_path_key": "last_loaded_dataset_path"},
        default=st.session_state.prefs.get("last_loaded_dataset_path") or st.session_state.loaded_path or "dataset.jsonl",
    )

    col_load, col_new = st.columns(2)

    with col_load:
        if st.button("Load", width='stretch', disabled=not load_path.strip()):
            p = load_path.strip()
            entries, errors = load_dataset(p)
            if errors:
                for e in errors:
                    st.error(e)
            set_loaded_entries(entries)
            st.session_state.loaded_path = p
            st.session_state.stale_last_path = ""
            st.session_state.entry_page = 0
            _update_prefs({
                "last_loaded_dataset_path": p,
                "last_open_directory": str(Path(p).parent),
            })
            st.success(f"Loaded {len(entries)} entries from `{p}`.")

    with col_new:
        if st.button("New Dataset", width='stretch'):
            prefs = st.session_state.prefs
            root = _tk_root()
            new_path = filedialog.asksaveasfilename(
                title="Create new dataset",
                defaultextension=".jsonl",
                initialfile="dataset.jsonl",
                initialdir=get_initial_dir(prefs, dir_key="last_open_directory"),
                filetypes=JSONL_TYPES,
            )
            root.destroy()

            if new_path:
                # Flush any in-memory entries to the current dataset first
                if st.session_state.loaded_entries and st.session_state.loaded_path:
                    try:
                        save_dataset(st.session_state.loaded_path, st.session_state.loaded_entries)
                    except Exception as exc:
                        st.error(f"Could not save current dataset before switching: {exc}")
                        new_path = ""  # cancel

            if new_path:
                try:
                    save_dataset(new_path, [])  # create empty file
                    set_loaded_entries([])
                    st.session_state.loaded_path = new_path
                    st.session_state.stale_last_path = ""
                    st.session_state.entry_page = 0
                    st.session_state["manage_load_path_pending"] = new_path
                    st.session_state["clear_entry_fields"] = True
                    _update_prefs({
                        "last_loaded_dataset_path": new_path,
                        "last_open_directory": str(Path(new_path).parent),
                    })
                    st.success(f"New dataset created at `{Path(new_path).resolve()}`.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Failed to create dataset: {exc}")

    entries = st.session_state.loaded_entries
    all_pairs = get_all_entry_pairs()
    if all_pairs:
        st.divider()
        st.subheader(f"Entries ({len(all_pairs)})")

        invalid_count = sum(1 for e in entries if validate_entry(e))
        if invalid_count:
            st.warning(f"{invalid_count} entry/entries have validation issues.")
        else:
            st.success("All entries are valid.")

        # ── Filter controls ────────────────────────────────────────────────────
        _label_map: dict[str, str] = {_UNTAGGED: "Untagged"}
        for _cat, _cat_tags in TAGS.items():
            for _tag in _cat_tags:
                _label_map[_tag] = f"{_cat} / {_tag}"

        _used_tags: set[str] = set()
        _has_untagged = False
        for _e in entries:
            _et = _e.get("tags") or []
            if _et:
                _used_tags.update(_et)
            else:
                _has_untagged = True

        def _reset_page() -> None:
            st.session_state.entry_page = 0

        def _reset_page_and_selection() -> None:
            st.session_state.entry_page = 0
            st.session_state.filter_tags = []

        only_used = st.checkbox(
            "Only show used tags",
            key="filter_only_used",
            on_change=_reset_page_and_selection,
        )

        _all_flat = [t for _c in TAGS.values() for t in _c]
        if only_used:
            _available = [t for t in _all_flat if t in _used_tags]
            if _has_untagged:
                _available.append(_UNTAGGED)
        else:
            _available = _all_flat + [_UNTAGGED]

        # Apply pending correction BEFORE the widget instantiates (Streamlit
        # forbids writing a widget's key after it has rendered in the same run).
        if "filter_tags_pending" in st.session_state:
            st.session_state["filter_tags"] = st.session_state.pop("filter_tags_pending")

        # Drop any stale selections no longer in the available option list
        _clamped = [t for t in st.session_state.get("filter_tags", []) if t in _available]
        if _clamped != st.session_state.get("filter_tags", []):
            st.session_state["filter_tags"] = _clamped

        filter_col, mode_col = st.columns([3, 1])
        with filter_col:
            filter_tags = st.multiselect(
                "Filter entries by tag",
                options=_available,
                format_func=lambda x: _label_map.get(x, x),
                key="filter_tags",
                on_change=_reset_page,
            )

        # If every available real tag is selected alongside __untagged__, the
        # user almost certainly hit "Select all". Write the correction to a
        # pending key and rerun so it is applied before the widget renders.
        _available_real = [t for t in _available if t != _UNTAGGED]
        _selected_real = [t for t in filter_tags if t != _UNTAGGED]
        if (
            _UNTAGGED in filter_tags
            and _available_real
            and set(_selected_real) == set(_available_real)
        ):
            st.session_state["filter_tags_pending"] = _selected_real
            st.rerun()
        with mode_col:
            match_mode = st.radio(
                "Match mode",
                options=["Any selected tags", "All selected tags", "Exact match"],
                key="filter_match_mode",
                on_change=_reset_page,
            )

        # ── Apply filter ───────────────────────────────────────────────────────
        filtered_pairs = filter_entry_pairs_by_tags(
            all_pairs,
            selected_tags=filter_tags,
            match_mode=match_mode,
        )

        # ── Pagination ─────────────────────────────────────────────────────────
        per_page_options = [10, 25, 50, 100]
        default_idx = per_page_options.index(st.session_state.get("entries_per_page", 25))
        selected_per_page = st.selectbox(
            "Entries per page",
            options=per_page_options,
            index=default_idx,
            key="_entries_per_page_select",
        )
        if selected_per_page != st.session_state.get("entries_per_page"):
            st.session_state.entries_per_page = selected_per_page
            st.session_state.entry_page = 0
            st.rerun()

        total_filtered = len(filtered_pairs)
        total_all = len(all_pairs)

        if total_filtered == 0:
            st.info("No entries match the current filters.")
        else:
            per_page = st.session_state.entries_per_page
            last_page = max(0, (total_filtered - 1) // per_page)
            # _cur_page used here to avoid shadowing the navigation `page` variable
            _cur_page = min(st.session_state.get("entry_page", 0), last_page)
            start = _cur_page * per_page
            end = min(start + per_page, total_filtered)

            if filter_tags:
                st.caption(
                    f"Showing {start + 1}–{end} of {total_filtered} filtered entries ({total_all} total)"
                )
            else:
                st.caption(f"Showing {start + 1}–{end} of {total_all} entries")

            for i, (entry_id, entry) in enumerate(filtered_pairs[start:end], start=start):
                errs = validate_entry(entry)
                entry_tags = entry.get("tags") or []
                _tag_part = ", ".join(entry_tags) if entry_tags else "untagged"
                _fmt_part = st.session_state.dataset_format
                _exc_part = count_exchanges(entry)
                label = (
                    f"Entry {i + 1} | FORMAT: {_fmt_part} | "
                    f"TAGS: {_tag_part} | EXCHANGES: {_exc_part}"
                )
                if errs:
                    label += " ⚠️"
                with st.expander(label):
                    st.caption(f"Temp ID: {entry_id}")
                    if errs:
                        for err in errs:
                            st.error(err)
                    msgs = entry.get("messages", [])
                    for msg in msgs:
                        role = msg.get("role", "?")
                        content = msg.get("content", "")
                        color = {"system": "#555", "user": "#1a73e8", "assistant": "#188038"}.get(role, "#000")
                        if role == "system":
                            body = f"<span style='color:#f1c40f'>{content}</span>"
                        else:
                            body = _format_preview_content(content)
                        st.markdown(
                            f"<span style='color:{color};font-weight:bold;text-transform:uppercase'>{role}:</span> {body}",
                            unsafe_allow_html=True,
                        )
                        st.write("")

            col_prev, col_next = st.columns(2)
            with col_prev:
                if st.button("Previous", disabled=(_cur_page == 0), width='stretch'):
                    st.session_state.entry_page = _cur_page - 1
                    st.rerun()
            with col_next:
                if st.button("Next", disabled=(_cur_page >= last_page), width='stretch'):
                    st.session_state.entry_page = _cur_page + 1
                    st.rerun()


# ── Edit Entries (placeholder) ─────────────────────────────────────────────────
elif page == "Edit Entries":
    st.info("This page is planned but not implemented yet.")


# ── Merge Datasets ─────────────────────────────────────────────────────────────
elif page == "Merge Datasets":
    st.subheader("Merge Multiple Datasets")

    if "merge_input_paths_pending" in st.session_state:
        st.session_state["merge_input_paths"] = st.session_state.pop("merge_input_paths_pending")
    elif "merge_input_paths" not in st.session_state:
        st.session_state["merge_input_paths"] = ""

    col_area, col_add = st.columns([5, 1])
    with col_area:
        raw_paths = st.text_area(
            "File paths to merge (one per line)",
            placeholder="data/set1.jsonl\ndata/set2.jsonl\ndata/set3.jsonl",
            height=120,
            key="merge_input_paths",
        )
    with col_add:
        st.write("")
        st.write("")
        if st.button("Add Files"):
            browse_open_multiple("merge_input_paths", "merge_input_paths_pending")

    shuffle = st.checkbox("Randomly shuffle merged output", value=True)

    output_path = path_input(
        "Output file path",
        state_key="merge_output_path",
        browse_fn=browse_save_file,
        browse_kwargs={"default_name": "merged_dataset.jsonl"},
        default="merged_dataset.jsonl",
    )

    if st.button("Merge", type="primary"):
        paths = [p.strip() for p in raw_paths.strip().splitlines() if p.strip()]
        if not paths:
            st.error("Enter at least one file path.")
        else:
            merged, stats = merge_datasets(paths, shuffle=shuffle)

            st.info(
                f"Loaded: **{stats['total_loaded']}** | "
                f"Duplicates removed: **{stats['duplicates_removed']}** | "
                f"Final count: **{len(merged)}**"
            )

            if stats["parse_errors"]:
                with st.expander("Parse errors"):
                    for err in stats["parse_errors"]:
                        st.error(err)

            if merged:
                p = output_path.strip()
                try:
                    save_dataset(p, merged)
                    st.success(f"Merged dataset saved to `{p}`.")

                    content = "\n".join(json.dumps(e, ensure_ascii=False) for e in merged)
                    st.download_button(
                        "Download merged JSONL",
                        data=content.encode("utf-8"),
                        file_name=Path(p).name,
                        mime="application/jsonlines",
                    )
                except Exception as exc:
                    st.error(f"Failed to save merged dataset: {exc}")


# ── Export ─────────────────────────────────────────────────────────────────────
elif page == "Export":
    ensure_entry_registry()
    st.subheader("Export Dataset")

    if "export_success_msg" in st.session_state:
        st.success(st.session_state.pop("export_success_msg"))

    _export_entries = st.session_state.loaded_entries
    if not _export_entries:
        st.info("Load a dataset to export.")
    else:
        st.caption(f"{len(_export_entries)} entries loaded from `{st.session_state.loaded_path or 'unknown'}`")

        clean_export = st.checkbox("Clean — Tag data removed", value=False, key="export_clean")

        # Browse button opens save dialog (pure Tkinter → rerun, no save work done here).
        # Export button only calls save_dataset — no Tkinter, no threading risk.
        export_save_path = path_input(
            "Export file path",
            state_key="export_save_path",
            browse_fn=browse_export_file,
            browse_kwargs={},
            default="",
        )

        if st.button("Export as JSONL", type="primary", width="stretch"):
            _p = export_save_path.strip()
            if not _p:
                st.error("Set an export path or use Browse to pick a location.")
            else:
                try:
                    _out = (
                        [{"messages": e["messages"]} for e in _export_entries]
                        if clean_export
                        else _export_entries
                    )
                    save_dataset(_p, _out)
                    st.session_state["export_success_msg"] = (
                        f"Exported {len(_out)} entries to `{Path(_p).resolve()}`."
                    )
                    st.session_state["export_save_path_pending"] = ""
                    st.rerun()
                except Exception as exc:
                    st.error(f"Export failed: {exc}")


# ── Validation (placeholder) ───────────────────────────────────────────────────
elif page == "Validation":
    st.info("This page is planned but not implemented yet.")


# ── Statistics ─────────────────────────────────────────────────────────────────
elif page == "Statistics":
    ensure_entry_registry()
    _stat_entries = st.session_state.loaded_entries

    if not _stat_entries:
        st.info("Load a dataset in Manage Dataset to see statistics.")
    else:
        _s = build_dataset_stats(_stat_entries)

        # ── Summary cards ──────────────────────────────────────────────────────
        _c1, _c2, _c3, _c4, _c5, _c6 = st.columns(6)
        _c1.metric("Total Entries", _s["total"])
        _c2.metric("Total Exchanges", _s["total_exchanges"])
        _c3.metric("Avg Exchanges / Entry", f"{_s['avg_exchanges']:.1f}")
        _c4.metric("Invalid Entries", _s["invalid_count"])
        _c5.metric("Untagged Entries", _s["untagged_count"])
        _c6.metric("Unique Tags", _s["unique_tags"])

        # ── Message Lengths ────────────────────────────────────────────────────
        st.divider()
        st.subheader("Message Lengths")
        _l1, _l2, _l3, _l4, _l5 = st.columns(5)
        _l1.metric("Avg User Message", f"{_s['avg_user_len']:.0f} chars")
        _l2.metric("Avg Assistant Message", f"{_s['avg_asst_len']:.0f} chars")
        _l3.metric("Avg Entry Length", f"{_s['avg_entry_len']:.0f} chars")
        _l4.metric("Shortest Assistant Response", f"{_s['min_asst_len']} chars")
        _l5.metric("Longest Assistant Response", f"{_s['max_asst_len']} chars")

        # ── Tag Balance ────────────────────────────────────────────────────────
        st.divider()
        st.subheader("Tag Balance")
        if not _s["tag_counts"]:
            st.info("No tags found in this dataset.")
        else:
            _tb1, _tb2 = st.columns(2)

            with _tb1:
                _df_tags = (
                    pd.DataFrame(
                        _s["tag_counts"].items(), columns=["Tag", "Count"]
                    )
                    .sort_values("Count", ascending=False)
                    .reset_index(drop=True)
                )
                st.plotly_chart(
                    px.bar(_df_tags, x="Tag", y="Count", title="Tag Counts"),
                    width='stretch',
                )

            with _tb2:
                _df_cat = (
                    pd.DataFrame(
                        _s["tag_category_counts"].items(), columns=["Category", "Count"]
                    )
                    .sort_values("Count", ascending=False)
                    .reset_index(drop=True)
                )
                st.plotly_chart(
                    px.bar(_df_cat, x="Category", y="Count", title="Tag Category Counts"),
                    width='stretch',
                )

            st.dataframe(
                _df_tags.rename(columns={"Tag": "Tag", "Count": "Entries using tag"}),
                width='stretch',
                hide_index=True,
            )

        # ── Exchange Depth ─────────────────────────────────────────────────────
        st.divider()
        st.subheader("Exchange Depth")
        _ed1, _ed2 = st.columns([3, 1])

        with _ed1:
            _df_exc = (
                pd.DataFrame(
                    sorted(_s["exchange_dist"].items()), columns=["Exchanges", "Entries"]
                )
            )
            st.plotly_chart(
                px.bar(_df_exc, x="Exchanges", y="Entries", title="Entries by Exchange Count"),
                width='stretch',
            )

        with _ed2:
            st.metric("Single-turn entries", _s["single_turn"])
            st.metric("Multi-turn entries", _s["multi_turn"])

        # ── Format Distribution ────────────────────────────────────────────────
        st.divider()
        st.subheader("Format Distribution")
        _fmt = st.session_state.dataset_format
        _f1, _f2 = st.columns(2)
        _f1.metric(_fmt, _s["total"], help="All entries are treated as this format.")
        with _f2:
            st.plotly_chart(
                px.bar(
                    pd.DataFrame([{"Format": _fmt, "Entries": _s["total"]}]),
                    x="Format",
                    y="Entries",
                    title="Format Distribution",
                ),
                width='stretch',
            )

        # ── Validation ────────────────────────────────────────────────────────
        st.divider()
        st.subheader("Validation")
        _v1, _v2 = st.columns(2)
        _v1.metric("Valid Entries", _s["valid_count"])
        _v2.metric("Invalid Entries", _s["invalid_count"])

        if _s["invalid_rows"]:
            _stat_ids = st.session_state.entry_registry.get("ids", [])
            _df_val = pd.DataFrame([
                {
                    "Temp ID": _stat_ids[r["entry"] - 1] if r["entry"] - 1 < len(_stat_ids) else "—",
                    "Entry": r["entry"],
                    "Error Count": r["error_count"],
                    "Errors": "; ".join(r["errors"]),
                }
                for r in _s["invalid_rows"]
            ])
            st.dataframe(_df_val, width='stretch', hide_index=True)


# ── Settings ───────────────────────────────────────────────────────────────────
elif page == "Settings":
    st.subheader("Dataset Format")

    def _persist_dataset_format():
        st.session_state.dataset_format = st.session_state["_dataset_format_select"]
        _update_prefs({"dataset_format": st.session_state.dataset_format})

    st.selectbox(
        "Default dataset format",
        options=["ChatML"],
        index=["ChatML"].index(st.session_state.dataset_format)
        if st.session_state.dataset_format in ["ChatML"] else 0,
        key="_dataset_format_select",
        on_change=_persist_dataset_format,
    )

    st.divider()
    st.subheader("Conversation Preview Settings")

    def _persist_preview_user_name():
        st.session_state.preview_user_name = st.session_state["_preview_user_name_input"]
        _update_prefs({"preview_user_name": st.session_state.preview_user_name})

    def _persist_preview_assistant_name():
        st.session_state.preview_assistant_name = st.session_state["_preview_assistant_name_input"]
        _update_prefs({"preview_assistant_name": st.session_state.preview_assistant_name})

    st.text_input(
        "User Name",
        value=st.session_state.preview_user_name,
        key="_preview_user_name_input",
        on_change=_persist_preview_user_name,
    )
    st.text_input(
        "Assistant Name",
        value=st.session_state.preview_assistant_name,
        key="_preview_assistant_name_input",
        on_change=_persist_preview_assistant_name,
    )
