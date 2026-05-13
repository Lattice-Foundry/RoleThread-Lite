"""Streamlit page for local app settings."""
from pathlib import Path

import streamlit as st

from core.dataset import DEFAULT_SYSTEM_PROMPT
from core.preferences import export_settings, import_settings
from ui.file_dialogs import (
    browse_directory,
    browse_settings_export_file,
    browse_settings_import_file,
    path_input,
)
from core.storage import get_backups_dir, get_default_training_data_dir
from ui.session_state import update_prefs


def render_settings_page() -> None:
    """Render the Settings page."""
    st.subheader("Default Dataset Folder")

    current_default_dir = (
        st.session_state.prefs.get("default_dataset_directory")
        or str(get_default_training_data_dir())
    )
    folder_value = path_input(
        "Default Dataset Folder",
        state_key="_default_dataset_dir_input",
        browse_fn=browse_directory,
        browse_kwargs={"title": "Select default dataset folder"},
        default=current_default_dir,
    )

    if st.button("Save Default Dataset Folder", width="stretch"):
        try:
            raw_folder = folder_value.strip()
            if not raw_folder:
                raise ValueError("Default Dataset Folder cannot be empty.")
            target = Path(raw_folder).expanduser()
            target.mkdir(parents=True, exist_ok=True)
            normalized = str(target.resolve())
            st.session_state.default_dataset_directory = normalized
            st.session_state["_default_dataset_dir_input"] = normalized
            update_prefs({"default_dataset_directory": normalized})
            st.success("Default Dataset Folder updated.")
        except Exception as exc:
            st.error(f"Could not update Default Dataset Folder: {exc}")

    st.divider()
    st.subheader("Backup Settings")

    def _persist_auto_backups_enabled():
        st.session_state.auto_backups_enabled = st.session_state["_auto_backups_checkbox"]
        update_prefs({"auto_backups_enabled": st.session_state.auto_backups_enabled})

    st.checkbox(
        "Enable automatic backups before protected operations",
        value=st.session_state.get("auto_backups_enabled", True),
        key="_auto_backups_checkbox",
        on_change=_persist_auto_backups_enabled,
    )

    current_backup_dir = (
        st.session_state.prefs.get("backup_directory")
        or str(get_backups_dir())
    )
    backup_folder_value = path_input(
        "Backup Folder",
        state_key="_backup_dir_input",
        browse_fn=browse_directory,
        browse_kwargs={"title": "Select backup folder", "dir_key": "backup_directory"},
        default=current_backup_dir,
    )

    if st.button("Save Backup Folder", width="stretch"):
        try:
            raw_folder = backup_folder_value.strip()
            if not raw_folder:
                raise ValueError("Backup Folder cannot be empty.")
            target = Path(raw_folder).expanduser()
            target.mkdir(parents=True, exist_ok=True)
            normalized = str(target.resolve())
            st.session_state.backup_directory = normalized
            st.session_state["_backup_dir_input"] = normalized
            update_prefs({"backup_directory": normalized})
            st.success("Backup Folder updated.")
        except Exception as exc:
            st.error(f"Could not update Backup Folder: {exc}")

    def _persist_backups_per_dataset():
        keep_count = int(st.session_state["_backups_per_dataset_input"])
        st.session_state.backups_per_dataset = keep_count
        update_prefs({"backups_per_dataset": keep_count})

    try:
        current_keep_count = int(st.session_state.prefs.get("backups_per_dataset", 25))
    except (TypeError, ValueError):
        current_keep_count = 25
    current_keep_count = max(1, min(current_keep_count, 500))

    st.number_input(
        "Backups to Keep Per Dataset",
        min_value=1,
        max_value=500,
        value=current_keep_count,
        step=1,
        key="_backups_per_dataset_input",
        on_change=_persist_backups_per_dataset,
        help="Older backups are automatically pruned after successful backup creation.",
    )

    st.divider()
    st.subheader("Data Normalization")

    def _persist_auto_correct_validation_errors():
        st.session_state.auto_correct_validation_errors = st.session_state[
            "_auto_correct_validation_errors_checkbox"
        ]
        update_prefs({
            "auto_correct_validation_errors": (
                st.session_state.auto_correct_validation_errors
            )
        })

    st.checkbox(
        "Auto Correct Validation Errors",
        value=st.session_state.get("auto_correct_validation_errors", True),
        key="_auto_correct_validation_errors_checkbox",
        on_change=_persist_auto_correct_validation_errors,
        help=(
            "When enabled, LoreForge also applies broader deterministic validation "
            "repairs during load. Baseline normalization for safe metadata, role "
            "formatting, and simple text cleanup always runs."
        ),
    )

    st.divider()
    st.subheader("Editing Safety")

    def _persist_confirm_delete():
        st.session_state.confirm_delete_entries = st.session_state["_confirm_delete_checkbox"]
        update_prefs({"confirm_delete_entries": st.session_state.confirm_delete_entries})

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
        update_prefs({"preview_user_name": st.session_state.preview_user_name})

    def _persist_preview_assistant_name():
        st.session_state.preview_assistant_name = st.session_state["_preview_assistant_name_input"]
        update_prefs({"preview_assistant_name": st.session_state.preview_assistant_name})

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

    st.divider()
    st.subheader("Settings Portability")
    export_path = path_input(
        "Export settings path",
        state_key="_settings_export_path",
        browse_fn=browse_settings_export_file,
        browse_kwargs={},
        default="",
    )
    if st.button("Export Settings", width="stretch", disabled=not export_path.strip()):
        try:
            export_settings(export_path.strip())
        except Exception as exc:
            st.error(f"Could not export settings: {exc}")
        else:
            st.success(f"Settings exported to `{Path(export_path).expanduser()}`.")

    import_path = path_input(
        "Import settings path",
        state_key="_settings_import_path",
        browse_fn=browse_settings_import_file,
        browse_kwargs={},
        default="",
    )
    if st.button("Import Settings", width="stretch", disabled=not import_path.strip()):
        try:
            imported = import_settings(import_path.strip())
        except Exception as exc:
            st.error(f"Could not import settings: {exc}")
        else:
            _apply_preferences_to_session(imported)
            st.success("Settings imported.")
            st.rerun()


def _apply_preferences_to_session(prefs: dict) -> None:
    """Refresh settings-related session state after a DB import."""

    st.session_state.prefs = prefs
    st.session_state.system_prompt = prefs.get("last_system_prompt") or DEFAULT_SYSTEM_PROMPT
    st.session_state.confirm_delete_entries = prefs.get("confirm_delete_entries", True)
    st.session_state.preview_user_name = prefs.get("preview_user_name", "User")
    st.session_state.preview_assistant_name = prefs.get("preview_assistant_name", "Assistant")
    st.session_state.default_dataset_directory = prefs.get("default_dataset_directory", "")
    st.session_state.auto_backups_enabled = prefs.get("auto_backups_enabled", True)
    st.session_state.backup_directory = prefs.get("backup_directory", "")
    st.session_state.backups_per_dataset = prefs.get("backups_per_dataset", 25)
    st.session_state.auto_correct_validation_errors = prefs.get(
        "auto_correct_validation_errors",
        prefs.get("auto_normalize_on_load", True),
    )
