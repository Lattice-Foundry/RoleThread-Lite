from litlaunch import ShutdownResult

from core import litlaunch_shutdown_bridge as bridge


def setup_function():
    bridge._reset_shutdown_bridge_state_for_tests()


def teardown_function():
    bridge._reset_shutdown_bridge_state_for_tests()


def test_shutdown_bridge_is_inert_without_litlaunch_env():
    registered = []

    enabled = bridge.configure_litlaunch_shutdown_bridge(
        environ={},
        register_atexit_fn=registered.append,
    )

    assert enabled is False
    assert registered == [bridge.run_cloud_sync_closeout]


def test_shutdown_bridge_registers_litlaunch_cleanup_hook():
    runtime = _FakeRuntime(available=True)
    exits = []

    enabled = bridge.configure_litlaunch_shutdown_bridge(
        runtime=runtime,
        exit_fn=exits.append,
        register_atexit_fn=lambda func: None,
    )

    assert enabled is True
    assert runtime.endpoint_enabled is True
    assert runtime.hook["label"] == "Cloud backup sync"
    assert callable(runtime.hook["func"])
    assert callable(runtime.completion_callback)

    runtime.completion_callback(ShutdownResult(ok=True, hook_results=(), message="ok"))
    assert exits == [0]


def test_cloud_sync_closeout_runs_once(monkeypatch):
    calls = []

    def fake_cloud_sync(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(bridge, "run_cloud_sync_shutdown", fake_cloud_sync)

    first = bridge.run_cloud_sync_closeout(
        diagnostics_enabled=True,
        status_callback=lambda message: None,
        diagnostic_callback=lambda message: None,
        environ={},
    )
    second = bridge.run_cloud_sync_closeout(
        diagnostics_enabled=True,
        status_callback=lambda message: None,
        diagnostic_callback=lambda message: None,
        environ={},
    )

    assert first is True
    assert second is False
    assert len(calls) == 1
    assert calls[0]["diagnostics_enabled"] is True


def test_cloud_sync_diagnostics_can_be_enabled_from_env(monkeypatch):
    calls = []
    monkeypatch.setattr(
        bridge,
        "run_cloud_sync_shutdown",
        lambda **kwargs: calls.append(kwargs),
    )

    bridge.run_cloud_sync_closeout(
        status_callback=lambda message: None,
        diagnostic_callback=lambda message: None,
        environ={bridge.ROLETHREAD_SHUTDOWN_DIAGNOSTICS_ENV: "true"},
    )

    assert calls[0]["diagnostics_enabled"] is True


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
