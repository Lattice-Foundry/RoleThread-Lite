from pathlib import Path
import sys

from litlaunch import BrowserChoice, LaunchMode, StreamlitLauncher

from core.runtime_profiles import (
    ROLETHREAD_APP_TITLE,
    ROLETHREAD_BROWSER_PROFILE,
    ROLETHREAD_WEBAPP_PROFILE,
    load_rolethread_profile,
    resolve_rolethread_root,
    rolethread_profile_path,
)


def test_webapp_profile_matches_rolethread_contract():
    profile = load_rolethread_profile()
    config = profile.config

    assert config.app_path == resolve_rolethread_root() / "app.py"
    assert config.title == ROLETHREAD_APP_TITLE == "RoleThread Lite"
    assert config.mode == LaunchMode.WEBAPP
    assert config.browser == BrowserChoice.EDGE
    assert config.host == "127.0.0.1"
    assert config.port == 8501
    assert config.auto_port is False
    assert config.headless is True
    assert config.allow_browser_fallback is False
    assert config.cwd == resolve_rolethread_root()
    assert config.app_args == ()
    assert profile.graceful_timeout_seconds == 15
    assert profile.window_monitor_config.appear_timeout_seconds == 60
    assert profile.window_monitor_config.poll_interval_seconds == 1
    assert profile.window_monitor_config.stable_poll_count == 2


def test_browser_profile_is_plain_browser_mode():
    profile = load_rolethread_profile(ROLETHREAD_BROWSER_PROFILE)
    config = profile.config

    assert config.title == ROLETHREAD_APP_TITLE
    assert config.mode == LaunchMode.BROWSER
    assert config.browser == BrowserChoice.AUTO
    assert config.host == "127.0.0.1"
    assert config.port == 8501
    assert config.auto_port is False
    assert config.allow_browser_fallback is True


def test_rolethread_profile_path_resolves_project_config():
    assert rolethread_profile_path() == resolve_rolethread_root() / "litlaunch.toml"


def test_source_webapp_launch_plan_is_headless_loopback():
    profile = load_rolethread_profile(ROLETHREAD_WEBAPP_PROFILE)
    plan = StreamlitLauncher(profile.config).build_launch_plan(
        include_browser_resolution=False
    )

    assert plan.command[:5] == (
        sys.executable,
        "-m",
        "streamlit",
        "run",
            str(resolve_rolethread_root() / "app.py"),
    )
    assert plan.app_url == "http://127.0.0.1:8501"
    assert plan.health_url == "http://127.0.0.1:8501/_stcore/health"
    assert plan.resolved_port == 8501
    command = plan.command
    assert command[command.index("--server.address") + 1] == "127.0.0.1"
    assert command[command.index("--server.headless") + 1] == "true"
    assert command[command.index("--server.port") + 1] == "8501"
    assert "webapp" not in command


def test_requirements_pin_current_litlaunch_beta():
    requirements = resolve_rolethread_root().joinpath("requirements.txt").read_text(
        encoding="utf-8"
    )

    assert "litlaunch==0.91.0b0" in requirements
