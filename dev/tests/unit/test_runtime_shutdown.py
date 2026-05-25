from litlaunch import HookConsoleVisibility, ShutdownHookStatus, ShutdownResult

from core.cloud_sync import CloudSyncResult
from core import runtime_shutdown as shutdown


def setup_function():
    shutdown._reset_shutdown_state_for_tests()


def teardown_function():
    shutdown._reset_shutdown_state_for_tests()


def test_shutdown_bridge_is_inert_without_litlaunch_env():
    registered = []

    enabled = shutdown.configure_runtime_shutdown(
        environ={},
        register_atexit_fn=registered.append,
    )

    assert enabled is False
    assert registered == [shutdown.run_cloud_sync_closeout]


def test_shutdown_bridge_registers_litlaunch_cleanup_hook():
    runtime = _FakeRuntime(available=True)
    exits = []

    enabled = shutdown.configure_runtime_shutdown(
        runtime=runtime,
        exit_fn=exits.append,
        register_atexit_fn=lambda func: None,
    )

    assert enabled is True
    assert runtime.endpoint_enabled is True
    assert runtime.hook["label"] == "Cloud backup sync"
    assert runtime.hook["success_message"] is None
    assert callable(runtime.hook["func"])
    assert callable(runtime.completion_callback)

    runtime.completion_callback(ShutdownResult(ok=True, hook_results=(), message="ok"))
    assert exits == [0]


def test_cloud_sync_closeout_runs_once(monkeypatch):
    calls = []

    def fake_cloud_sync(**kwargs):
        calls.append(kwargs)
        return CloudSyncResult(
            ok=True,
            message="Cloud backup sync complete. Copied 1 sidecar.",
            sidecars_copied=1,
        )

    monkeypatch.setattr(shutdown, "run_cloud_sync_shutdown", fake_cloud_sync)

    first = shutdown.run_cloud_sync_closeout(
        diagnostics_enabled=True,
        status_callback=lambda message: None,
        diagnostic_callback=lambda message: None,
        environ={},
    )
    second = shutdown.run_cloud_sync_closeout(
        diagnostics_enabled=True,
        status_callback=lambda message: None,
        diagnostic_callback=lambda message: None,
        environ={},
    )

    assert isinstance(first, ShutdownHookStatus)
    assert first.message == "Cloud sync: Staged cloud sync completed."
    assert first.console_visibility == HookConsoleVisibility.NORMAL
    assert second.render is False
    assert len(calls) == 1
    assert calls[0]["diagnostics_enabled"] is True


def test_cloud_sync_diagnostics_can_be_enabled_from_env(monkeypatch):
    calls = []
    monkeypatch.setattr(
        shutdown,
        "run_cloud_sync_shutdown",
        lambda **kwargs: calls.append(kwargs)
        or CloudSyncResult(
            ok=True,
            message="Cloud backup sync complete. Copied 1 sidecar.",
            sidecars_copied=1,
        ),
    )

    shutdown.run_cloud_sync_closeout(
        status_callback=lambda message: None,
        diagnostic_callback=lambda message: None,
        environ={shutdown.ROLETHREAD_SHUTDOWN_DIAGNOSTICS_ENV: "true"},
    )

    assert calls[0]["diagnostics_enabled"] is True


def test_cloud_sync_closeout_hides_not_configured_status(monkeypatch):
    monkeypatch.setattr(
        shutdown,
        "run_cloud_sync_shutdown",
        lambda **kwargs: CloudSyncResult(
            ok=True,
            message="Cloud backup sync is not configured.",
        ),
    )

    status = shutdown.run_cloud_sync_closeout(
        status_callback=lambda message: None,
        diagnostic_callback=lambda message: None,
        environ={},
    )

    assert status.message == "Cloud sync: No staged cloud sync work configured."
    assert status.console_visibility == HookConsoleVisibility.VERBOSE
    assert status.ok is True


def test_cloud_sync_closeout_surfaces_warning_status(monkeypatch):
    monkeypatch.setattr(
        shutdown,
        "run_cloud_sync_shutdown",
        lambda **kwargs: CloudSyncResult(
            ok=True,
            message="Cloud backup sync complete. Copied 1 sidecar.",
            sidecars_copied=1,
            warnings=("old staging directory was removed",),
        ),
    )

    status = shutdown.run_cloud_sync_closeout(
        status_callback=lambda message: None,
        diagnostic_callback=lambda message: None,
        environ={},
    )

    assert status.message == "Cloud sync: Staged cloud sync completed with cleanup warnings."
    assert status.console_visibility == HookConsoleVisibility.NORMAL
    assert status.ok is True


def test_cloud_sync_closeout_surfaces_failure_without_failing_shutdown(monkeypatch):
    monkeypatch.setattr(
        shutdown,
        "run_cloud_sync_shutdown",
        lambda **kwargs: CloudSyncResult(
            ok=False,
            message="Cloud backup sync failed: disk full",
            errors=("disk full",),
        ),
    )

    status = shutdown.run_cloud_sync_closeout(
        status_callback=lambda message: None,
        diagnostic_callback=lambda message: None,
        environ={},
    )

    assert status.message == (
        "Cloud sync warning: Staged cloud sync did not complete; "
        "pending work was preserved."
    )
    assert status.console_visibility == HookConsoleVisibility.NORMAL
    assert status.ok is True


def test_cloud_sync_closeout_does_not_print_raw_rolethread_status(monkeypatch, capsys):
    def fake_cloud_sync(**kwargs):
        kwargs["diagnostic_callback"]("Cloud sync: Checking staged cloud sync queue.")
        return CloudSyncResult(
            ok=True,
            message="Cloud backup sync complete. Copied 1 sidecar.",
            sidecars_copied=1,
        )

    monkeypatch.setattr(shutdown, "run_cloud_sync_shutdown", fake_cloud_sync)

    shutdown.run_cloud_sync_closeout(
        diagnostic_callback=lambda message: None,
        environ={},
    )

    captured = capsys.readouterr()
    assert "[RoleThread]" not in captured.out
    assert captured.err == ""


class _FakeRuntime:
    def __init__(self, *, available):
        self.available = available
        self.endpoint_enabled = False
        self.hook = {}
        self.completion_callback = None

    def register_shutdown_hook(self, func, **metadata):
        self.hook = {"func": func, **metadata}

    def set_shutdown_completion_callback(self, callback):
        self.completion_callback = callback

    def enable_shutdown_endpoint(self):
        self.endpoint_enabled = True
        return True
