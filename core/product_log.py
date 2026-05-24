"""Plain-text product runtime log helpers."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
import os
from pathlib import Path
import re


APP_NAME = "RoleThread Lite"
PRODUCT_LOG_FILE_NAME = "launcher.log"
PRODUCT_LOG_PATH_ENV = "ROLETHREAD_LAUNCHER_LOG_PATH"
SOURCE_RUNTIME_EVENT_LOG_PATH = Path(".litlaunch") / "runtime-events.log"
ANSI_PATTERN = re.compile(r"\033\[[0-9;]*m")


def resolve_product_log_path_from_env(
    env: Mapping[str, str] | None = None,
) -> Path | None:
    """Return the product log path advertised to a managed backend process."""

    env_map = os.environ if env is None else env
    raw_path = str(env_map.get(PRODUCT_LOG_PATH_ENV) or "").strip()
    return Path(raw_path) if raw_path else None


def resolve_diagnostics_event_log_path(
    env: Mapping[str, str] | None = None,
) -> Path:
    """Return the event log path the Diagnostics page should inspect."""

    return resolve_product_log_path_from_env(env) or SOURCE_RUNTIME_EVENT_LOG_PATH


def write_product_log(log_path: Path, lines: Sequence[str]) -> None:
    """Append plain-text runtime diagnostics."""

    log_path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().isoformat(timespec="seconds")
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"[{timestamp}] {APP_NAME} runtime\n")
        for line in lines:
            handle.write(f"{strip_ansi(str(line))}\n")
        handle.write("\n")


def strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from formatted output."""

    return ANSI_PATTERN.sub("", text)
