from pathlib import Path
from types import SimpleNamespace

import pytest
from litlaunch import BrowserChoice, LaunchMode
from litlaunch.windowing import WindowInfo, WindowMonitorResult, WindowMonitorStatus

from core.launcher_log import LAUNCHER_LOG_PATH_ENV
from core.litlaunch_adapter import ROLETHREAD_LITLAUNCH_TITLE
from core.litlaunch_shutdown_bridge import ROLETHREAD_SHUTDOWN_DIAGNOSTICS_ENV
from installer.windows.launcher import rolethread_launcher as launcher


def _make_app_root(tmp_path: Path) -> Path:
    app_root = tmp_path / "app"
    app_root.mkdir()
    (app_root / "app.py").write_text("print('RoleThread')", encoding="utf-8")
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

    assert litlaunch_config.title == ROLETHREAD_LITLAUNCH_TITLE
    assert litlaunch_config.mode == LaunchMode.WEBAPP
    assert litlaunch_config.browser == BrowserChoice.EDGE
    assert litlaunch_config.host == "127.0.0.1"
    assert litlaunch_config.port == 8501
    assert litlaunch_config.auto_port is False
    assert litlaunch_config.headless is True
    assert litlaunch_config.allow_browser_fallback is False
    assert litlaunch_config.cwd == config.app_root
    assert litlaunch_config.app_args == ()
    assert litlaunch_config.extra_env[LAUNCHER_LOG_PATH_ENV] == str(config.log_path)
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


def test_run_packaged_litlaunch_uses_litlaunch_session_and_monitor(tmp_path):
    config = launcher.PackagedLauncherConfig(
        app_root=_make_app_root(tmp_path),
        launcher_executable=tmp_path / "RoleThreadLauncher.exe",
        preferences_path=tmp_path / "preferences.json",
        log_path=tmp_path / "launcher.log",
        bundled_mode=True,
    )
    session = _FakeSession(
        monitor_result=WindowMonitorResult(
            supported=True,
            observed=True,
            closed=True,
            status=WindowMonitorStatus.WINDOW_CLOSED,
            message="closed",
        )
    )
    calls = []

    exit_code = launcher.run_packaged_litlaunch(
        config,
        launcher_factory=lambda cfg, *, console_renderer=None: _FakeLauncher(session),
        platform_detector_factory=_FakePlatformDetector,
        window_monitor_factory=lambda platform: _FakeMonitor(calls),
    )

    assert exit_code == 0
    assert session.run_called is True
    assert session.monitor_called is True
    assert session.stopped is False
    assert calls == [("capture", ROLETHREAD_LITLAUNCH_TITLE)]
    assert "backend_kind=rolethread-packaged" in config.log_path.read_text(
        encoding="utf-8"
    )


def test_run_packaged_litlaunch_stops_backend_when_monitor_fails(tmp_path):
    config = launcher.PackagedLauncherConfig(
        app_root=_make_app_root(tmp_path),
        launcher_executable=tmp_path / "RoleThreadLauncher.exe",
        preferences_path=tmp_path / "preferences.json",
        log_path=tmp_path / "launcher.log",
        bundled_mode=True,
    )
    session = _FakeSession(
        monitor_result=WindowMonitorResult(
            supported=True,
            observed=False,
            closed=False,
            status=WindowMonitorStatus.TIMEOUT,
            message="timeout",
        )
    )

    exit_code = launcher.run_packaged_litlaunch(
        config,
        launcher_factory=lambda cfg, *, console_renderer=None: _FakeLauncher(session),
        platform_detector_factory=_FakePlatformDetector,
        window_monitor_factory=lambda platform: _FakeMonitor([]),
    )

    assert exit_code == 1
    assert session.stopped is True


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

    result = launcher.run_bundled_streamlit([str(app_root / "app.py"), "--server.port", "8501"])

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


class _FakeLauncher:
    def __init__(self, session):
        self.session = session

    def build_launch_plan(self):
        return SimpleNamespace(
            backend_kind="rolethread-packaged",
            app_root="X:/rolethread",
            app_version="test",
            bundled_mode=True,
            preferences_path="preferences.json",
            command_display="RoleThreadLauncher.exe --rolethread-run-streamlit app.py",
            app_url="http://127.0.0.1:8501",
        )

    def run(self):
        self.session.run_called = True
        return self.session


class _FakeSession:
    ok = True
    url = "http://127.0.0.1:8501"
    browser = SimpleNamespace(kind=None)

    def __init__(self, *, monitor_result):
        self.monitor_result = monitor_result
        self.run_called = False
        self.monitor_called = False
        self.stopped = False

    def monitor_window(self, *args, **kwargs):
        self.monitor_called = True
        return self.monitor_result

    def stop(self, **kwargs):
        self.stopped = True


class _FakePlatformDetector:
    def detect(self):
        return SimpleNamespace(platform="windows")


class _FakeMonitor:
    def __init__(self, calls):
        self.calls = calls

    def capture(self, target):
        self.calls.append(("capture", target.title))
        return (WindowInfo(handle="0x100", title=target.title),)
