"""Streamlit page for merging JSONL datasets.

This module owns file selection and merge previews. Durable merge saves
delegate to services.
"""
import json
from pathlib import Path

import streamlit as st

from core.backups import auto_backups_enabled
from core.dataset import merge_datasets
from ui.file_dialogs import browse_open_multiple, browse_save_file, path_input
from ui.session_state import prune_selection_to_loaded_entries, set_loaded_entries
from services.dataset_service import save_merged_entries_service


def render_merge_page() -> None:
    """Render the Merge Datasets page."""
    st.subheader("Merge Multiple Datasets")

    if "merge_input_paths_pending" in st.session_state:
        st.session_state["merge_input_paths"] = st.session_state.pop(
            "merge_input_paths_pending"
        )
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
                result = save_merged_entries_service(
                    dataset_path=p,
                    entries=merged,
                    source_paths=paths,
                    backup_enabled=auto_backups_enabled(st.session_state.get("prefs", {})),
                )
                if result.ok and result.entries is not None:
                    saved_path = result.dataset_path or p
                    loaded_path = st.session_state.get("loaded_path", "")
                    if loaded_path and Path(loaded_path).resolve() == Path(p).resolve():
                        set_loaded_entries(result.entries)
                        st.session_state.loaded_path = saved_path
                        prune_selection_to_loaded_entries()
                    _backup_note = " Backup created." if result.backup_path else ""
                    st.success(f"Merged dataset saved to `{saved_path}`.{_backup_note}")
                    _render_source_sidecar_summary(result.source_sidecar_summary)

                    st.download_button(
                        "Download merged JSONL",
                        data=_merged_download_payload(result.entries),
                        file_name=Path(saved_path).name,
                        mime="application/jsonlines",
                    )
                else:
                    for err in result.errors:
                        st.error(err)
                    if not result.errors:
                        st.error(result.message)


def _render_source_sidecar_summary(summary) -> None:
    if summary is None or summary.source_count == 0:
        return
    if summary.imported_count:
        st.caption(
            "Imported registry metadata from "
            f"{summary.imported_count} source sidecar"
            f"{'' if summary.imported_count == 1 else 's'}."
        )
    if summary.failed_paths:
        st.warning(
            "Some source sidecars could not be imported. "
            "Merge continued with available registry metadata."
        )
        for error in summary.errors[:3]:
            st.caption(f"Source sidecar warning: {error}")
    if summary.conflicts:
        st.warning(
            f"{len(summary.conflicts)} source sidecar registry conflict"
            f"{'' if len(summary.conflicts) == 1 else 's'} detected."
        )


def _merged_download_payload(entries: list[dict]) -> bytes:
    """Return JSONL bytes for already-saved merge entries."""

    content = "\n".join(json.dumps(entry, ensure_ascii=False) for entry in entries)
    return content.encode("utf-8")
