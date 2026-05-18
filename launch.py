"""Canonical source/dev launcher for RoleThread Lite.

This entrypoint builds a source checkout configuration and delegates to the
same launcher-owned lifecycle used by the packaged Windows adapter.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Callable, Sequence

from core.launcher_console import format_launcher_status
from installer.windows.launcher import rolethread_launcher as launcher


@dataclass(frozen=True)
class LaunchOptions:
    """Command-line options for the canonical source launcher."""

    launch_mode: str
    debug: bool = False


def parse_launch_args(argv: Sequence[str] | None = None) -> LaunchOptions:
    """Parse root launcher arguments."""

    parser = argparse.ArgumentParser(
        description="Start RoleThread Lite through the canonical launcher lifecycle."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--webapp",
        dest="launch_mode",
        action="store_const",
        const=launcher.LAUNCH_MODE_WEBAPP,
        help="Start Streamlit headless and open the managed Edge webapp window.",
    )
    mode.add_argument(
        "--browser",
        dest="launch_mode",
        action="store_const",
        const=launcher.LAUNCH_MODE_NORMAL,
        help="Start RoleThread in the normal Streamlit browser workflow.",
    )
    parser.add_argument(
        "--debug",
        "--diag",
        dest="debug",
        action="store_true",
        help="Print launcher command details and lifecycle diagnostics before startup.",
    )
    namespace = parser.parse_args(argv)
    return LaunchOptions(
        launch_mode=namespace.launch_mode or launcher.LAUNCH_MODE_NORMAL,
        debug=bool(namespace.debug),
    )


def resolve_source_app_root() -> Path:
    """Return the source checkout root that contains app.py."""

    return Path(__file__).resolve().parent


def build_manual_launcher_config(
    options: LaunchOptions,
    *,
    app_root: Path | None = None,
    env: dict[str, str] | None = None,
    current_executable: str | None = None,
    shutdown_port: int | None = None,
    shutdown_token: str | None = None,
) -> launcher.LauncherConfig:
    """Build a launcher config for source runs without installer preferences."""

    resolved_root = launcher.validate_app_root(app_root or resolve_source_app_root())
    python_path = launcher.resolve_python_runtime(
        resolved_root,
        current_executable=current_executable or sys.executable,
        frozen=False,
    )
    command = launcher.build_streamlit_command(
        python_path,
        launch_mode=options.launch_mode,
        app_root=resolved_root,
        frozen=False,
    )
    return launcher.LauncherConfig(
        app_root=resolved_root,
        python_path=python_path,
        preferences_path=launcher.resolve_preferences_path(env),
        log_path=launcher.resolve_launcher_log_path(env),
        launch_mode=options.launch_mode,
        command=command,
        bundled_mode=False,
        shutdown_port=shutdown_port or launcher.find_available_local_port(),
        shutdown_token=shutdown_token or launcher.generate_shutdown_token(),
    )


def run(
    argv: Sequence[str] | None = None,
    *,
    config_builder: Callable[[LaunchOptions], launcher.LauncherConfig]
    | None = None,
    lifecycle_fn: Callable[..., object] = launcher.run_launcher_lifecycle,
) -> int:
    """Run RoleThread through the canonical source launcher."""

    options = parse_launch_args(argv)
    try:
        status_callback = (
            _print_launcher_status
            if options.debug or options.launch_mode == launcher.LAUNCH_MODE_WEBAPP
            else None
        )
        if options.debug:
            _print_launcher_status("Building launcher configuration.")
        builder = config_builder or build_manual_launcher_config
        config = builder(options)
        if options.debug:
            _print_launcher_status(f"Launch mode: {config.launch_mode}")
            if config.launch_mode == launcher.LAUNCH_MODE_WEBAPP:
                _print_launcher_status("Managed webapp mode: Streamlit will start headless.")
            _print_launcher_status(f"Command: {launcher.format_command(config.command)}")
        if status_callback:
            lifecycle_fn(config, status_callback=status_callback)
        else:
            lifecycle_fn(config)
        return 0
    except Exception as exc:
        print(f"RoleThread launch failed: {exc}", file=sys.stderr)
        return 1


def _print_launcher_status(message: str) -> None:
    print(format_launcher_status(message))


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint."""

    return run(argv)


if __name__ == "__main__":
    raise SystemExit(main())
