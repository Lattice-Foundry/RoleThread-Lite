"""Streamlit page for exporting the loaded dataset."""
from pathlib import Path

import streamlit as st

from core.dataset import save_dataset
from core.format_conversion import (
    FORMAT_CHATML,
    FORMAT_SHAREGPT,
    convert_chatml_to_format,
)
from core.working_copy import canonical_training_dataset_path
from services.registry_sidecar_service import export_registry_sidecar
from ui.file_dialogs import browse_export_file, path_input
from ui.flash_messages import enqueue_flash, render_flash_messages
from ui.session_state import ensure_entry_indexes

_EXPORT_FORMAT_OPTIONS = {
    "ChatML": FORMAT_CHATML,
    "ShareGPT": FORMAT_SHAREGPT,
}


def _prepare_export_entries(
    entries: list[dict],
    *,
    export_format: str,
    clean_export: bool,
) -> list[dict]:
    """Return entries in the requested export shape without mutating input."""
    if export_format == FORMAT_SHAREGPT:
        return convert_chatml_to_format(
            entries,
            target_format=FORMAT_SHAREGPT,
            include_metadata=not clean_export,
        ).entries
    if clean_export:
        return [{"messages": e["messages"]} for e in entries]
    return entries


def render_export_page() -> None:
    """Render the Export Dataset page."""
    ensure_entry_indexes()
    st.subheader("Export Dataset")
    render_flash_messages()

    _export_entries = st.session_state.loaded_entries
    if not _export_entries:
        st.info("Load a dataset to export.")
        return

    st.caption(
        f"{len(_export_entries)} entries loaded from "
        f"`{st.session_state.loaded_path or 'unknown'}`"
    )

    _format_label = st.selectbox(
        "Export format",
        options=list(_EXPORT_FORMAT_OPTIONS),
        key="export_format_select",
    )
    _export_format = _EXPORT_FORMAT_OPTIONS[_format_label]

    clean_export = st.checkbox("Clean — Tag data removed", value=False, key="export_clean")
    include_sidecar = st.checkbox(
        "Include registry sidecar",
        value=True,
        key="export_include_registry_sidecar",
    )

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
                _p = str(canonical_training_dataset_path(_p))
                _out = _prepare_export_entries(
                    _export_entries,
                    export_format=_export_format,
                    clean_export=clean_export,
                )
                save_dataset(_p, _out)
                success_message = f"Exported {len(_out)} entries to `{Path(_p).resolve()}`."
                if include_sidecar:
                    sidecar_result = export_registry_sidecar(
                        dataset_path=_p,
                        entries=_export_entries,
                    )
                    if sidecar_result.ok:
                        success_message += f" {sidecar_result.message}"
                    else:
                        enqueue_flash("warning", sidecar_result.message)
                enqueue_flash("success", success_message)
                st.session_state["export_save_path_pending"] = ""
                st.rerun()
            except Exception as exc:
                st.error(f"Export failed: {exc}")
