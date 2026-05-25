"""RoleThread product diagnostics panels for the LitLaunch support page."""

from __future__ import annotations

from collections.abc import Iterable
from html import escape

import streamlit as st

from core.platform import PATH_SOURCE_PLATFORM_DEFAULT
from core.product_diagnostics import (
    CloudBackupDiagnostics,
    DataHealthDiagnostics,
    ProductDiagnostics,
    ProductPathDiagnostics,
    SupportArtifactDiagnostics,
    collect_product_diagnostics,
)


PRIMARY_PATH_LABELS = {
    "App data",
    "Workspace",
    "Training data",
    "Backups",
    "Logs",
    "Database",
}


def render_product_diagnostics(
    diagnostics: ProductDiagnostics | None = None,
) -> None:
    """Render RoleThread-owned operational diagnostics."""

    try:
        product_diagnostics = diagnostics or collect_product_diagnostics()
    except Exception as exc:
        st.subheader("RoleThread Diagnostics")
        st.warning("RoleThread product diagnostics could not be collected.")
        st.caption(f"Collector error type: {type(exc).__name__}")
        return

    inject_product_diagnostics_styles()
    st.subheader("RoleThread Overview")
    _render_overview(product_diagnostics)
    _render_storage_and_data(product_diagnostics.paths)
    _render_cloud_backup(product_diagnostics.cloud_backup)
    _render_support_and_health(
        product_diagnostics.support_artifacts,
        product_diagnostics.data_health,
    )

    for note in product_diagnostics.privacy_notes:
        st.caption(note)


def _render_overview(diagnostics: ProductDiagnostics) -> None:
    overview = diagnostics.overview
    rows = (
        ("RoleThread", f"v{overview.rolethread_version}", "ok"),
        ("Python", f"{overview.python_version} - {overview.python_status}", "ok"),
        ("Streamlit", overview.streamlit_version, "ok"),
        ("LitLaunch", overview.litlaunch_version, "ok"),
        ("Platform", f"{overview.platform} - {overview.platform_support.title()}", "ok"),
        ("Runtime", overview.runtime_context.title(), "info"),
    )
    _render_card_grid(rows)


def _render_storage_and_data(paths: Iterable[ProductPathDiagnostics]) -> None:
    st.markdown("**Storage & Data**")
    path_rows = tuple(paths)
    primary_paths = tuple(
        path for path in path_rows if path.label in PRIMARY_PATH_LABELS
    )
    additional_paths = tuple(
        path for path in path_rows if path.label not in PRIMARY_PATH_LABELS
    )

    _render_path_grid(primary_paths)
    if additional_paths:
        with st.expander("Additional paths", expanded=False):
            _render_path_grid(additional_paths)


def _render_cloud_backup(cloud_backup: CloudBackupDiagnostics) -> None:
    st.markdown("**Cloud Backup**")
    status_label, status_level = _cloud_status(cloud_backup)
    rows = [
        ("Status", status_label, status_level),
        ("Provider", cloud_backup.provider, "info"),
    ]
    if cloud_backup.destination_path:
        destination_status = (
            "ok"
            if cloud_backup.destination_exists
            else "warning"
            if cloud_backup.destination_exists is False
            else "info"
        )
        rows.append(("Destination", cloud_backup.destination_path, destination_status))
    if cloud_backup.last_sync_at:
        rows.append(("Last sync", cloud_backup.last_sync_at, "info"))
    rows.append(
        (
            "Config",
            "found" if cloud_backup.config_exists else "not found",
            "ok" if cloud_backup.config_exists else "info",
        )
    )
    _render_card_grid(rows)
    for warning in cloud_backup.warnings:
        st.warning(warning)


def _render_support_and_health(
    support_artifacts: SupportArtifactDiagnostics,
    data_health: DataHealthDiagnostics,
) -> None:
    st.markdown("**Support & Data Health**")
    rows = (
        (
            "Product log",
            support_artifacts.product_log_path,
            "info",
        ),
        (
            "Runtime events",
            support_artifacts.runtime_event_log_path,
            "info",
        ),
        (
            "Reports",
            support_artifacts.reports_dir,
            "ok" if support_artifacts.reports_dir_exists else "info",
        ),
        (
            "Database",
            _availability_label(data_health.database_exists, data_health.database_readable),
            _availability_status(data_health.database_exists, data_health.database_readable),
        ),
        (
            "Preferences",
            _availability_label(
                data_health.preferences_exists,
                data_health.preferences_readable,
            ),
            _availability_status(
                data_health.preferences_exists,
                data_health.preferences_readable,
            ),
        ),
    )
    _render_card_grid(rows)
    for warning in data_health.warnings:
        st.warning(warning)


def _render_path_grid(paths: Iterable[ProductPathDiagnostics]) -> None:
    rows = tuple(paths)
    if not rows:
        st.caption("No path diagnostics available.")
        return
    for index in range(0, len(rows), 2):
        columns = st.columns(2)
        for column, path in zip(columns, rows[index:index + 2]):
            with column:
                source = _path_source_label(path)
                exists_label = "found" if path.exists else "missing"
                status = "ok" if path.exists else "info"
                _render_info_card(
                    path.label,
                    path.path,
                    status,
                    footer=f"{exists_label} - {source}",
                )


def _render_card_grid(rows: Iterable[tuple[str, str, str]]) -> None:
    row_values = tuple(rows)
    for index in range(0, len(row_values), 3):
        columns = st.columns(3)
        for column, (label, value, status) in zip(columns, row_values[index:index + 3]):
            with column:
                _render_info_card(label, value, status)


def _render_info_card(
    label: str,
    value: str,
    status: str,
    *,
    footer: str | None = None,
) -> None:
    status_class = _status_class(status)
    footer_html = (
        f"<div class='rolethread-diagnostics-footer'>{_html(footer)}</div>"
        if footer
        else ""
    )
    st.markdown(
        (
            f"<div class='rolethread-diagnostics-card {status_class}'>"
            f"<div class='rolethread-diagnostics-label'>{_html(label)}</div>"
            f"<div class='rolethread-diagnostics-value'>{_html(value)}</div>"
            f"{footer_html}</div>"
        ),
        unsafe_allow_html=True,
    )


def inject_product_diagnostics_styles() -> None:
    """Add compact RoleThread product diagnostics styles."""

    st.markdown(
        """
<style>
.rolethread-diagnostics-card {
    background: rgba(32, 35, 38, 0.72);
    border: 1px solid rgba(232, 232, 232, 0.12);
    border-left: 4px solid #8B949E;
    border-radius: 0.48rem;
    margin: 0.24rem 0 0.72rem 0;
    min-height: 5.2rem;
    padding: 0.72rem 0.82rem;
}
.rolethread-diagnostics-card.ok {
    border-left-color: #3EB489;
}
.rolethread-diagnostics-card.warning {
    border-left-color: #F4F15A;
}
.rolethread-diagnostics-card.error {
    border-left-color: #E74C3C;
}
.rolethread-diagnostics-label {
    color: #8B949E;
    font-size: 0.76rem;
    font-weight: 750;
    text-transform: uppercase;
}
.rolethread-diagnostics-value {
    color: #E8E8E8;
    font-size: 0.9rem;
    font-weight: 650;
    line-height: 1.35;
    margin-top: 0.16rem;
    overflow-wrap: anywhere;
}
.rolethread-diagnostics-footer {
    color: #8B949E;
    font-size: 0.76rem;
    line-height: 1.35;
    margin-top: 0.34rem;
}
</style>
        """,
        unsafe_allow_html=True,
    )


def _cloud_status(cloud_backup: CloudBackupDiagnostics) -> tuple[str, str]:
    if cloud_backup.status == "local_only":
        return "Local-only", "ok"
    if cloud_backup.status == "configured":
        if cloud_backup.destination_exists is False:
            return "Configured, destination missing", "warning"
        return "Configured", "ok"
    return "Needs attention", "warning"


def _availability_label(exists: bool, readable: bool) -> str:
    if readable:
        return "readable"
    if exists:
        return "exists, unreadable"
    return "not found"


def _availability_status(exists: bool, readable: bool) -> str:
    if readable:
        return "ok"
    if exists:
        return "warning"
    return "info"


def _path_source_label(path: ProductPathDiagnostics) -> str:
    if path.source == PATH_SOURCE_PLATFORM_DEFAULT:
        return "platform default"
    if path.platform_default:
        return f"user override; default {path.platform_default}"
    return "user override"


def _status_class(status: str) -> str:
    normalized = str(status or "info").lower()
    if normalized in {"ok", "warning", "error"}:
        return normalized
    return "info"


def _html(value: object) -> str:
    return escape(str(value), quote=True)
