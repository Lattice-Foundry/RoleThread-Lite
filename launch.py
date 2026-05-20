"""Source/dev launcher for RoleThread Lite.

Runtime ownership is delegated to LitLaunch. This wrapper exists only to keep
the source checkout command convenient while the packaged launcher catches up.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import sys
from typing import Callable, Sequence

from litlaunch import BrowserChoice, LauncherConfig, LaunchMode, StreamlitLauncher
from litlaunch.console import ConsoleMode, ConsoleRenderer, ConsoleTheme
from litlaunch.platforms import PlatformDetector
from litlaunch.windowing import (
    NoopWindowMonitor,
    WindowMonitorConfig,
    WindowMonitorStatus,
    WindowTarget,
    create_window_monitor,
)

from core.litlaunch_adapter import (
    ROLETHREAD_LITLAUNCH_GRACEFUL_TIMEOUT_SECONDS,
    ROLETHREAD_LITLAUNCH_HOST,
    ROLETHREAD_LITLAUNCH_PORT,
    ROLETHREAD_LITLAUNCH_TITLE,
    ROLETHREAD_LITLAUNCH_WEBAPP_MODE,
    ROLETHREAD_LITLAUNCH_WINDOW_APPEAR_TIMEOUT_SECONDS,
    ROLETHREAD_LITLAUNCH_WINDOW_POLL_SECONDS,
    ROLETHREAD_LITLAUNCH_WINDOW_STABLE_POLLS,
    build_source_webapp_launcher,
    resolve_rolethread_root,
)


LAUNCH_MODE_NORMAL = "browser"
LAUNCH_MODE_WEBAPP = ROLETHREAD_LITLAUNCH_WEBAPP_MODE


@dataclass(frozen=True)
class LaunchOptions:
    """Command-line options for the source launcher."""

    launch_mode: str
    debug: bool = False


def parse_launch_args(argv: Sequence[str] | None = None) -> LaunchOptions:
    """Parse source launcher arguments."""

    parser = argparse.ArgumentParser(
        description="Start RoleThread Lite through LitLaunch."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--webapp",
        dest="launch_mode",
        action="store_const",
        const=LAUNCH_MODE_WEBAPP,
        help="Start Streamlit headless and open a LitLaunch-managed app window.",
    )
    mode.add_argument(
        "--browser",
        dest="launch_mode",
        action="store_const",
        const=LAUNCH_MODE_NORMAL,
        help="Start RoleThread in the normal browser workflow.",
    )
    parser.add_argument(
        "--debug",
        "--diag",
        dest="debug",
        action="store_true",
        help="Print LitLaunch runtime diagnostics before startup.",
    )
    namespace = parser.parse_args(argv)
    return LaunchOptions(
        launch_mode=namespace.launch_mode or LAUNCH_MODE_NORMAL,
        debug=bool(namespace.debug),
    )


def build_browser_launcher(
    *,
    console_renderer: ConsoleRenderer | None = None,
) -> StreamlitLauncher:
    """Build the LitLaunch normal-browser source launcher."""

    config = LauncherConfig(
        app_path="app.py",
        title=ROLETHREAD_LITLAUNCH_TITLE,
        mode=LaunchMode.BROWSER,
        browser=BrowserChoice.AUTO,
        host=ROLETHREAD_LITLAUNCH_HOST,
        port=ROLETHREAD_LITLAUNCH_PORT,
        auto_port=False,
        cwd=resolve_rolethread_root(),
        app_args=(),
    )
    return StreamlitLauncher(config, console_renderer=console_renderer)


def build_litlaunch_launcher(
    options: LaunchOptions,
    *,
    console_renderer: ConsoleRenderer | None = None,
) -> StreamlitLauncher:
    """Build the LitLaunch launcher for the selected source mode."""

    if options.launch_mode == LAUNCH_MODE_WEBAPP:
        return build_source_webapp_launcher(console_renderer=console_renderer)
    return build_browser_launcher(console_renderer=console_renderer)


def run(
    argv: Sequence[str] | None = None,
    *,
    launcher_builder: Callable[..., StreamlitLauncher] = build_litlaunch_launcher,
    platform_detector_factory: Callable[[], PlatformDetector] = PlatformDetector,
    window_monitor_factory: Callable[..., object] = create_window_monitor,
) -> int:
    """Run RoleThread through LitLaunch."""

    options = parse_launch_args(argv)
    renderer = _build_console_renderer(debug=options.debug)
    try:
        launcher = launcher_builder(options, console_renderer=renderer)
        if options.debug:
            plan = launcher.build_launch_plan()
            renderer.info(f"Launch command: {plan.command_display}")
            renderer.info(f"App URL: {plan.app_url}")

        monitor_plan = None
        if options.launch_mode == LAUNCH_MODE_WEBAPP:
            monitor_plan = _prepare_window_monitor(
                platform_detector_factory=platform_detector_factory,
                window_monitor_factory=window_monitor_factory,
                renderer=renderer,
            )
            if monitor_plan is None:
                return 1

        session = launcher.run()
        if not session.ok:
            return 1

        if options.launch_mode == LAUNCH_MODE_WEBAPP:
            monitor, baseline_handles = monitor_plan
            return _monitor_webapp_session(
                session,
                monitor=monitor,
                baseline_handles=baseline_handles,
                renderer=renderer,
            )

        try:
            return int(session.wait() or 0)
        except KeyboardInterrupt:
            renderer.warning("Interrupt received; stopping runtime.")
            session.stop(
                graceful_timeout_seconds=ROLETHREAD_LITLAUNCH_GRACEFUL_TIMEOUT_SECONDS
            )
            return 0
    except Exception as exc:
        print(f"RoleThread launch failed: {exc}", file=sys.stderr)
        return 1


def _build_console_renderer(*, debug: bool) -> ConsoleRenderer:
    mode = ConsoleMode.VERBOSE if debug else ConsoleMode.NORMAL
    return ConsoleRenderer(mode=mode, theme=ConsoleTheme())


def _prepare_window_monitor(
    *,
    platform_detector_factory: Callable[[], PlatformDetector],
    window_monitor_factory: Callable[..., object],
    renderer: ConsoleRenderer,
) -> tuple[object, tuple[str, ...]] | None:
    platform_info = platform_detector_factory().detect()
    monitor = window_monitor_factory(platform_info)
    if isinstance(monitor, NoopWindowMonitor):
        renderer.failure_guidance(
            "Window monitoring is unavailable.",
            likely_cause="This platform does not support LitLaunch window monitoring.",
            next_steps=("Use --browser for normal browser launch.",),
        )
        return None

    try:
        baseline = monitor.capture(
            WindowTarget(ROLETHREAD_LITLAUNCH_TITLE, app_mode=True)
        )
    except Exception as exc:
        renderer.failure_guidance(
            "Window monitoring baseline capture failed.",
            likely_cause=str(exc),
            next_steps=("Use --browser for normal browser launch.",),
        )
        return None
    return monitor, tuple(window.handle for window in baseline)


def _monitor_webapp_session(
    session,
    *,
    monitor: object,
    baseline_handles: tuple[str, ...],
    renderer: ConsoleRenderer,
) -> int:
    target = WindowTarget(
        ROLETHREAD_LITLAUNCH_TITLE,
        url=session.url,
        browser_kind=getattr(session.browser, "kind", None),
        app_mode=True,
        baseline_handles=baseline_handles,
    )
    result = session.monitor_window(
        monitor,
        target,
        config=WindowMonitorConfig(
            appear_timeout_seconds=ROLETHREAD_LITLAUNCH_WINDOW_APPEAR_TIMEOUT_SECONDS,
            poll_interval_seconds=ROLETHREAD_LITLAUNCH_WINDOW_POLL_SECONDS,
            stable_poll_count=ROLETHREAD_LITLAUNCH_WINDOW_STABLE_POLLS,
        ),
        graceful_timeout_seconds=ROLETHREAD_LITLAUNCH_GRACEFUL_TIMEOUT_SECONDS,
    )
    if result.closed or result.status == WindowMonitorStatus.BACKEND_EXITED:
        return 0

    session.stop(graceful_timeout_seconds=ROLETHREAD_LITLAUNCH_GRACEFUL_TIMEOUT_SECONDS)
    renderer.render_window_monitor_result(result)
    return 1


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint."""

    return run(argv)


if __name__ == "__main__":
    raise SystemExit(main())
