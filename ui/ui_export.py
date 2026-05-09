"""Streamlit page for exporting the loaded dataset."""
from pathlib import Path

import streamlit as st

from core.dataset import save_dataset
from ui.file_dialogs import browse_export_file, path_input
from core.state import ensure_entry_registry


def render_export_page() -> None:
    """Render the Export Dataset page."""
    ensure_entry_registry()
    st.subheader("Export Dataset")

    if "export_success_msg" in st.session_state:
        st.success(st.session_state.pop("export_success_msg"))

    _export_entries = st.session_state.loaded_entries
    if not _export_entries:
        st.info("Load a dataset to export.")
        return

    st.caption(
        f"{len(_export_entries)} entries loaded from "
        f"`{st.session_state.loaded_path or 'unknown'}`"
    )

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
