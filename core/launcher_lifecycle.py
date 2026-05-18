"""Shared lifecycle status helpers for RoleThread launcher-owned runs."""

from __future__ import annotations

from collections.abc import Callable


LifecycleStatusCallback = Callable[[str], None]


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
