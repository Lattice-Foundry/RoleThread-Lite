"""Settings page."""
import streamlit as st

from state import _update_prefs


def render_settings_page() -> None:
    """Render the Settings page."""
    st.subheader("Dataset Format")

    def _persist_dataset_format():
        st.session_state.dataset_format = st.session_state["_dataset_format_select"]
        _update_prefs({"dataset_format": st.session_state.dataset_format})

    st.selectbox(
        "Default dataset format",
        options=["ChatML"],
        index=["ChatML"].index(st.session_state.dataset_format)
        if st.session_state.dataset_format in ["ChatML"] else 0,
        key="_dataset_format_select",
        on_change=_persist_dataset_format,
    )

    st.divider()
    st.subheader("Editing Safety")

    def _persist_confirm_delete():
        st.session_state.confirm_delete_entries = st.session_state["_confirm_delete_checkbox"]
        _update_prefs({"confirm_delete_entries": st.session_state.confirm_delete_entries})

    st.checkbox(
        "Confirm before deleting entries",
        value=st.session_state.get("confirm_delete_entries", True),
        key="_confirm_delete_checkbox",
        on_change=_persist_confirm_delete,
    )

    st.divider()
    st.subheader("Conversation Preview Settings")

    def _persist_preview_user_name():
        st.session_state.preview_user_name = st.session_state["_preview_user_name_input"]
        _update_prefs({"preview_user_name": st.session_state.preview_user_name})

    def _persist_preview_assistant_name():
        st.session_state.preview_assistant_name = st.session_state["_preview_assistant_name_input"]
        _update_prefs({"preview_assistant_name": st.session_state.preview_assistant_name})

    st.text_input(
        "User Name",
        value=st.session_state.preview_user_name,
        key="_preview_user_name_input",
        on_change=_persist_preview_user_name,
    )
    st.text_input(
        "Assistant Name",
        value=st.session_state.preview_assistant_name,
        key="_preview_assistant_name_input",
        on_change=_persist_preview_assistant_name,
    )
