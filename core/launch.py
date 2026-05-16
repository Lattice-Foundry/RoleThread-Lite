"""Development launch helpers for optional browser shell modes."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import subprocess
import sys
from typing import Callable, Sequence

from core.platform import (
    BrowserDetectionResult,
    OS_WINDOWS,
    detect_browser_capabilities,
)


WEBAPP_FLAG = "webapp"
DEFAULT_STREAMLIT_LOCAL_URL = "http://localhost:8501"
WEBAPP_LAUNCH_STATUS_ALREADY_ATTEMPTED = "already_attempted"
WEBAPP_LAUNCH_STATUS_FAILED = "failed"
WEBAPP_LAUNCH_STATUS_FALLBACK = "fallback"
WEBAPP_LAUNCH_STATUS_LAUNCHED = "launched"
WEBAPP_LAUNCH_STATUS_NOT_REQUESTED = "not_requested"

_webapp_launch_attempted = False
_webapp_launch_status: "EdgeWebappLaunchStatus | None" = None


@dataclass(frozen=True)
class LaunchFlags:
    """Runtime flags passed after Streamlit's app arguments separator."""

    webapp: bool = False


@dataclass(frozen=True)
class EdgeWebappLaunchStatus:
    """Result of the dev-only Edge web-app launch attempt."""

    webapp_requested: bool
    edge_available: bool
    attempted: bool
    launched: bool
    fallback_used: bool
    url: str
    edge_path: Path | None
    command: tuple[str, ...]
    message: str
    status_code: str


def parse_launch_flags(argv: Sequence[str] | None = None) -> LaunchFlags:
    """Parse LoreForge runtime launch flags from command-line arguments."""

    args = tuple(sys.argv[1:] if argv is None else argv)
    return LaunchFlags(webapp=WEBAPP_FLAG in args)


def get_streamlit_local_url(env: dict[str, str] | None = None) -> str:
    """Return the local URL used for dev web-app launch tests."""

    env_values = os.environ if env is None else env
    return env_values.get("LOREFORGE_STREAMLIT_URL", DEFAULT_STREAMLIT_LOCAL_URL).strip() or (
        DEFAULT_STREAMLIT_LOCAL_URL
    )


def build_edge_webapp_command(edge_path: Path | str, url: str) -> tuple[str, ...]:
    """Build the Microsoft Edge app-mode command without executing it."""

    return (str(edge_path), f"--app={url}")


def should_attempt_webapp_launch(flags: LaunchFlags, *, already_attempted: bool) -> bool:
    """Return whether this caller should ask the process-level launcher to run."""

    return flags.webapp and not already_attempted


def reset_webapp_launch_guard_for_tests() -> None:
    """Reset the process-level launch guard for deterministic unit tests."""

    global _webapp_launch_attempted, _webapp_launch_status
    _webapp_launch_attempted = False
    _webapp_launch_status = None


def get_webapp_launch_status() -> EdgeWebappLaunchStatus | None:
    """Return the last process-level web-app launch status, if any."""

    return _webapp_launch_status


def attempt_webapp_launch(
    flags: LaunchFlags,
    *,
    url: str | None = None,
    browser_detection: BrowserDetectionResult | None = None,
    popen_fn: Callable[..., object] = subprocess.Popen,
) -> EdgeWebappLaunchStatus:
    """Attempt the dev-only Edge web-app launch, returning a nonfatal status."""

    global _webapp_launch_attempted, _webapp_launch_status

    target_url = url or get_streamlit_local_url()
    if not flags.webapp:
        return EdgeWebappLaunchStatus(
            webapp_requested=False,
            edge_available=False,
            attempted=False,
            launched=False,
            fallback_used=False,
            url=target_url,
            edge_path=None,
            command=(),
            message="Web-app launch flag was not requested.",
            status_code=WEBAPP_LAUNCH_STATUS_NOT_REQUESTED,
        )

    if _webapp_launch_attempted:
        if _webapp_launch_status is not None:
            return EdgeWebappLaunchStatus(
                webapp_requested=True,
                edge_available=_webapp_launch_status.edge_available,
                attempted=False,
                launched=False,
                fallback_used=_webapp_launch_status.fallback_used,
                url=_webapp_launch_status.url,
                edge_path=_webapp_launch_status.edge_path,
                command=_webapp_launch_status.command,
                message=(
                    "Dev web-app launch was already attempted for this Python process; "
                    "skipping this rerun."
                ),
                status_code=WEBAPP_LAUNCH_STATUS_ALREADY_ATTEMPTED,
            )
        return EdgeWebappLaunchStatus(
            webapp_requested=True,
            edge_available=False,
            attempted=False,
            launched=False,
            fallback_used=False,
            url=target_url,
            edge_path=None,
            command=(),
            message=(
                "Dev web-app launch was already attempted for this Python process; "
                "skipping this rerun."
            ),
            status_code=WEBAPP_LAUNCH_STATUS_ALREADY_ATTEMPTED,
        )

    _webapp_launch_attempted = True

    detection = browser_detection or detect_browser_capabilities()
    platform_info = detection.platform
    edge_path = detection.browser.edge_path
    edge_available = detection.capabilities.edge_webapp_available and edge_path is not None

    if platform_info.os_name != OS_WINDOWS:
        _webapp_launch_status = EdgeWebappLaunchStatus(
            webapp_requested=True,
            edge_available=False,
            attempted=False,
            launched=False,
            fallback_used=True,
            url=target_url,
            edge_path=edge_path,
            command=(),
            message=(
                "Dev web-app mode is currently Windows/Microsoft Edge only. "
                "LoreForge will continue in the normal Streamlit browser flow."
            ),
            status_code=WEBAPP_LAUNCH_STATUS_FALLBACK,
        )
        return _webapp_launch_status

    if not edge_available:
        _webapp_launch_status = EdgeWebappLaunchStatus(
            webapp_requested=True,
            edge_available=False,
            attempted=False,
            launched=False,
            fallback_used=True,
            url=target_url,
            edge_path=edge_path,
            command=(),
            message=(
                "Dev web-app mode was requested, but Microsoft Edge was not detected. "
                "LoreForge will continue in the normal Streamlit browser flow."
            ),
            status_code=WEBAPP_LAUNCH_STATUS_FALLBACK,
        )
        return _webapp_launch_status

    command = build_edge_webapp_command(edge_path, target_url)
    try:
        popen_fn(command)
    except Exception as exc:
        _webapp_launch_status = EdgeWebappLaunchStatus(
            webapp_requested=True,
            edge_available=True,
            attempted=True,
            launched=False,
            fallback_used=True,
            url=target_url,
            edge_path=edge_path,
            command=command,
            message=(
                "Dev web-app mode was requested, but Edge launch failed. "
                f"LoreForge will continue normally. Error: {exc}"
            ),
            status_code=WEBAPP_LAUNCH_STATUS_FAILED,
        )
        return _webapp_launch_status

    _webapp_launch_status = EdgeWebappLaunchStatus(
        webapp_requested=True,
        edge_available=True,
        attempted=True,
        launched=True,
        fallback_used=False,
        url=target_url,
        edge_path=edge_path,
        command=command,
        message="Dev web-app mode requested; Microsoft Edge app window launch was attempted.",
        status_code=WEBAPP_LAUNCH_STATUS_LAUNCHED,
    )
    return _webapp_launch_status
