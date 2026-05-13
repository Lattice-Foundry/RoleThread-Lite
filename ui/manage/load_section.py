"""Dataset load and creation controls for Manage Dataset."""
from datetime import datetime
from pathlib import Path

import streamlit as st

from core.dataset import load_dataset_with_summary, save_dataset
from core.preferences import get_initial_dir
from core.working_copy import canonical_training_dataset_path, rename_working_dataset
from services.dataset_service import save_repaired_entries_service
from services.registry_sidecar_service import export_registry_sidecar
from ui.entry_search_state import ENTRY_SEARCH_DATASET_KEY
from ui.file_dialogs import JSONL_TYPES, browse_open_file, path_input, safe_saveas_filename
from ui.flash_messages import enqueue_flash, render_flash_messages
from ui.manage.load_summary import render_load_errors, render_load_format_summary
from ui.session_state import (
    apply_dataset_operation_result,
    clear_selected_entries,
    persist_loaded_normalization,
    set_loaded_entries,
    should_persist_loaded_normalization,
    update_prefs,
)


def render_load_section() -> None:
    """Render dataset load/new controls and any immediate load feedback."""

    stale_last_path_notice = st.empty()

    st.subheader("Load Dataset")
    render_flash_messages()
    _render_load_controls()

    with stale_last_path_notice:
        if st.session_state.stale_last_path and not st.session_state.loaded_path:
            st.warning(
                f"Last dataset `{st.session_state.stale_last_path}` no longer exists. "
                "Please load or create a dataset."
            )


def _render_load_controls() -> None:
    load_path = path_input(
        "File path",
        state_key="manage_load_path",
        browse_fn=browse_open_file,
        browse_kwargs={"pref_path_key": "last_loaded_dataset_path"},
        default=st.session_state.prefs.get("last_loaded_dataset_path")
        or st.session_state.loaded_path
        or "dataset.jsonl",
    )

    col_load, col_new = st.columns(2)
    with col_load:
        _render_load_button(load_path)
    with col_new:
        _render_new_dataset_button()
    _render_rename_controls()


def _render_load_button(load_path: str) -> None:
    dataset_already_loaded = _is_load_path_already_active(
        load_path.strip(),
        st.session_state.get("loaded_path"),
        st.session_state.get("working_copy_summary"),
    )
    if dataset_already_loaded:
        st.caption("Dataset already loaded.")
    if st.button(
        "Load",
        width="stretch",
        disabled=not load_path.strip() or dataset_already_loaded,
    ):
        _load_dataset(load_path.strip())


def _load_dataset(path: str) -> None:
    auto_correct_enabled = st.session_state.get(
        "auto_correct_validation_errors",
        st.session_state.get("prefs", {}).get(
            "auto_correct_validation_errors",
            # Compatibility fallback for older preference files.
            st.session_state.get("prefs", {}).get("auto_normalize_on_load", True),
        ),
    )
    normalization, errors = load_dataset_with_summary(
        path,
        auto_normalize=auto_correct_enabled,
    )
    entries = normalization.entries
    if render_load_errors(normalization, errors, entries):
        return
    loaded_dataset_path = set_loaded_entries(
        entries,
        normalization_summary=normalization,
        dataset_path=path,
    ) or path
    st.session_state.loaded_path = loaded_dataset_path
    st.session_state["manage_load_path_pending"] = loaded_dataset_path
    st.session_state.stale_last_path = ""
    st.session_state.entry_page = 0
    st.session_state["manage_select_all_mode"] = False
    clear_selected_entries()
    normalization_saved = False
    normalization_failed = False
    normalized_entries = int(
        st.session_state.get("tag_normalization_summary", {}).get(
            "changed_entries",
            0,
        )
        or 0
    )
    if should_persist_loaded_normalization(
        parse_errors=errors,
        normalization_pending=st.session_state.get("normalization_pending", False),
    ):
        normalize_result = persist_loaded_normalization(loaded_dataset_path)
        if normalize_result.ok:
            normalization_saved = True
        else:
            normalization_failed = True
            st.error(normalize_result.message)
            for error in normalize_result.errors:
                st.error(error)
    update_prefs({
        "last_loaded_dataset_path": loaded_dataset_path,
        "last_open_directory": str(Path(loaded_dataset_path).parent),
    })
    render_load_format_summary(
        normalization,
        loaded_dataset_path=loaded_dataset_path,
        loaded_entry_count=len(entries),
        correction_saved=normalization_saved,
        correction_failed=normalization_failed,
        normalized_entries=normalized_entries,
    )


def _render_new_dataset_button() -> None:
    if not st.button("New Dataset", width="stretch"):
        return

    prefs = st.session_state.prefs
    new_path = safe_saveas_filename(
        title="Create new dataset",
        defaultextension=".jsonl",
        initialfile=_default_new_dataset_filename(),
        initialdir=get_initial_dir(prefs, dir_key="default_dataset_directory"),
        filetypes=JSONL_TYPES,
    )

    if new_path:
        new_path = _save_current_before_switch(new_path)
    if new_path:
        _create_new_dataset(new_path)


def _render_rename_controls() -> None:
    loaded_path = st.session_state.get("loaded_path")
    if not loaded_path:
        return

    current_path = Path(loaded_path)
    st.caption(f"Loaded dataset: `{loaded_path}`")
    with st.expander("Rename dataset"):
        new_name = st.text_input(
            "New dataset name",
            value=current_path.stem,
            key="manage_rename_dataset_name",
            help="Use only letters, numbers, dashes, and underscores.",
        )
        unchanged = new_name.strip() == current_path.stem
        if st.button(
            "Rename",
            width="stretch",
            disabled=not new_name.strip() or unchanged,
        ):
            _rename_loaded_dataset(new_name.strip())


def _rename_loaded_dataset(new_name: str) -> None:
    loaded_path = st.session_state.get("loaded_path")
    if not loaded_path:
        st.error("No dataset is loaded.")
        return
    try:
        result = rename_working_dataset(loaded_path, new_name)
    except Exception as exc:
        st.error(f"Dataset rename failed: {exc}")
        return

    new_path = result.new_path
    st.session_state.loaded_path = new_path
    st.session_state["manage_load_path_pending"] = new_path
    st.session_state[ENTRY_SEARCH_DATASET_KEY] = str(Path(new_path).expanduser())
    working_copy = st.session_state.get("working_copy_summary")
    if (
        isinstance(working_copy, dict)
        and _same_dataset_path(working_copy.get("working_path"), result.old_path)
    ):
        st.session_state.working_copy_summary = {
            **working_copy,
            "working_path": new_path,
            "sidecar_path": result.new_sidecar_path or working_copy.get("sidecar_path"),
        }
    update_prefs({
        "last_loaded_dataset_path": new_path,
        "last_open_directory": str(Path(new_path).parent),
    })
    enqueue_flash("success", f"Dataset renamed to `{Path(new_path).stem}`.")
    st.rerun()


def _save_current_before_switch(new_path: str) -> str:
    if not (st.session_state.loaded_entries and st.session_state.loaded_path):
        return new_path

    result = save_repaired_entries_service(
        dataset_path=st.session_state.loaded_path,
        repaired_entries=st.session_state.loaded_entries,
        backup_reason="before_new_dataset_switch",
    )
    if result.ok:
        apply_dataset_operation_result(result)
        st.session_state.loaded_entries = result.entries or []
        return new_path

    st.error(
        "Could not save current dataset before switching: "
        f"{result.message}"
    )
    return ""


def _create_new_dataset(new_path: str) -> None:
    try:
        new_path = str(canonical_training_dataset_path(new_path))
        # New dataset bootstrap has no existing contents to protect; create the
        # empty JSONL and sibling sidecar directly, then normal service saves take over.
        save_dataset(new_path, [])
        sidecar_result = export_registry_sidecar(
            dataset_path=new_path,
            entries=[],
        )
        if not sidecar_result.ok:
            st.warning(sidecar_result.message)
        set_loaded_entries([])
        st.session_state.loaded_path = new_path
        st.session_state.stale_last_path = ""
        st.session_state.entry_page = 0
        st.session_state["manage_select_all_mode"] = False
        clear_selected_entries()
        st.session_state["manage_load_path_pending"] = new_path
        st.session_state["clear_entry_fields"] = True
        update_prefs({
            "last_loaded_dataset_path": new_path,
            "last_open_directory": str(Path(new_path).parent),
        })
        st.success(f"New dataset created at `{Path(new_path).resolve()}`.")
        st.rerun()
    except Exception as exc:
        st.error(f"Failed to create dataset: {exc}")


def _is_load_path_already_active(
    load_path: str | None,
    loaded_path: str | None,
    working_copy_summary: dict | None = None,
) -> bool:
    """Return True if load_path targets the active dataset or its source."""

    if _same_dataset_path(load_path, loaded_path):
        return True
    original_path = (
        working_copy_summary.get("original_path")
        if isinstance(working_copy_summary, dict)
        else None
    )
    return _same_dataset_path(load_path, original_path)


def _same_dataset_path(left: str | None, right: str | None) -> bool:
    if not left or not right:
        return False
    try:
        return Path(left).expanduser().resolve() == Path(right).expanduser().resolve()
    except (OSError, RuntimeError, ValueError):
        return str(left).strip() == str(right).strip()


def _default_new_dataset_filename(now: datetime | None = None) -> str:
    """Return a collision-resistant default filename for new datasets."""

    current = now or datetime.now()
    return f"dataset_{current.strftime('%Y%m%d_%H%M%S')}.jsonl"
