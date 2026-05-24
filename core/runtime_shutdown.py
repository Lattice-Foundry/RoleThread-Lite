"""RoleThread product cleanup hooks for LitLaunch-managed shutdown."""

from __future__ import annotations

import atexit
import os
import sys
import threading
from collections.abc import Callable, Mapping
from pathlib import Path

from litlaunch import (
    HookConsoleVisibility,
    LauncherRuntime,
    ShutdownHookStatus,
    ShutdownResult,
)

from core.cloud_sync import CloudSyncResult
from core.cloud_sync_shutdown import NOT_CONFIGURED_MESSAGE, run_cloud_sync_shutdown
from core.product_log import resolve_product_log_path_from_env, write_product_log


ROLETHREAD_SHUTDOWN_DIAGNOSTICS_ENV = "ROLETHREAD_LAUNCHER_SHUTDOWN_DIAGNOSTICS"

_STATE_LOCK = threading.Lock()
_CLOUD_SYNC_RAN = False
_ATEXIT_REGISTERED = False
_RUNTIME_CONFIGURED = False
_RUNTIME: LauncherRuntime | None = None


def configure_runtime_shutdown(
    *,
    environ: Mapping[str, str] | None = None,
    runtime: LauncherRuntime | None = None,
    exit_fn: Callable[[int], object] = os._exit,
    register_atexit_fn: Callable[[Callable[[], object]], object] = atexit.register,
) -> bool:
    """Configure RoleThread cleanup when LitLaunch runtime env is present."""

    global _ATEXIT_REGISTERED, _RUNTIME, _RUNTIME_CONFIGURED
    with _STATE_LOCK:
        if not _ATEXIT_REGISTERED:
            register_atexit_fn(run_cloud_sync_closeout)
            _ATEXIT_REGISTERED = True
        if _RUNTIME_CONFIGURED:
            return bool(_RUNTIME and _RUNTIME.available)

        resolved_runtime = runtime or LauncherRuntime.from_env(environ)
        _RUNTIME = resolved_runtime
        _RUNTIME_CONFIGURED = True

    if not resolved_runtime.available:
        return False

    resolved_runtime.register_shutdown_hook(
        run_cloud_sync_closeout,
        label="Cloud backup sync",
        success_message=None,
        failure_message="Cloud backup sync failed.",
        continue_on_error=True,
    )
    resolved_runtime.set_shutdown_completion_callback(
        lambda result: _finish_litlaunch_shutdown(result, exit_fn=exit_fn)
    )
    return resolved_runtime.enable_shutdown_endpoint()


def run_cloud_sync_closeout(
    *,
    diagnostics_enabled: bool | None = None,
    status_callback: Callable[[str], object] | None = None,
    diagnostic_callback: Callable[[str], object] | None = None,
    environ: Mapping[str, str] | None = None,
) -> ShutdownHookStatus:
    """Run RoleThread cloud sync closeout once per backend process."""

    global _CLOUD_SYNC_RAN
    with _STATE_LOCK:
        if _CLOUD_SYNC_RAN:
            return ShutdownHookStatus(render=False)
        _CLOUD_SYNC_RAN = True

    env = environ if environ is not None else os.environ
    log_path = resolve_product_log_path_from_env(env)
    resolved_diagnostics = (
        _diagnostics_enabled(env)
        if diagnostics_enabled is None
        else diagnostics_enabled
    )
    resolved_status_callback = _collect_status_messages(status_callback)
    resolved_diagnostic_callback = diagnostic_callback
    if resolved_diagnostic_callback is None and log_path is not None:
        resolved_diagnostic_callback = lambda message: _write_cloud_sync_log(
            log_path,
            message,
        )

    result = run_cloud_sync_shutdown(
        diagnostics_enabled=resolved_diagnostics,
        status_callback=resolved_status_callback,
        diagnostic_callback=resolved_diagnostic_callback,
    )
    return _cloud_sync_hook_status(result)


def _finish_litlaunch_shutdown(
    result: ShutdownResult,
    *,
    exit_fn: Callable[[int], object],
) -> None:
    _flush_standard_streams()
    exit_fn(0 if result.ok else 1)


def _collect_status_messages(
    callback: Callable[[str], object] | None,
) -> Callable[[str], None]:
    def collect(message: str) -> None:
        if callback is not None:
            callback(message)

    return collect


def _cloud_sync_hook_status(result: CloudSyncResult) -> ShutdownHookStatus:
    if result.ok and result.message == NOT_CONFIGURED_MESSAGE:
        return ShutdownHookStatus(
            message="Cloud sync: No staged cloud sync work configured.",
            console_visibility=HookConsoleVisibility.VERBOSE,
        )
    if result.ok and result.warnings:
        return ShutdownHookStatus(
            message="Cloud sync warning: Staged cloud sync completed with warnings.",
            console_visibility=HookConsoleVisibility.NORMAL,
        )
    if result.ok:
        return ShutdownHookStatus(
            message="Cloud sync: Staged cloud sync completed.",
            console_visibility=HookConsoleVisibility.NORMAL,
        )
    return ShutdownHookStatus(
        message=(
            "Cloud sync warning: Staged cloud sync did not complete; "
            "pending work was preserved."
        ),
        console_visibility=HookConsoleVisibility.NORMAL,
    )


def _write_cloud_sync_log(log_path: Path, message: str) -> None:
    write_product_log(
        log_path,
        (
            "lifecycle=cloud_sync_shutdown",
            f"message={message}",
        ),
    )


def _diagnostics_enabled(environ: Mapping[str, str]) -> bool:
    return str(environ.get(ROLETHREAD_SHUTDOWN_DIAGNOSTICS_ENV, "")).lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _flush_standard_streams() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.flush()
        except Exception:
            pass


def _reset_shutdown_state_for_tests() -> None:
    global _ATEXIT_REGISTERED, _CLOUD_SYNC_RAN, _RUNTIME, _RUNTIME_CONFIGURED
    with _STATE_LOCK:
        _ATEXIT_REGISTERED = False
        _CLOUD_SYNC_RAN = False
        _RUNTIME = None
        _RUNTIME_CONFIGURED = False
