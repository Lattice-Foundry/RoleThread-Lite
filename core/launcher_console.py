"""Console formatting helpers for RoleThread launcher status output."""

from __future__ import annotations

import os
import re
import sys
from collections.abc import Mapping
from typing import TextIO


LAUNCHER_STATUS_PREFIX = "[RoleThread Launcher]"
ANSI_RESET = "\033[0m"
ANSI_MINT = "\033[38;2;79;198;154m"
ANSI_STREAMLIT_BLUE = "\033[38;2;28;131;225m"
ANSI_PATTERN = re.compile(r"\033\[[0-9;]*m")


def terminal_supports_ansi(
    stream: TextIO | None = None,
    env: Mapping[str, str] | None = None,
) -> bool:
    """Return whether launcher console output should include ANSI styling."""

    resolved_env = env if env is not None else os.environ
    if resolved_env.get("NO_COLOR"):
        return False
    if resolved_env.get("FORCE_COLOR"):
        return True
    resolved_stream = stream if stream is not None else sys.stdout
    isatty = getattr(resolved_stream, "isatty", None)
    if not callable(isatty) or not isatty():
        return False
    return resolved_env.get("TERM", "").lower() != "dumb"


def strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from formatted launcher output."""

    return ANSI_PATTERN.sub("", text)


def format_launcher_status(
    message: str,
    *,
    prefix: str = LAUNCHER_STATUS_PREFIX,
    color: bool | None = None,
    stream: TextIO | None = None,
    env: Mapping[str, str] | None = None,
) -> str:
    """Format one launcher status line with optional restrained ANSI styling."""

    use_color = terminal_supports_ansi(stream=stream, env=env) if color is None else color
    if not use_color:
        return f"{prefix} {message}"

    styled_prefix = f"{ANSI_MINT}{prefix}{ANSI_RESET}"
    label, separator, remainder = message.partition(":")
    if separator and label.strip() and "\n" not in label:
        styled_label = f"{ANSI_STREAMLIT_BLUE}{label}:{ANSI_RESET}"
        return f"{styled_prefix} {styled_label}{remainder}"
    return f"{styled_prefix} {message}"
