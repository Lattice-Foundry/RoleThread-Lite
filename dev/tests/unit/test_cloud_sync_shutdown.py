from core.cloud_sync import CloudSyncResult
from core.cloud_sync_shutdown import run_cloud_sync_shutdown


def test_cloud_sync_shutdown_skips_quietly_when_not_configured():
    messages = []

    result = run_cloud_sync_shutdown(
        sync_fn=lambda: CloudSyncResult(
            ok=True,
            message="Cloud backup sync is not configured.",
        ),
        status_callback=messages.append,
    )

    assert result.ok is True
    assert messages == []


def test_cloud_sync_shutdown_reports_skip_in_diagnostics():
    messages = []

    run_cloud_sync_shutdown(
        sync_fn=lambda: CloudSyncResult(
            ok=True,
            message="Cloud backup sync is not configured.",
        ),
        diagnostics_enabled=True,
        status_callback=messages.append,
    )

    assert messages == [
        "Cloud sync: Checking staged cloud sync queue.",
        "Cloud sync: No staged cloud sync work configured.",
    ]


def test_cloud_sync_shutdown_reports_success_when_sync_runs():
    messages = []

    result = run_cloud_sync_shutdown(
        sync_fn=lambda: CloudSyncResult(
            ok=True,
            message="Cloud backup sync complete. Copied 2 sidecars.",
            destination_path="X:/Backups/RoleThread Lite/backups",
            sidecars_copied=2,
        ),
        status_callback=messages.append,
    )

    assert result.ok is True
    assert messages == ["Cloud sync: Staged cloud sync completed."]


def test_cloud_sync_shutdown_reports_diagnostic_details_for_success():
    messages = []

    run_cloud_sync_shutdown(
        sync_fn=lambda: CloudSyncResult(
            ok=True,
            message="Cloud backup sync complete. Copied 1 sidecar.",
            destination_path="X:/Backups/RoleThread Lite/backups",
            sidecars_copied=1,
            warnings=("old staging directory was removed",),
        ),
        diagnostics_enabled=True,
        status_callback=messages.append,
    )

    assert messages == [
        "Cloud sync: Checking staged cloud sync queue.",
        "Cloud sync: Staged cloud sync completed.",
        "Cloud sync: Destination X:/Backups/RoleThread Lite/backups.",
        "Cloud sync: Copied 1 sidecar.",
        "Cloud sync warning: old staging directory was removed",
    ]


def test_cloud_sync_shutdown_reports_failure_without_discarding_pending_work():
    messages = []

    result = run_cloud_sync_shutdown(
        sync_fn=lambda: CloudSyncResult(
            ok=False,
            message="Cloud backup sync failed: disk full",
            destination_path="X:/Backups/RoleThread Lite/backups",
            errors=("disk full",),
        ),
        diagnostics_enabled=True,
        status_callback=messages.append,
    )

    assert result.ok is False
    assert messages == [
        "Cloud sync: Checking staged cloud sync queue.",
        "Cloud sync warning: Staged cloud sync did not complete; pending work was preserved.",
        "Cloud sync warning: Cloud backup sync failed: disk full",
        "Cloud sync warning: disk full",
    ]
