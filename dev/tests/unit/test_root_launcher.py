from types import SimpleNamespace

from litlaunch import BrowserChoice, LaunchMode
from litlaunch.windowing import WindowInfo, WindowMonitorResult, WindowMonitorStatus

import launch as root_launcher
from core.launcher_console import (
    ANSI_CLOUD_GOLD,
    ANSI_MINT,
    ANSI_STREAMLIT_BLUE,
    format_launcher_status,
    strip_ansi,
    terminal_supports_ansi,
)
from core.litlaunch_adapter import ROLETHREAD_LITLAUNCH_TITLE, resolve_rolethread_root


def test_parse_launch_args_defaults_to_browser_mode():
    options = root_launcher.parse_launch_args([])

    assert options.launch_mode == root_launcher.LAUNCH_MODE_NORMAL
    assert options.debug is False


def test_parse_launch_args_supports_webapp_and_debug():
    options = root_launcher.parse_launch_args(["--webapp", "--debug"])

    assert options.launch_mode == root_launcher.LAUNCH_MODE_WEBAPP
    assert options.debug is True


def test_parse_launch_args_supports_diag_alias_for_launcher_debug():
    options = root_launcher.parse_launch_args(["--webapp", "--diag"])

    assert options.launch_mode == root_launcher.LAUNCH_MODE_WEBAPP
    assert options.debug is True


def test_browser_launcher_uses_litlaunch_source_config():
    launcher = root_launcher.build_browser_launcher()
    config = launcher.config

    assert config.app_path.name == "app.py"
    assert config.title == ROLETHREAD_LITLAUNCH_TITLE
    assert config.mode == LaunchMode.BROWSER
    assert config.browser == BrowserChoice.AUTO
    assert config.host == "127.0.0.1"
    assert config.port == 8501
    assert config.auto_port is False
    assert config.cwd == resolve_rolethread_root()
    assert config.app_args == ()


def test_webapp_run_uses_litlaunch_session_and_window_monitor():
    calls = []
    session = _FakeSession(
        monitor_result=WindowMonitorResult(
            supported=True,
            observed=True,
            closed=True,
            status=WindowMonitorStatus.WINDOW_CLOSED,
            message="closed",
        )
    )

    def build_launcher(options, *, console_renderer=None):
        calls.append(("builder", options.launch_mode, console_renderer is not None))
        return _FakeLauncher(session)

    exit_code = root_launcher.run(
        ["--webapp"],
        launcher_builder=build_launcher,
        platform_detector_factory=_FakePlatformDetector,
        window_monitor_factory=lambda platform: _FakeMonitor(calls),
    )

    assert exit_code == 0
    assert calls[:3] == [
        ("builder", root_launcher.LAUNCH_MODE_WEBAPP, True),
        ("detect",),
        ("capture", ROLETHREAD_LITLAUNCH_TITLE),
    ]
    assert session.run_called is True
    assert session.monitor_called is True
    assert session.stopped is False


def test_webapp_run_stops_session_when_monitoring_fails():
    session = _FakeSession(
        monitor_result=WindowMonitorResult(
            supported=True,
            observed=False,
            closed=False,
            status=WindowMonitorStatus.TIMEOUT,
            message="timeout",
        )
    )

    exit_code = root_launcher.run(
        ["--webapp"],
        launcher_builder=lambda options, *, console_renderer=None: _FakeLauncher(
            session
        ),
        platform_detector_factory=_FakePlatformDetector,
        window_monitor_factory=lambda platform: _FakeMonitor([]),
    )

    assert exit_code == 1
    assert session.stopped is True


def test_browser_run_waits_on_litlaunch_session():
    session = _FakeSession(wait_result=0)

    exit_code = root_launcher.run(
        ["--browser"],
        launcher_builder=lambda options, *, console_renderer=None: _FakeLauncher(
            session
        ),
    )

    assert exit_code == 0
    assert session.wait_called is True
    assert session.monitor_called is False


class _FakeLauncher:
    def __init__(self, session):
        self.session = session

    def build_launch_plan(self):
        return SimpleNamespace(
            command_display="python -m streamlit run app.py",
            app_url="http://127.0.0.1:8501",
        )

    def run(self):
        self.session.run_called = True
        return self.session


class _FakeSession:
    ok = True
    url = "http://127.0.0.1:8501"
    browser = SimpleNamespace(kind=None)

    def __init__(self, *, monitor_result=None, wait_result=0):
        self.monitor_result = monitor_result
        self.wait_result = wait_result
        self.run_called = False
        self.monitor_called = False
        self.wait_called = False
        self.stopped = False

    def monitor_window(self, *args, **kwargs):
        self.monitor_called = True
        return self.monitor_result

    def wait(self):
        self.wait_called = True
        return self.wait_result

    def stop(self, **kwargs):
        self.stopped = True


class _FakePlatformDetector:
    def detect(self):
        return SimpleNamespace(platform="windows")


class _FakeMonitor:
    def __init__(self, calls):
        self.calls = calls

    def capture(self, target):
        self.calls.append(("detect",))
        self.calls.append(("capture", target.title))
        return (WindowInfo(handle="0x100", title=target.title),)


def test_launcher_status_formatting_keeps_plain_text_without_color():
    formatted = format_launcher_status("Streamlit health: endpoint responded.", color=False)

    assert formatted == "[RoleThread Launcher] Streamlit health: endpoint responded."


def test_launcher_status_formatting_colors_prefix_and_lifecycle_label():
    formatted = format_launcher_status("Streamlit health: endpoint responded.", color=True)

    assert ANSI_MINT in formatted
    assert ANSI_STREAMLIT_BLUE in formatted
    assert strip_ansi(formatted) == "[RoleThread Launcher] Streamlit health: endpoint responded."


def test_launcher_status_formatting_colors_cloud_sync_labels_gold():
    formatted = format_launcher_status(
        "Cloud sync warning: staged sync timeout.",
        color=True,
    )

    assert ANSI_MINT in formatted
    assert ANSI_CLOUD_GOLD in formatted
    assert ANSI_STREAMLIT_BLUE not in formatted
    assert strip_ansi(formatted) == (
        "[RoleThread Launcher] Cloud sync warning: staged sync timeout."
    )


def test_launcher_status_formatting_does_not_color_non_label_message_body():
    formatted = format_launcher_status("Monitoring app window for close.", color=True)

    assert ANSI_MINT in formatted
    assert ANSI_STREAMLIT_BLUE not in formatted
    assert strip_ansi(formatted) == "[RoleThread Launcher] Monitoring app window for close."


def test_terminal_supports_ansi_honors_no_color_and_force_color():
    class NonTty:
        def isatty(self):
            return False

    assert terminal_supports_ansi(stream=NonTty(), env={"FORCE_COLOR": "1"}) is True
    assert terminal_supports_ansi(stream=NonTty(), env={"NO_COLOR": "1"}) is False
    assert terminal_supports_ansi(stream=NonTty(), env={}) is False
