import json
from pathlib import Path
import subprocess

import pytest

from core.shutdown_control import (
    SHUTDOWN_HEADER,
    SHUTDOWN_PORT_ENV,
    SHUTDOWN_TOKEN_ENV,
    LauncherShutdownControl,
    resolve_launcher_shutdown_control,
    start_launcher_shutdown_server,
)
from installer.windows.launcher import rolethread_launcher as launcher


def _make_app_root(tmp_path: Path, *, with_dev_python: bool = True) -> Path:
    app_root = tmp_path / "app"
    app_root.mkdir()
    (app_root / "app.py").write_text("print('RoleThread')", encoding="utf-8")
    if with_dev_python:
        python_path = app_root / ".venv" / "Scripts" / "python.exe"
        python_path.parent.mkdir(parents=True)
        python_path.write_text("", encoding="utf-8")
    return app_root


def test_missing_preferences_selects_normal_launch_mode(tmp_path):
    preferences_path = tmp_path / "missing.json"

    assert launcher.read_enable_webapp_launch_mode(preferences_path) is False
    assert launcher.select_launch_mode(enable_webapp_launch_mode=False) == "normal"


def test_false_preference_selects_normal_launch_mode(tmp_path):
    preferences_path = tmp_path / "preferences.json"
    preferences_path.write_text(
        json.dumps({"enable_webapp_launch_mode": False}),
        encoding="utf-8",
    )

    assert launcher.read_enable_webapp_launch_mode(preferences_path) is False
    assert launcher.select_launch_mode(enable_webapp_launch_mode=False) == "normal"


def test_true_preference_selects_webapp_launch_mode(tmp_path):
    preferences_path = tmp_path / "preferences.json"
    preferences_path.write_text(
        json.dumps({"enable_webapp_launch_mode": True}),
        encoding="utf-8",
    )

    assert launcher.read_enable_webapp_launch_mode(preferences_path) is True
    assert launcher.select_launch_mode(enable_webapp_launch_mode=True) == "webapp"


def test_command_construction_for_normal_launch(tmp_path):
    python_path = tmp_path / "python.exe"

    command = launcher.build_streamlit_command(
        python_path,
        launch_mode=launcher.LAUNCH_MODE_NORMAL,
    )

    assert command == (
        str(python_path),
        "-m",
        "streamlit",
        "run",
        "app.py",
        "--server.port",
        "8501",
    )


def test_command_construction_for_webapp_launch(tmp_path):
    python_path = tmp_path / "python.exe"

    command = launcher.build_streamlit_command(
        python_path,
        launch_mode=launcher.LAUNCH_MODE_WEBAPP,
    )

    assert command[-2:] == ("--", "webapp")
    assert command[:4] == (str(python_path), "-m", "streamlit", "run")


def test_bundled_command_uses_internal_streamlit_mode(tmp_path):
    app_root = _make_app_root(tmp_path, with_dev_python=False)
    launcher_exe = tmp_path / "RoleThreadLauncher.exe"
    launcher_exe.write_text("", encoding="utf-8")

    command = launcher.build_streamlit_command(
        launcher_exe,
        launch_mode=launcher.LAUNCH_MODE_WEBAPP,
        app_root=app_root,
        frozen=True,
    )

    assert command == (
        str(launcher_exe),
        launcher.INTERNAL_STREAMLIT_FLAG,
        str(app_root / "app.py"),
        "--global.developmentMode=false",
        "--server.port",
        "8501",
        "--",
        "webapp",
    )


def test_dev_python_path_selection_prefers_venv_runtime(tmp_path):
    app_root = _make_app_root(tmp_path, with_dev_python=True)
    fallback = tmp_path / "fallback.exe"
    fallback.write_text("", encoding="utf-8")

    python_path = launcher.resolve_python_runtime(
        app_root,
        current_executable=str(fallback),
    )

    assert python_path == app_root / ".venv" / "Scripts" / "python.exe"


def test_python_path_selection_falls_back_to_current_executable(tmp_path):
    app_root = _make_app_root(tmp_path, with_dev_python=False)
    fallback = tmp_path / "fallback.exe"
    fallback.write_text("", encoding="utf-8")

    python_path = launcher.resolve_python_runtime(
        app_root,
        current_executable=str(fallback),
    )

    assert python_path == fallback


def test_bundled_runtime_selection_uses_launcher_executable(tmp_path):
    app_root = _make_app_root(tmp_path, with_dev_python=False)
    launcher_exe = tmp_path / "RoleThreadLauncher.exe"
    launcher_exe.write_text("", encoding="utf-8")

    python_path = launcher.resolve_python_runtime(
        app_root,
        current_executable=str(launcher_exe),
        frozen=True,
    )

    assert python_path == launcher_exe


def test_python_path_selection_errors_without_runtime(tmp_path):
    app_root = _make_app_root(tmp_path, with_dev_python=False)

    with pytest.raises(launcher.LauncherConfigurationError):
        launcher.resolve_python_runtime(
            app_root,
            current_executable=str(tmp_path / "missing.exe"),
        )


def test_build_launcher_config_errors_when_app_root_has_no_app_py(tmp_path):
    app_root = tmp_path / "not_rolethread"
    app_root.mkdir()

    with pytest.raises(launcher.LauncherConfigurationError) as exc_info:
        launcher.build_launcher_config(
            app_root=app_root,
            current_executable=str(tmp_path / "missing.exe"),
        )

    assert "app.py" in str(exc_info.value)


def test_resolve_app_root_uses_pyinstaller_meipass_in_frozen_mode(tmp_path, monkeypatch):
    app_root = _make_app_root(tmp_path, with_dev_python=False)
    monkeypatch.setattr(launcher.sys, "_MEIPASS", str(app_root), raising=False)

    assert launcher.resolve_app_root(frozen=True) == app_root.resolve()


def test_build_launcher_config_uses_bundled_command_in_frozen_mode(tmp_path):
    app_root = _make_app_root(tmp_path, with_dev_python=False)
    launcher_exe = tmp_path / "RoleThreadLauncher.exe"
    launcher_exe.write_text("", encoding="utf-8")

    config = launcher.build_launcher_config(
        app_root=app_root,
        env={"LOCALAPPDATA": str(tmp_path / "local")},
        current_executable=str(launcher_exe),
        frozen=True,
        shutdown_port=54321,
        shutdown_token="token",
    )

    assert config.python_path == launcher_exe
    assert config.bundled_mode is True
    assert config.command[:3] == (
        str(launcher_exe),
        launcher.INTERNAL_STREAMLIT_FLAG,
        str(app_root / "app.py"),
    )
    assert "-m" not in config.command
    assert config.shutdown_port == 54321
    assert config.shutdown_token == "token"


def test_launcher_log_path_resolution_uses_localappdata():
    log_path = launcher.resolve_launcher_log_path(
        {"LOCALAPPDATA": "C:/Users/Public/AppData/Local"}
    )

    assert log_path == Path("C:/Users/Public/AppData/Local/RoleThread/logs/launcher.log")


def test_build_launcher_config_reads_preference_and_builds_webapp_command(tmp_path):
    app_root = _make_app_root(tmp_path)
    local_app_data = tmp_path / "local"
    preferences_path = local_app_data / "RoleThread" / "preferences.json"
    preferences_path.parent.mkdir(parents=True)
    preferences_path.write_text(
        json.dumps({"enable_webapp_launch_mode": True}),
        encoding="utf-8",
    )

    config = launcher.build_launcher_config(
        app_root=app_root,
        env={"LOCALAPPDATA": str(local_app_data)},
        current_executable=str(tmp_path / "unused.exe"),
        shutdown_port=54321,
        shutdown_token="token",
    )

    assert config.launch_mode == launcher.LAUNCH_MODE_WEBAPP
    assert config.preferences_path == preferences_path
    assert config.log_path == local_app_data / "RoleThread" / "logs" / "launcher.log"
    assert config.command[-2:] == ("--", "webapp")


def test_launch_rolethread_logs_and_invokes_subprocess(tmp_path):
    app_root = _make_app_root(tmp_path)
    log_path = tmp_path / "logs" / "launcher.log"
    command = ("python.exe", "-m", "streamlit", "run", "app.py")
    config = launcher.LauncherConfig(
        app_root=app_root,
        python_path=Path("python.exe"),
        preferences_path=tmp_path / "preferences.json",
        log_path=log_path,
        launch_mode=launcher.LAUNCH_MODE_NORMAL,
        command=command,
    )
    calls = []

    class FakeProcess:
        pid = 1234

    def fake_popen(*args, **kwargs):
        calls.append((args, kwargs))
        return FakeProcess()

    result = launcher.launch_rolethread(
        config,
        popen=fake_popen,
        port_available_fn=lambda: True,
    )

    assert isinstance(result, FakeProcess)
    assert len(calls) == 1
    assert calls[0][0] == (command,)
    assert calls[0][1]["cwd"] == app_root
    assert SHUTDOWN_PORT_ENV not in calls[0][1]["env"]
    log_text = log_path.read_text(encoding="utf-8")
    assert "launch_mode=normal" in log_text
    assert f"app_version={launcher.get_app_version()}" in log_text
    assert "bundled_mode=False" in log_text
    assert "command=python.exe -m streamlit run app.py" in log_text
    assert "started_pid=1234" in log_text


def test_launch_rolethread_reports_port_in_use_without_starting_subprocess(tmp_path):
    app_root = _make_app_root(tmp_path)
    log_path = tmp_path / "logs" / "launcher.log"
    config = launcher.LauncherConfig(
        app_root=app_root,
        python_path=Path("python.exe"),
        preferences_path=tmp_path / "preferences.json",
        log_path=log_path,
        launch_mode=launcher.LAUNCH_MODE_NORMAL,
        command=("python.exe", "-m", "streamlit", "run", "app.py"),
    )

    with pytest.raises(launcher.LauncherConfigurationError) as exc_info:
        launcher.launch_rolethread(
            config,
            popen=lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError("subprocess should not start")
            ),
            port_available_fn=lambda: False,
        )

    assert "Port 8501 is already in use" in str(exc_info.value)
    assert "Port 8501 is already in use" in log_path.read_text(encoding="utf-8")


def test_launch_rolethread_logs_subprocess_failure(tmp_path):
    app_root = _make_app_root(tmp_path)
    log_path = tmp_path / "logs" / "launcher.log"
    config = launcher.LauncherConfig(
        app_root=app_root,
        python_path=Path("python.exe"),
        preferences_path=tmp_path / "preferences.json",
        log_path=log_path,
        launch_mode=launcher.LAUNCH_MODE_NORMAL,
        command=("python.exe", "-m", "streamlit", "run", "app.py"),
    )

    def fail_popen(*args, **kwargs):
        raise OSError("streamlit exploded")

    with pytest.raises(OSError):
        launcher.launch_rolethread(
            config,
            popen=fail_popen,
            port_available_fn=lambda: True,
        )

    log_text = log_path.read_text(encoding="utf-8")
    assert "subprocess_error=streamlit exploded" in log_text


def test_port_available_false_when_connection_succeeds(monkeypatch):
    class FakeSocket:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(launcher.socket, "create_connection", lambda *args, **kwargs: FakeSocket())

    assert launcher.is_port_available() is False


def test_port_available_true_when_connection_fails(monkeypatch):
    def fail(*args, **kwargs):
        raise OSError("closed")

    monkeypatch.setattr(launcher.socket, "create_connection", fail)

    assert launcher.is_port_available() is True


def test_pyinstaller_spec_uses_windowed_no_console_mode():
    spec_path = Path(__file__).parents[3] / "installer" / "windows" / "rolethread_launcher.spec"
    spec_text = spec_path.read_text(encoding="utf-8")

    assert "console=False" in spec_text
    assert "console=True" not in spec_text


def test_shutdown_control_resolves_only_when_launcher_env_is_complete():
    assert resolve_launcher_shutdown_control({}) is None
    assert resolve_launcher_shutdown_control(
        {SHUTDOWN_PORT_ENV: "not-a-port", SHUTDOWN_TOKEN_ENV: "token"}
    ) is None

    control = resolve_launcher_shutdown_control(
        {SHUTDOWN_PORT_ENV: "54321", SHUTDOWN_TOKEN_ENV: "token"}
    )

    assert control == LauncherShutdownControl(port=54321, token="token")


def test_start_launcher_shutdown_server_ignores_missing_control():
    assert start_launcher_shutdown_server(None, shutdown_fn=lambda: None) is False


def test_build_subprocess_env_includes_shutdown_control(tmp_path):
    app_root = _make_app_root(tmp_path)
    config = launcher.LauncherConfig(
        app_root=app_root,
        python_path=Path("python.exe"),
        preferences_path=tmp_path / "preferences.json",
        log_path=tmp_path / "launcher.log",
        launch_mode=launcher.LAUNCH_MODE_WEBAPP,
        command=("python.exe", "-m", "streamlit"),
        shutdown_port=54321,
        shutdown_token="secret",
    )

    env = launcher.build_subprocess_env(config, {"BASE": "1"})

    assert env["BASE"] == "1"
    assert env[SHUTDOWN_PORT_ENV] == "54321"
    assert env[SHUTDOWN_TOKEN_ENV] == "secret"


def test_request_graceful_shutdown_builds_tokenized_local_request(tmp_path):
    app_root = _make_app_root(tmp_path)
    config = launcher.LauncherConfig(
        app_root=app_root,
        python_path=Path("python.exe"),
        preferences_path=tmp_path / "preferences.json",
        log_path=tmp_path / "launcher.log",
        launch_mode=launcher.LAUNCH_MODE_WEBAPP,
        command=("python.exe", "-m", "streamlit"),
        shutdown_port=54321,
        shutdown_token="secret",
    )
    calls = []

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    def fake_urlopen(request_obj, timeout):
        calls.append((request_obj, timeout))
        return FakeResponse()

    result = launcher.request_graceful_shutdown(config, urlopen=fake_urlopen)

    assert result.ok is True
    assert result.status_code == 200
    assert calls[0][0].full_url == "http://127.0.0.1:54321/shutdown"
    headers = dict(calls[0][0].header_items())
    assert headers["X-rolethread-launcher-token"] == "secret"


def test_wait_for_app_window_close_detects_webapp_close_sequence():
    counts = iter([0, 1, 1, 0])

    result = launcher.wait_for_app_window_close(
        launcher.LAUNCH_MODE_WEBAPP,
        count_windows_fn=lambda: next(counts),
        sleep_fn=lambda _: None,
        appear_timeout_seconds=5,
        poll_seconds=0,
    )

    assert result.supported is True
    assert result.observed is True
    assert result.closed is True


def test_wait_for_app_window_close_reports_normal_mode_limitation():
    result = launcher.wait_for_app_window_close(launcher.LAUNCH_MODE_NORMAL)

    assert result.supported is False
    assert result.closed is False
    assert "normal browser" in result.message


def test_terminate_process_fallback_uses_terminate_before_kill():
    class FakeProcess:
        def __init__(self):
            self.calls = []
            self.exited = False

        def poll(self):
            return 0 if self.exited else None

        def terminate(self):
            self.calls.append("terminate")
            self.exited = True

        def kill(self):
            self.calls.append("kill")

        def wait(self, timeout):
            if self.exited:
                return 0
            raise subprocess.TimeoutExpired("fake", timeout)

    process = FakeProcess()

    result = launcher.terminate_process_fallback(process)

    assert result.method == "terminate"
    assert result.completed is True
    assert process.calls == ["terminate"]


def test_terminate_process_fallback_kills_as_last_resort(monkeypatch):
    class FakeProcess:
        def __init__(self):
            self.calls = []

        def poll(self):
            return None

        def terminate(self):
            self.calls.append("terminate")

        def kill(self):
            self.calls.append("kill")

    process = FakeProcess()
    waits = iter([False, True])
    monkeypatch.setattr(launcher, "wait_for_process_exit", lambda *args, **kwargs: next(waits))

    result = launcher.terminate_process_fallback(process)

    assert result.method == "kill"
    assert result.completed is True
    assert process.calls == ["terminate", "kill"]


def test_run_launcher_lifecycle_graceful_shutdown_path(tmp_path):
    app_root = _make_app_root(tmp_path)
    log_path = tmp_path / "logs" / "launcher.log"
    config = launcher.LauncherConfig(
        app_root=app_root,
        python_path=Path("python.exe"),
        preferences_path=tmp_path / "preferences.json",
        log_path=log_path,
        launch_mode=launcher.LAUNCH_MODE_WEBAPP,
        command=("python.exe", "-m", "streamlit"),
        shutdown_port=54321,
        shutdown_token="secret",
    )

    class FakeProcess:
        pid = 777

        def __init__(self):
            self.exited = False

        def poll(self):
            return 0 if self.exited else None

        def wait(self, timeout):
            self.exited = True
            return 0

    result = launcher.run_launcher_lifecycle(
        config,
        popen=lambda *args, **kwargs: FakeProcess(),
        port_available_fn=lambda: True,
        health_check_fn=lambda: launcher.HealthCheckResult(
            ok=True,
            url="http://127.0.0.1:8501/_stcore/health",
            attempts=1,
            message="ok",
        ),
        wait_for_close_fn=lambda mode, process: launcher.WindowCloseDetectionResult(
            supported=True,
            closed=True,
            observed=True,
            message="closed",
        ),
        shutdown_request_fn=lambda cfg: launcher.ShutdownRequestResult(
            attempted=True,
            ok=True,
            status_code=200,
            message="ok",
        ),
        termination_fn=lambda process: (_ for _ in ()).throw(
            AssertionError("termination should not run")
        ),
    )

    assert result.final_state == "graceful_shutdown"
    assert result.shutdown_request.ok is True
    log_text = log_path.read_text(encoding="utf-8")
    assert "lifecycle=health_check" in log_text
    assert "lifecycle=window_monitor" in log_text
    assert "lifecycle=shutdown_request" in log_text


def test_run_launcher_lifecycle_terminates_after_shutdown_timeout(tmp_path, monkeypatch):
    app_root = _make_app_root(tmp_path)
    config = launcher.LauncherConfig(
        app_root=app_root,
        python_path=Path("python.exe"),
        preferences_path=tmp_path / "preferences.json",
        log_path=tmp_path / "logs" / "launcher.log",
        launch_mode=launcher.LAUNCH_MODE_WEBAPP,
        command=("python.exe", "-m", "streamlit"),
        shutdown_port=54321,
        shutdown_token="secret",
    )

    class FakeProcess:
        pid = 888

        def poll(self):
            return None

    monkeypatch.setattr(launcher, "wait_for_process_exit", lambda *args, **kwargs: False)

    result = launcher.run_launcher_lifecycle(
        config,
        popen=lambda *args, **kwargs: FakeProcess(),
        port_available_fn=lambda: True,
        health_check_fn=lambda: launcher.HealthCheckResult(True, "url", 1, "ok"),
        wait_for_close_fn=lambda mode, process: launcher.WindowCloseDetectionResult(
            True,
            True,
            True,
            "closed",
        ),
        shutdown_request_fn=lambda cfg: launcher.ShutdownRequestResult(
            True,
            False,
            None,
            "failed",
        ),
        termination_fn=lambda process: launcher.TerminationResult(
            True,
            "terminate",
            True,
            "terminated",
        ),
    )

    assert result.final_state == "terminated"
    assert result.termination.method == "terminate"


def test_run_launcher_lifecycle_terminates_when_health_check_fails(tmp_path):
    app_root = _make_app_root(tmp_path)
    config = launcher.LauncherConfig(
        app_root=app_root,
        python_path=Path("python.exe"),
        preferences_path=tmp_path / "preferences.json",
        log_path=tmp_path / "logs" / "launcher.log",
        launch_mode=launcher.LAUNCH_MODE_WEBAPP,
        command=("python.exe", "-m", "streamlit"),
        shutdown_port=54321,
        shutdown_token="secret",
    )

    class FakeProcess:
        pid = 889

    result = launcher.run_launcher_lifecycle(
        config,
        popen=lambda *args, **kwargs: FakeProcess(),
        port_available_fn=lambda: True,
        health_check_fn=lambda: launcher.HealthCheckResult(False, "url", 3, "timeout"),
        wait_for_close_fn=lambda mode, process: (_ for _ in ()).throw(
            AssertionError("window monitoring should not run")
        ),
        shutdown_request_fn=lambda cfg: (_ for _ in ()).throw(
            AssertionError("shutdown should not run")
        ),
        termination_fn=lambda process: launcher.TerminationResult(
            True,
            "terminate",
            True,
            "terminated",
        ),
    )

    assert result.final_state == "health_failed"
    assert result.termination.method == "terminate"
    assert result.shutdown_request.attempted is False


def test_run_launcher_lifecycle_does_not_shutdown_when_monitoring_unsupported(tmp_path):
    app_root = _make_app_root(tmp_path)
    config = launcher.LauncherConfig(
        app_root=app_root,
        python_path=Path("python.exe"),
        preferences_path=tmp_path / "preferences.json",
        log_path=tmp_path / "logs" / "launcher.log",
        launch_mode=launcher.LAUNCH_MODE_NORMAL,
        command=("python.exe", "-m", "streamlit"),
        shutdown_port=54321,
        shutdown_token="secret",
    )

    class FakeProcess:
        pid = 999

    result = launcher.run_launcher_lifecycle(
        config,
        popen=lambda *args, **kwargs: FakeProcess(),
        port_available_fn=lambda: True,
        health_check_fn=lambda: launcher.HealthCheckResult(True, "url", 1, "ok"),
        wait_for_close_fn=lambda mode, process: launcher.WindowCloseDetectionResult(
            False,
            False,
            False,
            "unsupported",
        ),
        shutdown_request_fn=lambda cfg: (_ for _ in ()).throw(
            AssertionError("shutdown should not run")
        ),
        termination_fn=lambda process: (_ for _ in ()).throw(
            AssertionError("termination should not run")
        ),
    )

    assert result.final_state == "monitoring_unavailable"
    assert result.shutdown_request.attempted is False
