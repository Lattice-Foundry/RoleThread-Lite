"""Windows launcher prototype for LoreForge Lite.

This source module is intended to be wrapped by PyInstaller in a later pass.
It does not implement final installer integration, shortcut creation, or
complete shutdown lifecycle management yet.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import subprocess
import sys
from typing import Callable, Sequence


APP_NAME = "LoreForge Lite"
APP_DATA_DIR_NAME = "LoreForge"
PREFERENCES_FILE_NAME = "preferences.json"
LAUNCHER_LOG_FILE_NAME = "launcher.log"
STREAMLIT_PORT = "8501"
STREAMLIT_ARGS = (
    "-m",
    "streamlit",
    "run",
    "app.py",
    "--server.port",
    STREAMLIT_PORT,
)
LAUNCH_MODE_NORMAL = "normal"
LAUNCH_MODE_WEBAPP = "webapp"
WEBAPP_PREFERENCE_KEY = "enable_webapp_launch_mode"


@dataclass(frozen=True)
class LauncherConfig:
    app_root: Path
    python_path: Path
    preferences_path: Path
    log_path: Path
    launch_mode: str
    command: tuple[str, ...]


class LauncherConfigurationError(RuntimeError):
    """Raised when the launcher cannot construct a runnable command."""


def resolve_app_root(
    *,
    start_path: Path | None = None,
    frozen: bool | None = None,
) -> Path:
    """Resolve the LoreForge app root for dev mode, with bundled mode left explicit."""

    is_frozen = bool(getattr(sys, "frozen", False)) if frozen is None else frozen
    if is_frozen:
        # Future bundled builds can adjust this if PyInstaller layout differs.
        return Path(sys.executable).resolve().parent

    current = Path(start_path or Path(__file__)).resolve()
    candidates = [current, *current.parents]
    for candidate in candidates:
        if (candidate / "app.py").is_file():
            return candidate
    return Path.cwd().resolve()


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
) -> Path:
    dev_runtime = app_root / "trainer" / "Scripts" / "python.exe"
    if dev_runtime.is_file():
        return dev_runtime

    fallback = Path(current_executable or sys.executable)
    if fallback.is_file():
        return fallback

    raise LauncherConfigurationError(
        "Could not find a usable Python runtime. Expected trainer\\Scripts\\python.exe "
        "or a valid current Python executable."
    )


def build_streamlit_command(python_path: Path, *, launch_mode: str) -> tuple[str, ...]:
    command: tuple[str, ...] = (str(python_path), *STREAMLIT_ARGS)
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
) -> LauncherConfig:
    resolved_root = Path(app_root).resolve() if app_root is not None else resolve_app_root()
    preferences_path = resolve_preferences_path(env)
    log_path = resolve_launcher_log_path(env)
    python_path = resolve_python_runtime(
        resolved_root,
        current_executable=current_executable,
    )
    launch_mode = select_launch_mode(
        enable_webapp_launch_mode=read_enable_webapp_launch_mode(preferences_path),
    )
    command = build_streamlit_command(python_path, launch_mode=launch_mode)
    return LauncherConfig(
        app_root=resolved_root,
        python_path=python_path,
        preferences_path=preferences_path,
        log_path=log_path,
        launch_mode=launch_mode,
        command=command,
    )


def write_launcher_log(log_path: Path, lines: Sequence[str]) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().isoformat(timespec="seconds")
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"[{timestamp}] {APP_NAME} launcher\n")
        for line in lines:
            handle.write(f"{line}\n")
        handle.write("\n")


def format_command(command: Sequence[str]) -> str:
    return " ".join(f'"{part}"' if " " in part else part for part in command)


def launch_loreforge(
    config: LauncherConfig,
    *,
    popen: Callable[..., subprocess.Popen] = subprocess.Popen,
) -> subprocess.Popen:
    write_launcher_log(
        config.log_path,
        (
            f"app_root={config.app_root}",
            f"python_path={config.python_path}",
            f"preferences_path={config.preferences_path}",
            f"launch_mode={config.launch_mode}",
            f"command={format_command(config.command)}",
        ),
    )
    # Future pass: own subprocess lifecycle, browser/window close detection,
    # graceful shutdown, and forceful termination fallback if needed.
    return popen(config.command, cwd=config.app_root)


def main() -> int:
    try:
        config = build_launcher_config()
        print(f"Starting {APP_NAME} in {config.launch_mode} mode...")
        print(format_command(config.command))
        launch_loreforge(config)
        return 0
    except Exception as exc:
        try:
            log_path = resolve_launcher_log_path()
            write_launcher_log(log_path, (f"error={exc}",))
            print(f"Launcher error: {exc}")
            print(f"Details written to {log_path}")
        except Exception:
            print(f"Launcher error: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

