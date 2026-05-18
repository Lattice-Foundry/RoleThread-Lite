"""Streamlit page for local app settings."""
from pathlib import Path

import streamlit as st

from core.dataset import DEFAULT_SYSTEM_PROMPT
from core.cloud_sync import (
    BACKUP_DESTINATION_BOX,
    BACKUP_DESTINATION_CUSTOM,
    BACKUP_DESTINATION_DROPBOX,
    BACKUP_DESTINATION_GOOGLE_DRIVE,
    BACKUP_DESTINATION_ICLOUD_DRIVE,
    BACKUP_DESTINATION_LOCAL,
    BACKUP_DESTINATION_ONEDRIVE,
    cloud_backup_destination_path,
    detect_cloud_sync_provider_for_path,
    save_backup_config_from_settings,
    sync_configured_backups_to_cloud,
)
from core.platform import (
    PATH_SOURCE_PLATFORM_DEFAULT,
    detect_browser_capabilities,
    detect_onedrive_path,
    detect_platform,
    get_platform_path_resolutions,
    get_platform_launch_plan,
)
from core.preferences import export_settings, get_all_settings, import_settings
from core.runtime import get_python_runtime_status
from core.version import ROLETHREAD_VERSION
from ui.file_dialogs import (
    browse_directory,
    browse_settings_export_file,
    browse_settings_import_file,
    path_input,
)
from core.storage import get_backups_dir, get_default_training_data_dir
from ui.session_state import update_prefs

INLINE_CODE_TEXT_GREEN = "#3D9F64"


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
        show_browse=False,
    )

    browse_col, save_col, _default_folder_spacer = st.columns([1, 1, 2])
    with browse_col:
        if st.button("Browse", key="browse_default_dataset_folder", width="stretch"):
            browse_directory(
                "_default_dataset_dir_input_pending",
                title="Select default dataset folder",
            )
    with save_col:
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
        "Local Backup Folder",
        state_key="_backup_dir_input",
        browse_fn=browse_directory,
        browse_kwargs={
            "title": "Select local backup folder",
            "dir_key": "backup_directory",
        },
        default=current_backup_dir,
        show_browse=False,
    )
    backup_browse_col, _backup_browse_spacer = st.columns([1, 3])
    with backup_browse_col:
        if st.button("Browse", key="browse_local_backup_folder", width="stretch"):
            browse_directory(
                "_backup_dir_input_pending",
                title="Select local backup folder",
                dir_key="backup_directory",
            )
    st.caption("Do not use a cloud-synced folder here. Use Cloud Backup below instead.")
    _render_local_backup_confirmation(backup_folder_value, current_backup_dir)

    def _persist_backups_per_dataset():
        keep_count = int(st.session_state["_backups_per_dataset_input"])
        st.session_state.backups_per_dataset = keep_count
        update_prefs({"backups_per_dataset": keep_count})

    try:
        current_keep_count = int(st.session_state.prefs.get("backups_per_dataset", 25))
    except (TypeError, ValueError):
        current_keep_count = 25
    current_keep_count = max(1, min(current_keep_count, 500))

    keep_col, _keep_spacer = st.columns([0.55, 4])
    with keep_col:
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
    st.caption("Applies to local backups. Cloud receives only the latest.")

    _render_cloud_backup_settings()

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
            "When enabled, RoleThread also applies broader deterministic validation "
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
    st.caption(
        "Default display names for conversation previews. These are cosmetic only "
        "and don't affect training data. When using Group Chat mode, per-turn "
        "character assignments override these defaults."
    )

    def _persist_preview_user_name():
        st.session_state.preview_user_name = st.session_state[
            "_preview_human_display_name_input"
        ]
        update_prefs({"preview_user_name": st.session_state.preview_user_name})

    def _persist_preview_assistant_name():
        st.session_state.preview_assistant_name = st.session_state["_preview_assistant_name_input"]
        update_prefs({"preview_assistant_name": st.session_state.preview_assistant_name})

    user_col, assistant_col, _preview_name_spacer = st.columns([1, 1, 2])
    with user_col:
        st.text_input(
            "Human Display Name",
            value=st.session_state.preview_user_name,
            key="_preview_human_display_name_input",
            on_change=_persist_preview_user_name,
            autocomplete="off",
        )
    with assistant_col:
        st.text_input(
            "Assistant Display Name",
            value=st.session_state.preview_assistant_name,
            key="_preview_assistant_name_input",
            on_change=_persist_preview_assistant_name,
            autocomplete="off",
        )

    st.divider()
    st.subheader("Settings Portability")
    export_path = path_input(
        "Export settings path",
        state_key="_settings_export_path",
        browse_fn=browse_settings_export_file,
        browse_kwargs={},
        default="",
        show_browse=False,
    )
    export_browse_col, export_button_col, _export_spacer = st.columns([1, 1, 2])
    with export_browse_col:
        if st.button("Browse", key="browse_settings_export_path", width="stretch"):
            browse_settings_export_file("_settings_export_path_pending")
    with export_button_col:
        if st.button(
            "Export Settings",
            width="stretch",
            disabled=not export_path.strip(),
        ):
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
        show_browse=False,
    )
    import_browse_col, import_button_col, _import_spacer = st.columns([1, 1, 2])
    with import_browse_col:
        if st.button("Browse", key="browse_settings_import_path", width="stretch"):
            browse_settings_import_file("_settings_import_path_pending")
    with import_button_col:
        if st.button(
            "Import Settings",
            width="stretch",
            disabled=not import_path.strip(),
        ):
            try:
                imported = import_settings(import_path.strip())
            except Exception as exc:
                st.error(f"Could not import settings: {exc}")
            else:
                _apply_preferences_to_session(imported)
                st.success("Settings imported.")
                st.rerun()

    st.divider()
    _render_platform_about()


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
    st.session_state.backup_destination_type = prefs.get(
        "backup_destination_type",
        BACKUP_DESTINATION_LOCAL,
    )
    st.session_state.backup_destination_custom_path = prefs.get(
        "backup_destination_custom_path",
        "",
    )
    save_backup_config_from_settings(prefs)
    st.session_state.auto_correct_validation_errors = prefs.get(
        "auto_correct_validation_errors",
        prefs.get("auto_normalize_on_load", True),
    )


def _render_platform_about() -> None:
    """Render current OS support information without changing behavior."""

    platform_info = detect_platform()
    dev_mode = _is_dev_mode()
    flags = st.session_state.get("_runtime_launch_flags")
    capabilities = platform_info.capabilities
    diagnostics = platform_info.diagnostics
    runtime_status = get_python_runtime_status()
    preferences = get_all_settings()
    platform_paths = get_platform_path_resolutions(preferences=preferences)
    browser_detection = detect_browser_capabilities(platform_info=platform_info)
    launch_plan = get_platform_launch_plan(browser_detection)

    st.subheader("About This Installation")
    version_col, platform_col, support_col, python_col = st.columns(4)
    with version_col:
        st.markdown("**RoleThread**")
        st.caption(f"v{ROLETHREAD_VERSION}")
    with platform_col:
        st.markdown("**Detected Platform**")
        st.caption(platform_info.display_name)
    with support_col:
        st.markdown("**Support Level**")
        st.caption(platform_info.support_level.title())
    with python_col:
        st.markdown("**Python**")
        st.caption(runtime_status.current_version)

    with st.expander("Python Runtime Compatibility"):
        st.caption(_format_about_row("Current Python", f"`{runtime_status.current_version}`"))
        st.caption(_format_about_row("Official Python", f"`{runtime_status.official_version}`"))
        st.caption(_format_about_row("Runtime status", f"`{runtime_status.status_label}`"))
        st.caption(_format_about_row("Message", runtime_status.message))

    with st.expander("Launch Behavior"):
        st.caption(
            _format_about_row(
                "Launch mode",
                _format_public_launch_mode(flags, preferences),
            )
        )
        st.caption(_format_about_row("Fallback behavior", f"`{launch_plan.fallback_label}`"))
        st.caption(
            _format_about_row(
                "Webapp support",
                f"`{'Available' if launch_plan.edge_webapp_ready else 'Unavailable'}`",
            )
        )
        if capabilities.supports_edge_webapp:
            st.caption(
                _format_about_row(
                    "Note",
                    "Managed webapp mode is owned by `python launch.py --webapp` or the installed launcher.",
                )
            )
        for note in launch_plan.notes:
            st.caption(_format_about_row("Note", note))

    if dev_mode:
        with st.expander("Launch Flags Detected"):
            st.caption(_format_about_row("Flags", _format_launch_flags_detected(flags)))

        with st.expander("Platform Capabilities"):
            for label, enabled in _platform_capability_labels(capabilities):
                st.caption(_format_about_row(label, f"`{'Yes' if enabled else 'No'}`"))

        with st.expander("Browser Support"):
            st.caption(
                _format_about_row(
                    "Edge detected",
                    f"`{'Yes' if browser_detection.browser.edge_detected else 'No'}`",
                )
            )
            if browser_detection.browser.edge_path is not None:
                st.caption(
                    _format_about_row("Edge path", f"`{browser_detection.browser.edge_path}`")
                )
            st.caption(
                _format_about_row(
                    "Default browser fallback",
                    f"`{'Yes' if browser_detection.capabilities.fallback_to_default_browser else 'No'}`",
                )
            )
            st.caption(
                _format_about_row(
                    "Edge web app available",
                    f"`{'Yes' if browser_detection.capabilities.edge_webapp_available else 'No'}`",
                )
            )
            st.caption(_format_about_row("Browser mode", browser_detection.message))

        with st.expander("Platform Path Defaults"):
            _render_platform_paths(platform_paths, include_source=True, include_advanced=True)

        with st.expander("Raw Platform Diagnostics"):
            st.caption(_format_about_row("Platform slug", f"`{platform_info.platform_slug}`"))
            st.caption(_format_about_row("Raw system", f"`{diagnostics.raw_system}`"))
            st.caption(_format_about_row("Release", f"`{diagnostics.release}`"))
            st.caption(_format_about_row("Version", f"`{diagnostics.version}`"))
            st.caption(
                _format_about_row("Platform string", f"`{diagnostics.platform_string}`")
            )
            st.caption(_format_about_row("Machine", f"`{diagnostics.machine}`"))
            st.caption(_format_about_row("Processor", f"`{diagnostics.processor}`"))
            st.caption(
                _format_about_row(
                    "Python architecture",
                    f"`{diagnostics.python_architecture}`",
                )
            )
            st.caption(
                _format_about_row(
                    "Python implementation",
                    f"`{diagnostics.python_implementation}`",
                )
            )

    else:
        with st.expander("Storage Locations"):
            _render_platform_paths(platform_paths, include_source=False, include_advanced=False)
            with st.expander("Advanced storage paths"):
                _render_advanced_platform_paths(platform_paths, include_source=False)

    st.divider()
    st.markdown(_format_project_info_markup(), unsafe_allow_html=True)


def _format_project_info_markup() -> str:
    """Return the official project attribution block for Settings/About."""

    return f"""
<div style="line-height: 1.7; color: #FFFFFF;">
  <div>Developed by:</div>
  <br>
  <div>
    <span style="color: {INLINE_CODE_TEXT_GREEN}; font-weight: 700;">LatticeFoundry</span><br>
    <span>A Sierra Cognitive Group company</span>
  </div>
  <br>
  <div>
    <span>latticefoundry.dev</span><br>
    <span>github.com/Lattice-Foundry/RoleThread-Lite</span>
  </div>
  <br>
  <div>
    <span>Scott Jackson | </span><span style="color: {INLINE_CODE_TEXT_GREEN}; font-weight: 700;">d1g1talshad0w</span>
  </div>
</div>
"""


def _platform_capability_labels(capabilities) -> tuple[tuple[str, bool], ...]:
    return (
        ("Installer support", capabilities.supports_installer),
        ("Edge web app support", capabilities.supports_edge_webapp),
        ("Default browser support", capabilities.supports_default_browser),
        ("OneDrive detection", capabilities.supports_onedrive),
        ("Safe cloud sync support", capabilities.supports_safe_cloud_sync),
        ("Linux manual run support", capabilities.supports_linux_manual_run),
        ("macOS beta support", capabilities.supports_macos_beta),
    )


def _render_platform_paths(
    platform_paths,
    *,
    include_source: bool,
    include_advanced: bool,
) -> None:
    for label, resolved_path in (
        ("App data", platform_paths.app_data_root),
        ("Workspace", platform_paths.workspace_root),
        ("Training data", platform_paths.training_data_dir),
        ("Exports", platform_paths.exports_dir),
        ("Imports", platform_paths.imports_dir),
        ("Backups", platform_paths.backups_dir),
    ):
        st.caption(
            _format_about_row(
                label,
                _format_platform_path_value(resolved_path, include_source=include_source),
            )
        )
    if include_advanced:
        _render_advanced_platform_paths(platform_paths, include_source=include_source)


def _render_advanced_platform_paths(platform_paths, *, include_source: bool) -> None:
    for label, resolved_path in (
        ("Logs", platform_paths.logs_dir),
        ("Cache", platform_paths.cache_dir),
        ("Database", platform_paths.database_path),
        ("Preferences", platform_paths.preferences_path),
    ):
        st.caption(
            _format_about_row(
                label,
                _format_platform_path_value(resolved_path, include_source=include_source),
            )
        )


def _format_path_source(source: str) -> str:
    if source == PATH_SOURCE_PLATFORM_DEFAULT:
        return "Platform Default"
    return "User Override"


def _is_dev_mode() -> bool:
    return bool(st.session_state.get("_dev_mode"))


def _format_public_launch_mode(flags, preferences: dict) -> str:
    return "`Dev diagnostics`" if getattr(flags, "dev", False) else "`Normal Streamlit mode`"


def _format_launch_flags_detected(flags) -> str:
    active: list[str] = []
    if getattr(flags, "dev", False):
        active.append("dev")
    if not active:
        return "`None`"
    return "`" + "`, `".join(active) + "`"


def _format_platform_path_value(resolved_path, *, include_source: bool = True) -> str:
    if not include_source:
        return f"`{resolved_path.path}`"
    source_label = _format_path_source(resolved_path.source)
    value = f"`{resolved_path.path}` ({source_label})"
    if resolved_path.source != PATH_SOURCE_PLATFORM_DEFAULT:
        value += f"; default `{resolved_path.platform_default}`"
    return value


def _format_about_row(label: str, value: str) -> str:
    return f"{label}: {value}"


def _normalize_folder_path(raw_path: str, *, label: str) -> str:
    raw_path = (raw_path or "").strip()
    if not raw_path:
        raise ValueError(f"{label} cannot be empty.")
    target = Path(raw_path).expanduser()
    target.mkdir(parents=True, exist_ok=True)
    return str(target.resolve())


def _render_local_backup_confirmation(
    backup_folder_value: str,
    current_backup_dir: str,
) -> None:
    """Confirm local backup folder changes before applying them."""

    if not (backup_folder_value or "").strip():
        return
    try:
        proposed = Path(backup_folder_value).expanduser().resolve()
        current = Path(current_backup_dir).expanduser().resolve()
    except OSError:
        proposed = Path(backup_folder_value).expanduser()
        current = Path(current_backup_dir).expanduser()
    if proposed == current:
        st.session_state.pop("pending_local_backup_folder", None)
        return

    provider = detect_cloud_sync_provider_for_path(proposed)
    if provider:
        st.warning(
            f"This path appears to be inside a {provider} sync folder. "
            "This may cause issues during your session. Consider using Cloud Backup instead."
        )

    st.warning(f"Change local backup folder to `{proposed}`?")
    confirm_col, cancel_col = st.columns(2)
    with confirm_col:
        if st.button("Confirm Local Backup Folder", key="btn_confirm_local_backup"):
            try:
                normalized = _normalize_folder_path(
                    backup_folder_value,
                    label="Local Backup Folder",
                )
                st.session_state.backup_directory = normalized
                st.session_state["_backup_dir_input_pending"] = normalized
                update_prefs({"backup_directory": normalized})
                st.success("Local Backup Folder updated.")
                st.rerun()
            except Exception as exc:
                st.error(f"Could not update Local Backup Folder: {exc}")
    with cancel_col:
        if st.button("Cancel Local Backup Change", key="btn_cancel_local_backup"):
            st.session_state["_backup_dir_input_pending"] = current_backup_dir
            st.rerun()


def _render_cloud_backup_settings() -> None:
    """Render optional cloud backup destination controls."""

    st.markdown("**Cloud Backup Destination**")
    platform_info = detect_platform()
    destination_options = _cloud_destination_options(platform_info.capabilities)

    current_type = st.session_state.prefs.get(
        "backup_destination_type",
        BACKUP_DESTINATION_LOCAL,
    )
    option_values = [value for _, value in destination_options]
    unavailable_reason = ""
    if current_type not in option_values:
        if current_type == BACKUP_DESTINATION_ONEDRIVE:
            unavailable_reason = (
                "OneDrive backup is unavailable on this platform. "
                "Choose another cloud provider or local-only backups."
            )
        current_type = BACKUP_DESTINATION_LOCAL
    if unavailable_reason:
        st.info(unavailable_reason)
    option_labels = [label for label, _value in destination_options]
    current_label = option_labels[option_values.index(current_type)]

    pending_provider = st.session_state.pop("_cloud_provider_select_pending", None)
    if pending_provider in option_labels:
        st.session_state["_cloud_provider_select"] = pending_provider
    elif "_cloud_provider_select" not in st.session_state:
        st.session_state["_cloud_provider_select"] = current_label

    provider_col, _provider_spacer = st.columns([1, 3])
    with provider_col:
        selected_label = st.selectbox(
            "Cloud Provider",
            option_labels,
            key="_cloud_provider_select",
            help="Cloud sync mirrors local backups on demand and when the app exits.",
        )
    selected_type = dict(destination_options)[selected_label]
    if selected_type != current_type:
        _render_cloud_provider_confirmation(
            selected_label=selected_label,
            selected_type=selected_type,
            current_label=current_label,
        )
        return

    if current_type == BACKUP_DESTINATION_LOCAL:
        return

    provider_name = _cloud_provider_display_name(current_type)
    stored_path = st.session_state.prefs.get("backup_destination_custom_path", "")
    default_path = stored_path
    if current_type == BACKUP_DESTINATION_ONEDRIVE and not default_path:
        detected = detect_onedrive_path()
        if detected is not None:
            default_path = str(cloud_backup_destination_path(detected))
        else:
            st.warning("OneDrive was not detected. Choose another provider or browse to a sync folder.")

    cloud_path = path_input(
        f"{provider_name} sync folder:",
        state_key="_cloud_backup_custom_path_input",
        browse_fn=browse_directory,
        browse_kwargs={
            "title": f"Select {provider_name} sync folder",
            "dir_key": "backup_destination_custom_path",
        },
        default=default_path,
    )
    _render_cloud_path_confirmation(
        provider_name=provider_name,
        cloud_path=cloud_path,
        current_path=stored_path,
    )

    configured_path = (st.session_state.prefs.get("backup_destination_custom_path") or "").strip()
    if configured_path and Path(configured_path).expanduser().exists():
        if st.button("Sync to Cloud Now", width="stretch"):
            result = sync_configured_backups_to_cloud()
            if result.ok:
                _apply_preferences_to_session({
                    **st.session_state.prefs,
                    "cloud_backup_last_sync_at": result.synced_at
                    or st.session_state.prefs.get("cloud_backup_last_sync_at", ""),
                })
                st.success(result.message)
                if result.destination_path:
                    st.caption(f"Destination: `{result.destination_path}`")
                for warning in result.warnings:
                    st.warning(warning)
            else:
                st.warning(result.message)
                for error in result.errors:
                    st.caption(error)

        last_sync = st.session_state.prefs.get("cloud_backup_last_sync_at") or ""
        st.caption(f"Last synced: `{last_sync}`" if last_sync else "Last synced: never")


def _cloud_provider_display_name(provider_type: str) -> str:
    return {
        BACKUP_DESTINATION_ONEDRIVE: "OneDrive",
        BACKUP_DESTINATION_GOOGLE_DRIVE: "Google Drive",
        BACKUP_DESTINATION_DROPBOX: "Dropbox",
        BACKUP_DESTINATION_ICLOUD_DRIVE: "iCloud Drive",
        BACKUP_DESTINATION_BOX: "Box",
        BACKUP_DESTINATION_CUSTOM: "Custom",
    }.get(provider_type, "Cloud")


def _cloud_destination_options(capabilities) -> list[tuple[str, str]]:
    destination_options = [("Local (no cloud sync)", BACKUP_DESTINATION_LOCAL)]
    if capabilities.supports_onedrive:
        destination_options.append(
            ("OneDrive (auto-detected)", BACKUP_DESTINATION_ONEDRIVE)
        )
    destination_options.extend([
        ("Google Drive", BACKUP_DESTINATION_GOOGLE_DRIVE),
        ("Dropbox", BACKUP_DESTINATION_DROPBOX),
        ("iCloud Drive", BACKUP_DESTINATION_ICLOUD_DRIVE),
        ("Box", BACKUP_DESTINATION_BOX),
    ])
    return destination_options


def _render_cloud_provider_confirmation(
    *,
    selected_label: str,
    selected_type: str,
    current_label: str,
) -> None:
    if selected_type == BACKUP_DESTINATION_LOCAL:
        st.warning("Switch to local-only backups? Cloud sync will be disabled.")
        confirm_label = "Confirm Local-Only Backups"
    else:
        st.warning(f"Change cloud provider to {selected_label}?")
        confirm_label = "Confirm Cloud Provider"
    confirm_col, cancel_col = st.columns(2)
    with confirm_col:
        if st.button(confirm_label, key="btn_confirm_cloud_provider"):
            updates = {"backup_destination_type": selected_type}
            if selected_type == BACKUP_DESTINATION_LOCAL:
                updates["backup_destination_custom_path"] = ""
            elif selected_type == BACKUP_DESTINATION_ONEDRIVE:
                detected = detect_onedrive_path()
                if detected is not None:
                    destination = cloud_backup_destination_path(detected)
                    destination.mkdir(parents=True, exist_ok=True)
                    updates["backup_destination_custom_path"] = str(destination.resolve())
                else:
                    updates["backup_destination_custom_path"] = ""
            else:
                updates["backup_destination_custom_path"] = ""
            st.session_state.backup_destination_type = selected_type
            if "backup_destination_custom_path" in updates:
                st.session_state.backup_destination_custom_path = updates[
                    "backup_destination_custom_path"
                ]
                st.session_state["_cloud_backup_custom_path_input_pending"] = updates[
                    "backup_destination_custom_path"
                ]
            update_prefs(updates)
            save_backup_config_from_settings(st.session_state.prefs)
            st.session_state["_cloud_provider_select_pending"] = selected_label
            st.success("Cloud backup destination updated.")
            st.rerun()
    with cancel_col:
        if st.button("Cancel Cloud Provider Change", key="btn_cancel_cloud_provider"):
            st.session_state["_cloud_provider_select_pending"] = current_label
            st.rerun()


def _render_cloud_path_confirmation(
    *,
    provider_name: str,
    cloud_path: str,
    current_path: str,
) -> None:
    if not (cloud_path or "").strip():
        return
    try:
        proposed = Path(cloud_path).expanduser().resolve()
        current = (
            Path(current_path).expanduser().resolve()
            if current_path
            else Path()
        )
    except OSError:
        proposed = Path(cloud_path).expanduser()
        current = Path(current_path).expanduser() if current_path else Path()
    if current_path and proposed == current:
        return

    destination = cloud_backup_destination_path(proposed)
    st.warning(
        f"Use `{proposed}` as the {provider_name} sync folder? "
        f"Backups will sync to `{destination}`."
    )
    confirm_col, cancel_col = st.columns(2)
    with confirm_col:
        if st.button("Confirm Cloud Folder", key="btn_confirm_cloud_folder"):
            try:
                provider_root = _normalize_folder_path(
                    cloud_path,
                    label=f"{provider_name} sync folder",
                )
                destination = cloud_backup_destination_path(provider_root)
                destination.mkdir(parents=True, exist_ok=True)
                normalized = str(destination.resolve())
                st.session_state.backup_destination_custom_path = normalized
                st.session_state["_cloud_backup_custom_path_input_pending"] = normalized
                update_prefs({"backup_destination_custom_path": normalized})
                save_backup_config_from_settings(st.session_state.prefs)
                st.success("Cloud sync folder updated.")
                st.rerun()
            except Exception as exc:
                st.error(f"Could not update cloud sync folder: {exc}")
    with cancel_col:
        if st.button("Cancel Cloud Folder Change", key="btn_cancel_cloud_folder"):
            st.session_state["_cloud_backup_custom_path_input_pending"] = current_path
            st.rerun()

