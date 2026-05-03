import json
import re
import tkinter as tk
from pathlib import Path
from tkinter import filedialog

import streamlit as st

from dataset import (
    DEFAULT_SYSTEM_PROMPT,
    TAGS,
    append_to_dataset,
    load_dataset,
    make_entry,
    merge_datasets,
    save_dataset,
    validate_entry,
)
from preferences import get_initial_dir, load_preferences, save_preferences

st.set_page_config(page_title="Roleplay Dataset Manager", layout="wide")
st.title("Roleplay Dataset Manager")

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
</style>
""", unsafe_allow_html=True)

JSONL_TYPES = [("JSONL files", "*.jsonl"), ("All files", "*.*")]

# ── One-time session initialisation ───────────────────────────────────────────
if "prefs" not in st.session_state:
    prefs = load_preferences()
    st.session_state.prefs = prefs

    st.session_state.system_prompt = prefs.get("last_system_prompt") or DEFAULT_SYSTEM_PROMPT
    st.session_state.loaded_entries = []
    st.session_state.loaded_path = ""
    st.session_state.stale_last_path = ""
    st.session_state.entry_page = 0
    st.session_state.entries_per_page = 25
    st.session_state.filter_tags = []
    st.session_state.filter_only_used = True
    st.session_state.filter_match_mode = "Any selected tags"
    st.session_state.turns = [{"role": "user"}, {"role": "assistant"}]

    last = prefs.get("last_loaded_dataset_path", "")
    if last:
        if Path(last).exists():
            entries, errors = load_dataset(last)
            st.session_state.loaded_entries = entries
            st.session_state.loaded_path = last
        else:
            st.session_state.stale_last_path = last


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
    pref_path_key: str = "last_save_dataset_path",
) -> None:
    prefs = st.session_state.prefs
    root = _tk_root()
    path = filedialog.asksaveasfilename(
        title="Save dataset as",
        defaultextension=".jsonl",
        initialfile=default_name,
        initialdir=get_initial_dir(prefs, path_key=pref_path_key, dir_key="last_save_directory"),
        filetypes=JSONL_TYPES,
    )
    root.destroy()
    if path:
        st.session_state[pending_key] = path
        _update_prefs({
            pref_path_key: path,
            "last_save_directory": str(Path(path).parent),
        })
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
_UNTAGGED = "__untagged__"

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


# ── Tabs ───────────────────────────────────────────────────────────────────────
tab_create, tab_manage, tab_merge = st.tabs(["✍️ Create Entry", "📂 Manage Dataset", "🔀 Merge Datasets"])


# ── Tab 1: Create Entry ────────────────────────────────────────────────────────
with tab_create:
    _col_left, _col_right = st.columns([3, 2])

    with _col_left:
        st.subheader("Save Location")

        save_path = path_input(
            "Dataset file path (.jsonl)",
            state_key="create_save_path",
            browse_fn=browse_save_file,
            browse_kwargs={
                "default_name": Path(st.session_state.loaded_path).name or "dataset.jsonl",
                "pref_path_key": "last_loaded_dataset_path",
            },
            default=st.session_state.prefs.get("last_loaded_dataset_path") or st.session_state.loaded_path or "dataset.jsonl",
        )

        # Keep Load Dataset path in sync with Save Location
        if save_path and save_path != st.session_state.get("manage_load_path"):
            st.session_state["manage_load_path_pending"] = save_path

        st.divider()
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

        # Apply any pending clear before widgets are instantiated
        if st.session_state.pop("clear_entry_fields", False):
            _old_turn_count = len(st.session_state.get("turns", []))
            st.session_state.turns = [{"role": "user"}, {"role": "assistant"}]
            # Explicitly blank the first pair so Streamlit actually resets the widgets
            st.session_state["turn_0"] = ""
            st.session_state["turn_1"] = ""
            # Remove any extra turns beyond the reset pair
            for _i in range(2, _old_turn_count):
                st.session_state.pop(f"turn_{_i}", None)
            for _cat in TAGS:
                st.session_state[f"tags_{_cat}"] = []

        # ── Multi-turn conversation builder ───────────────────────────────────
        # Restore any tag values that were saved before an Add/Remove rerun.
        for _cat in TAGS:
            _bk = f"_tags_backup_{_cat}"
            if _bk in st.session_state:
                st.session_state[f"tags_{_cat}"] = st.session_state.pop(_bk)

        _ROLE_COLOR = {"user": "#1a73e8", "assistant": "#188038"}
        _ROLE_PLACEHOLDER = {
            "user": "What the user says…",
            "assistant": "What the assistant replies…",
        }

        for _i, _turn in enumerate(st.session_state.turns):
            _role = _turn["role"]
            _color = _ROLE_COLOR.get(_role, "#000")
            st.markdown(
                f"<span style='color:{_color};font-weight:bold;text-transform:uppercase'>{_role}</span>",
                unsafe_allow_html=True,
            )
            st.text_area(
                label=f"turn_{_i}",
                placeholder=_ROLE_PLACEHOLDER.get(_role, ""),
                key=f"turn_{_i}",
                height=150,
                label_visibility="collapsed",
            )

        _btn_add, _btn_remove = st.columns(2)
        with _btn_add:
            if st.button("Add Exchange", use_container_width=True):
                for _cat in TAGS:
                    st.session_state[f"_tags_backup_{_cat}"] = list(st.session_state.get(f"tags_{_cat}", []))
                st.session_state.turns += [{"role": "user"}, {"role": "assistant"}]
                st.rerun()
        with _btn_remove:
            if st.button(
                "Remove Last Exchange",
                disabled=len(st.session_state.turns) <= 2,
                use_container_width=True,
            ):
                for _cat in TAGS:
                    st.session_state[f"_tags_backup_{_cat}"] = list(st.session_state.get(f"tags_{_cat}", []))
                _n = len(st.session_state.turns)
                st.session_state.turns = st.session_state.turns[:-2]
                for _k in [f"turn_{_n - 2}", f"turn_{_n - 1}"]:
                    st.session_state.pop(_k, None)
                st.rerun()

        st.divider()
        st.subheader("Tag & Complete Exchange")
        selected_tags: list[str] = []
        tag_cols = st.columns(len(TAGS))
        for col, (category, options) in zip(tag_cols, TAGS.items()):
            with col:
                chosen = st.multiselect(f"{category} tags", options=options, key=f"tags_{category}")
                selected_tags.extend(chosen)

        # Build current turn content and trigger preview if anything has been written
        _turns_now = [
            {"role": t["role"], "content": st.session_state.get(f"turn_{i}", "")}
            for i, t in enumerate(st.session_state.turns)
        ]
        _has_content = any(t["content"].strip() for t in _turns_now)

        entry_preview = None
        _entry_valid = False
        if _has_content:
            entry_preview = make_entry(
                turns=_turns_now,
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

        if st.button("Complete Exchange", disabled=not _entry_valid, type="primary", use_container_width=True):
            if not save_path.strip():
                st.error("Please set a dataset file path at the top of this tab.")
            else:
                try:
                    p = save_path.strip()
                    append_to_dataset(p, entry_preview)
                    st.session_state.loaded_path = p
                    entries, _ = load_dataset(p)
                    st.session_state.loaded_entries = entries
                    _update_prefs({
                        "last_loaded_dataset_path": p,
                        "last_save_directory": str(Path(p).parent),
                    })
                    st.session_state["manage_load_path_pending"] = p
                    st.session_state["clear_entry_fields"] = True
                    st.success(f"Entry appended to `{Path(p).resolve()}`.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Failed to save: {exc}")

    # ── Right column: live conversation preview ────────────────────────────────
    # _turns_now is computed above inside _col_left and is in scope here.
    with _col_right:
        st.subheader("Conversation Preview")

        # TODO: make speaker names configurable via preferences
        _SPEAKER_LABEL = {"user": "Scott", "assistant": "Emma"}

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

        _preview_turns = [t for t in _turns_now if t["content"].strip()]
        if not _preview_turns:
            st.caption("Your conversation will appear here as you write…")
        else:
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


# ── Tab 2: Manage Dataset ──────────────────────────────────────────────────────
with tab_manage:
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

    # Keep Save Location path in sync with Load Dataset
    if load_path and load_path != st.session_state.get("create_save_path"):
        st.session_state["create_save_path_pending"] = load_path

    col_load, col_new = st.columns(2)

    with col_load:
        if st.button("Load", use_container_width=True):
            p = load_path.strip()
            entries, errors = load_dataset(p)
            if errors:
                for e in errors:
                    st.error(e)
            st.session_state.loaded_entries = entries
            st.session_state.loaded_path = p
            st.session_state.stale_last_path = ""
            st.session_state.entry_page = 0
            st.session_state["create_save_path_pending"] = p
            _update_prefs({
                "last_loaded_dataset_path": p,
                "last_open_directory": str(Path(p).parent),
            })
            st.success(f"Loaded {len(entries)} entries from `{p}`.")

    with col_new:
        if st.button("New Dataset", use_container_width=True):
            prefs = st.session_state.prefs
            root = _tk_root()
            new_path = filedialog.asksaveasfilename(
                title="Create new dataset",
                defaultextension=".jsonl",
                initialfile="dataset.jsonl",
                initialdir=get_initial_dir(prefs, dir_key="last_save_directory"),
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
                    st.session_state.loaded_entries = []
                    st.session_state.loaded_path = new_path
                    st.session_state.stale_last_path = ""
                    st.session_state.entry_page = 0
                    # Push new path into both path fields via pending keys
                    st.session_state["manage_load_path_pending"] = new_path
                    st.session_state["create_save_path_pending"] = new_path
                    st.session_state["clear_entry_fields"] = True
                    _update_prefs({
                        "last_loaded_dataset_path": new_path,
                        "last_save_dataset_path": new_path,
                        "last_save_directory": str(Path(new_path).parent),
                    })
                    st.success(f"New dataset created at `{Path(new_path).resolve()}`.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Failed to create dataset: {exc}")

    entries = st.session_state.loaded_entries
    if entries:
        st.divider()
        export_path = path_input(
            "Export path",
            state_key="manage_export_path",
            browse_fn=browse_save_file,
            browse_kwargs={
                "default_name": Path(st.session_state.loaded_path).name or "dataset.jsonl",
                "pref_path_key": "last_save_dataset_path",
            },
            default=st.session_state.loaded_path,
        )
        if st.button("Save / Overwrite Dataset"):
            try:
                p = export_path.strip()
                save_dataset(p, entries)
                _update_prefs({
                    "last_save_dataset_path": p,
                    "last_save_directory": str(Path(p).parent),
                })
                st.success(f"Saved {len(entries)} entries to `{p}`.")
            except Exception as exc:
                st.error(f"Failed to save: {exc}")

        dl_name = Path(st.session_state.loaded_path).name or "dataset.jsonl"
        dl_col, clean_col = st.columns([2, 3])
        with clean_col:
            st.write("")
            clean_download = st.checkbox("Clean — Tag data removed", value=False)
        with dl_col:
            if clean_download:
                dl_entries = [{"messages": e["messages"]} for e in entries]
            else:
                dl_entries = entries
            content = "\n".join(json.dumps(e, ensure_ascii=False) for e in dl_entries)
            st.download_button(
                "Download as JSONL",
                data=content.encode("utf-8"),
                file_name=dl_name,
                mime="application/jsonlines",
                use_container_width=True,
            )

        st.divider()
        st.subheader(f"Entries ({len(entries)})")

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
        filtered_entries = filter_entries_by_tags(
            entries,
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

        total_filtered = len(filtered_entries)
        total_all = len(entries)

        if total_filtered == 0:
            st.info("No entries match the current filters.")
        else:
            per_page = st.session_state.entries_per_page
            last_page = max(0, (total_filtered - 1) // per_page)
            page = min(st.session_state.get("entry_page", 0), last_page)
            start = page * per_page
            end = min(start + per_page, total_filtered)

            if filter_tags:
                st.caption(
                    f"Showing {start + 1}–{end} of {total_filtered} filtered entries ({total_all} total)"
                )
            else:
                st.caption(f"Showing {start + 1}–{end} of {total_all} entries")

            for i, entry in enumerate(filtered_entries[start:end], start=start):
                errs = validate_entry(entry)
                entry_tags = entry.get("tags") or []
                tag_str = f" [{', '.join(entry_tags)}]" if entry_tags else " [untagged]"
                label = f"Entry {i + 1}{tag_str}"
                if errs:
                    label += " ⚠️"
                with st.expander(label):
                    if errs:
                        for err in errs:
                            st.error(err)
                    msgs = entry.get("messages", [])
                    for msg in msgs:
                        role = msg.get("role", "?")
                        content = msg.get("content", "")
                        color = {"system": "#555", "user": "#1a73e8", "assistant": "#188038"}.get(role, "#000")
                        st.markdown(
                            f"<span style='color:{color};font-weight:bold;text-transform:uppercase'>{role}</span>",
                            unsafe_allow_html=True,
                        )
                        st.text(content)

            col_prev, col_next = st.columns(2)
            with col_prev:
                if st.button("Previous", disabled=(page == 0), use_container_width=True):
                    st.session_state.entry_page = page - 1
                    st.rerun()
            with col_next:
                if st.button("Next", disabled=(page >= last_page), use_container_width=True):
                    st.session_state.entry_page = page + 1
                    st.rerun()


# ── Tab 3: Merge Datasets ──────────────────────────────────────────────────────
with tab_merge:
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
        browse_kwargs={
            "default_name": "merged_dataset.jsonl",
            "pref_path_key": "last_merge_output_path",
        },
        default=st.session_state.prefs.get("last_merge_output_path") or "merged_dataset.jsonl",
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
                    _update_prefs({
                        "last_merge_output_path": p,
                        "last_save_directory": str(Path(p).parent),
                    })
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
