"""Development launch helpers for optional browser shell modes."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
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
EDGE_DEBUG_FLAG = "edge-debug"
WEBAPP_DEBUG_FLAG = "webapp-debug"
EXTERNAL_WEBAPP_LAUNCH_ENV = "LOREFORGE_EXTERNAL_WEBAPP_LAUNCH"
DEFAULT_STREAMLIT_LOCAL_URL = "http://localhost:8501"
RECOMMENDED_V1_LAUNCH_COMMAND = "streamlit run app.py"
WEBAPP_EXPERIMENTAL_MESSAGE = (
    "The dev-only webapp flag attempts to open Microsoft Edge app mode when "
    "available. Streamlit may still open its normal browser window because "
    "that browser behavior is controlled before app.py runs."
)
WEBAPP_AUTOMATION_DEFERRED_MESSAGE = (
    "Automated cleanup of Streamlit's extra browser window is deferred for V1. "
    "Run LoreForge normally and use the browser's install-as-app or "
    "create-shortcut feature manually for the reliable V1 workflow."
)
RECOMMENDED_WEBAPP_STREAMLIT_COMMAND = (
    "trainer\\Scripts\\python.exe -m streamlit run app.py "
    "--server.headless true --server.port 8501 -- webapp"
)
WEBAPP_LAUNCH_STATUS_ALREADY_ATTEMPTED = "already_attempted"
WEBAPP_LAUNCH_STATUS_EXTERNAL = "external_orchestrated"
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
    edge_debug: bool = False


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


@dataclass(frozen=True)
class WebappLaunchGuidance:
    """User/developer guidance for suppressing Streamlit's normal browser launch."""

    webapp_requested: bool
    external_launcher: bool
    streamlit_headless: bool | None
    normal_browser_suppressed: bool
    warning: bool
    can_suppress_from_app: bool
    recommended_command: str
    message: str


@dataclass(frozen=True)
class EdgeProcessInfo:
    """Observe-only metadata for one Microsoft Edge process."""

    pid: int
    parent_pid: int | None
    command_line: str
    executable_path: str
    window_title: str


@dataclass(frozen=True)
class EdgeProcessSnapshot:
    """Observe-only Microsoft Edge process snapshot."""

    processes: tuple[EdgeProcessInfo, ...]
    error: str = ""


@dataclass(frozen=True)
class EdgeProcessDiff:
    """Observe-only diff between two Edge process snapshots."""

    before_pids: tuple[int, ...]
    after_pids: tuple[int, ...]
    new_pids: tuple[int, ...]
    new_processes: tuple[EdgeProcessInfo, ...]
    distinguishability_note: str


def parse_launch_flags(argv: Sequence[str] | None = None) -> LaunchFlags:
    """Parse LoreForge runtime launch flags from command-line arguments."""

    args = tuple(sys.argv[1:] if argv is None else argv)
    return LaunchFlags(
        webapp=WEBAPP_FLAG in args,
        edge_debug=EDGE_DEBUG_FLAG in args or WEBAPP_DEBUG_FLAG in args,
    )


def get_streamlit_local_url(env: dict[str, str] | None = None) -> str:
    """Return the local URL used for dev web-app launch tests."""

    env_values = os.environ if env is None else env
    return env_values.get("LOREFORGE_STREAMLIT_URL", DEFAULT_STREAMLIT_LOCAL_URL).strip() or (
        DEFAULT_STREAMLIT_LOCAL_URL
    )


def is_external_webapp_launcher(env: dict[str, str] | None = None) -> bool:
    """Return whether an outer dev launcher is responsible for opening Edge."""

    env_values = os.environ if env is None else env
    return env_values.get(EXTERNAL_WEBAPP_LAUNCH_ENV, "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def build_edge_webapp_command(edge_path: Path | str, url: str) -> tuple[str, ...]:
    """Build the Microsoft Edge app-mode command without executing it."""

    return (str(edge_path), f"--app={url}")


def should_attempt_webapp_launch(
    flags: LaunchFlags,
    *,
    already_attempted: bool,
    external_launcher: bool = False,
) -> bool:
    """Return whether this caller should ask the process-level launcher to run."""

    return flags.webapp and not already_attempted and not external_launcher


def get_webapp_launch_guidance(
    flags: LaunchFlags,
    *,
    streamlit_headless: bool | None,
    external_launcher: bool = False,
) -> WebappLaunchGuidance:
    """Return dev guidance for Streamlit's command/config-controlled browser open."""

    if not flags.webapp:
        return WebappLaunchGuidance(
            webapp_requested=False,
            external_launcher=external_launcher,
            streamlit_headless=streamlit_headless,
            normal_browser_suppressed=False,
            warning=False,
            can_suppress_from_app=False,
            recommended_command=RECOMMENDED_V1_LAUNCH_COMMAND,
            message="Web-app launch mode is not active.",
        )

    if external_launcher:
        normal_browser_suppressed = streamlit_headless is True
        return WebappLaunchGuidance(
            webapp_requested=True,
            external_launcher=True,
            streamlit_headless=streamlit_headless,
            normal_browser_suppressed=normal_browser_suppressed,
            warning=True,
            can_suppress_from_app=False,
            recommended_command=RECOMMENDED_V1_LAUNCH_COMMAND,
            message=(
                "External dev launcher mode is experimental and deferred. "
                f"{WEBAPP_AUTOMATION_DEFERRED_MESSAGE}"
            )
            if normal_browser_suppressed
            else (
                "External dev launcher mode is experimental and deferred, and "
                "Streamlit headless mode was not confirmed. "
                f"{WEBAPP_AUTOMATION_DEFERRED_MESSAGE}"
            ),
        )

    if streamlit_headless is True:
        return WebappLaunchGuidance(
            webapp_requested=True,
            external_launcher=False,
            streamlit_headless=True,
            normal_browser_suppressed=True,
            warning=True,
            can_suppress_from_app=False,
            recommended_command=RECOMMENDED_V1_LAUNCH_COMMAND,
            message=(
                f"{WEBAPP_EXPERIMENTAL_MESSAGE} {WEBAPP_AUTOMATION_DEFERRED_MESSAGE}"
            ),
        )

    if streamlit_headless is False:
        return WebappLaunchGuidance(
            webapp_requested=True,
            external_launcher=False,
            streamlit_headless=False,
            normal_browser_suppressed=False,
            warning=True,
            can_suppress_from_app=False,
            recommended_command=RECOMMENDED_V1_LAUNCH_COMMAND,
            message=(
                f"{WEBAPP_EXPERIMENTAL_MESSAGE} {WEBAPP_AUTOMATION_DEFERRED_MESSAGE}"
            ),
        )

    return WebappLaunchGuidance(
        webapp_requested=True,
        external_launcher=False,
        streamlit_headless=None,
        normal_browser_suppressed=False,
        warning=True,
        can_suppress_from_app=False,
        recommended_command=RECOMMENDED_V1_LAUNCH_COMMAND,
        message=(
            f"LoreForge could not confirm Streamlit headless mode. {WEBAPP_EXPERIMENTAL_MESSAGE} "
            f"{WEBAPP_AUTOMATION_DEFERRED_MESSAGE}"
        ),
    )


def capture_edge_process_snapshot(
    *,
    system_name: str | None = None,
    run_fn: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> EdgeProcessSnapshot:
    """Capture observe-only Microsoft Edge process metadata on Windows."""

    target_system = system_name or detect_browser_capabilities().platform.raw_system
    if target_system.lower() != "windows":
        return EdgeProcessSnapshot(
            processes=(),
            error="Edge process observation is Windows-only.",
        )

    script = r"""
$titles = @{}
Get-Process msedge -ErrorAction SilentlyContinue | ForEach-Object {
    $titles[[int]$_.Id] = [string]$_.MainWindowTitle
}
Get-CimInstance Win32_Process -Filter "name='msedge.exe'" -ErrorAction SilentlyContinue | ForEach-Object {
    [PSCustomObject]@{
        pid = [int]$_.ProcessId
        parent_pid = [int]$_.ParentProcessId
        command_line = [string]$_.CommandLine
        executable_path = [string]$_.ExecutablePath
        window_title = [string]$titles[[int]$_.ProcessId]
    }
} | ConvertTo-Json -Compress
"""
    try:
        result = run_fn(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception as exc:
        return EdgeProcessSnapshot(processes=(), error=f"Edge observation failed: {exc}")

    if result.returncode != 0:
        message = (result.stderr or result.stdout or "").strip()
        return EdgeProcessSnapshot(
            processes=(),
            error=f"Edge observation command failed: {message}".strip(),
        )

    payload = (result.stdout or "").strip()
    if not payload:
        return EdgeProcessSnapshot(processes=())

    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError as exc:
        return EdgeProcessSnapshot(
            processes=(),
            error=f"Edge observation returned unreadable JSON: {exc}",
        )

    records = parsed if isinstance(parsed, list) else [parsed]
    processes: list[EdgeProcessInfo] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        try:
            pid = int(record.get("pid", 0))
        except (TypeError, ValueError):
            continue
        if pid <= 0:
            continue
        parent_pid = _coerce_optional_int(record.get("parent_pid"))
        processes.append(
            EdgeProcessInfo(
                pid=pid,
                parent_pid=parent_pid,
                command_line=str(record.get("command_line") or ""),
                executable_path=str(record.get("executable_path") or ""),
                window_title=str(record.get("window_title") or ""),
            )
        )

    return EdgeProcessSnapshot(processes=tuple(sorted(processes, key=lambda item: item.pid)))


def diff_edge_process_snapshots(
    before: EdgeProcessSnapshot,
    after: EdgeProcessSnapshot,
) -> EdgeProcessDiff:
    """Return observe-only PID differences between Edge snapshots."""

    before_pids = tuple(sorted(process.pid for process in before.processes))
    after_pids = tuple(sorted(process.pid for process in after.processes))
    before_set = set(before_pids)
    new_processes = tuple(
        process for process in after.processes if process.pid not in before_set
    )
    new_pids = tuple(process.pid for process in new_processes)
    distinguishability_note = _describe_edge_process_distinguishability(new_processes)
    return EdgeProcessDiff(
        before_pids=before_pids,
        after_pids=after_pids,
        new_pids=new_pids,
        new_processes=new_processes,
        distinguishability_note=distinguishability_note,
    )


def _coerce_optional_int(value: object) -> int | None:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _describe_edge_process_distinguishability(
    processes: tuple[EdgeProcessInfo, ...],
) -> str:
    if not processes:
        return "No new Edge processes were observed."

    app_mode = [
        process
        for process in processes
        if "--app=" in process.command_line.lower()
    ]
    local_url = [
        process
        for process in processes
        if DEFAULT_STREAMLIT_LOCAL_URL in process.command_line
        and "--app=" not in process.command_line.lower()
    ]
    titled = [process for process in processes if process.window_title.strip()]

    notes: list[str] = []
    if app_mode:
        notes.append(f"{len(app_mode)} app-mode candidate(s) include --app in the command line.")
    if local_url:
        notes.append(
            f"{len(local_url)} normal-browser candidate(s) reference the local Streamlit URL."
        )
    if titled:
        notes.append(f"{len(titled)} new process(es) exposed a visible window title.")
    if not notes:
        notes.append(
            "New Edge processes were observed, but app-mode and normal browser windows "
            "were not clearly distinguishable from process metadata alone."
        )
    return " ".join(notes)


def build_external_webapp_launch_status(
    flags: LaunchFlags,
    *,
    url: str | None = None,
) -> EdgeWebappLaunchStatus | None:
    """Return a diagnostic status when an outer launcher owns Edge startup."""

    if not flags.webapp:
        return None
    target_url = url or get_streamlit_local_url()
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
            "External dev launcher mode is experimental and deferred. LoreForge skipped "
            "in-app Edge launch; use the normal browser workflow for V1."
        ),
        status_code=WEBAPP_LAUNCH_STATUS_EXTERNAL,
    )


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
