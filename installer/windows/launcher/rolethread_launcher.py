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
import sqlite3
import sys
import time
from typing import Callable, Sequence
from urllib import request
from urllib.error import URLError

from core.launcher_lifecycle import (
    EdgeLaunchResult,
    HealthCheckResult,
    LauncherConfig,
    LauncherLifecycleResult,
    LifecycleStatusCallback,
    PortReleaseStatus,
    ShutdownRequestResult,
    TerminationResult,
    WindowCloseDetectionResult,
    run_launcher_lifecycle as run_shared_launcher_lifecycle,
)
from core.launcher_runtime import (
    LAUNCH_MODE_NORMAL,
    LAUNCH_MODE_WEBAPP,
    STREAMLIT_HOST,
    STREAMLIT_PORT,
    build_launcher_shutdown_url,
    build_streamlit_app_url,
    build_streamlit_command as build_shared_streamlit_command,
    build_streamlit_health_url,
    format_command,
)
from core.shutdown_control import (
    SHUTDOWN_HEADER,
    SHUTDOWN_PORT_ENV,
    SHUTDOWN_TOKEN_ENV,
)
from core.launch import EXTERNAL_WEBAPP_LAUNCH_ENV
from core.edge_version_history import record_installed_edge_version
from core.platform import detect_browser_capabilities
from core.webapp_browser_state import consume_pending_webapp_browser_state_reset


APP_NAME = "RoleThread Lite"
APP_DATA_DIR_NAME = "RoleThread"
PREFERENCES_FILE_NAME = "preferences.json"
INSTALLER_SEED_FILE_NAME = "installer_seed.json"
LAUNCHER_LOG_FILE_NAME = "launcher.log"
DATABASE_FILE_NAME = "rolethread.db"
INTERNAL_STREAMLIT_FLAG = "--rolethread-run-streamlit"
LAUNCHER_LOG_PATH_ENV = "ROLETHREAD_LAUNCHER_LOG_PATH"
WEBAPP_PREFERENCE_KEY = "enable_webapp_launch_mode"
DEFAULT_HEALTH_TIMEOUT_SECONDS = 30.0
DEFAULT_SHUTDOWN_TIMEOUT_SECONDS = 15.0
DEFAULT_WINDOW_APPEAR_TIMEOUT_SECONDS = 60.0
DEFAULT_WINDOW_POLL_SECONDS = 2.0


@dataclass(frozen=True)
class WebappWindowInfo:
    handle: str
    pid: int
    title: str
    class_name: str
    process_name: str


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


def resolve_database_path(env: dict[str, str] | None = None) -> Path:
    return resolve_app_data_root(env) / DATABASE_FILE_NAME


def resolve_installer_seed_path(env: dict[str, str] | None = None) -> Path:
    return resolve_app_data_root(env) / INSTALLER_SEED_FILE_NAME


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


def read_enable_webapp_launch_mode_from_db(database_path: Path) -> bool | None:
    if not database_path.exists():
        return None

    try:
        with sqlite3.connect(str(database_path)) as connection:
            row = connection.execute(
                "SELECT value FROM app_settings WHERE key = ?",
                (WEBAPP_PREFERENCE_KEY,),
            ).fetchone()
    except sqlite3.Error:
        return None

    if row is None:
        return None

    try:
        return bool(json.loads(row[0] or "false"))
    except Exception:
        return None


def write_webapp_launch_preference_to_db(database_path: Path, enabled: bool) -> None:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().isoformat()
    with sqlite3.connect(str(database_path)) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS app_settings (
                key VARCHAR(120) NOT NULL PRIMARY KEY,
                value TEXT,
                updated_at DATETIME NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO app_settings (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = excluded.updated_at
            """,
            (WEBAPP_PREFERENCE_KEY, json.dumps(bool(enabled)), timestamp),
        )
        connection.commit()


def read_installer_seed(seed_path: Path) -> bool | None:
    try:
        data = json.loads(seed_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except Exception:
        return None

    if not isinstance(data, dict) or WEBAPP_PREFERENCE_KEY not in data:
        return None
    return bool(data.get(WEBAPP_PREFERENCE_KEY))


def apply_installer_seed(
    *,
    seed_path: Path,
    database_path: Path,
    log_path: Path | None = None,
) -> bool | None:
    enabled = read_installer_seed(seed_path)
    if enabled is None:
        return None

    try:
        write_webapp_launch_preference_to_db(database_path, enabled)
        seed_path.unlink(missing_ok=True)
        if log_path is not None:
            write_launcher_log(
                log_path,
                [f"installer_seed_applied {WEBAPP_PREFERENCE_KEY}={enabled}"],
            )
        return enabled
    except Exception as exc:
        if log_path is not None:
            write_launcher_log(log_path, [f"installer_seed_error={exc}"])
        return None


def resolve_enable_webapp_launch_mode(
    *,
    preferences_path: Path,
    database_path: Path,
) -> bool:
    db_value = read_enable_webapp_launch_mode_from_db(database_path)
    if db_value is not None:
        return db_value
    return read_enable_webapp_launch_mode(preferences_path)


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
    """Build the Streamlit command after resolving adapter-specific app paths."""

    if frozen:
        if app_root is None:
            raise LauncherConfigurationError("Bundled launch requires an app root.")
        app_script = validate_app_root(app_root) / "app.py"
    else:
        app_script = None

    try:
        return build_shared_streamlit_command(
            python_path,
            launch_mode=launch_mode,
            app_script=app_script,
            internal_streamlit_flag=INTERNAL_STREAMLIT_FLAG if frozen else None,
        )
    except ValueError as exc:
        raise LauncherConfigurationError(str(exc)) from exc


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
    database_path = resolve_database_path(env)
    seed_path = resolve_installer_seed_path(env)
    apply_installer_seed(
        seed_path=seed_path,
        database_path=database_path,
        log_path=log_path,
    )
    python_path = resolve_python_runtime(
        resolved_root,
        current_executable=current_executable,
        frozen=is_frozen,
    )
    launch_mode = select_launch_mode(
        enable_webapp_launch_mode=resolve_enable_webapp_launch_mode(
            preferences_path=preferences_path,
            database_path=database_path,
        ),
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


def is_port_available(host: str = STREAMLIT_HOST, port: int = int(STREAMLIT_PORT)) -> bool:
    """Return False when something is already listening on the Streamlit port."""

    try:
        with socket.create_connection((host, port), timeout=0.25):
            return False
    except OSError:
        return True


def get_port_owner_pid(port: int = int(STREAMLIT_PORT)) -> int | None:
    """Return the owning PID for a listening TCP port when Windows exposes it."""

    if os.name != "nt":
        return None

    script = f"""
$connection = Get-NetTCPConnection -LocalPort {port} -State Listen -ErrorAction SilentlyContinue |
    Select-Object -First 1
if ($null -eq $connection) {{
    Write-Output ''
}} else {{
    Write-Output ([string]$connection.OwningProcess)
}}
"""
    try:
        result = subprocess.run(
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


def check_port_release_status(
    *,
    owned_pid: int | None,
    port_available_fn: Callable[[], bool] = is_port_available,
    port_owner_fn: Callable[[], int | None] = get_port_owner_pid,
) -> PortReleaseStatus:
    """Return the final Streamlit port state without killing unknown listeners."""

    if port_available_fn():
        return PortReleaseStatus(
            released=True,
            owner_pid=None,
            owner_kind="free",
            message=f"Port {STREAMLIT_PORT} is released.",
        )

    owner = port_owner_fn()
    if owner is not None and owned_pid is not None and owner == owned_pid:
        return PortReleaseStatus(
            released=False,
            owner_pid=owner,
            owner_kind="owned_process",
            message=f"Port {STREAMLIT_PORT} is still occupied by owned process {owner}.",
        )

    if owner is not None:
        return PortReleaseStatus(
            released=False,
            owner_pid=owner,
            owner_kind="unknown_process",
            message=f"Port {STREAMLIT_PORT} is still occupied by unknown process {owner}.",
        )

    return PortReleaseStatus(
        released=False,
        owner_pid=None,
        owner_kind="unknown_process",
        message=f"Port {STREAMLIT_PORT} is still occupied; owner PID was unavailable.",
    )


def format_port_release_status(*, owned_pid: int | None) -> str:
    """Return a concise final status for the Streamlit port after shutdown."""

    status = check_port_release_status(owned_pid=owned_pid)
    if status.released:
        return "released"
    if status.owner_kind == "owned_process":
        return f"still occupied by owned process {status.owner_pid}"
    if status.owner_pid is not None:
        return f"still occupied by unknown process {status.owner_pid}"
    return "still occupied by unknown process"


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


def build_subprocess_env(
    config: LauncherConfig,
    env: dict[str, str] | None = None,
) -> dict[str, str]:
    """Build the child-process environment with launcher shutdown controls."""

    # WEBAPP_LIFECYCLE_TODO: these environment boundaries should remain the
    # shared contract between the launcher-owned lifecycle and app-side
    # compatibility/diagnostic code.
    child_env = dict(os.environ if env is None else env)
    if config.shutdown_port and config.shutdown_token:
        child_env[SHUTDOWN_PORT_ENV] = str(config.shutdown_port)
        child_env[SHUTDOWN_TOKEN_ENV] = config.shutdown_token
    child_env[LAUNCHER_LOG_PATH_ENV] = str(config.log_path)
    if config.launch_mode == LAUNCH_MODE_WEBAPP:
        child_env[EXTERNAL_WEBAPP_LAUNCH_ENV] = "1"
    return child_env


def launch_rolethread(
    config: LauncherConfig,
    *,
    popen: Callable[..., subprocess.Popen] = subprocess.Popen,
    port_available_fn: Callable[[], bool] = is_port_available,
    env: dict[str, str] | None = None,
) -> subprocess.Popen:
    # WEBAPP_LIFECYCLE_TODO: subprocess ownership, port checks, and logging are
    # already the right launcher-owned shape; future dev/manual launcher mode
    # should reuse this instead of invoking raw `streamlit run`.
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

    # Lifecycle management is handled after startup by run_launcher_lifecycle().
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


def launch_edge_webapp_window(
    *,
    url: str | None = None,
    popen: Callable[..., subprocess.Popen] = subprocess.Popen,
) -> EdgeLaunchResult:
    """Open the launcher-managed Edge app window after Streamlit is healthy."""

    # WEBAPP_LIFECYCLE_TODO: this is the canonical owner for Edge app-mode
    # startup; app.py should eventually stop launching Edge directly.
    detection = detect_browser_capabilities()
    edge_path = detection.browser.edge_path
    if detection.platform.os_name != "windows" or edge_path is None:
        return EdgeLaunchResult(
            attempted=False,
            launched=False,
            command=(),
            message="Windows Microsoft Edge webapp launch is unavailable.",
        )
    record_installed_edge_version(edge_path, source="launcher")

    target_url = url or build_streamlit_app_url()
    command = (str(edge_path), f"--app={target_url}")
    try:
        popen(command)
    except Exception as exc:
        return EdgeLaunchResult(
            attempted=True,
            launched=False,
            command=command,
            message=f"Edge webapp launch failed: {exc}",
        )

    return EdgeLaunchResult(
        attempted=True,
        launched=True,
        command=command,
        message="Edge webapp launch command was started.",
    )


def wait_for_streamlit_health(
    *,
    url: str | None = None,
    timeout_seconds: float = DEFAULT_HEALTH_TIMEOUT_SECONDS,
    poll_seconds: float = 0.5,
    urlopen: Callable[..., object] = request.urlopen,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> HealthCheckResult:
    """Wait for the local Streamlit health endpoint to respond."""

    # WEBAPP_LIFECYCLE_TODO: keep readiness as an explicit launcher step. Health
    # means the backend is listening; Edge window readiness is handled later.
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

    windows = capture_rolethread_webapp_windows(run_fn=run_fn)
    if windows is None:
        return None
    return len(windows)


def capture_rolethread_webapp_windows(
    *,
    run_fn: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> tuple[WebappWindowInfo, ...] | None:
    """Return visible RoleThread Edge app windows with exact HWND metadata."""

    # WEBAPP_LIFECYCLE_TODO: exact HWND observation should remain shared
    # lifecycle infrastructure because Edge PID/command metadata drifts.
    if os.name != "nt":
        return None
    if run_fn is subprocess.run:
        return capture_rolethread_webapp_windows_native()

    return capture_rolethread_webapp_windows_powershell(run_fn=run_fn)


def _resolve_process_name_native(pid: int) -> str:
    """Return a Windows process image name using Win32 APIs when available."""

    process_query_limited_information = 0x1000
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(process_query_limited_information, False, int(pid))
    if not handle:
        return ""
    try:
        buffer = ctypes.create_unicode_buffer(32768)
        size = ctypes.c_ulong(len(buffer))
        if kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            return Path(buffer.value).stem
    finally:
        kernel32.CloseHandle(handle)
    return ""


def capture_rolethread_webapp_windows_native() -> tuple[WebappWindowInfo, ...] | None:
    """Return visible RoleThread Edge app windows using direct Win32 HWND APIs."""

    if os.name != "nt":
        return None
    try:
        user32 = ctypes.windll.user32
    except Exception:
        return None

    enum_windows_proc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    windows: list[WebappWindowInfo] = []

    def callback(hwnd: int, lparam: int) -> bool:
        try:
            if not user32.IsWindowVisible(hwnd):
                return True
            title_buffer = ctypes.create_unicode_buffer(512)
            class_buffer = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(hwnd, title_buffer, len(title_buffer))
            user32.GetClassNameW(hwnd, class_buffer, len(class_buffer))
            title = title_buffer.value.strip()
            class_name = class_buffer.value.strip()
            if not _is_rolethread_webapp_window_title(title):
                return True
            if not class_name.startswith("Chrome_WidgetWin"):
                return True
            pid_value = ctypes.c_ulong(0)
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid_value))
            pid = int(pid_value.value)
            process_name = _resolve_process_name_native(pid).lower()
            if process_name and process_name != "msedge":
                return True
            windows.append(
                WebappWindowInfo(
                    handle=f"0x{int(hwnd):X}",
                    pid=pid,
                    title=title,
                    class_name=class_name,
                    process_name=process_name or "unknown",
                )
            )
        except Exception:
            return True
        return True

    try:
        if not user32.EnumWindows(enum_windows_proc(callback), 0):
            return None
    except Exception:
        return None
    return tuple(sorted(windows, key=lambda item: item.handle))


def _is_rolethread_webapp_window_title(title: str) -> bool:
    """Return whether a title looks like the app-mode window, not browser chrome."""

    normalized = title.strip().lower()
    if "rolethread lite" not in normalized:
        return False
    if "microsoft edge" in normalized:
        return False
    return True


def capture_rolethread_webapp_windows_powershell(
    *,
    run_fn: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> tuple[WebappWindowInfo, ...] | None:
    """Return visible RoleThread Edge app windows using the legacy PowerShell probe."""

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
$script:matches = New-Object System.Collections.Generic.List[object]
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
            if ($process.ProcessName -eq 'msedge') {
                $script:matches.Add([pscustomobject]@{
                    handle = ('0x{0:X}' -f $hWnd.ToInt64())
                    pid = [int]$pid
                    title = $title
                    class_name = $className
                    process_name = $process.ProcessName
                }) | Out-Null
            }
        } catch {}
    }
    return $true
}
[void][RoleThreadWindowEnumerator]::EnumWindows($callback, [IntPtr]::Zero)
$script:matches | Sort-Object handle | ConvertTo-Json -Compress
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
    output = (result.stdout or "").strip()
    if not output:
        return ()
    try:
        parsed = json.loads(output)
    except json.JSONDecodeError:
        return None
    if isinstance(parsed, dict):
        parsed_items = [parsed]
    elif isinstance(parsed, list):
        parsed_items = parsed
    else:
        return ()

    windows: list[WebappWindowInfo] = []
    for item in parsed_items:
        if not isinstance(item, dict):
            continue
        try:
            windows.append(
                WebappWindowInfo(
                    handle=str(item.get("handle", "")),
                    pid=int(item.get("pid", 0)),
                    title=str(item.get("title", "")),
                    class_name=str(item.get("class_name", "")),
                    process_name=str(item.get("process_name", "")),
                )
            )
        except (TypeError, ValueError):
            continue
    return tuple(windows)


def wait_for_app_window_close(
    launch_mode: str,
    *,
    process: subprocess.Popen | None = None,
    count_windows_fn: Callable[[], int | None] = count_rolethread_webapp_windows,
    capture_windows_fn: Callable[
        [], tuple[WebappWindowInfo, ...] | None
    ] | None = None,
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

    if capture_windows_fn is not None:
        return wait_for_exact_app_window_close(
            process=process,
            capture_windows_fn=capture_windows_fn,
            sleep_fn=sleep_fn,
            appear_timeout_seconds=appear_timeout_seconds,
            poll_seconds=poll_seconds,
        )

    if count_windows_fn is count_rolethread_webapp_windows:
        return wait_for_exact_app_window_close(
            process=process,
            capture_windows_fn=capture_rolethread_webapp_windows,
            sleep_fn=sleep_fn,
            appear_timeout_seconds=appear_timeout_seconds,
            poll_seconds=poll_seconds,
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


def wait_for_exact_app_window_close(
    *,
    process: subprocess.Popen | None = None,
    capture_windows_fn: Callable[
        [], tuple[WebappWindowInfo, ...] | None
    ] = capture_rolethread_webapp_windows,
    sleep_fn: Callable[[float], None] = time.sleep,
    appear_timeout_seconds: float = DEFAULT_WINDOW_APPEAR_TIMEOUT_SECONDS,
    poll_seconds: float = DEFAULT_WINDOW_POLL_SECONDS,
) -> WindowCloseDetectionResult:
    """Monitor one observed Edge app-window HWND until that exact handle closes."""

    # WEBAPP_LIFECYCLE_TODO: this exact-HWND monitor is the canonical shutdown
    # trigger for launcher-owned webapp sessions.
    deadline = time.monotonic() + appear_timeout_seconds
    target: WebappWindowInfo | None = None
    while time.monotonic() <= deadline:
        if process is not None and process.poll() is not None:
            return WindowCloseDetectionResult(
                supported=True,
                closed=True,
                observed=target is not None,
                message="Streamlit subprocess exited before app-window monitoring completed.",
                target_handle=target.handle if target else "",
                target_pid=target.pid if target else None,
                target_title=target.title if target else "",
            )
        windows = capture_windows_fn()
        if windows is None:
            return WindowCloseDetectionResult(
                supported=False,
                closed=False,
                observed=target is not None,
                message="Windows app-window detection was unavailable.",
                target_handle=target.handle if target else "",
                target_pid=target.pid if target else None,
                target_title=target.title if target else "",
            )
        if windows:
            candidate = sorted(windows, key=lambda item: item.handle)[0]
            sleep_fn(poll_seconds)
            stable_windows = capture_windows_fn()
            if stable_windows is None:
                return WindowCloseDetectionResult(
                    supported=False,
                    closed=False,
                    observed=False,
                    message="Windows app-window detection became unavailable while selecting a stable target.",
                    target_handle=candidate.handle,
                    target_pid=candidate.pid,
                    target_title=candidate.title,
                )
            stable_handles = {window.handle for window in stable_windows}
            if candidate.handle in stable_handles:
                target = candidate
                break
            continue
        sleep_fn(poll_seconds)

    if target is None:
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
                target_handle=target.handle,
                target_pid=target.pid,
                target_title=target.title,
            )
        windows = capture_windows_fn()
        if windows is None:
            return WindowCloseDetectionResult(
                supported=False,
                closed=False,
                observed=True,
                message="Windows app-window detection became unavailable.",
                target_handle=target.handle,
                target_pid=target.pid,
                target_title=target.title,
            )
        active_handles = {window.handle for window in windows}
        if target.handle not in active_handles:
            return WindowCloseDetectionResult(
                supported=True,
                closed=True,
                observed=True,
                message="RoleThread app-window handle closed.",
                target_handle=target.handle,
                target_pid=target.pid,
                target_title=target.title,
            )
        sleep_fn(poll_seconds)


def request_graceful_shutdown(
    config: LauncherConfig,
    *,
    urlopen: Callable[..., object] = request.urlopen,
    timeout_seconds: float = 5.0,
) -> ShutdownRequestResult:
    """Request local launcher-controlled app shutdown."""

    # WEBAPP_LIFECYCLE_TODO: keep graceful shutdown scoped to the local tokened
    # control channel; fallback termination must target only this launcher-owned
    # subprocess.
    if not config.shutdown_port or not config.shutdown_token:
        return ShutdownRequestResult(
            attempted=False,
            ok=False,
            status_code=None,
            message="No shutdown control channel was configured.",
        )
    url = build_launcher_shutdown_url(port=config.shutdown_port)
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

    # WEBAPP_LIFECYCLE_TODO: this fallback is intentionally process-object
    # scoped. It must not become port-owner, Edge, or arbitrary Python cleanup.
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
    port_release_fn: Callable[[int | None], PortReleaseStatus] | None = None,
    edge_launch_fn: Callable[[], EdgeLaunchResult] = launch_edge_webapp_window,
    pending_browser_reset_fn: Callable[[], object] | None = None,
    status_callback: LifecycleStatusCallback | None = None,
) -> LauncherLifecycleResult:
    """Delegate launcher-owned lifecycle orchestration to shared core code."""

    close_waiter = wait_for_close_fn or (
        lambda mode, process: wait_for_app_window_close(mode, process=process)
    )
    reset_consumer = pending_browser_reset_fn or (
        lambda: consume_pending_webapp_browser_state_reset(
            app_data_root=config.preferences_path.parent,
        )
    )
    release_checker = port_release_fn or (
        lambda owner_pid: check_port_release_status(owned_pid=owner_pid)
    )
    return run_shared_launcher_lifecycle(
        config,
        launch_backend_fn=lambda lifecycle_config: launch_rolethread(
            lifecycle_config,
            popen=popen,
            port_available_fn=port_available_fn,
        ),
        health_check_fn=health_check_fn,
        wait_for_close_fn=close_waiter,
        shutdown_request_fn=shutdown_request_fn,
        termination_fn=termination_fn,
        port_release_fn=release_checker,
        edge_launch_fn=edge_launch_fn,
        pending_browser_reset_fn=reset_consumer,
        write_log_fn=write_launcher_log,
        format_command_fn=format_command,
        wait_for_process_exit_fn=lambda process: wait_for_process_exit(
            process,
            timeout_seconds=DEFAULT_SHUTDOWN_TIMEOUT_SECONDS,
        ),
        webapp_launch_mode=LAUNCH_MODE_WEBAPP,
        status_callback=status_callback,
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
