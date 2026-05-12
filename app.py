"""LoreForge Streamlit entry point.

Owns app startup, session initialization, sidebar navigation, and page
dispatch. Page rendering belongs in ui modules.
"""
from pathlib import Path

import streamlit as st

from core.dataset import DEFAULT_SYSTEM_PROMPT, load_dataset_with_summary
from core.preferences import load_preferences
from ui.session_state import clear_entry_edit_state, set_loaded_entries
from core.storage import ensure_app_directories
from core.tag_registry import seed_default_tags
from ui.browser_helpers import DEFAULT_PAGE_SIZE, MATCH_MODE_ANY
from ui.ui_create import init_editor_state, render_create_page
from ui.ui_edit_entries import render_edit_entries_page
from ui.ui_export import render_export_page
from ui.ui_tag_management import render_tag_management_page
from ui.ui_manage import render_manage_page
from ui.ui_merge import render_merge_page
from ui.ui_settings import render_settings_page
from ui.ui_stats import render_stats_page
from ui.ui_validation import render_validation_page

# ── Page config ────────────────────────────────────────────────────────────────
ensure_app_directories()
st.set_page_config(page_title="LoreForge", layout="wide")

st.markdown(
    "<h1 style='color:#1a73e8'>LoreForge — Narrative Intelligence Studio</h1>",
    unsafe_allow_html=True,
)

st.markdown("""
<style>
/* Primary button — enabled state only (:not(:disabled) keeps disabled grey) */
button[data-testid="baseButton-primary"]:not(:disabled),
button[kind="primary"]:not(:disabled),
.stButton > button[type="submit"]:not(:disabled),
.stButton > button:not([kind="secondary"]):not([kind="tertiary"]):not(:disabled) {
    background-color: #1a73e8 !important;
    border-color: #1565c0 !important;
    color: white !important;
}
button[data-testid="baseButton-primary"]:not(:disabled):hover,
button[kind="primary"]:not(:disabled):hover,
.stButton > button[type="submit"]:not(:disabled):hover,
.stButton > button:not([kind="secondary"]):not([kind="tertiary"]):not(:disabled):hover {
    background-color: #1565c0 !important;
    border-color: #0d47a1 !important;
    color: white !important;
}
/* Active sidebar nav button — blue text, no background fill.
   More specific selector overrides the general primary-button rule above. */
section[data-testid="stSidebar"] button[data-testid="baseButton-primary"]:not(:disabled),
section[data-testid="stSidebar"] button[kind="primary"]:not(:disabled) {
    background-color: transparent !important;
    border-color: transparent !important;
    color: #1a73e8 !important;
    box-shadow: none !important;
}
section[data-testid="stSidebar"] button[data-testid="baseButton-primary"]:not(:disabled):hover,
section[data-testid="stSidebar"] button[kind="primary"]:not(:disabled):hover {
    background-color: rgba(26, 115, 232, 0.08) !important;
    border-color: transparent !important;
    color: #1565c0 !important;
}
</style>
""", unsafe_allow_html=True)

# ── One-time session initialisation ───────────────────────────────────────────
if "prefs" not in st.session_state:
    prefs = load_preferences()
    st.session_state.prefs = prefs

    try:
        seed_default_tags()
    except Exception as _seed_exc:
        st.warning(f"Tag database initialisation failed: {_seed_exc}")

    st.session_state.system_prompt = prefs.get("last_system_prompt") or DEFAULT_SYSTEM_PROMPT
    set_loaded_entries([])
    st.session_state.loaded_path = ""
    st.session_state.stale_last_path = ""
    st.session_state.entry_page = 0
    st.session_state.entries_per_page = DEFAULT_PAGE_SIZE
    st.session_state.filter_tags = []
    st.session_state.filter_only_used = True
    st.session_state.filter_match_mode = MATCH_MODE_ANY
    st.session_state.selected_entry_ids = set()
    st.session_state.confirm_delete_entries = prefs.get("confirm_delete_entries", True)
    st.session_state.quick_edit_entry_id = None
    st.session_state.edit_entry_page = 0
    st.session_state.edit_entries_per_page = DEFAULT_PAGE_SIZE
    st.session_state.edit_filter_tags = []
    st.session_state.edit_filter_only_used = True
    st.session_state.edit_filter_match_mode = MATCH_MODE_ANY
    st.session_state.edit_entries_mode = "browser"
    st.session_state.editing_entry_id = None
    init_editor_state("create")
    st.session_state.preview_user_name = prefs.get("preview_user_name", "User")
    st.session_state.preview_assistant_name = prefs.get("preview_assistant_name", "Assistant")
    st.session_state.default_dataset_directory = prefs.get("default_dataset_directory", "")
    st.session_state.auto_backups_enabled = prefs.get("auto_backups_enabled", True)
    st.session_state.backup_directory = prefs.get("backup_directory", "")
    st.session_state.backups_per_dataset = prefs.get("backups_per_dataset", 25)
    st.session_state.auto_normalize_on_load = prefs.get("auto_normalize_on_load", True)
    st.session_state.page = "Create Entry"

    last = prefs.get("last_loaded_dataset_path", "")
    if last:
        if Path(last).exists():
            normalization, errors = load_dataset_with_summary(
                last,
                auto_normalize=st.session_state.get("auto_normalize_on_load", True),
            )
            if errors and not normalization.entries:
                st.warning(f"Could not reload last dataset: {errors[0]}")
            else:
                loaded_dataset_path = set_loaded_entries(
                    normalization.entries,
                    normalization_summary=normalization,
                    dataset_path=last,
                ) or last
                st.session_state.loaded_path = loaded_dataset_path
        else:
            st.session_state.stale_last_path = last


# ── Sidebar navigation ─────────────────────────────────────────────────────────
if "page" not in st.session_state:
    st.session_state.page = "Create Entry"

_page = st.session_state.page

_NAV_SECTIONS = [
    ("Create", [
        ("New Entry",       "Create Entry"),
    ]),
    ("Dataset", [
        ("Manage",          "Manage Dataset"),
        ("Merge",           "Merge Datasets"),
        ("Edit Entries",    "Edit Entries"),
    ]),
    ("Tools", [
        ("Export",          "Export"),
        ("Validate",        "Validation"),
        ("Tag Management",  "Tag Management"),
    ]),
    ("Analytics", [
        ("Statistics",      "Statistics"),
    ]),
    ("Settings", [
        ("Preferences",     "Settings"),
    ]),
]

for _sec_name, _sec_items in _NAV_SECTIONS:
    st.sidebar.markdown(f"**{_sec_name}**")
    for _display_label, _target in _sec_items:
        _btn_label = f"▶ {_display_label}" if _page == _target else _display_label
        if st.sidebar.button(
            _btn_label,
            key=f"_nav_{_target}",
            width="stretch",
            type="primary" if _page == _target else "secondary",
        ):
            if st.session_state.page == "Edit Entries" and _target != "Edit Entries":
                clear_entry_edit_state()
            st.session_state.page = _target
            st.rerun()

page = st.session_state.page


# ── Page dispatch ──────────────────────────────────────────────────────────────
if page == "Create Entry":
    render_create_page()
elif page == "Manage Dataset":
    render_manage_page()
elif page == "Edit Entries":
    render_edit_entries_page()
elif page == "Merge Datasets":
    render_merge_page()
elif page == "Export":
    render_export_page()
elif page == "Validation":
    render_validation_page()
elif page == "Tag Management":
    render_tag_management_page()
elif page == "Statistics":
    render_stats_page()
elif page == "Settings":
    render_settings_page()
