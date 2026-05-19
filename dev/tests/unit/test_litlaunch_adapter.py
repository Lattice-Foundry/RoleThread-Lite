import sys
from pathlib import Path

from litlaunch import BrowserChoice, LaunchMode

from core.litlaunch_adapter import (
    ROLETHREAD_LITLAUNCH_BROWSER,
    ROLETHREAD_LITLAUNCH_HOST,
    ROLETHREAD_LITLAUNCH_PORT,
    ROLETHREAD_LITLAUNCH_TITLE,
    build_source_webapp_command_preview,
    build_source_webapp_config,
)


def test_source_webapp_litlaunch_config_matches_rolethread_contract():
    config = build_source_webapp_config()

    assert config.app_path == Path("app.py")
    assert config.title == ROLETHREAD_LITLAUNCH_TITLE == "RoleThread Lite"
    assert config.mode == LaunchMode.WEBAPP
    assert config.browser == BrowserChoice.EDGE
    assert config.host == ROLETHREAD_LITLAUNCH_HOST == "127.0.0.1"
    assert config.port == ROLETHREAD_LITLAUNCH_PORT == 8501
    assert config.auto_port is False
    assert config.headless is True
    assert config.allow_browser_fallback is False
    assert config.app_args == ()


def test_source_webapp_litlaunch_command_preview_is_headless_loopback():
    command = build_source_webapp_command_preview()

    assert command[:5] == (
        sys.executable,
        "-m",
        "streamlit",
        "run",
        "app.py",
    )
    assert command[command.index("--server.address") + 1] == "127.0.0.1"
    assert command[command.index("--server.headless") + 1] == "true"
    assert command[command.index("--server.port") + 1] == "8501"


def test_source_webapp_litlaunch_command_preview_has_no_app_webapp_arg():
    command = build_source_webapp_command_preview()

    assert "--" not in command
    assert "webapp" not in command


def test_source_webapp_litlaunch_config_accepts_explicit_app_path(tmp_path):
    app_path = tmp_path / "app.py"

    config = build_source_webapp_config(app_path=app_path)

    assert config.app_path == app_path
    assert config.browser.value == ROLETHREAD_LITLAUNCH_BROWSER
