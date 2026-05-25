from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from litlaunch import BrowserChoice, LaunchMode, MonitoredRunResult, RuntimeEvent
from litlaunch.windowing import WindowMonitorResult, WindowMonitorStatus

from core.product_log import PRODUCT_LOG_PATH_ENV
from core.runtime_profiles import ROLETHREAD_APP_TITLE
from core.runtime_shutdown import ROLETHREAD_SHUTDOWN_DIAGNOSTICS_ENV
from installer.windows.launcher import rolethread_launcher as launcher


def _make_app_root(tmp_path: Path) -> Path:
    app_root = tmp_path / "app"
    app_root.mkdir()
    (app_root / "app.py").write_text("print('RoleThread')", encoding="utf-8")
    (app_root / "litlaunch.toml").write_text(
        """
[profiles.rolethread-webapp]
app_path = "app.py"
cwd = "."
title = "RoleThread Lite"
mode = "webapp"
browser = "edge"
trust_mode = "strict_local"
host = "127.0.0.1"
port = 8501
auto_port = false
headless = true
allow_browser_fallback = false
graceful_timeout = 15

[profiles.rolethread-webapp.window_monitor]
enabled = true
appear_timeout = 60
poll_interval = 1
stable_polls = 2
""".strip(),
        encoding="utf-8",
    )
    return app_root


def test_build_launcher_config_resolves_packaged_product_paths(tmp_path):
    app_root = _make_app_root(tmp_path)
    launcher_exe = tmp_path / "RoleThreadLauncher.exe"
    launcher_exe.write_text("", encoding="utf-8")

    config = launcher.build_launcher_config(
        app_root=app_root,
        env={"LOCALAPPDATA": str(tmp_path / "local")},
        current_executable=str(launcher_exe),
        frozen=True,
        diagnostics_enabled=True,
    )

    assert config.app_root == app_root.resolve()
    assert config.launcher_executable == launcher_exe
    assert config.bundled_mode is True
    assert config.diagnostics_enabled is True
    assert config.preferences_path == tmp_path / "local" / "RoleThread" / "preferences.json"
    assert config.log_path == tmp_path / "local" / "RoleThread" / "logs" / "launcher.log"


def test_litlaunch_config_preserves_rolethread_packaged_contract(tmp_path):
    config = launcher.PackagedLauncherConfig(
        app_root=_make_app_root(tmp_path),
        launcher_executable=tmp_path / "RoleThreadLauncher.exe",
        preferences_path=tmp_path / "preferences.json",
        log_path=tmp_path / "launcher.log",
        bundled_mode=True,
        diagnostics_enabled=True,
    )

    litlaunch_config = launcher.build_litlaunch_config(config)

    assert litlaunch_config.title == ROLETHREAD_APP_TITLE
    assert litlaunch_config.mode == LaunchMode.WEBAPP
    assert litlaunch_config.browser == BrowserChoice.EDGE
    assert litlaunch_config.host == "127.0.0.1"
    assert litlaunch_config.port == 8501
    assert litlaunch_config.auto_port is False
    assert litlaunch_config.headless is True
    assert litlaunch_config.allow_browser_fallback is False
    assert litlaunch_config.cwd == config.app_root
    assert litlaunch_config.app_args == ()
    assert litlaunch_config.runtime_event_log is None
    assert litlaunch_config.extra_env[PRODUCT_LOG_PATH_ENV] == str(config.log_path)
    assert litlaunch_config.extra_env[ROLETHREAD_SHUTDOWN_DIAGNOSTICS_ENV] == "1"


def test_packaged_backend_provider_builds_internal_streamlit_command(tmp_path):
    app_root = _make_app_root(tmp_path)
    launcher_exe = tmp_path / "RoleThreadLauncher.exe"
    provider = launcher.PackagedRoleThreadBackendProvider(
        launcher_executable=launcher_exe,
        app_root=app_root,
    )
    context = SimpleNamespace(
        host="127.0.0.1",
        port=8501,
        headless=True,
    )

    command = provider.build_backend_command(context).command

    assert command == (
        str(launcher_exe),
        launcher.INTERNAL_STREAMLIT_FLAG,
        str(app_root.resolve() / "app.py"),
        "--global.developmentMode=false",
        "--server.address",
        "127.0.0.1",
        "--server.headless",
        "true",
        "--server.port",
        "8501",
    )
    assert "-- webapp" not in " ".join(command)


def test_packaged_launch_plan_uses_backend_provider(tmp_path):
    app_root = _make_app_root(tmp_path)
    launcher_exe = tmp_path / "RoleThreadLauncher.exe"
    launcher_exe.write_text("", encoding="utf-8")
    config = launcher.PackagedLauncherConfig(
        app_root=app_root,
        launcher_executable=launcher_exe,
        preferences_path=tmp_path / "preferences.json",
        log_path=tmp_path / "launcher.log",
        bundled_mode=True,
    )

    plan = launcher.build_launch_plan(config)

    assert plan.backend_kind == "rolethread-packaged"
    assert plan.cwd == app_root.resolve()
    assert plan.app_url == "http://127.0.0.1:8501"
    assert plan.health_url == "http://127.0.0.1:8501/_stcore/health"
    assert plan.command[:2] == (str(launcher_exe), launcher.INTERNAL_STREAMLIT_FLAG)
    assert "webapp" not in plan.command


def test_packaged_launcher_wires_litlaunch_runtime_events_to_product_log(tmp_path):
    config = launcher.PackagedLauncherConfig(
        app_root=_make_app_root(tmp_path),
        launcher_executable=tmp_path / "RoleThreadLauncher.exe",
        preferences_path=tmp_path / "preferences.json",
        log_path=tmp_path / "launcher.log",
        bundled_mode=True,
    )
    streamlit_launcher = launcher.build_streamlit_launcher(config)

    assert streamlit_launcher.event_sink is not None
    streamlit_launcher.event_sink(
        RuntimeEvent(
            name="browser_launched",
            category="browser",
            level="info",
            message="Browser launched.\nNewline ignored.",
            timestamp=datetime.now(UTC),
            details={
                "browser": "edge",
                "host": "127.0.0.1",
                "port": "8501",
                "url": "http://127.0.0.1:8501",
                "shutdown_token": "secret-token",
                "extra_env": "API_KEY=secret",
            },
        )
    )

    log_text = config.log_path.read_text(encoding="utf-8")
    assert "litlaunch_event level=info category=browser name=browser_launched" in log_text
    assert "message=Browser launched. Newline ignored." in log_text
    assert "browser=Edge" in log_text
    assert "host=127.0.0.1" in log_text
    assert "port=8501" in log_text
    assert "url=" not in log_text
    assert "shutdown_token" not in log_text
    assert "secret-token" not in log_text
    assert "API_KEY" not in log_text


def test_run_packaged_runtime_delegates_monitored_webapp_to_litlaunch(tmp_path):
    config = launcher.PackagedLauncherConfig(
        app_root=_make_app_root(tmp_path),
        launcher_executable=tmp_path / "RoleThreadLauncher.exe",
        preferences_path=tmp_path / "preferences.json",
        log_path=tmp_path / "launcher.log",
        bundled_mode=True,
    )
    monitor_result = WindowMonitorResult(
        supported=True,
        observed=True,
        closed=True,
        status=WindowMonitorStatus.WINDOW_CLOSED,
        message="closed",
    )
    calls = []

    def fake_runner(launcher_obj, **kwargs):
        calls.append((launcher_obj, kwargs))
        return MonitoredRunResult(
            exit_code=0,
            session=None,
            monitor_result=monitor_result,
            message="closed",
            launched=True,
            stopped_cleanly=True,
        )

    exit_code = launcher.run_packaged_runtime(
        config,
        launcher_factory=lambda cfg, *, console_renderer=None: _FakeLauncher(),
        monitored_runner=fake_runner,
    )

    assert exit_code == 0
    assert len(calls) == 1
    assert calls[0][1]["graceful_timeout_seconds"] == 15
    assert calls[0][1]["window_monitor_config"].appear_timeout_seconds == 60
    log_text = config.log_path.read_text(encoding="utf-8")
    assert "backend_kind=rolethread-packaged" in log_text
    assert "monitor_status=window_closed" in log_text
    assert "app_url=" not in log_text


def test_run_packaged_runtime_returns_litlaunch_failure_code(tmp_path):
    config = launcher.PackagedLauncherConfig(
        app_root=_make_app_root(tmp_path),
        launcher_executable=tmp_path / "RoleThreadLauncher.exe",
        preferences_path=tmp_path / "preferences.json",
        log_path=tmp_path / "launcher.log",
        bundled_mode=True,
    )
    monitor_result = WindowMonitorResult(
        supported=True,
        observed=False,
        closed=False,
        status=WindowMonitorStatus.TIMEOUT,
        message="timeout",
    )

    def fake_runner(launcher_obj, **kwargs):
        return MonitoredRunResult(
            exit_code=1,
            session=None,
            monitor_result=monitor_result,
            message="timeout",
            launched=True,
            stopped_cleanly=True,
        )

    exit_code = launcher.run_packaged_runtime(
        config,
        launcher_factory=lambda cfg, *, console_renderer=None: _FakeLauncher(),
        monitored_runner=fake_runner,
    )

    assert exit_code == 1
    assert "monitor_status=timeout" in config.log_path.read_text(encoding="utf-8")


def test_build_launcher_config_errors_when_app_root_has_no_app_py(tmp_path):
    with pytest.raises(launcher.LauncherConfigurationError):
        launcher.build_launcher_config(app_root=tmp_path / "missing")


def test_run_bundled_streamlit_rewrites_argv(monkeypatch, tmp_path):
    app_root = _make_app_root(tmp_path)
    calls = []

    monkeypatch.setitem(
        __import__("sys").modules,
        "streamlit.web.cli",
        SimpleNamespace(main=lambda: calls.append(tuple(__import__("sys").argv))),
    )

    result = launcher.run_bundled_streamlit(
        [str(app_root / "app.py"), "--server.port", "8501"]
    )

    assert result == 0
    assert calls == [
        (
            "streamlit",
            "run",
            str((app_root / "app.py").resolve()),
            "--server.port",
            "8501",
        )
    ]


def test_windowed_launcher_handles_missing_stdout(monkeypatch):
    monkeypatch.setattr(launcher.sys, "stdout", None)

    launcher._safe_print("hello")
    renderer = launcher._build_console_renderer()
    renderer.info("hello")


def test_pyinstaller_spec_uses_windowed_no_console_mode():
    spec_path = Path(__file__).parents[3] / "installer" / "windows" / "rolethread_launcher.spec"
    spec_text = spec_path.read_text(encoding="utf-8")

    assert "console=False" in spec_text
    assert "console=True" not in spec_text


def test_pyinstaller_spec_packages_litlaunch_runtime():
    spec_path = Path(__file__).parents[3] / "installer" / "windows" / "rolethread_launcher.spec"
    spec_text = spec_path.read_text(encoding="utf-8")

    assert '"litlaunch"' in spec_text
    assert "rolethread_launcher.py" in spec_text
    assert "litlaunch.toml" in spec_text


class _FakeLauncher:
    def build_launch_plan(self):
        return SimpleNamespace(
            backend_kind="rolethread-packaged",
            cwd="X:/rolethread",
            command_display="RoleThreadLauncher.exe --rolethread-run-streamlit app.py",
            command=("RoleThreadLauncher.exe", "--rolethread-run-streamlit", "app.py"),
            app_url="http://127.0.0.1:8501",
        )
