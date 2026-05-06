import json
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
    filter_entry_pairs_by_tags,
    get_all_tags,
    get_available_filter_tags,
    get_entry_messages,
    get_entry_pairs,
    get_entry_tags,
    get_index_for_entry_id,
    get_role_messages,
    get_tag_label_map,
    load_dataset,
    make_entry,
    merge_datasets,
    registry_is_valid,
    remove_registry_id,
    replace_entry_tags,
    save_dataset,
    set_entry_system_prompt,
    validate_entry,
)
from file_dialogs import (
    JSONL_TYPES,
    _tk_root,
    browse_export_file,
    browse_open_file,
    browse_open_multiple,
    browse_save_file,
    path_input,
)
from preferences import get_initial_dir, load_preferences, save_preferences
from ui_components import (
    _ROLE_COLOR,
    render_conversation_preview,
    render_json_preview,
    render_message_preview,
    render_tag_multiselects,
)

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
_ROLE_PLACEHOLDER = {
    "user": "What the user says…",
    "assistant": "What the assistant replies…",
}

_UNTAGGED = "__untagged__"


# ── Preferences helpers ────────────────────────────────────────────────────────
def _update_prefs(updates: dict) -> None:
    st.session_state.prefs.update(updates)
    save_preferences(st.session_state.prefs)


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


# ── Selection helpers ─────────────────────────────────────────────────────────

def ensure_selection_state() -> None:
    """Ensure selected_entry_ids exists as a set in session state."""
    if not isinstance(st.session_state.get("selected_entry_ids"), set):
        st.session_state.selected_entry_ids = set()


def clear_selected_entries() -> None:
    """Clear all selected entry IDs."""
    st.session_state.selected_entry_ids = set()


def toggle_entry_selection(entry_id: str, selected: bool) -> None:
    """Add or remove entry_id from selected_entry_ids."""
    ensure_selection_state()
    if selected:
        st.session_state.selected_entry_ids.add(entry_id)
    else:
        st.session_state.selected_entry_ids.discard(entry_id)


def select_visible_entries(visible_pairs: list[tuple[str, dict]]) -> None:
    """Add all visible (current-page) entry IDs to selected_entry_ids."""
    ensure_selection_state()
    for entry_id, _ in visible_pairs:
        st.session_state.selected_entry_ids.add(entry_id)


def deselect_visible_entries(visible_pairs: list[tuple[str, dict]]) -> None:
    """Remove all visible (current-page) entry IDs from selected_entry_ids."""
    ensure_selection_state()
    for entry_id, _ in visible_pairs:
        st.session_state.selected_entry_ids.discard(entry_id)


def get_selected_entry_ids() -> list[str]:
    """Return selected IDs as a list."""
    ensure_selection_state()
    return list(st.session_state.selected_entry_ids)


def prune_selection_to_loaded_entries() -> None:
    """Remove selected IDs that no longer exist in the current registry.

    Call after loading, creating, deleting, or any registry rebuild.
    """
    ensure_selection_state()
    ensure_entry_registry()
    valid_ids = set(st.session_state.entry_registry.get("ids", []))
    st.session_state.selected_entry_ids &= valid_ids


def save_loaded_dataset() -> bool:
    """Save loaded_entries to loaded_path. Returns True on success, False on failure."""
    try:
        save_dataset(st.session_state.loaded_path, st.session_state.loaded_entries)
        return True
    except Exception as exc:
        st.error(f"Failed to save dataset: {exc}")
        return False


def delete_selected_entries() -> tuple[int, list[str]]:
    """Delete selected entries by temp ID and persist to disk.

    Clears selection only if the save succeeds.
    Returns (count_deleted, list_of_failed_ids).
    """
    ids_to_delete = get_selected_entry_ids()
    deleted = 0
    failures: list[str] = []
    for entry_id in ids_to_delete:
        if delete_loaded_entry_by_id(entry_id):
            deleted += 1
        else:
            failures.append(entry_id)
    if deleted > 0 and save_loaded_dataset():
        clear_selected_entries()
    return deleted, failures


# ── Quick-edit helpers ────────────────────────────────────────────────────────

def start_quick_edit(entry_id: str, entry: dict) -> None:
    """Enter quick edit mode for entry_id.

    Sets quick_edit_entry_id and pre-loads each user/assistant message into
    its text-area session-state key so the widget opens with current content.
    """
    st.session_state.quick_edit_entry_id = entry_id
    for idx, msg in enumerate(entry.get("messages", [])):
        if isinstance(msg, dict) and msg.get("role") in ("user", "assistant"):
            st.session_state[f"quick_edit_{entry_id}_{idx}"] = msg.get("content", "")


def cancel_quick_edit() -> None:
    """Exit quick edit mode without saving."""
    entry_id = st.session_state.get("quick_edit_entry_id")
    st.session_state.quick_edit_entry_id = None
    # Remove stale text-area keys for the closed entry so re-opening starts fresh
    if entry_id:
        keys_to_drop = [
            k for k in list(st.session_state.keys())
            if k.startswith(f"quick_edit_{entry_id}_")
        ]
        for k in keys_to_drop:
            st.session_state.pop(k, None)


def save_quick_edit(entry_id: str, entry: dict) -> bool:
    """Read edited message content from session state, validate, then save.

    Updates only user/assistant message content in place.
    System message, role names, tags, and message order are preserved.
    Returns True on successful save, False if validation fails or save errors.
    """
    msgs = entry.get("messages", [])
    updated_msgs = []
    for idx, msg in enumerate(msgs):
        if not isinstance(msg, dict):
            updated_msgs.append(msg)
            continue
        role = msg.get("role")
        if role in ("user", "assistant"):
            new_content = st.session_state.get(
                f"quick_edit_{entry_id}_{idx}", msg.get("content", "")
            )
            updated_msgs.append({**msg, "content": new_content})
        else:
            updated_msgs.append(dict(msg))

    # Validate against a temporary copy before committing
    temp_entry = {**entry, "messages": updated_msgs}
    errors = validate_entry(temp_entry)
    if errors:
        for err in errors:
            st.error(err)
        return False

    # Apply in-place and persist
    entry["messages"] = updated_msgs
    return save_loaded_dataset()


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
    _col_planned, _col_planned_spacer = st.columns([1, 3])
    with _col_planned:
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
    selected_tags = render_tag_multiselects(prefix)

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

        render_json_preview(entry_preview, expanded=False)

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
    st.session_state.selected_entry_ids = set()
    st.session_state.confirm_delete_entries = prefs.get("confirm_delete_entries", True)
    st.session_state.quick_edit_entry_id = None
    st.session_state.edit_entry_page = 0
    st.session_state.edit_entries_per_page = 25
    st.session_state.edit_filter_tags = []
    st.session_state.edit_filter_only_used = True
    st.session_state.edit_filter_match_mode = "Any selected tags"
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
    ensure_selection_state()
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
            clear_selected_entries()
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
                    clear_selected_entries()
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
        _label_map = get_tag_label_map(untagged_key=_UNTAGGED)

        def _reset_page() -> None:
            st.session_state.entry_page = 0

        def _reset_page_and_selection() -> None:
            st.session_state.entry_page = 0
            st.session_state.filter_tags = []

        only_used = st.checkbox(
            "Only show used tags",
            value=st.session_state.get("filter_only_used", True),
            key="filter_only_used",
            on_change=_reset_page_and_selection,
        )

        _available = get_available_filter_tags(entries, only_used=only_used, untagged_key=_UNTAGGED)

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
        per_page_options = [10, 25, 50, 100, 500, "Show All"]
        _saved_per_page = st.session_state.get("entries_per_page", 25)
        default_idx = (
            per_page_options.index(_saved_per_page)
            if _saved_per_page in per_page_options
            else 1  # fallback to 25
        )
        _col_per_page, _col_per_page_spacer = st.columns([1, 3])
        with _col_per_page:
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
            _per_page_setting = st.session_state.entries_per_page
            if _per_page_setting == "Show All":
                per_page = total_filtered
                last_page = 0
                _cur_page = 0
                start = 0
                end = total_filtered
            else:
                per_page = _per_page_setting
                last_page = max(0, (total_filtered - 1) // per_page)
                # _cur_page used here to avoid shadowing the navigation `page` variable
                _cur_page = min(st.session_state.get("entry_page", 0), last_page)
                start = _cur_page * per_page
                end = min(start + per_page, total_filtered)
            visible_pairs = filtered_pairs[start:end]

            # ── Flash messages ─────────────────────────────────────────────────
            if "quick_edit_success" in st.session_state:
                st.success(st.session_state.pop("quick_edit_success"))

            # ── Status line (always visible) ───────────────────────────────────
            _selected_ids = get_selected_entry_ids()
            _total_sel = len(_selected_ids)
            if filter_tags:
                st.caption(
                    f"Showing {start + 1}–{end} of {total_filtered} filtered entries "
                    f"({total_all} total) | {_total_sel} of {total_filtered} selected"
                )
            else:
                st.caption(
                    f"Showing {start + 1}–{end} of {total_all} entries "
                    f"| {_total_sel} of {total_all} selected"
                )

            # ── Selection + action buttons (single row) ────────────────────────
            _no_sel = _total_sel == 0
            (
                _col_sel_all, _col_clear,
                _col_sys_prompt, _col_delete, _col_act_spacer,
            ) = st.columns([1, 1, 1, 1, 2])
            with _col_sel_all:
                if st.button("Select all visible", key="btn_select_all_visible",
                             width="stretch"):
                    select_visible_entries(visible_pairs)
                    st.rerun()
            with _col_clear:
                if st.button("Clear Selection", key="btn_clear_visible",
                             width="stretch"):
                    deselect_visible_entries(visible_pairs)
                    st.rerun()
            with _col_sys_prompt:
                if st.button("Modify System", key="btn_modify_sys_prompt",
                             disabled=_no_sel, width="stretch"):
                    st.session_state["pending_system_prompt_edit"] = True
                    st.session_state.pop("bulk_system_prompt_text", None)
                    st.rerun()
            with _col_delete:
                if st.button("Delete Selected", key="btn_delete_selected",
                             disabled=_no_sel, width="stretch"):
                    if st.session_state.get("confirm_delete_entries", True):
                        st.session_state["pending_delete_selected"] = True
                        st.rerun()
                    else:
                        _n, _failures = delete_selected_entries()
                        prune_selection_to_loaded_entries()
                        _new_total = len(st.session_state.loaded_entries)
                        if _new_total == 0 or st.session_state.entry_page > max(
                            0, (_new_total - 1) // per_page
                        ):
                            st.session_state.entry_page = 0
                        if _failures:
                            st.warning(
                                f"Deleted {_n} entries. "
                                f"{len(_failures)} could not be removed."
                            )
                        else:
                            st.success(f"Deleted {_n} entries.")
                        st.rerun()

            # ── Confirmation UI (shown below button row when pending) ───────────
            if st.session_state.get("pending_delete_selected"):
                _pending_sel_ids = get_selected_entry_ids()
                st.warning(
                    f"Delete {len(_pending_sel_ids)} selected entrie(s)? "
                    "This cannot be undone."
                )
                _col_confirm, _col_cancel, _col_del_spacer = st.columns([1, 1, 2])
                with _col_confirm:
                    if st.button("Confirm Delete", type="primary",
                                 key="btn_confirm_delete", width="stretch"):
                        _n, _failures = delete_selected_entries()
                        st.session_state.pop("pending_delete_selected", None)
                        prune_selection_to_loaded_entries()
                        _new_total = len(st.session_state.loaded_entries)
                        if _new_total == 0 or st.session_state.entry_page > max(
                            0, (_new_total - 1) // per_page
                        ):
                            st.session_state.entry_page = 0
                        if _failures:
                            st.warning(
                                f"Deleted {_n} entries. "
                                f"{len(_failures)} could not be removed."
                            )
                        else:
                            st.success(f"Deleted {_n} entries.")
                        st.rerun()
                with _col_cancel:
                    if st.button("Cancel", key="btn_cancel_delete", width="stretch"):
                        st.session_state.pop("pending_delete_selected", None)
                        st.rerun()

            # ── System prompt editor (shown when pending) ──────────────────────
            if "sys_prompt_success" in st.session_state:
                st.success(st.session_state.pop("sys_prompt_success"))

            if st.session_state.get("pending_system_prompt_edit"):
                st.info(
                    f"Replace the system prompt for {_total_sel} selected "
                    "entrie(s). This will overwrite existing system prompts "
                    "or insert one if missing."
                )
                _new_prompt = st.text_area(
                    "New system prompt",
                    key="bulk_system_prompt_text",
                    height=120,
                )
                _col_apply, _col_sp_cancel, _col_sp_spacer = st.columns([1, 1, 2])
                with _col_apply:
                    if st.button(
                        "Apply System Prompt",
                        key="btn_apply_sys_prompt",
                        disabled=not (_new_prompt or "").strip(),
                        width="stretch",
                    ):
                        for _sid in _selected_ids:
                            _se = get_loaded_entry_by_id(_sid)
                            if _se is not None:
                                set_entry_system_prompt(_se, _new_prompt.strip())
                        if save_loaded_dataset():
                            st.session_state.pop("pending_system_prompt_edit", None)
                            st.session_state["sys_prompt_success"] = (
                                f"System prompt updated for {_total_sel} entries."
                            )
                            st.rerun()
                with _col_sp_cancel:
                    if st.button("Cancel", key="btn_sp_cancel", width="stretch"):
                        st.session_state.pop("pending_system_prompt_edit", None)
                        st.rerun()

            # ── Quick tag editor ───────────────────────────────────────────────
            _selected_count = len(_selected_ids)
            if _selected_count >= 1:
                _tag_label_map = get_tag_label_map(include_untagged=False)

            if _selected_count == 1:
                st.markdown("**Quick Tag Edit**")
                _qt_entry_id = _selected_ids[0]
                _qt_entry = get_loaded_entry_by_id(_qt_entry_id)
                if _qt_entry is not None:
                    _qt_current_tags = get_entry_tags(_qt_entry)
                    _qt_chosen = st.multiselect(
                        "Tags for selected entry",
                        options=get_all_tags(),
                        default=_qt_current_tags,
                        format_func=lambda t: _tag_label_map.get(t, t),
                        key=f"single_quick_tags_{_qt_entry_id}",
                    )
                    if st.button("Save Tags", key="btn_save_single_tags"):
                        replace_entry_tags(_qt_entry, _qt_chosen)
                        if save_loaded_dataset():
                            st.success("Tags updated for selected entry.")
                            st.rerun()

            elif _selected_count >= 2:
                st.markdown("**Bulk Tag Edit**")
                _bulk_chosen = st.multiselect(
                    "Replacement tags",
                    options=get_all_tags(),
                    format_func=lambda t: _tag_label_map.get(t, t),
                    key="bulk_replace_tags",
                )
                _col_bulk_replace, _col_bulk_clear = st.columns(2)
                with _col_bulk_replace:
                    if st.button(
                        f"Replace tags on {_selected_count} selected",
                        key="btn_bulk_replace_tags",
                        width="stretch",
                    ):
                        for _bid in _selected_ids:
                            _be = get_loaded_entry_by_id(_bid)
                            if _be is not None:
                                replace_entry_tags(_be, _bulk_chosen)
                        if save_loaded_dataset():
                            st.success(f"Tags replaced for {_selected_count} entries.")
                            st.rerun()
                with _col_bulk_clear:
                    if st.button(
                        f"Clear tags on {_selected_count} selected",
                        key="btn_bulk_clear_tags",
                        width="stretch",
                    ):
                        for _bid in _selected_ids:
                            _be = get_loaded_entry_by_id(_bid)
                            if _be is not None:
                                replace_entry_tags(_be, [])
                        if save_loaded_dataset():
                            st.success(f"Tags cleared for {_selected_count} entries.")
                            st.rerun()

            # ── Entry list ─────────────────────────────────────────────────────
            # Sync all visible checkbox widget keys from selected_entry_ids
            # BEFORE any checkbox widget renders so visual state is always correct.
            # Only visible_pairs (current page) are synced — other pages are unaffected.
            for _sync_id, _ in visible_pairs:
                st.session_state[f"select_{_sync_id}"] = (
                    _sync_id in st.session_state.selected_entry_ids
                )

            def _on_checkbox_change(entry_id: str) -> None:
                toggle_entry_selection(
                    entry_id, st.session_state[f"select_{entry_id}"]
                )

            for i, (entry_id, entry) in enumerate(visible_pairs, start=start):
                errs = validate_entry(entry)
                entry_tags = get_entry_tags(entry)
                _tag_part = ", ".join(entry_tags) if entry_tags else "untagged"
                _fmt_part = st.session_state.dataset_format
                _exc_part = count_exchanges(entry)
                label = (
                    f"Entry {i + 1} | FORMAT: {_fmt_part} | "
                    f"TAGS: {_tag_part} | EXCHANGES: {_exc_part}"
                )
                if errs:
                    label += " ⚠️"
                _col_cb, _col_entry = st.columns([1, 20])
                with _col_cb:
                    st.checkbox(
                        "Select",
                        key=f"select_{entry_id}",
                        on_change=_on_checkbox_change,
                        args=(entry_id,),
                        label_visibility="collapsed",
                    )
                with _col_entry:
                    with st.expander(label):
                        st.caption(f"Temp ID: {entry_id}")
                        _is_qe = (
                            st.session_state.get("quick_edit_entry_id") == entry_id
                        )

                        if _is_qe:
                            # ── Quick edit mode ────────────────────────────────
                            st.markdown("**Quick Edit Messages**")
                            _qe_msgs = entry.get("messages", [])
                            _exchange_num = 0
                            for _qe_idx, _qe_msg in enumerate(_qe_msgs):
                                if not isinstance(_qe_msg, dict):
                                    continue
                                _qe_role = _qe_msg.get("role")
                                if _qe_role == "user":
                                    _exchange_num += 1
                                if _qe_role in ("user", "assistant"):
                                    st.text_area(
                                        f"{_qe_role.upper()} message {_exchange_num}",
                                        key=f"quick_edit_{entry_id}_{_qe_idx}",
                                        height=120,
                                    )
                            _col_save_qe, _col_cancel_qe = st.columns(2)
                            with _col_save_qe:
                                if st.button(
                                    "Save Quick Edit",
                                    key=f"btn_save_qe_{entry_id}",
                                    type="primary",
                                    width="stretch",
                                ):
                                    if save_quick_edit(entry_id, entry):
                                        cancel_quick_edit()
                                        st.session_state["quick_edit_success"] = (
                                            "Entry updated."
                                        )
                                        st.rerun()
                            with _col_cancel_qe:
                                if st.button(
                                    "Cancel",
                                    key=f"btn_cancel_qe_{entry_id}",
                                    width="stretch",
                                ):
                                    cancel_quick_edit()
                                    st.rerun()

                        else:
                            # ── Normal preview mode ────────────────────────────
                            if st.button(
                                "Quick Edit",
                                key=f"btn_quick_edit_{entry_id}",
                            ):
                                start_quick_edit(entry_id, entry)
                                st.rerun()
                            if errs:
                                for err in errs:
                                    st.error(err)
                            render_message_preview(
                                entry.get("messages", []), include_system=True
                            )

            # ── Pagination buttons ─────────────────────────────────────────────
            col_prev, col_next = st.columns(2)
            with col_prev:
                if st.button("Previous", disabled=(_cur_page == 0), width='stretch'):
                    st.session_state.entry_page = _cur_page - 1
                    st.rerun()
            with col_next:
                if st.button("Next", disabled=(_cur_page >= last_page), width='stretch'):
                    st.session_state.entry_page = _cur_page + 1
                    st.rerun()


# ── Edit Entries ───────────────────────────────────────────────────────────────
elif page == "Edit Entries":
    ensure_entry_registry()
    _ee_entries = st.session_state.loaded_entries
    _ee_all_pairs = get_all_entry_pairs()

    if not _ee_all_pairs:
        st.info("Load a dataset in Manage Dataset to edit entries.")
    else:
        st.subheader(f"Browse Entries ({len(_ee_all_pairs)})")

        # ── Filter controls ────────────────────────────────────────────────────
        _ee_label_map = get_tag_label_map(untagged_key=_UNTAGGED)

        def _ee_reset_page() -> None:
            st.session_state.edit_entry_page = 0

        def _ee_reset_page_and_selection() -> None:
            st.session_state.edit_entry_page = 0
            st.session_state.edit_filter_tags = []

        _ee_only_used = st.checkbox(
            "Only show used tags",
            value=st.session_state.get("edit_filter_only_used", True),
            key="edit_filter_only_used",
            on_change=_ee_reset_page_and_selection,
        )

        _ee_available = get_available_filter_tags(
            _ee_entries, only_used=_ee_only_used, untagged_key=_UNTAGGED
        )

        # Apply pending correction before the multiselect widget renders
        if "edit_filter_tags_pending" in st.session_state:
            st.session_state["edit_filter_tags"] = st.session_state.pop(
                "edit_filter_tags_pending"
            )

        # Drop stale selections no longer in available options
        _ee_clamped = [
            t for t in st.session_state.get("edit_filter_tags", [])
            if t in _ee_available
        ]
        if _ee_clamped != st.session_state.get("edit_filter_tags", []):
            st.session_state["edit_filter_tags"] = _ee_clamped

        _ee_filter_col, _ee_mode_col = st.columns([3, 1])
        with _ee_filter_col:
            _ee_filter_tags = st.multiselect(
                "Filter entries by tag",
                options=_ee_available,
                format_func=lambda x: _ee_label_map.get(x, x),
                key="edit_filter_tags",
                on_change=_ee_reset_page,
            )

        # Guard against "Select all" accidentally including __untagged__
        _ee_available_real = [t for t in _ee_available if t != _UNTAGGED]
        _ee_selected_real = [t for t in _ee_filter_tags if t != _UNTAGGED]
        if (
            _UNTAGGED in _ee_filter_tags
            and _ee_available_real
            and set(_ee_selected_real) == set(_ee_available_real)
        ):
            st.session_state["edit_filter_tags_pending"] = _ee_selected_real
            st.rerun()

        with _ee_mode_col:
            _ee_match_mode = st.radio(
                "Match mode",
                options=["Any selected tags", "All selected tags", "Exact match"],
                key="edit_filter_match_mode",
                on_change=_ee_reset_page,
            )

        # ── Apply filter ───────────────────────────────────────────────────────
        _ee_filtered_pairs = filter_entry_pairs_by_tags(
            _ee_all_pairs,
            selected_tags=_ee_filter_tags,
            match_mode=_ee_match_mode,
        )

        # ── Pagination ─────────────────────────────────────────────────────────
        _ee_per_page_options = [10, 25, 50, 100, 500, "Show All"]
        _ee_saved_per_page = st.session_state.get("edit_entries_per_page", 25)
        _ee_default_idx = (
            _ee_per_page_options.index(_ee_saved_per_page)
            if _ee_saved_per_page in _ee_per_page_options
            else 1
        )
        _ee_col_per_page, _ee_col_per_page_spacer = st.columns([1, 3])
        with _ee_col_per_page:
            _ee_selected_per_page = st.selectbox(
                "Entries per page",
                options=_ee_per_page_options,
                index=_ee_default_idx,
                key="_ee_entries_per_page_select",
            )
        if _ee_selected_per_page != st.session_state.get("edit_entries_per_page"):
            st.session_state.edit_entries_per_page = _ee_selected_per_page
            st.session_state.edit_entry_page = 0
            st.rerun()

        _ee_total_filtered = len(_ee_filtered_pairs)
        _ee_total_all = len(_ee_all_pairs)

        if _ee_total_filtered == 0:
            st.info("No entries match the current filters.")
        else:
            _ee_per_page_setting = st.session_state.edit_entries_per_page
            if _ee_per_page_setting == "Show All":
                _ee_per_page = _ee_total_filtered
                _ee_last_page = 0
                _ee_cur_page = 0
                _ee_start = 0
                _ee_end = _ee_total_filtered
            else:
                _ee_per_page = _ee_per_page_setting
                _ee_last_page = max(0, (_ee_total_filtered - 1) // _ee_per_page)
                _ee_cur_page = min(
                    st.session_state.get("edit_entry_page", 0), _ee_last_page
                )
                _ee_start = _ee_cur_page * _ee_per_page
                _ee_end = min(_ee_start + _ee_per_page, _ee_total_filtered)
            _ee_visible_pairs = _ee_filtered_pairs[_ee_start:_ee_end]

            # ── Status line ────────────────────────────────────────────────────
            if _ee_filter_tags:
                st.caption(
                    f"Showing {_ee_start + 1}–{_ee_end} of {_ee_total_filtered} "
                    f"filtered entries ({_ee_total_all} total)"
                )
            else:
                st.caption(
                    f"Showing {_ee_start + 1}–{_ee_end} of {_ee_total_all} entries"
                )

            # ── Entry list ─────────────────────────────────────────────────────
            for _ee_i, (_ee_entry_id, _ee_entry) in enumerate(
                _ee_visible_pairs, start=_ee_start
            ):
                _ee_errs = validate_entry(_ee_entry)
                _ee_entry_tags = get_entry_tags(_ee_entry)
                _ee_tag_part = ", ".join(_ee_entry_tags) if _ee_entry_tags else "untagged"
                _ee_fmt_part = st.session_state.dataset_format
                _ee_exc_part = count_exchanges(_ee_entry)
                _ee_label = (
                    f"Entry {_ee_i + 1} | FORMAT: {_ee_fmt_part} | "
                    f"TAGS: {_ee_tag_part} | EXCHANGES: {_ee_exc_part}"
                )
                if _ee_errs:
                    _ee_label += " ⚠️"
                with st.expander(_ee_label):
                    st.caption(f"Temp ID: {_ee_entry_id}")
                    if _ee_errs:
                        for _ee_err in _ee_errs:
                            st.error(_ee_err)
                    render_message_preview(
                        _ee_entry.get("messages", []), include_system=True
                    )

            # ── Pagination buttons ─────────────────────────────────────────────
            _ee_col_prev, _ee_col_next = st.columns(2)
            with _ee_col_prev:
                if st.button(
                    "Previous",
                    disabled=(_ee_cur_page == 0),
                    width="stretch",
                    key="ee_btn_prev",
                ):
                    st.session_state.edit_entry_page = _ee_cur_page - 1
                    st.rerun()
            with _ee_col_next:
                if st.button(
                    "Next",
                    disabled=(_ee_cur_page >= _ee_last_page),
                    width="stretch",
                    key="ee_btn_next",
                ):
                    st.session_state.edit_entry_page = _ee_cur_page + 1
                    st.rerun()


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
    st.subheader("Editing Safety")

    def _persist_confirm_delete():
        st.session_state.confirm_delete_entries = st.session_state["_confirm_delete_checkbox"]
        _update_prefs({"confirm_delete_entries": st.session_state.confirm_delete_entries})

    st.checkbox(
        "Confirm before deleting entries",
        value=st.session_state.get("confirm_delete_entries", True),
        key="_confirm_delete_checkbox",
        on_change=_persist_confirm_delete,
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
