from pathlib import Path
import sys

from litlaunch import BrowserChoice, LaunchMode, StreamlitLauncher, TrustMode
from packaging.requirements import Requirement
from packaging.version import Version

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
    assert config.trust_mode == TrustMode.STRICT_LOCAL
    assert config.host == "127.0.0.1"
    assert config.port == 8501
    assert config.auto_port is False
    assert config.headless is True
    assert config.allow_browser_fallback is False
    assert config.cwd == resolve_rolethread_root()
    assert config.app_args == ()
    assert config.extra_env == {}
    assert config.runtime_event_log == (
        resolve_rolethread_root() / ".litlaunch" / "runtime-events.log"
    )
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
    assert config.trust_mode == TrustMode.STRICT_LOCAL
    assert config.host == "127.0.0.1"
    assert config.port == 8501
    assert config.auto_port is False
    assert config.allow_browser_fallback is True
    assert config.extra_env == {}
    assert config.runtime_event_log == (
        resolve_rolethread_root() / ".litlaunch" / "runtime-events.log"
    )


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


def test_requirements_do_not_pin_litlaunch_before_pypi_release():
    requirements = resolve_rolethread_root().joinpath("requirements.txt").read_text(
        encoding="utf-8"
    )

    assert "litlaunch==" not in requirements


def test_requirements_keep_streamlit_on_tested_v1_line():
    requirements = resolve_rolethread_root().joinpath("requirements.txt").read_text(
        encoding="utf-8"
    )
    streamlit_requirement = _requirement_for(requirements, "streamlit")

    specifier = streamlit_requirement.specifier
    assert Version("1.57.0") in specifier
    assert Version("1.56.9") not in specifier
    assert Version("1.58.0") not in specifier


def test_requirements_keep_direct_dependencies_on_tested_v1_lines():
    requirements = resolve_rolethread_root().joinpath("requirements.txt").read_text(
        encoding="utf-8"
    )
    expected_lines = {
        "pandas": ("3.0.3", "3.0.2", "3.1.0"),
        "plotly": ("6.7.0", "6.6.9", "6.8.0"),
        "sqlalchemy": ("2.0.49", "2.0.48", "2.1.0"),
    }

    for (
        package_name,
        (tested_floor, previous_version, next_minor),
    ) in expected_lines.items():
        specifier = _requirement_for(requirements, package_name).specifier
        assert Version(tested_floor) in specifier
        assert Version(previous_version) not in specifier
        assert Version(next_minor) not in specifier


def _requirement_for(requirements: str, package_name: str) -> Requirement:
    return next(
        Requirement(line)
        for line in requirements.splitlines()
        if line.lower().startswith(package_name.lower())
    )
