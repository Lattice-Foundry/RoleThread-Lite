"""File dialog adapter used by the Streamlit UI.

This module owns Tkinter dialogs, pending path keys, and Streamlit reruns.
It should not contain dataset business logic.
"""
import tkinter as tk
from pathlib import Path
from tkinter import filedialog

import streamlit as st

from core.preferences import get_initial_dir, save_preferences

# ── Constants ──────────────────────────────────────────────────────────────────
JSONL_TYPES = [("JSONL files", "*.jsonl"), ("All files", "*.*")]


# ── Internal helpers ───────────────────────────────────────────────────────────

def _tk_root() -> tk.Tk:
    """Return a hidden, topmost Tkinter root window."""
    root = tk.Tk()
    root.withdraw()
    root.wm_attributes("-topmost", 1)
    return root


def _show_dialog_error(exc: Exception) -> None:
    st.warning(
        "The native file dialog could not be opened. "
        "Paste the file path manually and try again."
    )
    st.caption(str(exc))


def _run_dialog(dialog_fn, **kwargs):
    root: tk.Tk | None = None
    try:
        root = _tk_root()
        root.update()
        return dialog_fn(parent=root, **kwargs)
    except (RuntimeError, tk.TclError) as exc:
        _show_dialog_error(exc)
        return None
    finally:
        if root is not None:
            try:
                root.destroy()
            except (RuntimeError, tk.TclError):
                pass


def safe_saveas_filename(**kwargs) -> str | None:
    """Return a save-as path, or None if the native dialog is unavailable."""

    return _run_dialog(filedialog.asksaveasfilename, **kwargs) or None


def _save_prefs(updates: dict) -> None:
    """Update st.session_state.prefs in place and persist to disk.

    Mirrors the session-state preference helper without importing the
    session bridge from file dialog callbacks.
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
    path = _run_dialog(
        filedialog.askopenfilename,
        title="Select dataset file",
        filetypes=JSONL_TYPES,
        initialdir=get_initial_dir(
            prefs, path_key=pref_path_key, dir_key="last_open_directory"
        ),
    )
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
    dir_key: str = "default_dataset_directory",
) -> None:
    """Open a save-as picker and store the result in pending_key."""
    prefs = st.session_state.prefs
    path = safe_saveas_filename(
        title="Save dataset as",
        defaultextension=".jsonl",
        initialfile=default_name,
        initialdir=get_initial_dir(prefs, dir_key=dir_key),
        filetypes=JSONL_TYPES,
    )
    if path:
        st.session_state[pending_key] = path
        st.rerun()


def browse_directory(
    pending_key: str,
    title: str = "Select folder",
    dir_key: str = "default_dataset_directory",
) -> None:
    """Open a directory picker and store the result in pending_key."""
    prefs = st.session_state.prefs
    path = _run_dialog(
        filedialog.askdirectory,
        title=title,
        initialdir=get_initial_dir(prefs, dir_key=dir_key),
    )
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
        else get_initial_dir(st.session_state.prefs, dir_key="default_dataset_directory")
    )
    path = safe_saveas_filename(
        title="Export dataset",
        defaultextension=".jsonl",
        initialfile=_default,
        initialdir=_initial_dir,
        filetypes=JSONL_TYPES,
    )
    if path:
        st.session_state[pending_key] = path
        st.rerun()


def browse_open_multiple(widget_key: str, pending_key: str) -> None:
    """Open a multi-file picker and append chosen paths to widget_key."""
    prefs = st.session_state.prefs
    paths = _run_dialog(
        filedialog.askopenfilenames,
        title="Select dataset files to merge",
        filetypes=JSONL_TYPES,
        initialdir=get_initial_dir(prefs, dir_key="last_open_directory"),
    )
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
