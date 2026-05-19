"""Thin RoleThread-to-LitLaunch launch configuration helpers.

This module is preparation scaffolding only. It describes the intended
LitLaunch source webapp configuration without replacing the current launcher
lifecycle yet.
"""

from __future__ import annotations

from pathlib import Path

from litlaunch import LauncherConfig, StreamlitLauncher


ROLETHREAD_LITLAUNCH_TITLE = "RoleThread Lite"
ROLETHREAD_LITLAUNCH_HOST = "127.0.0.1"
ROLETHREAD_LITLAUNCH_PORT = 8501
ROLETHREAD_LITLAUNCH_BROWSER = "edge"
ROLETHREAD_LITLAUNCH_WEBAPP_MODE = "webapp"


def build_source_webapp_config(
    *,
    app_path: str | Path = "app.py",
) -> LauncherConfig:
    """Build the future LitLaunch config for source ``launch.py --webapp`` runs."""

    return LauncherConfig(
        app_path=app_path,
        title=ROLETHREAD_LITLAUNCH_TITLE,
        mode=ROLETHREAD_LITLAUNCH_WEBAPP_MODE,
        browser=ROLETHREAD_LITLAUNCH_BROWSER,
        host=ROLETHREAD_LITLAUNCH_HOST,
        port=ROLETHREAD_LITLAUNCH_PORT,
        auto_port=False,
        headless=True,
        allow_browser_fallback=False,
        app_args=(),
    )


def build_source_webapp_command_preview(
    *,
    app_path: str | Path = "app.py",
) -> tuple[str, ...]:
    """Build the LitLaunch Streamlit command preview without launching anything."""

    launcher = StreamlitLauncher(build_source_webapp_config(app_path=app_path))
    return launcher.build_command()
