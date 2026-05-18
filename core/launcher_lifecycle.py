"""Shared lifecycle orchestration for RoleThread launcher-owned runs."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


LifecycleStatusCallback = Callable[[str], None]
DEFAULT_WEBAPP_LAUNCH_MODE = "webapp"


@dataclass(frozen=True)
class LauncherConfig:
    """Shared launcher runtime configuration."""

    app_root: Path
    python_path: Path
    preferences_path: Path
    log_path: Path
    launch_mode: str
    command: tuple[str, ...]
    bundled_mode: bool = False
    shutdown_port: int = 0
    shutdown_token: str = ""


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


@dataclass(frozen=True)
class EdgeLaunchResult:
    attempted: bool
    launched: bool
    command: tuple[str, ...]
    message: str


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


def log_pending_webapp_browser_state_reset(
    log_path: Path,
    result: object,
    *,
    write_log_fn: Callable[[Path, Sequence[str]], None],
) -> None:
    """Log a pending browser-state reset attempt without knowing its concrete type."""

    reset_result = getattr(result, "reset_result", None)
    lines = [
        "lifecycle=webapp_browser_state_reset",
        f"pending={getattr(result, 'pending', False)}",
        f"attempted={getattr(result, 'attempted', False)}",
        f"completed={getattr(result, 'completed', False)}",
        f"marker_path={getattr(result, 'marker_path', '')}",
        f"message={getattr(result, 'message', '')}",
    ]
    if reset_result is not None:
        lines.extend(
            [
                f"reset_success={reset_result.success}",
                f"profile_path={reset_result.profile_path}",
                f"items_cleared={len(reset_result.items_cleared)}",
                f"items_skipped={len(reset_result.items_skipped)}",
                f"warnings={len(reset_result.warnings)}",
                f"errors={len(reset_result.errors)}",
            ]
        )
        if reset_result.items_skipped:
            lines.append(f"first_skipped={reset_result.items_skipped[0]}")
        if reset_result.warnings:
            lines.append(f"first_warning={reset_result.warnings[0]}")
        if reset_result.errors:
            lines.append(f"first_error={reset_result.errors[0]}")
    write_log_fn(log_path, tuple(lines))


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
    pending_browser_reset_fn: Callable[[], object],
    write_log_fn: Callable[[Path, Sequence[str]], None],
    format_command_fn: Callable[[Sequence[str]], str],
    wait_for_process_exit_fn: Callable[[object], bool],
    webapp_launch_mode: str = DEFAULT_WEBAPP_LAUNCH_MODE,
    status_callback: LifecycleStatusCallback | None = None,
) -> LauncherLifecycleResult:
    """Run the shared launcher-owned backend/browser/shutdown lifecycle."""

    if config.launch_mode == webapp_launch_mode:
        report_lifecycle_status(
            status_callback,
            "Checking pending webapp browser-state reset before Edge launch.",
        )
        reset_result = pending_browser_reset_fn()
        if getattr(reset_result, "attempted", False):
            log_pending_webapp_browser_state_reset(
                config.log_path,
                reset_result,
                write_log_fn=write_log_fn,
            )
            report_lifecycle_status(
                status_callback,
                f"Pending webapp browser-state reset: {getattr(reset_result, 'message', '')}",
            )

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
