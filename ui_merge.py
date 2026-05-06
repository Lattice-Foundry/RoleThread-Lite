"""Merge Datasets page."""
import json
from pathlib import Path

import streamlit as st

from dataset import merge_datasets, save_dataset
from file_dialogs import browse_open_multiple, browse_save_file, path_input


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
