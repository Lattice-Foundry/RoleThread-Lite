"""Thin RoleThread-to-LitLaunch runtime configuration helpers."""

from __future__ import annotations

from pathlib import Path

from litlaunch import LauncherConfig, LaunchPlan, StreamlitLauncher


ROLETHREAD_LITLAUNCH_TITLE = "RoleThread Lite"
ROLETHREAD_LITLAUNCH_HOST = "127.0.0.1"
ROLETHREAD_LITLAUNCH_PORT = 8501
ROLETHREAD_LITLAUNCH_BROWSER = "edge"
ROLETHREAD_LITLAUNCH_WEBAPP_MODE = "webapp"
ROLETHREAD_LITLAUNCH_GRACEFUL_TIMEOUT_SECONDS = 15.0
ROLETHREAD_LITLAUNCH_WINDOW_APPEAR_TIMEOUT_SECONDS = 60.0
ROLETHREAD_LITLAUNCH_WINDOW_POLL_SECONDS = 1.0
ROLETHREAD_LITLAUNCH_WINDOW_STABLE_POLLS = 2


def resolve_rolethread_root() -> Path:
    """Return the active RoleThread checkout root."""

    return Path(__file__).resolve().parents[1]


def build_source_webapp_config(
    *,
    app_path: str | Path = "app.py",
    app_root: str | Path | None = None,
    extra_env: dict[str, str] | None = None,
) -> LauncherConfig:
    """Build the LitLaunch config for source ``launch.py --webapp`` runs."""

    resolved_root = (
        Path(app_root).resolve() if app_root is not None else resolve_rolethread_root()
    )

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
        cwd=resolved_root,
        extra_env=extra_env or {},
        app_args=(),
    )


def build_source_webapp_launcher(
    *,
    app_path: str | Path = "app.py",
    app_root: str | Path | None = None,
    extra_env: dict[str, str] | None = None,
    console_renderer=None,
) -> StreamlitLauncher:
    """Build the LitLaunch source webapp launcher without starting it."""

    config = build_source_webapp_config(
        app_path=app_path,
        app_root=app_root,
        extra_env=extra_env,
    )
    return StreamlitLauncher(config, console_renderer=console_renderer)


def build_source_webapp_launch_plan(
    *,
    app_path: str | Path = "app.py",
    app_root: str | Path | None = None,
    extra_env: dict[str, str] | None = None,
    include_browser_resolution: bool = True,
) -> LaunchPlan:
    """Build a LitLaunch launch plan without starting backend or browser."""

    return build_source_webapp_launcher(
        app_path=app_path,
        app_root=app_root,
        extra_env=extra_env,
    ).build_launch_plan(include_browser_resolution=include_browser_resolution)


def build_source_webapp_command_preview(
    *,
    app_path: str | Path = "app.py",
    app_root: str | Path | None = None,
    extra_env: dict[str, str] | None = None,
) -> tuple[str, ...]:
    """Build the LitLaunch backend command preview without launching anything."""

    return build_source_webapp_launch_plan(
        app_path=app_path,
        app_root=app_root,
        extra_env=extra_env,
        include_browser_resolution=False,
    ).command
