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
DEV_FLAG = "dev"
EDGE_DEBUG_FLAG = "edge-debug"
WEBAPP_DEBUG_FLAG = "webapp-debug"
EXTERNAL_WEBAPP_LAUNCH_ENV = "ROLETHREAD_EXTERNAL_WEBAPP_LAUNCH"
DEFAULT_STREAMLIT_LOCAL_URL = "http://localhost:8501"
RECOMMENDED_V1_LAUNCH_COMMAND = "streamlit run app.py"
WEBAPP_EXPERIMENTAL_MESSAGE = (
    "The webapp flag opens Microsoft Edge app mode when available. Streamlit "
    "may still open its normal browser window before app.py runs; RoleThread "
    "then closes the duplicate browser window when Windows metadata identifies "
    "a safe exact window target."
)
WEBAPP_AUTOMATION_DEFERRED_MESSAGE = (
    "Future installer and shortcut workflows will call this internal launch "
    "method. Manual browser install-as-app remains the reliable fallback."
)
RECOMMENDED_WEBAPP_STREAMLIT_COMMAND = (
    ".venv\\Scripts\\python.exe -m streamlit run app.py "
    "--server.headless true --server.port 8501 -- webapp"
)
EDGE_CLASSIFICATION_APP = "app_window_candidate"
EDGE_CLASSIFICATION_BROWSER = "browser_window_candidate"
EDGE_CLASSIFICATION_UNCERTAIN = "uncertain"
EDGE_CONFIDENCE_INSUFFICIENT = "insufficient_evidence"
EDGE_CONFIDENCE_LIKELY = "likely_distinguishable"
EDGE_CONFIDENCE_PARTIAL = "partially_distinguishable"
EDGE_CONFIDENCE_UNRELIABLE = "unreliable"
EDGE_CLEANUP_METHOD_CLOSE_MAIN_WINDOW = "close_main_window"
EDGE_CLEANUP_METHOD_STOP_PROCESS_EXACT_PID = "stop_process_exact_pid"
EDGE_CLEANUP_METHOD_CLOSE_WINDOW_HANDLE = "close_window_handle"
EDGE_CLEANUP_STATUS_ATTEMPTED = "attempted"
EDGE_CLEANUP_STATUS_SKIPPED = "skipped"
WEBAPP_LAUNCH_STATUS_ALREADY_ATTEMPTED = "already_attempted"
WEBAPP_LAUNCH_STATUS_EXTERNAL = "external_orchestrated"
WEBAPP_LAUNCH_STATUS_FAILED = "failed"
WEBAPP_LAUNCH_STATUS_FALLBACK = "fallback"
WEBAPP_LAUNCH_STATUS_LAUNCHED = "launched"
WEBAPP_LAUNCH_STATUS_NOT_REQUESTED = "not_requested"
WEBAPP_UNSUPPORTED_PLATFORM_MESSAGE = (
    "RoleThread webapp mode is only supported on Windows with Microsoft Edge. "
    "Continuing in normal browser mode."
)

_webapp_launch_attempted = False
_webapp_launch_status: "EdgeWebappLaunchStatus | None" = None


@dataclass(frozen=True)
class LaunchFlags:
    """Runtime flags passed after Streamlit's app arguments separator."""

    dev: bool = False
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
    creation_time: str = ""


@dataclass(frozen=True)
class EdgeProcessClassification:
    """Observe-only app/browser classification for one Edge process."""

    pid: int
    classification: str
    confidence: str
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class EdgeProcessSnapshot:
    """Observe-only Microsoft Edge process snapshot."""

    processes: tuple[EdgeProcessInfo, ...]
    error: str = ""


@dataclass(frozen=True)
class EdgeWindowInfo:
    """Observe-only metadata for one visible Microsoft Edge top-level window."""

    handle: str
    pid: int
    process_name: str
    title: str
    class_name: str
    command_line: str = ""


@dataclass(frozen=True)
class EdgeWindowSnapshot:
    """Observe-only Microsoft Edge top-level window snapshot."""

    windows: tuple[EdgeWindowInfo, ...]
    error: str = ""


@dataclass(frozen=True)
class EdgeWindowDiff:
    """Observe-only diff between Edge top-level window snapshots."""

    before_handles: tuple[str, ...]
    after_handles: tuple[str, ...]
    new_handles: tuple[str, ...]
    before_windows: tuple[EdgeWindowInfo, ...]
    after_windows: tuple[EdgeWindowInfo, ...]
    new_windows: tuple[EdgeWindowInfo, ...]
    note: str


@dataclass(frozen=True)
class EdgeProcessDiff:
    """Observe-only diff between two Edge process snapshots."""

    before_pids: tuple[int, ...]
    after_pids: tuple[int, ...]
    new_pids: tuple[int, ...]
    new_processes: tuple[EdgeProcessInfo, ...]
    classifications: tuple[EdgeProcessClassification, ...]
    confidence_level: str
    distinguishability_note: str
    process_order_note: str


@dataclass(frozen=True)
class EdgeDuplicateCleanupStatus:
    """Result of the experimental duplicate browser close attempt."""

    cleanup_requested: bool
    attempted: bool
    skipped: bool
    target_pid: int | None
    target_title: str
    method: str
    result: str
    message: str
    status_code: str
    decision_details: tuple[str, ...] = ()


@dataclass(frozen=True)
class EdgeSnapshotPollResult:
    """Merged after-launch Edge observation snapshots."""

    snapshot: EdgeProcessSnapshot
    attempts: int
    delay_seconds: float
    error: str = ""


def parse_launch_flags(argv: Sequence[str] | None = None) -> LaunchFlags:
    """Parse RoleThread runtime launch flags from command-line arguments."""

    args = tuple(sys.argv[1:] if argv is None else argv)
    return LaunchFlags(
        dev=DEV_FLAG in args,
        webapp=WEBAPP_FLAG in args,
        edge_debug=EDGE_DEBUG_FLAG in args or WEBAPP_DEBUG_FLAG in args,
    )


def should_show_dev_diagnostics(flags: LaunchFlags) -> bool:
    """Return whether raw/internal diagnostics should be visible in the UI."""

    return flags.dev


def get_streamlit_local_url(env: dict[str, str] | None = None) -> str:
    """Return the local URL used for dev web-app launch tests."""

    env_values = os.environ if env is None else env
    return env_values.get("ROLETHREAD_STREAMLIT_URL", DEFAULT_STREAMLIT_LOCAL_URL).strip() or (
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


def supports_managed_webapp_launch(
    browser_detection: BrowserDetectionResult,
) -> bool:
    """Return whether RoleThread should run managed Edge webapp launch work."""

    return (
        browser_detection.platform.os_name == OS_WINDOWS
        and browser_detection.platform.capabilities.supports_edge_webapp
    )


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
            f"RoleThread could not confirm Streamlit headless mode. {WEBAPP_EXPERIMENTAL_MESSAGE} "
            f"{WEBAPP_AUTOMATION_DEFERRED_MESSAGE}"
        ),
    )


def capture_edge_process_snapshot(
    *,
    system_name: str | None = None,
    run_fn: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> EdgeProcessSnapshot:
    """Capture observe-only Microsoft Edge process metadata on Windows."""

    target_system = system_name or detect_browser_capabilities().platform.diagnostics.raw_system
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
        creation_time = [string]$_.CreationDate
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
                creation_time=str(record.get("creation_time") or ""),
            )
        )

    return EdgeProcessSnapshot(processes=tuple(sorted(processes, key=lambda item: item.pid)))


def capture_edge_process_snapshot_poll(
    *,
    attempts: int = 5,
    delay_seconds: float = 0.35,
    sleep_fn: Callable[[float], object] | None = None,
    snapshot_fn: Callable[[], EdgeProcessSnapshot] | None = None,
) -> EdgeSnapshotPollResult:
    """Capture and merge several Edge snapshots to wait out Chromium metadata timing."""

    import time

    sleep = sleep_fn or time.sleep
    capture = snapshot_fn or capture_edge_process_snapshot
    merged: dict[int, EdgeProcessInfo] = {}
    errors: list[str] = []
    safe_attempts = max(1, attempts)

    for attempt in range(safe_attempts):
        snapshot = capture()
        if snapshot.error:
            errors.append(snapshot.error)
        for process in snapshot.processes:
            existing = merged.get(process.pid)
            merged[process.pid] = _merge_edge_process_info(existing, process)
        if attempt < safe_attempts - 1:
            sleep(delay_seconds)

    return EdgeSnapshotPollResult(
        snapshot=EdgeProcessSnapshot(
            processes=tuple(sorted(merged.values(), key=lambda item: item.pid)),
            error="; ".join(dict.fromkeys(errors)),
        ),
        attempts=safe_attempts,
        delay_seconds=delay_seconds,
        error="; ".join(dict.fromkeys(errors)),
    )


def capture_edge_window_snapshot(
    *,
    system_name: str | None = None,
    run_fn: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> EdgeWindowSnapshot:
    """Capture observe-only visible Microsoft Edge top-level window metadata."""

    target_system = system_name or detect_browser_capabilities().platform.diagnostics.raw_system
    if target_system.lower() != "windows":
        return EdgeWindowSnapshot(
            windows=(),
            error="Edge window observation is Windows-only.",
        )

    script = r"""
Add-Type @"
using System;
using System.Text;
using System.Runtime.InteropServices;
public class Win32WindowProbe {
    public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);
    [DllImport("user32.dll")]
    public static extern bool EnumWindows(EnumWindowsProc lpEnumFunc, IntPtr lParam);
    [DllImport("user32.dll")]
    public static extern bool IsWindowVisible(IntPtr hWnd);
    [DllImport("user32.dll", CharSet=CharSet.Unicode)]
    public static extern int GetWindowText(IntPtr hWnd, StringBuilder lpString, int nMaxCount);
    [DllImport("user32.dll", CharSet=CharSet.Unicode)]
    public static extern int GetClassName(IntPtr hWnd, StringBuilder lpClassName, int nMaxCount);
    [DllImport("user32.dll")]
    public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint lpdwProcessId);
}
"@

$processNames = @{}
$processCommands = @{}
Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | ForEach-Object {
    $processNames[[int]$_.ProcessId] = [string]$_.Name
    $processCommands[[int]$_.ProcessId] = [string]$_.CommandLine
}

$rows = New-Object System.Collections.Generic.List[object]
$callback = [Win32WindowProbe+EnumWindowsProc]{
    param([IntPtr]$hWnd, [IntPtr]$lParam)
    if (-not [Win32WindowProbe]::IsWindowVisible($hWnd)) { return $true }
    [uint32]$windowPid = 0
    [void][Win32WindowProbe]::GetWindowThreadProcessId($hWnd, [ref]$windowPid)

    $titleBuilder = New-Object System.Text.StringBuilder 512
    [void][Win32WindowProbe]::GetWindowText($hWnd, $titleBuilder, $titleBuilder.Capacity)
    $classBuilder = New-Object System.Text.StringBuilder 256
    [void][Win32WindowProbe]::GetClassName($hWnd, $classBuilder, $classBuilder.Capacity)

    $title = [string]$titleBuilder.ToString()
    $className = [string]$classBuilder.ToString()
    $processName = [string]$processNames[[int]$windowPid]
    $commandLine = [string]$processCommands[[int]$windowPid]
    $looksLikeEdge = $processName -ieq 'msedge.exe'
    $looksLikeRoleThread = $title -like '*RoleThread*'
    $looksLikeChromiumWindow = $className -like 'Chrome_WidgetWin*'

    if (-not ($looksLikeEdge -or $looksLikeRoleThread -or $looksLikeChromiumWindow)) {
        return $true
    }

    $rows.Add([PSCustomObject]@{
        handle = "0x{0:X}" -f $hWnd.ToInt64()
        pid = [int]$windowPid
        process_name = $processName
        title = $title
        class_name = $className
        command_line = $commandLine
    })
    return $true
}
[void][Win32WindowProbe]::EnumWindows($callback, [IntPtr]::Zero)
$rows | ConvertTo-Json -Compress
"""
    try:
        result = run_fn(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception as exc:
        return EdgeWindowSnapshot(windows=(), error=f"Edge window observation failed: {exc}")

    if result.returncode != 0:
        message = (result.stderr or result.stdout or "").strip()
        return EdgeWindowSnapshot(
            windows=(),
            error=f"Edge window observation command failed: {message}".strip(),
        )

    payload = (result.stdout or "").strip()
    if not payload:
        return EdgeWindowSnapshot(windows=())

    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError as exc:
        return EdgeWindowSnapshot(
            windows=(),
            error=f"Edge window observation returned unreadable JSON: {exc}",
        )

    records = parsed if isinstance(parsed, list) else [parsed]
    windows: list[EdgeWindowInfo] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        handle = str(record.get("handle") or "").strip()
        if not handle:
            continue
        try:
            pid = int(record.get("pid", 0))
        except (TypeError, ValueError):
            continue
        if pid <= 0:
            continue
        windows.append(
            EdgeWindowInfo(
                handle=handle,
                pid=pid,
                process_name=str(record.get("process_name") or ""),
                title=str(record.get("title") or ""),
                class_name=str(record.get("class_name") or ""),
                command_line=str(record.get("command_line") or ""),
            )
        )

    return EdgeWindowSnapshot(windows=tuple(sorted(windows, key=lambda item: item.handle)))


def diff_edge_window_snapshots(
    before: EdgeWindowSnapshot,
    after: EdgeWindowSnapshot,
) -> EdgeWindowDiff:
    """Diff Edge top-level windows to catch reused-process browser windows."""

    before_handles = tuple(window.handle for window in before.windows)
    after_handles = tuple(window.handle for window in after.windows)
    new_windows = tuple(
        window for window in after.windows if window.handle not in set(before_handles)
    )
    if new_windows:
        note = f"{len(new_windows)} new Edge top-level window(s) were observed."
    else:
        note = "No new Edge top-level windows were observed."
    if before.error or after.error:
        errors = "; ".join(part for part in (before.error, after.error) if part)
        note = f"{note} Observation note: {errors}"
    return EdgeWindowDiff(
        before_handles=before_handles,
        after_handles=after_handles,
        new_handles=tuple(window.handle for window in new_windows),
        before_windows=before.windows,
        after_windows=after.windows,
        new_windows=new_windows,
        note=note,
    )


def _merge_edge_process_info(
    existing: EdgeProcessInfo | None,
    current: EdgeProcessInfo,
) -> EdgeProcessInfo:
    if existing is None:
        return current
    return EdgeProcessInfo(
        pid=current.pid,
        parent_pid=current.parent_pid if current.parent_pid is not None else existing.parent_pid,
        command_line=current.command_line or existing.command_line,
        executable_path=current.executable_path or existing.executable_path,
        window_title=current.window_title or existing.window_title,
        creation_time=current.creation_time or existing.creation_time,
    )


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
    classifications = tuple(classify_edge_process(process) for process in new_processes)
    confidence_level = _resolve_edge_debug_confidence(classifications, new_processes)
    distinguishability_note = _describe_edge_process_distinguishability(classifications)
    process_order_note = _describe_edge_process_order(new_processes, classifications)
    return EdgeProcessDiff(
        before_pids=before_pids,
        after_pids=after_pids,
        new_pids=new_pids,
        new_processes=new_processes,
        classifications=classifications,
        confidence_level=confidence_level,
        distinguishability_note=distinguishability_note,
        process_order_note=process_order_note,
    )


def close_duplicate_edge_browser_window(
    flags: LaunchFlags,
    diff: EdgeProcessDiff,
    *,
    window_diff: EdgeWindowDiff | None = None,
    system_name: str | None = None,
    run_fn: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> EdgeDuplicateCleanupStatus:
    """Experimentally close only a newly observed duplicate Edge browser window."""

    if not flags.webapp:
        return _skip_edge_cleanup("Web-app flag is not active.")

    target_system = system_name or detect_browser_capabilities().platform.diagnostics.raw_system
    if target_system.lower() != "windows":
        return _skip_edge_cleanup("Duplicate Edge cleanup is Windows-only.")

    window_status = _close_duplicate_edge_browser_window_by_handle(
        flags,
        window_diff,
        run_fn=run_fn,
    )
    if window_status is not None:
        return window_status

    if diff.confidence_level != EDGE_CONFIDENCE_LIKELY:
        return _skip_edge_cleanup(
            f"Classification confidence is {diff.confidence_level}, not likely_distinguishable."
        )

    classifications = {item.pid: item for item in diff.classifications}
    new_processes = {process.pid: process for process in diff.new_processes}
    browser_candidates = [
        new_processes[item.pid]
        for item in diff.classifications
        if item.classification == EDGE_CLASSIFICATION_BROWSER
        and item.confidence == EDGE_CONFIDENCE_LIKELY
        and item.pid in diff.new_pids
        and item.pid in new_processes
    ]

    if len(browser_candidates) != 1:
        return _skip_edge_cleanup(
            f"Expected exactly one likely new browser candidate, found {len(browser_candidates)}."
        )
    app_candidates = [
        item
        for item in diff.classifications
        if item.classification == EDGE_CLASSIFICATION_APP
        and item.confidence == EDGE_CONFIDENCE_LIKELY
        and item.pid in diff.new_pids
    ]
    if len(app_candidates) != 1:
        return _skip_edge_cleanup(
            f"Expected exactly one likely new app-window candidate, found {len(app_candidates)}."
        )

    target = browser_candidates[0]
    classification = classifications.get(target.pid)
    if classification is None or classification.classification != EDGE_CLASSIFICATION_BROWSER:
        return _skip_edge_cleanup("Target process classification was not a browser candidate.")
    if target.pid in diff.before_pids:
        return _skip_edge_cleanup("Target process existed before web-app launch.")
    command = target.command_line.lower()
    if not command or DEFAULT_STREAMLIT_LOCAL_URL.lower() not in command or "--app" in command:
        return _skip_edge_cleanup(
            "Target command line did not safely identify a normal Streamlit browser window."
        )
    if not _process_title_identifies_normal_edge_browser(target):
        return _skip_edge_cleanup(
            "Target process did not expose a visible normal Edge browser title."
        )

    close_script = f"""
$ErrorActionPreference = 'Stop'
$process = Get-Process -Id {target.pid} -ErrorAction Stop
if ($process.ProcessName -ne 'msedge') {{
    Write-Output 'not_msedge'
    exit 4
}}
if ($process.MainWindowHandle -eq 0) {{
    Write-Output 'no_main_window'
    exit 3
}}
$closed = $process.CloseMainWindow()
if ($closed) {{
    Write-Output 'close_main_window_sent'
    exit 0
}}
Write-Output 'close_main_window_failed'
exit 2
"""
    try:
        result = run_fn(
            ["powershell", "-NoProfile", "-Command", close_script],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception as exc:
        return EdgeDuplicateCleanupStatus(
            cleanup_requested=True,
            attempted=True,
            skipped=False,
            target_pid=target.pid,
            target_title=target.window_title,
            method=EDGE_CLEANUP_METHOD_CLOSE_MAIN_WINDOW,
            result="exception",
            message=f"Duplicate browser cleanup failed nonfatally: {exc}",
            status_code=EDGE_CLEANUP_STATUS_ATTEMPTED,
        )

    output = (result.stdout or result.stderr or "").strip()
    if result.returncode == 0:
        return EdgeDuplicateCleanupStatus(
            cleanup_requested=True,
            attempted=True,
            skipped=False,
            target_pid=target.pid,
            target_title=target.window_title,
            method=EDGE_CLEANUP_METHOD_CLOSE_MAIN_WINDOW,
            result=output or "close_main_window_sent",
            message=(
                "Experimental duplicate Edge browser cleanup sent a graceful close "
                f"request to PID {target.pid}."
            ),
            status_code=EDGE_CLEANUP_STATUS_ATTEMPTED,
        )

    return EdgeDuplicateCleanupStatus(
        cleanup_requested=True,
        attempted=True,
        skipped=False,
        target_pid=target.pid,
        target_title=target.window_title,
        method=EDGE_CLEANUP_METHOD_CLOSE_MAIN_WINDOW,
        result=output or f"return_code_{result.returncode}",
        message=(
            "Experimental duplicate Edge browser cleanup attempted a graceful close "
            f"for PID {target.pid}, but Windows reported no successful close."
        ),
        status_code=EDGE_CLEANUP_STATUS_ATTEMPTED,
    )


def _close_duplicate_edge_browser_window_by_handle(
    flags: LaunchFlags,
    window_diff: EdgeWindowDiff | None,
    *,
    run_fn: Callable[..., subprocess.CompletedProcess[str]],
) -> EdgeDuplicateCleanupStatus | None:
    """Close one normal browser HWND only when app-window evidence is present."""

    if not flags.webapp or window_diff is None:
        return None

    decision_details = _describe_window_cleanup_candidates(window_diff)
    app_candidates = [
        window
        for window in window_diff.after_windows
        if _is_rolethread_app_window_candidate(window)
    ]
    if not app_candidates:
        return _skip_edge_cleanup(
            "Window cleanup found no confirmed app-window candidate.",
            decision_details=decision_details,
        )

    browser_candidates = [
        window
        for window in window_diff.after_windows
        if _is_streamlit_browser_window_candidate(window)
    ]

    if len(browser_candidates) != 1:
        return _skip_edge_cleanup(
            f"Window cleanup expected exactly one browser candidate, found {len(browser_candidates)}.",
            decision_details=decision_details,
        )

    target = browser_candidates[0]
    close_script = f"""
$ErrorActionPreference = 'Stop'
Add-Type @"
using System;
using System.Text;
using System.Runtime.InteropServices;
public class RoleThreadWindowCloser {{
    [DllImport("user32.dll", SetLastError=true)]
    public static extern bool PostMessage(IntPtr hWnd, UInt32 Msg, IntPtr wParam, IntPtr lParam);
    [DllImport("user32.dll")]
    public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint lpdwProcessId);
    [DllImport("user32.dll", CharSet=CharSet.Unicode)]
    public static extern int GetWindowText(IntPtr hWnd, StringBuilder lpString, int nMaxCount);
}}
"@
$handle = [IntPtr]([Convert]::ToInt64("{target.handle}", 16))
[uint32]$windowPid = 0
[void][RoleThreadWindowCloser]::GetWindowThreadProcessId($handle, [ref]$windowPid)
if ([int]$windowPid -ne {target.pid}) {{
    Write-Output "pid_mismatch"
    exit 5
}}
$process = Get-Process -Id {target.pid} -ErrorAction Stop
if ($process.ProcessName -ne 'msedge') {{
    Write-Output 'not_msedge'
    exit 4
}}
$command = [string](Get-CimInstance Win32_Process -Filter "ProcessId={target.pid}" -ErrorAction Stop).CommandLine
if ($command -notlike '*localhost:8501*' -or $command -like '*--app=*') {{
    Write-Output 'unsafe_command'
    exit 3
}}
$titleBuilder = New-Object System.Text.StringBuilder 512
[void][RoleThreadWindowCloser]::GetWindowText($handle, $titleBuilder, $titleBuilder.Capacity)
$title = [string]$titleBuilder.ToString()
if ($title -notlike '*RoleThread*' -and $title -notlike '*localhost:8501*') {{
    Write-Output 'unsafe_title'
    exit 2
}}
$sent = [RoleThreadWindowCloser]::PostMessage($handle, 0x0010, [IntPtr]::Zero, [IntPtr]::Zero)
if ($sent) {{
    Write-Output 'wm_close_sent'
    exit 0
}}
Write-Output 'wm_close_failed'
exit 1
"""
    try:
        result = run_fn(
            ["powershell", "-NoProfile", "-Command", close_script],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception as exc:
        return EdgeDuplicateCleanupStatus(
            cleanup_requested=True,
            attempted=True,
            skipped=False,
            target_pid=target.pid,
            target_title=target.title,
            method=EDGE_CLEANUP_METHOD_CLOSE_WINDOW_HANDLE,
            result="exception",
            message=f"Window-handle duplicate browser cleanup failed nonfatally: {exc}",
            status_code=EDGE_CLEANUP_STATUS_ATTEMPTED,
            decision_details=decision_details,
        )

    output = (result.stdout or result.stderr or "").strip()
    return EdgeDuplicateCleanupStatus(
        cleanup_requested=True,
        attempted=True,
        skipped=False,
        target_pid=target.pid,
        target_title=target.title,
        method=EDGE_CLEANUP_METHOD_CLOSE_WINDOW_HANDLE,
        result=output or f"return_code_{result.returncode}",
        message=(
            "Experimental duplicate Edge browser cleanup used exact window handle "
            f"{target.handle} after confirming a RoleThread app window."
        ),
        status_code=EDGE_CLEANUP_STATUS_ATTEMPTED,
        decision_details=decision_details,
    )


def _is_streamlit_browser_window_candidate(window: EdgeWindowInfo) -> bool:
    command = window.command_line.lower()
    title = window.title.lower()
    process_name = window.process_name.lower()
    class_name = window.class_name
    return (
        process_name == "msedge.exe"
        and class_name.startswith("Chrome_WidgetWin")
        and _window_command_references_streamlit_browser(command)
        and _window_title_can_be_rolethread_browser(title)
    )


def _window_command_references_streamlit_browser(command: str) -> bool:
    return (
        DEFAULT_STREAMLIT_LOCAL_URL.lower() in command
        and "--app" not in command
    )


def _window_title_can_be_rolethread_browser(title: str) -> bool:
    return "rolethread" in title or "localhost:8501" in title


def _process_title_identifies_normal_edge_browser(process: EdgeProcessInfo) -> bool:
    title = process.window_title.lower()
    return "rolethread" in title and "microsoft" in title and "edge" in title


def _is_rolethread_app_window_candidate(window: EdgeWindowInfo) -> bool:
    title = window.title.strip().lower()
    command = window.command_line.lower()
    return (
        window.class_name.startswith("Chrome_WidgetWin")
        and _window_command_references_app_mode(command)
        and "rolethread" in title
        and "microsoft" not in title
        and "edge" not in title
    )


def _window_command_references_app_mode(command: str) -> bool:
    return (
        "--app=" in command
        or "--app-id=" in command
        or "--embedded-browser-edgeview=1" in command
    )


def _describe_window_cleanup_candidates(window_diff: EdgeWindowDiff) -> tuple[str, ...]:
    details = [
        f"window observation: {window_diff.note}",
        f"after windows: {len(window_diff.after_windows)}",
        f"new windows: {len(window_diff.new_windows)}",
    ]
    for window in window_diff.after_windows:
        if _is_rolethread_app_window_candidate(window):
            classification = "app_window_candidate"
            reason = "title looks app-mode without normal Edge browser branding"
        elif _is_streamlit_browser_window_candidate(window):
            classification = "browser_window_candidate"
            reason = "top-level Edge window references local Streamlit URL without app mode"
        else:
            classification = "rejected"
            reason = _describe_rejected_window_candidate(window)
        details.append(
            (
                f"{window.handle}: {classification}; pid={window.pid}; "
                f"title={window.title or 'No visible title'}; "
                f"class={window.class_name or 'Unknown'}; reason={reason}"
            )
        )
    return tuple(details)


def _describe_rejected_window_candidate(window: EdgeWindowInfo) -> str:
    reasons: list[str] = []
    command = window.command_line.lower()
    title = window.title.lower()
    if window.process_name.lower() != "msedge.exe":
        reasons.append("process is not msedge.exe")
    if not window.class_name.startswith("Chrome_WidgetWin"):
        reasons.append("not a Chrome_WidgetWin top-level window")
    if DEFAULT_STREAMLIT_LOCAL_URL.lower() not in command:
        reasons.append("command does not reference local Streamlit URL")
    if _window_command_references_app_mode(command) and not _is_rolethread_app_window_candidate(window):
        reasons.append("command contains app-mode flag but title was not app-like")
    if "rolethread" not in title and "localhost:8501" not in title:
        reasons.append("title does not identify RoleThread or localhost")
    return "; ".join(reasons) or "candidate did not meet browser/app safety gates"


def _skip_edge_cleanup(
    reason: str,
    *,
    decision_details: tuple[str, ...] = (),
) -> EdgeDuplicateCleanupStatus:
    return EdgeDuplicateCleanupStatus(
        cleanup_requested=False,
        attempted=False,
        skipped=True,
        target_pid=None,
        target_title="",
        method="none",
        result="skipped",
        message=reason,
        status_code=EDGE_CLEANUP_STATUS_SKIPPED,
        decision_details=decision_details,
    )


def classify_edge_process(process: EdgeProcessInfo) -> EdgeProcessClassification:
    """Classify one observed Edge process without mutating browser state."""

    command = process.command_line.lower()
    title = process.window_title.lower()
    reasons: list[str] = []

    if "--app=" in command or "--app-id=" in command:
        reasons.append("command line contains Edge app-mode argument")
        return EdgeProcessClassification(
            pid=process.pid,
            classification=EDGE_CLASSIFICATION_APP,
            confidence=EDGE_CONFIDENCE_LIKELY,
            reasons=tuple(reasons),
        )

    if DEFAULT_STREAMLIT_LOCAL_URL.lower() in command:
        reasons.append("command line references the local Streamlit URL without app mode")
        return EdgeProcessClassification(
            pid=process.pid,
            classification=EDGE_CLASSIFICATION_BROWSER,
            confidence=EDGE_CONFIDENCE_LIKELY,
            reasons=tuple(reasons),
        )

    if DEFAULT_STREAMLIT_LOCAL_URL.lower() in title or "streamlit" in title:
        reasons.append("visible window title looks like a normal Streamlit browser tab")
        return EdgeProcessClassification(
            pid=process.pid,
            classification=EDGE_CLASSIFICATION_BROWSER,
            confidence=EDGE_CONFIDENCE_PARTIAL,
            reasons=tuple(reasons),
        )

    if title.strip():
        reasons.append("visible title captured, but it does not expose app/browser metadata")
    if process.creation_time:
        reasons.append("process creation time captured for order comparison")
    if not reasons:
        reasons.append("no app-mode argument, local URL, or useful window title was captured")
    return EdgeProcessClassification(
        pid=process.pid,
        classification=EDGE_CLASSIFICATION_UNCERTAIN,
        confidence=EDGE_CONFIDENCE_UNRELIABLE,
        reasons=tuple(reasons),
    )


def _coerce_optional_int(value: object) -> int | None:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _resolve_edge_debug_confidence(
    classifications: tuple[EdgeProcessClassification, ...],
    processes: tuple[EdgeProcessInfo, ...],
) -> str:
    if not processes:
        return EDGE_CONFIDENCE_INSUFFICIENT
    has_likely_app = any(
        item.classification == EDGE_CLASSIFICATION_APP
        and item.confidence == EDGE_CONFIDENCE_LIKELY
        for item in classifications
    )
    has_likely_browser = any(
        item.classification == EDGE_CLASSIFICATION_BROWSER
        and item.confidence == EDGE_CONFIDENCE_LIKELY
        for item in classifications
    )
    if has_likely_app and has_likely_browser:
        return EDGE_CONFIDENCE_LIKELY
    if any(item.classification != EDGE_CLASSIFICATION_UNCERTAIN for item in classifications):
        return EDGE_CONFIDENCE_PARTIAL
    return EDGE_CONFIDENCE_UNRELIABLE


def _describe_edge_process_distinguishability(
    classifications: tuple[EdgeProcessClassification, ...],
) -> str:
    if not classifications:
        return "No new Edge processes were observed."

    app_mode = [
        item for item in classifications if item.classification == EDGE_CLASSIFICATION_APP
    ]
    browser = [
        item
        for item in classifications
        if item.classification == EDGE_CLASSIFICATION_BROWSER
    ]
    uncertain = [
        item
        for item in classifications
        if item.classification == EDGE_CLASSIFICATION_UNCERTAIN
    ]

    notes: list[str] = []
    if app_mode:
        notes.append(f"{len(app_mode)} app-window candidate(s) were identified.")
    if browser:
        notes.append(
            f"{len(browser)} normal-browser candidate(s) were identified."
        )
    if uncertain:
        notes.append(
            f"{len(uncertain)} new Edge process(es) remained uncertain from metadata alone."
        )
    return " ".join(notes)


def _describe_edge_process_order(
    processes: tuple[EdgeProcessInfo, ...],
    classifications: tuple[EdgeProcessClassification, ...],
) -> str:
    timed = [process for process in processes if process.creation_time]
    if not timed:
        return "Process creation timing was not available."

    by_pid = {item.pid: item.classification for item in classifications}
    ordered = sorted(timed, key=lambda process: (process.creation_time, process.pid))
    parts = [
        f"{process.pid}:{by_pid.get(process.pid, EDGE_CLASSIFICATION_UNCERTAIN)}"
        for process in ordered
    ]
    return "Observed creation order: " + " -> ".join(parts)


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
            "External dev launcher mode is experimental and deferred. RoleThread skipped "
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
                    "Webapp launch was already handled for this Python process."
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
                "Webapp launch was already handled for this Python process."
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
            message=WEBAPP_UNSUPPORTED_PLATFORM_MESSAGE,
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
                "RoleThread will continue in the normal Streamlit browser flow."
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
                f"RoleThread will continue normally. Error: {exc}"
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
