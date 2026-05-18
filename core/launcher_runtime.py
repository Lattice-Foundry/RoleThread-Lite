"""Shared launcher runtime command and URL helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence


STREAMLIT_PORT = "8501"
STREAMLIT_HOST = "127.0.0.1"
STREAMLIT_HEALTH_PATH = "/_stcore/health"
LAUNCH_MODE_NORMAL = "normal"
LAUNCH_MODE_WEBAPP = "webapp"
STREAMLIT_MODULE_ARGS = (
    "-m",
    "streamlit",
    "run",
    "app.py",
)


def build_streamlit_command(
    python_path: Path,
    *,
    launch_mode: str,
    app_script: Path | None = None,
    internal_streamlit_flag: str | None = None,
    streamlit_host: str = STREAMLIT_HOST,
    streamlit_port: str = STREAMLIT_PORT,
) -> tuple[str, ...]:
    """Build a Streamlit command for launcher-owned dev or packaged runs."""

    if app_script is not None:
        if not internal_streamlit_flag:
            raise ValueError("Bundled Streamlit command requires an internal flag.")
        command_parts: tuple[str, ...] = (
            str(python_path),
            internal_streamlit_flag,
            str(app_script),
            "--global.developmentMode=false",
            "--server.port",
            streamlit_port,
        )
    else:
        command_parts = (
            str(python_path),
            *STREAMLIT_MODULE_ARGS,
            "--server.port",
            streamlit_port,
        )

    if launch_mode == LAUNCH_MODE_WEBAPP:
        return (
            *command_parts,
            "--server.address",
            streamlit_host,
            "--server.headless",
            "true",
            "--",
            "webapp",
        )
    if launch_mode == LAUNCH_MODE_NORMAL:
        return command_parts
    raise ValueError(f"Unknown launch mode: {launch_mode}")


def build_streamlit_health_url(
    *,
    host: str = STREAMLIT_HOST,
    port: str = STREAMLIT_PORT,
) -> str:
    """Build the local Streamlit health endpoint URL."""

    return f"http://{host}:{port}{STREAMLIT_HEALTH_PATH}"


def build_streamlit_app_url(
    *,
    host: str = STREAMLIT_HOST,
    port: str = STREAMLIT_PORT,
) -> str:
    """Build the local Streamlit app URL used by managed browser launch."""

    return f"http://{host}:{port}"


def build_launcher_shutdown_url(
    *,
    port: int,
    host: str = STREAMLIT_HOST,
) -> str:
    """Build the local launcher shutdown control URL."""

    return f"http://{host}:{port}/shutdown"


def format_command(command: Sequence[str]) -> str:
    """Format a command for console/debug output without shell execution."""

    return " ".join(f'"{part}"' if " " in part else part for part in command)
