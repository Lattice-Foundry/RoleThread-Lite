"""Shared launcher log helpers used by adapters and backend closeout hooks."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
import os
from pathlib import Path

from core.launcher_console import strip_ansi


APP_NAME = "RoleThread Lite"
LAUNCHER_LOG_FILE_NAME = "launcher.log"
LAUNCHER_LOG_PATH_ENV = "ROLETHREAD_LAUNCHER_LOG_PATH"


def resolve_launcher_log_path_from_env(
    env: Mapping[str, str] | None = None,
) -> Path | None:
    """Return the launcher log path advertised to a managed backend process."""

    env_map = os.environ if env is None else env
    raw_path = str(env_map.get(LAUNCHER_LOG_PATH_ENV) or "").strip()
    return Path(raw_path) if raw_path else None


def write_launcher_log(log_path: Path, lines: Sequence[str]) -> None:
    """Append plain-text launcher diagnostics without terminal styling."""

    log_path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().isoformat(timespec="seconds")
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"[{timestamp}] {APP_NAME} launcher\n")
        for line in lines:
            handle.write(f"{strip_ansi(str(line))}\n")
        handle.write("\n")
