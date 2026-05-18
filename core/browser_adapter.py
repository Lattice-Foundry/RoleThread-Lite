"""Browser adapter boundary for launcher-owned webapp windows.

The lifecycle core asks an adapter to open a managed app window; browser
discovery, launch flags, and version diagnostics stay inside the adapter.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from core.edge_version_history import record_installed_edge_version
from core.platform import BrowserDetectionResult, detect_browser_capabilities


DEFAULT_BROWSER_ADAPTER_ID = "edge"


@dataclass(frozen=True)
class BrowserLaunchResult:
    """Result from asking a browser adapter to open a managed app window."""

    attempted: bool
    launched: bool
    command: tuple[str, ...]
    message: str
    adapter_id: str = DEFAULT_BROWSER_ADAPTER_ID


def get_default_browser_adapter_id() -> str:
    """Return the default managed-webapp browser adapter id."""

    # Edge is the only implemented adapter today. Chrome/Chromium and non-
    # Windows adapters can be added here without changing lifecycle ordering.
    return DEFAULT_BROWSER_ADAPTER_ID


def build_edge_app_mode_command(edge_path: Path, url: str) -> tuple[str, ...]:
    """Build the Microsoft Edge app-mode command for one local webapp URL."""

    return (str(edge_path), f"--app={url}")


def launch_edge_app_mode(
    *,
    url: str,
    popen: Callable[..., object],
    browser_detection_fn: Callable[[], BrowserDetectionResult] = detect_browser_capabilities,
    edge_version_recorder: Callable[..., object] = record_installed_edge_version,
    source: str = "launcher",
) -> BrowserLaunchResult:
    """Launch Microsoft Edge app-mode as the first browser adapter implementation."""

    detection = browser_detection_fn()
    edge_path = detection.browser.edge_path
    if detection.platform.os_name != "windows" or edge_path is None:
        return BrowserLaunchResult(
            attempted=False,
            launched=False,
            command=(),
            message="Windows Microsoft Edge webapp launch is unavailable.",
        )
    edge_version_recorder(edge_path, source=source)

    command = build_edge_app_mode_command(edge_path, url)
    try:
        popen(command)
    except Exception as exc:
        return BrowserLaunchResult(
            attempted=True,
            launched=False,
            command=command,
            message=f"Edge webapp launch failed: {exc}",
        )

    return BrowserLaunchResult(
        attempted=True,
        launched=True,
        command=command,
        message="Edge webapp launch command was started.",
    )
