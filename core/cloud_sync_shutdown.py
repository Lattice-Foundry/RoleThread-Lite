"""Shutdown closeout helpers for staged cloud backup sync."""

from __future__ import annotations

from collections.abc import Callable

from core.cloud_sync import CloudSyncResult, sync_configured_backups_to_cloud


NOT_CONFIGURED_MESSAGE = "Cloud backup sync is not configured."


def run_cloud_sync_shutdown(
    *,
    sync_fn: Callable[[], CloudSyncResult] = sync_configured_backups_to_cloud,
    diagnostics_enabled: bool = False,
    status_callback: Callable[[str], None] | None = None,
    diagnostic_callback: Callable[[str], None] | None = None,
) -> CloudSyncResult:
    """Run configured cloud sync for process shutdown and emit concise statuses."""

    def emit(message: str) -> None:
        if status_callback is not None:
            status_callback(message)

    def emit_diagnostic(message: str) -> None:
        if diagnostics_enabled:
            emit(message)
        if diagnostic_callback is not None:
            diagnostic_callback(message)

    emit_diagnostic("Cloud sync: Checking staged cloud sync queue.")

    result = sync_fn()
    if _is_not_configured(result):
        emit_diagnostic("Cloud sync: No staged cloud sync work configured.")
        return result

    if result.ok:
        emit("Cloud sync: Staged cloud sync completed.")
        if result.destination_path:
            emit_diagnostic(f"Cloud sync: Destination {result.destination_path}.")
        emit_diagnostic(
            "Cloud sync: "
            f"Copied {result.sidecars_copied} sidecar"
            f"{'' if result.sidecars_copied == 1 else 's'}."
        )
    else:
        emit(
            "Cloud sync warning: "
            "Staged cloud sync did not complete; pending work was preserved."
        )
        emit_diagnostic(f"Cloud sync warning: {result.message}")

    for warning in result.warnings:
        emit_diagnostic(f"Cloud sync warning: {warning}")
    for error in result.errors:
        emit_diagnostic(f"Cloud sync warning: {error}")

    return result


def _is_not_configured(result: CloudSyncResult) -> bool:
    return result.ok and result.message == NOT_CONFIGURED_MESSAGE
