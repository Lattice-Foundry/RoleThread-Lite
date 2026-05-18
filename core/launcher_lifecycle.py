"""Shared launcher-owned lifecycle orchestration.

Streamlit owns the app runtime. This module owns the ordered desktop/webapp
sequence around it: start backend, wait for health, launch browser, monitor the
app window, request shutdown, and verify port release.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from core.browser_adapter import BrowserLaunchResult
from core.launcher_runtime import LAUNCH_MODE_WEBAPP


LifecycleStatusCallback = Callable[[str], None]
DEFAULT_WEBAPP_LAUNCH_MODE = LAUNCH_MODE_WEBAPP


@dataclass(frozen=True)
class LauncherConfig:
    """Runtime configuration shared by source and packaged launchers."""

    app_root: Path
    python_path: Path
    preferences_path: Path
    log_path: Path
    launch_mode: str
    command: tuple[str, ...]
    bundled_mode: bool = False
    shutdown_port: int = 0
    shutdown_token: str = ""
    shutdown_diagnostics: bool = False


@dataclass(frozen=True)
class HealthCheckResult:
    ok: bool
    url: str
    attempts: int
    message: str


@dataclass(frozen=True)
class WindowCloseDetectionResult:
    supported: bool
    closed: bool
    observed: bool
    message: str
    target_handle: str = ""
    target_pid: int | None = None
    target_title: str = ""


@dataclass(frozen=True)
class ShutdownRequestResult:
    attempted: bool
    ok: bool
    status_code: int | None
    message: str


@dataclass(frozen=True)
class TerminationResult:
    attempted: bool
    method: str
    completed: bool
    message: str


EdgeLaunchResult = BrowserLaunchResult


@dataclass(frozen=True)
class PortReleaseStatus:
    released: bool
    owner_pid: int | None
    owner_kind: str
    message: str


@dataclass(frozen=True)
class LauncherLifecycleResult:
    process_pid: int | None
    launch_mode: str
    health: HealthCheckResult
    close_detection: WindowCloseDetectionResult
    shutdown_request: ShutdownRequestResult
    termination: TerminationResult
    final_state: str


def report_lifecycle_status(
    status_callback: LifecycleStatusCallback | None,
    message: str,
) -> None:
    """Report one lifecycle status message when a caller requested diagnostics."""

    if status_callback is not None:
        status_callback(message)


def format_port_release_lifecycle_status(message: str) -> str:
    """Return the common status text for final Streamlit port checks."""

    return f"Port release: {message}"


def log_port_release_status(
    log_path: Path,
    status: PortReleaseStatus,
    *,
    write_log_fn: Callable[[Path, Sequence[str]], None],
) -> None:
    """Log the final Streamlit port state for a launcher-owned run."""

    write_log_fn(
        log_path,
        (
            "lifecycle=port_release",
            f"released={status.released}",
            f"owner_pid={status.owner_pid}",
            f"owner_kind={status.owner_kind}",
            f"message={status.message}",
        ),
    )


def _resolve_port_release_status(
    port_release_fn: Callable[[int | None], PortReleaseStatus],
    pid: int | None,
) -> PortReleaseStatus:
    return port_release_fn(pid)


def _log_and_report_port_release_status(
    log_path: Path,
    status: PortReleaseStatus,
    *,
    write_log_fn: Callable[[Path, Sequence[str]], None],
    status_callback: LifecycleStatusCallback | None,
) -> None:
    log_port_release_status(log_path, status, write_log_fn=write_log_fn)
    report_lifecycle_status(
        status_callback,
        format_port_release_lifecycle_status(status.message),
    )


def run_launcher_lifecycle(
    config: LauncherConfig,
    *,
    launch_backend_fn: Callable[[LauncherConfig], object],
    health_check_fn: Callable[[], HealthCheckResult],
    wait_for_close_fn: Callable[[str, object], WindowCloseDetectionResult],
    shutdown_request_fn: Callable[[LauncherConfig], ShutdownRequestResult],
    termination_fn: Callable[[object], TerminationResult],
    port_release_fn: Callable[[int | None], PortReleaseStatus],
    edge_launch_fn: Callable[[], EdgeLaunchResult],
    write_log_fn: Callable[[Path, Sequence[str]], None],
    format_command_fn: Callable[[Sequence[str]], str],
    wait_for_process_exit_fn: Callable[[object], bool],
    webapp_launch_mode: str = DEFAULT_WEBAPP_LAUNCH_MODE,
    status_callback: LifecycleStatusCallback | None = None,
) -> LauncherLifecycleResult:
    """Run the managed backend, browser-window, shutdown, and port lifecycle."""

    report_lifecycle_status(
        status_callback,
        f"Starting Streamlit backend: {format_command_fn(config.command)}",
    )
    process = launch_backend_fn(config)
    pid = getattr(process, "pid", None)
    report_lifecycle_status(status_callback, f"Streamlit backend started with PID {pid}.")
    report_lifecycle_status(status_callback, "Waiting for Streamlit health endpoint.")
    health = health_check_fn()
    write_log_fn(
        config.log_path,
        (
            "lifecycle=health_check",
            f"pid={pid}",
            f"health_ok={health.ok}",
            f"health_message={health.message}",
        ),
    )
    report_lifecycle_status(status_callback, f"Streamlit health: {health.message}")

    if not health.ok:
        report_lifecycle_status(
            status_callback,
            "Health check failed; terminating owned backend.",
        )
        termination = termination_fn(process)
        shutdown_result = ShutdownRequestResult(
            attempted=False,
            ok=False,
            status_code=None,
            message="Skipped graceful shutdown because health check failed.",
        )
        close_detection = WindowCloseDetectionResult(
            supported=False,
            closed=False,
            observed=False,
            message="Skipped window monitoring because health check failed.",
        )
        write_log_fn(
            config.log_path,
            (
                "lifecycle=health_failed",
                f"termination_method={termination.method}",
                f"termination_completed={termination.completed}",
            ),
        )
        _log_and_report_port_release_status(
            config.log_path,
            _resolve_port_release_status(port_release_fn, pid),
            write_log_fn=write_log_fn,
            status_callback=status_callback,
        )
        return LauncherLifecycleResult(
            process_pid=pid,
            launch_mode=config.launch_mode,
            health=health,
            close_detection=close_detection,
            shutdown_request=shutdown_result,
            termination=termination,
            final_state="health_failed",
        )

    if config.launch_mode == webapp_launch_mode:
        report_lifecycle_status(status_callback, "Launching Edge app-mode window.")
        edge_launch = edge_launch_fn()
        write_log_fn(
            config.log_path,
            (
                "lifecycle=edge_webapp_launch",
                f"attempted={edge_launch.attempted}",
                f"launched={edge_launch.launched}",
                f"command={format_command_fn(edge_launch.command)}",
                f"message={edge_launch.message}",
            ),
        )
        report_lifecycle_status(status_callback, f"Edge app-mode launch: {edge_launch.message}")

    report_lifecycle_status(status_callback, "Monitoring app window for close.")
    close_detection = wait_for_close_fn(config.launch_mode, process)
    write_log_fn(
        config.log_path,
        (
            "lifecycle=window_monitor",
            f"supported={close_detection.supported}",
            f"observed={close_detection.observed}",
            f"closed={close_detection.closed}",
            f"target_handle={close_detection.target_handle}",
            f"target_pid={close_detection.target_pid}",
            f"target_title={close_detection.target_title}",
            f"message={close_detection.message}",
        ),
    )
    report_lifecycle_status(status_callback, f"Window monitor: {close_detection.message}")

    if not close_detection.supported or not close_detection.closed:
        shutdown_result = ShutdownRequestResult(
            attempted=False,
            ok=False,
            status_code=None,
            message="Skipped shutdown request because app-window close was not detected.",
        )
        if config.launch_mode == webapp_launch_mode:
            report_lifecycle_status(
                status_callback,
                "App-window close was not detected; terminating owned backend.",
            )
            termination = termination_fn(process)
            final_state = (
                "window_monitor_failed_terminated"
                if termination.completed
                else "window_monitor_failed_termination_failed"
            )
            write_log_fn(
                config.log_path,
                (
                    "lifecycle=window_monitor_failed",
                    "reason=webapp window was not observed or did not close",
                    f"termination_method={termination.method}",
                    f"termination_completed={termination.completed}",
                    f"termination_message={termination.message}",
                ),
            )
        else:
            termination = TerminationResult(
                attempted=False,
                method="none",
                completed=False,
                message="Lifecycle monitor did not own shutdown for this launch mode.",
            )
            final_state = "monitoring_unavailable"
        _log_and_report_port_release_status(
            config.log_path,
            _resolve_port_release_status(port_release_fn, pid),
            write_log_fn=write_log_fn,
            status_callback=status_callback,
        )
        return LauncherLifecycleResult(
            process_pid=pid,
            launch_mode=config.launch_mode,
            health=health,
            close_detection=close_detection,
            shutdown_request=shutdown_result,
            termination=termination,
            final_state=final_state,
        )

    report_lifecycle_status(
        status_callback,
        "App window closed; requesting graceful backend shutdown.",
    )
    shutdown_result = shutdown_request_fn(config)
    write_log_fn(
        config.log_path,
        (
            "lifecycle=shutdown_request",
            f"attempted={shutdown_result.attempted}",
            f"ok={shutdown_result.ok}",
            f"status_code={shutdown_result.status_code}",
            f"message={shutdown_result.message}",
        ),
    )
    report_lifecycle_status(
        status_callback,
        f"Graceful shutdown request: {shutdown_result.message}",
    )

    if shutdown_result.ok and wait_for_process_exit_fn(process):
        termination = TerminationResult(
            attempted=False,
            method="none",
            completed=True,
            message="Process exited after graceful shutdown request.",
        )
        final_state = "graceful_shutdown"
        report_lifecycle_status(status_callback, "Backend exited after graceful shutdown.")
    else:
        if shutdown_result.ok:
            write_log_fn(
                config.log_path,
                (
                    "lifecycle=cloud_sync_shutdown_timeout",
                    "message=Graceful closeout did not complete before shutdown timeout.",
                ),
            )
            report_lifecycle_status(
                status_callback,
                "Cloud sync warning: Graceful closeout did not complete before shutdown timeout.",
            )
        report_lifecycle_status(
            status_callback,
            "Graceful shutdown did not complete; terminating owned backend.",
        )
        termination = termination_fn(process)
        final_state = "terminated" if termination.completed else "termination_failed"

    write_log_fn(
        config.log_path,
        (
            "lifecycle=final",
            f"final_state={final_state}",
            f"termination_method={termination.method}",
            f"termination_completed={termination.completed}",
            f"termination_message={termination.message}",
        ),
    )
    _log_and_report_port_release_status(
        config.log_path,
        _resolve_port_release_status(port_release_fn, pid),
        write_log_fn=write_log_fn,
        status_callback=status_callback,
    )
    return LauncherLifecycleResult(
        process_pid=pid,
        launch_mode=config.launch_mode,
        health=health,
        close_detection=close_detection,
        shutdown_request=shutdown_result,
        termination=termination,
        final_state=final_state,
    )
