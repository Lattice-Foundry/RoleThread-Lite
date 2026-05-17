"""Windows launcher prototype for RoleThread Lite.

This source module is intended to be wrapped by PyInstaller. It does not
implement final installer integration or shortcut creation.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
import secrets
import socket
import ctypes
from datetime import datetime
from pathlib import Path
import subprocess
import sys
import time
from typing import Callable, Sequence
from urllib import request
from urllib.error import URLError

from core.shutdown_control import (
    SHUTDOWN_HEADER,
    SHUTDOWN_PORT_ENV,
    SHUTDOWN_TOKEN_ENV,
)


APP_NAME = "RoleThread Lite"
APP_DATA_DIR_NAME = "RoleThread"
PREFERENCES_FILE_NAME = "preferences.json"
LAUNCHER_LOG_FILE_NAME = "launcher.log"
STREAMLIT_PORT = "8501"
STREAMLIT_HOST = "127.0.0.1"
STREAMLIT_HEALTH_PATH = "/_stcore/health"
STREAMLIT_ARGS = (
    "-m",
    "streamlit",
    "run",
    "app.py",
    "--server.port",
    STREAMLIT_PORT,
)
INTERNAL_STREAMLIT_FLAG = "--rolethread-run-streamlit"
LAUNCH_MODE_NORMAL = "normal"
LAUNCH_MODE_WEBAPP = "webapp"
WEBAPP_PREFERENCE_KEY = "enable_webapp_launch_mode"
DEFAULT_HEALTH_TIMEOUT_SECONDS = 30.0
DEFAULT_SHUTDOWN_TIMEOUT_SECONDS = 15.0
DEFAULT_WINDOW_APPEAR_TIMEOUT_SECONDS = 60.0
DEFAULT_WINDOW_POLL_SECONDS = 2.0


@dataclass(frozen=True)
class LauncherConfig:
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
class LauncherLifecycleResult:
    process_pid: int | None
    launch_mode: str
    health: HealthCheckResult
    close_detection: WindowCloseDetectionResult
    shutdown_request: ShutdownRequestResult
    termination: TerminationResult
    final_state: str


class LauncherConfigurationError(RuntimeError):
    """Raised when the launcher cannot construct a runnable command."""


def validate_app_root(app_root: Path) -> Path:
    resolved = Path(app_root).resolve()
    if not (resolved / "app.py").is_file():
        raise LauncherConfigurationError(
            f"Could not find RoleThread app.py under app root: {resolved}"
        )
    return resolved


def resolve_app_root(
    *,
    start_path: Path | None = None,
    frozen: bool | None = None,
) -> Path:
    """Resolve the RoleThread app root for dev mode, with bundled mode left explicit."""

    is_frozen = bool(getattr(sys, "frozen", False)) if frozen is None else frozen
    if is_frozen:
        bundled_root = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
        return validate_app_root(bundled_root)

    current = Path(start_path or Path(__file__)).resolve()
    candidates = [current, *current.parents]
    for candidate in candidates:
        if (candidate / "app.py").is_file():
            return candidate
    return validate_app_root(Path.cwd())


def resolve_app_data_root(env: dict[str, str] | None = None) -> Path:
    env_map = env if env is not None else os.environ
    local_app_data = env_map.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / APP_DATA_DIR_NAME
    return Path.home() / "AppData" / "Local" / APP_DATA_DIR_NAME


def resolve_preferences_path(env: dict[str, str] | None = None) -> Path:
    return resolve_app_data_root(env) / PREFERENCES_FILE_NAME


def resolve_launcher_log_path(env: dict[str, str] | None = None) -> Path:
    return resolve_app_data_root(env) / "logs" / LAUNCHER_LOG_FILE_NAME


def find_available_local_port() -> int:
    """Return an available localhost port for the launcher control channel."""

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
        server_socket.bind((STREAMLIT_HOST, 0))
        return int(server_socket.getsockname()[1])


def generate_shutdown_token() -> str:
    """Return an unguessable token for the launcher shutdown endpoint."""

    return secrets.token_urlsafe(32)


def read_enable_webapp_launch_mode(preferences_path: Path) -> bool:
    try:
        data = json.loads(preferences_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return False
    except Exception:
        return False
    if not isinstance(data, dict):
        return False
    return bool(data.get(WEBAPP_PREFERENCE_KEY, False))


def select_launch_mode(*, enable_webapp_launch_mode: bool) -> str:
    return LAUNCH_MODE_WEBAPP if enable_webapp_launch_mode else LAUNCH_MODE_NORMAL


def resolve_python_runtime(
    app_root: Path,
    *,
    current_executable: str | None = None,
    frozen: bool | None = None,
) -> Path:
    is_frozen = bool(getattr(sys, "frozen", False)) if frozen is None else frozen
    if is_frozen:
        executable = Path(current_executable or sys.executable)
        if executable.is_file():
            return executable
        raise LauncherConfigurationError(
            "Could not find the bundled RoleThread launcher executable."
        )

    dev_runtime = app_root / ".venv" / "Scripts" / "python.exe"
    if dev_runtime.is_file():
        return dev_runtime

    fallback = Path(current_executable or sys.executable)
    if fallback.is_file():
        return fallback

    raise LauncherConfigurationError(
        "Could not find a usable Python runtime. Expected .venv\\Scripts\\python.exe "
        "or a valid current Python executable."
    )


def build_streamlit_command(
    python_path: Path,
    *,
    launch_mode: str,
    app_root: Path | None = None,
    frozen: bool = False,
) -> tuple[str, ...]:
    if frozen:
        if app_root is None:
            raise LauncherConfigurationError("Bundled launch requires an app root.")
        app_script = validate_app_root(app_root) / "app.py"
        command: tuple[str, ...] = (
            str(python_path),
            INTERNAL_STREAMLIT_FLAG,
            str(app_script),
            "--global.developmentMode=false",
            "--server.port",
            STREAMLIT_PORT,
        )
    else:
        command = (str(python_path), *STREAMLIT_ARGS)

    if launch_mode == LAUNCH_MODE_WEBAPP:
        return (*command, "--", "webapp")
    if launch_mode == LAUNCH_MODE_NORMAL:
        return command
    raise LauncherConfigurationError(f"Unknown launch mode: {launch_mode}")


def build_launcher_config(
    *,
    app_root: Path | None = None,
    env: dict[str, str] | None = None,
    current_executable: str | None = None,
    frozen: bool | None = None,
    shutdown_port: int | None = None,
    shutdown_token: str | None = None,
) -> LauncherConfig:
    is_frozen = bool(getattr(sys, "frozen", False)) if frozen is None else frozen
    resolved_root = (
        validate_app_root(app_root)
        if app_root is not None
        else resolve_app_root(frozen=is_frozen)
    )
    preferences_path = resolve_preferences_path(env)
    log_path = resolve_launcher_log_path(env)
    python_path = resolve_python_runtime(
        resolved_root,
        current_executable=current_executable,
        frozen=is_frozen,
    )
    launch_mode = select_launch_mode(
        enable_webapp_launch_mode=read_enable_webapp_launch_mode(preferences_path),
    )
    command = build_streamlit_command(
        python_path,
        launch_mode=launch_mode,
        app_root=resolved_root,
        frozen=is_frozen,
    )
    return LauncherConfig(
        app_root=resolved_root,
        python_path=python_path,
        preferences_path=preferences_path,
        log_path=log_path,
        launch_mode=launch_mode,
        command=command,
        bundled_mode=is_frozen,
        shutdown_port=shutdown_port or find_available_local_port(),
        shutdown_token=shutdown_token or generate_shutdown_token(),
    )


def is_port_available(host: str = "127.0.0.1", port: int = int(STREAMLIT_PORT)) -> bool:
    """Return False when something is already listening on the Streamlit port."""

    try:
        with socket.create_connection((host, port), timeout=0.25):
            return False
    except OSError:
        return True


def ensure_streamlit_port_available(
    *,
    port_available_fn: Callable[[], bool] = is_port_available,
) -> None:
    if not port_available_fn():
        raise LauncherConfigurationError(
            f"Port {STREAMLIT_PORT} is already in use. Close the existing RoleThread "
            "session or choose a future launcher port before starting another copy."
        )


def write_launcher_log(log_path: Path, lines: Sequence[str]) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().isoformat(timespec="seconds")
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"[{timestamp}] {APP_NAME} launcher\n")
        for line in lines:
            handle.write(f"{line}\n")
        handle.write("\n")


def get_app_version() -> str:
    try:
        from core.version import ROLETHREAD_VERSION
    except Exception:
        return "unknown"
    return ROLETHREAD_VERSION


def show_failure_message(message: str, *, title: str = APP_NAME) -> None:
    if os.name != "nt":
        return
    try:
        ctypes.windll.user32.MessageBoxW(None, message, title, 0x00000010)
    except Exception:
        return


def format_command(command: Sequence[str]) -> str:
    return " ".join(f'"{part}"' if " " in part else part for part in command)


def build_subprocess_env(
    config: LauncherConfig,
    env: dict[str, str] | None = None,
) -> dict[str, str]:
    """Build the child-process environment with launcher shutdown controls."""

    child_env = dict(os.environ if env is None else env)
    if config.shutdown_port and config.shutdown_token:
        child_env[SHUTDOWN_PORT_ENV] = str(config.shutdown_port)
        child_env[SHUTDOWN_TOKEN_ENV] = config.shutdown_token
    return child_env


def launch_rolethread(
    config: LauncherConfig,
    *,
    popen: Callable[..., subprocess.Popen] = subprocess.Popen,
    port_available_fn: Callable[[], bool] = is_port_available,
    env: dict[str, str] | None = None,
) -> subprocess.Popen:
    write_launcher_log(
        config.log_path,
        (
            f"app_root={config.app_root}",
            f"python_path={config.python_path}",
            f"app_version={get_app_version()}",
            f"bundled_mode={config.bundled_mode}",
            f"preferences_path={config.preferences_path}",
            f"launch_mode={config.launch_mode}",
            f"shutdown_port={config.shutdown_port}",
            f"command={format_command(config.command)}",
        ),
    )
    try:
        ensure_streamlit_port_available(port_available_fn=port_available_fn)
    except Exception as exc:
        write_launcher_log(config.log_path, (f"error={exc}",))
        raise

    # Future pass: own subprocess lifecycle, browser/window close detection,
    # graceful shutdown, and forceful termination fallback if needed.
    try:
        process = popen(
            config.command,
            cwd=config.app_root,
            env=build_subprocess_env(config, env),
        )
    except Exception as exc:
        write_launcher_log(config.log_path, (f"subprocess_error={exc}",))
        raise

    write_launcher_log(
        config.log_path,
        (f"started_pid={getattr(process, 'pid', 'unknown')}",),
    )
    return process


def build_streamlit_health_url(
    *,
    host: str = STREAMLIT_HOST,
    port: str = STREAMLIT_PORT,
) -> str:
    return f"http://{host}:{port}{STREAMLIT_HEALTH_PATH}"


def wait_for_streamlit_health(
    *,
    url: str | None = None,
    timeout_seconds: float = DEFAULT_HEALTH_TIMEOUT_SECONDS,
    poll_seconds: float = 0.5,
    urlopen: Callable[..., object] = request.urlopen,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> HealthCheckResult:
    """Wait for the local Streamlit health endpoint to respond."""

    target_url = url or build_streamlit_health_url()
    deadline = time.monotonic() + timeout_seconds
    attempts = 0
    last_error = ""
    while time.monotonic() <= deadline:
        attempts += 1
        try:
            with urlopen(target_url, timeout=1):
                return HealthCheckResult(
                    ok=True,
                    url=target_url,
                    attempts=attempts,
                    message="Streamlit health endpoint responded.",
                )
        except Exception as exc:
            last_error = str(exc)
            sleep_fn(poll_seconds)
    return HealthCheckResult(
        ok=False,
        url=target_url,
        attempts=attempts,
        message=f"Timed out waiting for Streamlit health. Last error: {last_error}",
    )


def count_rolethread_webapp_windows(
    *,
    run_fn: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> int | None:
    """Return the number of visible RoleThread Edge app windows, if Windows allows it."""

    if os.name != "nt":
        return None

    script = """
$ErrorActionPreference = 'Stop'
Add-Type @"
using System;
using System.Text;
using System.Runtime.InteropServices;
public class RoleThreadWindowEnumerator {
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
$matches = 0
$callback = [RoleThreadWindowEnumerator+EnumWindowsProc]{
    param([IntPtr]$hWnd, [IntPtr]$lParam)
    if (-not [RoleThreadWindowEnumerator]::IsWindowVisible($hWnd)) { return $true }
    $titleBuilder = New-Object System.Text.StringBuilder 512
    $classBuilder = New-Object System.Text.StringBuilder 256
    [void][RoleThreadWindowEnumerator]::GetWindowText($hWnd, $titleBuilder, $titleBuilder.Capacity)
    [void][RoleThreadWindowEnumerator]::GetClassName($hWnd, $classBuilder, $classBuilder.Capacity)
    $title = [string]$titleBuilder.ToString()
    $className = [string]$classBuilder.ToString()
    if ($title -like '*RoleThread Lite*' -and $title -notlike '*Microsoft*Edge*' -and $className -like 'Chrome_WidgetWin*') {
        [uint32]$pid = 0
        [void][RoleThreadWindowEnumerator]::GetWindowThreadProcessId($hWnd, [ref]$pid)
        try {
            $process = Get-Process -Id ([int]$pid) -ErrorAction Stop
            if ($process.ProcessName -eq 'msedge') { $script:matches += 1 }
        } catch {}
    }
    return $true
}
[void][RoleThreadWindowEnumerator]::EnumWindows($callback, [IntPtr]::Zero)
Write-Output $matches
"""
    try:
        result = run_fn(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    output = (result.stdout or "").strip().splitlines()
    if not output:
        return None
    try:
        return int(output[-1].strip())
    except ValueError:
        return None


def wait_for_app_window_close(
    launch_mode: str,
    *,
    process: subprocess.Popen | None = None,
    count_windows_fn: Callable[[], int | None] = count_rolethread_webapp_windows,
    sleep_fn: Callable[[float], None] = time.sleep,
    appear_timeout_seconds: float = DEFAULT_WINDOW_APPEAR_TIMEOUT_SECONDS,
    poll_seconds: float = DEFAULT_WINDOW_POLL_SECONDS,
) -> WindowCloseDetectionResult:
    """Wait until the app window closes when the launch mode supports detection."""

    if launch_mode != LAUNCH_MODE_WEBAPP:
        return WindowCloseDetectionResult(
            supported=False,
            closed=False,
            observed=False,
            message=(
                "Automatic browser-close detection is not enabled for normal "
                "browser launch mode."
            ),
        )

    deadline = time.monotonic() + appear_timeout_seconds
    observed = False
    while time.monotonic() <= deadline:
        if process is not None and process.poll() is not None:
            return WindowCloseDetectionResult(
                supported=True,
                closed=True,
                observed=observed,
                message="Streamlit subprocess exited before app-window monitoring completed.",
            )
        count = count_windows_fn()
        if count is None:
            return WindowCloseDetectionResult(
                supported=False,
                closed=False,
                observed=observed,
                message="Windows app-window detection was unavailable.",
            )
        if count > 0:
            observed = True
            break
        sleep_fn(poll_seconds)

    if not observed:
        return WindowCloseDetectionResult(
            supported=False,
            closed=False,
            observed=False,
            message="Timed out waiting for the Edge app window to appear.",
        )

    while True:
        if process is not None and process.poll() is not None:
            return WindowCloseDetectionResult(
                supported=True,
                closed=True,
                observed=True,
                message="Streamlit subprocess exited while monitoring the app window.",
            )
        count = count_windows_fn()
        if count is None:
            return WindowCloseDetectionResult(
                supported=False,
                closed=False,
                observed=True,
                message="Windows app-window detection became unavailable.",
            )
        if count == 0:
            return WindowCloseDetectionResult(
                supported=True,
                closed=True,
                observed=True,
                message="RoleThread app window closed.",
            )
        sleep_fn(poll_seconds)


def request_graceful_shutdown(
    config: LauncherConfig,
    *,
    urlopen: Callable[..., object] = request.urlopen,
    timeout_seconds: float = 5.0,
) -> ShutdownRequestResult:
    """Request local launcher-controlled app shutdown."""

    if not config.shutdown_port or not config.shutdown_token:
        return ShutdownRequestResult(
            attempted=False,
            ok=False,
            status_code=None,
            message="No shutdown control channel was configured.",
        )
    url = f"http://{STREAMLIT_HOST}:{config.shutdown_port}/shutdown"
    shutdown_request = request.Request(
        url,
        data=b"",
        method="POST",
    )
    shutdown_request.add_header(SHUTDOWN_HEADER, config.shutdown_token)
    try:
        with urlopen(shutdown_request, timeout=timeout_seconds) as response:
            status_code = int(getattr(response, "status", 200))
        return ShutdownRequestResult(
            attempted=True,
            ok=200 <= status_code < 300,
            status_code=status_code,
            message=f"Shutdown endpoint returned HTTP {status_code}.",
        )
    except URLError as exc:
        return ShutdownRequestResult(
            attempted=True,
            ok=False,
            status_code=None,
            message=f"Shutdown request failed: {exc}",
        )
    except Exception as exc:
        return ShutdownRequestResult(
            attempted=True,
            ok=False,
            status_code=None,
            message=f"Shutdown request failed: {exc}",
        )


def wait_for_process_exit(
    process: subprocess.Popen,
    *,
    timeout_seconds: float,
) -> bool:
    try:
        process.wait(timeout=timeout_seconds)
        return True
    except subprocess.TimeoutExpired:
        return False


def terminate_process_fallback(
    process: subprocess.Popen,
    *,
    timeout_seconds: float = DEFAULT_SHUTDOWN_TIMEOUT_SECONDS,
) -> TerminationResult:
    """Terminate the Streamlit subprocess, escalating to kill only if needed."""

    if process.poll() is not None:
        return TerminationResult(
            attempted=False,
            method="none",
            completed=True,
            message="Process already exited.",
        )

    process.terminate()
    if wait_for_process_exit(process, timeout_seconds=timeout_seconds):
        return TerminationResult(
            attempted=True,
            method="terminate",
            completed=True,
            message="Process exited after terminate().",
        )

    process.kill()
    if wait_for_process_exit(process, timeout_seconds=5.0):
        return TerminationResult(
            attempted=True,
            method="kill",
            completed=True,
            message="Process exited after kill().",
        )

    return TerminationResult(
        attempted=True,
        method="kill",
        completed=False,
        message="Process did not exit after kill().",
    )


def run_launcher_lifecycle(
    config: LauncherConfig,
    *,
    popen: Callable[..., subprocess.Popen] = subprocess.Popen,
    port_available_fn: Callable[[], bool] = is_port_available,
    health_check_fn: Callable[[], HealthCheckResult] = wait_for_streamlit_health,
    wait_for_close_fn: (
        Callable[[str, subprocess.Popen], WindowCloseDetectionResult] | None
    ) = None,
    shutdown_request_fn: Callable[
        [LauncherConfig],
        ShutdownRequestResult,
    ] = request_graceful_shutdown,
    termination_fn: Callable[
        [subprocess.Popen],
        TerminationResult,
    ] = terminate_process_fallback,
) -> LauncherLifecycleResult:
    """Start RoleThread and manage the first launcher-owned shutdown lifecycle."""

    process = launch_rolethread(
        config,
        popen=popen,
        port_available_fn=port_available_fn,
    )
    pid = getattr(process, "pid", None)
    health = health_check_fn()
    write_launcher_log(
        config.log_path,
        (
            f"lifecycle=health_check",
            f"pid={pid}",
            f"health_ok={health.ok}",
            f"health_message={health.message}",
        ),
    )

    if not health.ok:
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
        write_launcher_log(
            config.log_path,
            (
                "lifecycle=health_failed",
                f"termination_method={termination.method}",
                f"termination_completed={termination.completed}",
            ),
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

    close_waiter = wait_for_close_fn or (
        lambda mode, proc: wait_for_app_window_close(mode, process=proc)
    )
    close_detection = close_waiter(config.launch_mode, process)
    write_launcher_log(
        config.log_path,
        (
            "lifecycle=window_monitor",
            f"supported={close_detection.supported}",
            f"observed={close_detection.observed}",
            f"closed={close_detection.closed}",
            f"message={close_detection.message}",
        ),
    )

    if not close_detection.supported or not close_detection.closed:
        shutdown_result = ShutdownRequestResult(
            attempted=False,
            ok=False,
            status_code=None,
            message="Skipped shutdown request because app-window close was not detected.",
        )
        termination = TerminationResult(
            attempted=False,
            method="none",
            completed=False,
            message="Lifecycle monitor did not own shutdown for this launch mode.",
        )
        return LauncherLifecycleResult(
            process_pid=pid,
            launch_mode=config.launch_mode,
            health=health,
            close_detection=close_detection,
            shutdown_request=shutdown_result,
            termination=termination,
            final_state="monitoring_unavailable",
        )

    shutdown_result = shutdown_request_fn(config)
    write_launcher_log(
        config.log_path,
        (
            "lifecycle=shutdown_request",
            f"attempted={shutdown_result.attempted}",
            f"ok={shutdown_result.ok}",
            f"status_code={shutdown_result.status_code}",
            f"message={shutdown_result.message}",
        ),
    )

    if shutdown_result.ok and wait_for_process_exit(
        process,
        timeout_seconds=DEFAULT_SHUTDOWN_TIMEOUT_SECONDS,
    ):
        termination = TerminationResult(
            attempted=False,
            method="none",
            completed=True,
            message="Process exited after graceful shutdown request.",
        )
        final_state = "graceful_shutdown"
    else:
        termination = termination_fn(process)
        final_state = "terminated" if termination.completed else "termination_failed"

    write_launcher_log(
        config.log_path,
        (
            "lifecycle=final",
            f"final_state={final_state}",
            f"termination_method={termination.method}",
            f"termination_completed={termination.completed}",
            f"termination_message={termination.message}",
        ),
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


def run_bundled_streamlit(argv: Sequence[str] | None = None) -> int:
    """Run Streamlit from inside the frozen PyInstaller runtime."""

    args = list(sys.argv[2:] if argv is None else argv)
    if not args:
        raise LauncherConfigurationError("Bundled Streamlit mode requires an app.py path.")

    app_script = Path(args[0]).resolve()
    if not app_script.is_file():
        raise LauncherConfigurationError(f"Could not find bundled app.py: {app_script}")

    streamlit_args = ["streamlit", "run", str(app_script), *args[1:]]
    sys.path.insert(0, str(app_script.parent))
    sys.argv = streamlit_args

    from streamlit.web.cli import main as streamlit_main

    streamlit_main()
    return 0


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == INTERNAL_STREAMLIT_FLAG:
        return run_bundled_streamlit()

    try:
        config = build_launcher_config()
        print(f"Starting {APP_NAME} in {config.launch_mode} mode...")
        print(format_command(config.command))
        run_launcher_lifecycle(config)
        return 0
    except Exception as exc:
        try:
            log_path = resolve_launcher_log_path()
            write_launcher_log(log_path, (f"error={exc}",))
            show_failure_message(
                f"RoleThread could not start.\n\n{exc}\n\nDetails were written to:\n{log_path}"
            )
            print(f"Launcher error: {exc}")
            print(f"Details written to {log_path}")
        except Exception:
            show_failure_message(f"RoleThread could not start.\n\n{exc}")
            print(f"Launcher error: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
