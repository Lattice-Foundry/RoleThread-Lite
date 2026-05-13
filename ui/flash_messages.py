"""Shared Streamlit flash-message queue helpers."""
from __future__ import annotations

import streamlit as st

_FLASH_KEY = "_flash_messages"


def enqueue_flash(level: str, message: str) -> None:
    """Queue a flash message for the next page render."""

    if not message:
        return
    messages = list(st.session_state.get(_FLASH_KEY, []))
    messages.append((level, message))
    st.session_state[_FLASH_KEY] = messages


def enqueue_dataset_result_flash(message: str, result) -> None:
    """Queue a success plus sidecar warning for a dataset operation result."""

    enqueue_flash("success", message)
    if getattr(result, "sidecar_ok", True):
        return
    detail = getattr(result, "sidecar_message", None)
    warning = "Dataset saved successfully but registry sidecar could not be updated."
    if detail:
        warning = f"{warning} {detail}"
    enqueue_flash("warning", warning)


def render_flash_messages() -> None:
    """Render and clear queued flash messages."""

    messages = list(st.session_state.pop(_FLASH_KEY, []) or [])
    for level, message in messages:
        if level == "success":
            st.success(message)
        elif level == "warning":
            st.warning(message)
        elif level == "error":
            st.error(message)
        else:
            st.info(message)
