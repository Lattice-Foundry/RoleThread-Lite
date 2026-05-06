"""File dialog helpers and the reusable path_input widget.

All Tkinter/filedialog logic lives here so app.py stays free of dialog
boilerplate.  Every function follows the same threading-safe pattern:

    open dialog → destroy root → set pending key → st.rerun()

This means the Tkinter root is always destroyed on the same thread that
created it, which avoids the Tcl_AsyncDelete crash.
"""
import tkinter as tk
from pathlib import Path
from tkinter import filedialog

import streamlit as st

from preferences import get_initial_dir, save_preferences

# ── Constants ──────────────────────────────────────────────────────────────────
JSONL_TYPES = [("JSONL files", "*.jsonl"), ("All files", "*.*")]


# ── Internal helpers ───────────────────────────────────────────────────────────

def _tk_root() -> tk.Tk:
    """Return a hidden, topmost Tkinter root window."""
    root = tk.Tk()
    root.withdraw()
    root.wm_attributes("-topmost", 1)
    return root


def _save_prefs(updates: dict) -> None:
    """Update st.session_state.prefs in place and persist to disk.

    Mirrors _update_prefs() in app.py — kept separate to avoid a circular
    import.  Only call from within file dialog callbacks.
    """
    st.session_state.prefs.update(updates)
    save_preferences(st.session_state.prefs)


# ── File dialog helpers ────────────────────────────────────────────────────────

def browse_open_file(
    pending_key: str,
    pref_path_key: str = "last_loaded_dataset_path",
) -> None:
    """Open a single-file picker and store the result in pending_key."""
    prefs = st.session_state.prefs
    root = _tk_root()
    path = filedialog.askopenfilename(
        title="Select dataset file",
        filetypes=JSONL_TYPES,
        initialdir=get_initial_dir(
            prefs, path_key=pref_path_key, dir_key="last_open_directory"
        ),
    )
    root.destroy()
    if path:
        st.session_state[pending_key] = path
        _save_prefs({
            pref_path_key: path,
            "last_open_directory": str(Path(path).parent),
        })
        st.rerun()


def browse_save_file(
    pending_key: str,
    default_name: str = "dataset.jsonl",
) -> None:
    """Open a save-as picker and store the result in pending_key."""
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

    Does NOT update preferences — export is a one-off operation.
    """
    _default = (
        Path(st.session_state.loaded_path).name
        if st.session_state.loaded_path
        else "dataset.jsonl"
    )
    _initial_dir = (
        str(Path(st.session_state.loaded_path).parent)
        if st.session_state.loaded_path
        and Path(st.session_state.loaded_path).parent.exists()
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
    """Open a multi-file picker and append chosen paths to widget_key."""
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
        _save_prefs({"last_open_directory": str(Path(paths[0]).parent)})
        st.rerun()


# ── Reusable widget ────────────────────────────────────────────────────────────

def path_input(
    label: str,
    state_key: str,
    browse_fn,
    browse_kwargs: dict,
    default: str = "",
) -> str:
    """Render a text input + Browse button pair.

    Uses the pending-key pattern so a browse callback can update the field
    across reruns without triggering a Streamlit widget-key conflict.

    Returns the current value of the text input.
    """
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
