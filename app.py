import json
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

    # Apply any pending clear before the widgets are instantiated
    if st.session_state.pop("clear_entry_fields", False):
        st.session_state["user_msg"] = ""
        st.session_state["assistant_msg"] = ""
        for _cat in TAGS:
            st.session_state[f"tags_{_cat}"] = []

    col_left, col_right = st.columns(2)
    with col_left:
        user_msg = st.text_area("User message", height=200, placeholder="What the user says…", key="user_msg")
    with col_right:
        assistant_msg = st.text_area("Assistant response", height=200, placeholder="What the assistant replies…", key="assistant_msg")

    st.divider()
    st.subheader("Tags")
    selected_tags: list[str] = []
    tag_cols = st.columns(len(TAGS))
    for col, (category, options) in zip(tag_cols, TAGS.items()):
        with col:
            chosen = st.multiselect(f"{category} tags", options=options, key=f"tags_{category}")
            selected_tags.extend(chosen)

    entry_preview = None
    if user_msg.strip() and assistant_msg.strip():
        entry_preview = make_entry(
            user_msg.strip(),
            assistant_msg.strip(),
            st.session_state.system_prompt,
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

    st.divider()
    st.subheader("Save Entry")

    save_path = path_input(
        "Dataset file path (.jsonl)",
        state_key="create_save_path",
        browse_fn=browse_save_file,
        browse_kwargs={
            "default_name": Path(st.session_state.loaded_path).name or "dataset.jsonl",
            "pref_path_key": "last_save_dataset_path",
        },
        default=st.session_state.prefs.get("last_save_dataset_path") or st.session_state.loaded_path or "dataset.jsonl",
    )

    if st.button("Append to Dataset", disabled=entry_preview is None, type="primary"):
        errors = validate_entry(entry_preview)
        if errors:
            for err in errors:
                st.error(err)
        elif not save_path.strip():
            st.error("Please enter or browse for a save path.")
        else:
            try:
                p = save_path.strip()
                append_to_dataset(p, entry_preview)
                st.session_state.loaded_path = p
                entries, _ = load_dataset(p)
                st.session_state.loaded_entries = entries
                _update_prefs({
                    "last_save_dataset_path": p,
                    "last_save_directory": str(Path(p).parent),
                })
                st.session_state["clear_entry_fields"] = True
                st.success(f"Entry appended to `{Path(p).resolve()}`.")
                st.rerun()
            except Exception as exc:
                st.error(f"Failed to save: {exc}")


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
