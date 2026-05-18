from pathlib import Path
from types import SimpleNamespace

from core.browser_adapter import (
    DEFAULT_BROWSER_ADAPTER_ID,
    build_edge_app_mode_command,
    get_default_browser_adapter_id,
    launch_edge_app_mode,
)


def _browser_detection(*, os_name="windows", edge_path=None):
    return SimpleNamespace(
        platform=SimpleNamespace(os_name=os_name),
        browser=SimpleNamespace(edge_path=edge_path),
    )


def test_default_browser_adapter_is_edge_for_now():
    assert get_default_browser_adapter_id() == DEFAULT_BROWSER_ADAPTER_ID == "edge"


def test_edge_adapter_builds_app_mode_command():
    edge_path = Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe")

    assert build_edge_app_mode_command(edge_path, "http://127.0.0.1:8501") == (
        str(edge_path),
        "--app=http://127.0.0.1:8501",
    )


def test_edge_adapter_launches_detected_edge_and_records_version():
    edge_path = Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe")
    commands = []
    records = []

    result = launch_edge_app_mode(
        url="http://127.0.0.1:8501",
        popen=lambda command: commands.append(tuple(command)),
        browser_detection_fn=lambda: _browser_detection(edge_path=edge_path),
        edge_version_recorder=lambda path, source: records.append((path, source)),
        source="launcher-test",
    )

    assert result.attempted is True
    assert result.launched is True
    assert result.adapter_id == "edge"
    assert result.command == (str(edge_path), "--app=http://127.0.0.1:8501")
    assert commands == [result.command]
    assert records == [(edge_path, "launcher-test")]


def test_edge_adapter_skips_when_edge_is_unavailable():
    result = launch_edge_app_mode(
        url="http://127.0.0.1:8501",
        popen=lambda command: (_ for _ in ()).throw(
            AssertionError("should not launch without Edge")
        ),
        browser_detection_fn=lambda: _browser_detection(edge_path=None),
        edge_version_recorder=lambda path, source: None,
    )

    assert result.attempted is False
    assert result.launched is False
    assert result.command == ()
    assert "unavailable" in result.message


def test_edge_adapter_skips_on_non_windows_platform():
    edge_path = Path("/usr/bin/msedge")

    result = launch_edge_app_mode(
        url="http://127.0.0.1:8501",
        popen=lambda command: (_ for _ in ()).throw(
            AssertionError("should not launch on unsupported platform")
        ),
        browser_detection_fn=lambda: _browser_detection(os_name="linux", edge_path=edge_path),
        edge_version_recorder=lambda path, source: None,
    )

    assert result.attempted is False
    assert result.launched is False


def test_edge_adapter_reports_launch_failure():
    edge_path = Path("C:/Edge/msedge.exe")

    result = launch_edge_app_mode(
        url="http://127.0.0.1:8501",
        popen=lambda command: (_ for _ in ()).throw(RuntimeError("boom")),
        browser_detection_fn=lambda: _browser_detection(edge_path=edge_path),
        edge_version_recorder=lambda path, source: None,
    )

    assert result.attempted is True
    assert result.launched is False
    assert result.command == (str(edge_path), "--app=http://127.0.0.1:8501")
    assert "boom" in result.message
