"""LoreForge Lite Streamlit entry point.

Owns app startup and session initialization. Navigation wiring and page-state
compatibility live in ui.navigation.
"""
import atexit
from pathlib import Path
import time

import streamlit as st
from streamlit import config as st_config

from core.launch import (
    attempt_webapp_launch,
    capture_edge_process_snapshot,
    capture_edge_process_snapshot_poll,
    capture_edge_window_snapshot,
    close_duplicate_edge_browser_window,
    diff_edge_process_snapshots,
    diff_edge_window_snapshots,
    get_webapp_launch_guidance,
    should_attempt_webapp_launch,
    should_show_dev_diagnostics,
    parse_launch_flags,
)
from core.runtime import get_python_runtime_status

st.set_page_config(page_title="LoreForge Lite", layout="wide")

_runtime_status = get_python_runtime_status()
if _runtime_status.is_below_minimum:
    st.error(_runtime_status.message)
    st.stop()
if _runtime_status.is_newer_than_tested:
    st.warning(_runtime_status.message)


def _get_streamlit_headless_config() -> bool | None:
    try:
        return bool(st_config.get_option("server.headless"))
    except Exception:
        return None


_launch_flags = parse_launch_flags()
st.session_state["_runtime_launch_flags"] = _launch_flags
st.session_state["_dev_mode"] = should_show_dev_diagnostics(_launch_flags)
if _launch_flags.webapp:
    if _launch_flags.dev:
        st.session_state["_dev_webapp_launch_guidance"] = get_webapp_launch_guidance(
            _launch_flags,
            streamlit_headless=_get_streamlit_headless_config(),
        )
    _should_attempt_webapp_launch = should_attempt_webapp_launch(
        _launch_flags,
        already_attempted=bool(st.session_state.get("_dev_webapp_launch_attempted")),
    )
    if _should_attempt_webapp_launch:
        _edge_before = capture_edge_process_snapshot()
        _edge_windows_before = capture_edge_window_snapshot()
        st.session_state["_dev_webapp_launch_attempted"] = True
        st.session_state["_dev_webapp_launch_status"] = attempt_webapp_launch(_launch_flags)
        if st.session_state["_dev_webapp_launch_status"].launched:
            time.sleep(0.4)
            _edge_poll = capture_edge_process_snapshot_poll()
            _edge_after = _edge_poll.snapshot
            _edge_windows_after = capture_edge_window_snapshot()
            _edge_diff = diff_edge_process_snapshots(_edge_before, _edge_after)
            _edge_window_diff = diff_edge_window_snapshots(
                _edge_windows_before,
                _edge_windows_after,
            )
            st.session_state["_dev_edge_snapshot_poll"] = _edge_poll
            if _launch_flags.edge_debug:
                st.session_state["_dev_edge_debug_report"] = _edge_diff
                st.session_state["_dev_edge_window_debug_report"] = _edge_window_diff
            st.session_state["_dev_edge_cleanup_status"] = close_duplicate_edge_browser_window(
                _launch_flags,
                _edge_diff,
                window_diff=_edge_window_diff,
            )
            _cleanup_status = st.session_state["_dev_edge_cleanup_status"]
            if _launch_flags.dev:
                print(
                    "LoreForge Edge cleanup: "
                    f"status={_cleanup_status.status_code}; "
                    f"attempted={_cleanup_status.attempted}; "
                    f"method={_cleanup_status.method}; "
                    f"target={_cleanup_status.target_pid}; "
                    f"result={_cleanup_status.result}; "
                    f"message={_cleanup_status.message}"
                )

from core.cloud_sync import (
    get_cloud_restore_candidate,
    restore_cloud_backup,
    sync_configured_backups_to_cloud,
)
from core.dataset import DEFAULT_SYSTEM_PROMPT, load_dataset_with_summary
from core.preferences import load_preferences
from ui.session_state import (
    persist_loaded_normalization,
    set_loaded_entries,
    should_persist_loaded_normalization,
)
from ui.navigation import (
    PAGE_CHARACTER_MANAGEMENT,
    PAGE_CREATE_ENTRY,
    PAGE_EDIT_ENTRIES,
    PAGE_EXPORT,
    PAGE_FAQ,
    PAGE_HELP,
    PAGE_INSIGHTS,
    PAGE_MANAGE_DATASET,
    PAGE_MERGE_DATASETS,
    PAGE_SETTINGS,
    PAGE_SYSTEM_PROMPTS,
    PAGE_TAG_MANAGEMENT,
    PAGE_VALIDATION,
    get_default_page,
    render_navigation,
    set_current_page,
)
from core.storage import ensure_app_directories
from core.tag_registry import seed_default_tags
from ui.browser_helpers import DEFAULT_PAGE_SIZE, MATCH_MODE_ANY
from ui.ui_character_management import render_character_management_page
from ui.ui_create import init_editor_state, render_create_page
from ui.ui_edit_entries import render_edit_entries_page
from ui.ui_export import render_export_page
from ui.ui_faq import render_faq_page
from ui.ui_help import render_help_page
from ui.ui_tag_management import render_tag_management_page
from ui.manage import render_manage_page
from ui.ui_merge import render_merge_page
from ui.ui_settings import render_settings_page
from ui.ui_stats import render_stats_page
from ui.ui_system_prompts import render_system_prompts_page
from ui.ui_validation import render_validation_page
from ui.theme import (
    COLOR_WARNING_ACCENT,
    COLOR_WARNING_BACKGROUND,
    COLOR_WARNING_TEXT,
    COLOR_PRIMARY,
    COLOR_PRIMARY_ACTIVE,
    COLOR_PRIMARY_HOVER,
    COLOR_PRIMARY_HOVER_BACKGROUND,
    COLOR_SIDEBAR_BACKGROUND,
    COLOR_SIDEBAR_BUTTON_BORDER,
    COLOR_SIDEBAR_BUTTON_TEXT,
    COLOR_SUBTITLE,
)

# ── Page config ────────────────────────────────────────────────────────────────
ensure_app_directories()

st.markdown(f"""
<style>
/* Sidebar gets its own graphite shade, separate from input/card grey. */
section[data-testid="stSidebar"],
section[data-testid="stSidebar"] > div {{
    background-color: {COLOR_SIDEBAR_BACKGROUND} !important;
}}
/* Sidebar shell branding. */
.loreforge-sidebar-brand {{
    align-items: center;
    display: flex;
    gap: 0.72rem;
    justify-content: center;
    margin: 0.35rem 0 1.35rem 0;
    padding-bottom: 0.3rem;
}}
.loreforge-sidebar-logo {{
    flex: 0 0 auto;
    height: 4.55rem;
    width: 4.55rem;
}}
.loreforge-sidebar-copy {{
    min-width: 0;
    text-align: left;
}}
.loreforge-sidebar-title {{
    color: {COLOR_PRIMARY};
    font-size: 1.5rem;
    font-weight: 800;
    line-height: 1.05;
    margin: 0;
}}
.loreforge-sidebar-subtitle {{
    color: {COLOR_SUBTITLE};
    font-size: 0.82rem;
    font-weight: 540;
    letter-spacing: 0;
    line-height: 1.25;
    margin-top: 0.24rem;
}}
/* Native top navigation: align hover/current indicators with LoreForge mint. */
div[data-testid="stTopNavLinkContainer"]:hover,
div[data-testid="stTopNavLinkContainer"]:has(a[aria-current="page"]),
a[data-testid="stTopNavLink"]:hover,
a[data-testid="stTopNavLink"][aria-current="page"],
a[data-testid="stTopNavDropdownLink"]:hover,
a[data-testid="stTopNavDropdownLink"][aria-current="page"] {{
    background-color: {COLOR_PRIMARY_HOVER_BACKGROUND} !important;
    color: {COLOR_PRIMARY} !important;
}}
a[data-testid="stTopNavLink"][aria-current="page"],
a[data-testid="stTopNavDropdownLink"][aria-current="page"] {{
    box-shadow: inset 0 -2px 0 {COLOR_PRIMARY} !important;
}}
/* Primary button — enabled state only (:not(:disabled) keeps disabled grey) */
button[data-testid="baseButton-primary"]:not(:disabled),
button[kind="primary"]:not(:disabled),
.stButton > button[type="submit"]:not(:disabled),
.stButton > button:not([kind="secondary"]):not([kind="tertiary"]):not(:disabled) {{
    background-color: {COLOR_PRIMARY} !important;
    border-color: {COLOR_PRIMARY_HOVER} !important;
    color: white !important;
}}
button[data-testid="baseButton-primary"]:not(:disabled):hover,
button[kind="primary"]:not(:disabled):hover,
.stButton > button[type="submit"]:not(:disabled):hover,
.stButton > button:not([kind="secondary"]):not([kind="tertiary"]):not(:disabled):hover {{
    background-color: {COLOR_PRIMARY_HOVER} !important;
    border-color: {COLOR_PRIMARY_ACTIVE} !important;
    color: white !important;
}}
/* Sidebar nav buttons: outline by default, mint fill for the active page. */
section[data-testid="stSidebar"] button[data-testid="baseButton-secondary"]:not(:disabled),
section[data-testid="stSidebar"] button[kind="secondary"]:not(:disabled) {{
    background-color: transparent !important;
    border-color: {COLOR_SIDEBAR_BUTTON_BORDER} !important;
    color: {COLOR_SIDEBAR_BUTTON_TEXT} !important;
    box-shadow: none !important;
}}
section[data-testid="stSidebar"] button[data-testid="baseButton-secondary"]:not(:disabled):hover,
section[data-testid="stSidebar"] button[kind="secondary"]:not(:disabled):hover {{
    background-color: {COLOR_PRIMARY_HOVER_BACKGROUND} !important;
    border-color: {COLOR_PRIMARY} !important;
    color: {COLOR_PRIMARY_HOVER} !important;
}}
section[data-testid="stSidebar"] button[data-testid="baseButton-primary"]:not(:disabled),
section[data-testid="stSidebar"] button[kind="primary"]:not(:disabled) {{
    background-color: {COLOR_PRIMARY} !important;
    border-color: {COLOR_PRIMARY_HOVER} !important;
    color: white !important;
    box-shadow: none !important;
}}
section[data-testid="stSidebar"] button[data-testid="baseButton-primary"]:not(:disabled):hover,
section[data-testid="stSidebar"] button[kind="primary"]:not(:disabled):hover {{
    background-color: {COLOR_PRIMARY_HOVER} !important;
    border-color: {COLOR_PRIMARY_ACTIVE} !important;
    color: white !important;
}}
/* Alerts keep Streamlit's native shape, narrowed slightly for readability. */
div[data-testid="stAlert"] {{
    width: 75% !important;
    padding-right: 0.65rem !important;
}}
/* Manage Dataset recent-file rows: borderless, left-aligned, and compact. */
div.st-key-recent_dataset_list div[data-testid="stButton"] {{
    margin-bottom: -0.5rem !important;
}}
div.st-key-recent_dataset_list button[data-testid="baseButton-tertiary"],
div.st-key-recent_dataset_list button[kind="tertiary"] {{
    justify-content: flex-start !important;
    min-height: 1.65rem !important;
    padding: 0.05rem 0.35rem !important;
    text-align: left !important;
    width: auto !important;
    max-width: 100% !important;
}}
div.st-key-recent_dataset_list button[data-testid="baseButton-tertiary"] p,
div.st-key-recent_dataset_list button[kind="tertiary"] p {{
    text-align: left !important;
    white-space: normal !important;
    overflow-wrap: anywhere !important;
}}
/* Warning alerts only — replace Streamlit's muddy yellow-green default. */
div[data-testid="stAlert"]:has(div[data-testid="stAlertContentWarning"]) {{
    background-color: {COLOR_WARNING_BACKGROUND} !important;
    border-color: transparent !important;
    border-left: 0 !important;
}}
div[data-testid="stAlert"] div[data-testid="stAlertContentWarning"],
div[data-testid="stAlert"] div[data-baseweb="notification"][kind="warning"] {{
    background-color: transparent !important;
    color: inherit !important;
}}
div[data-testid="stAlert"]:has(div[data-testid="stAlertContentWarning"]) svg {{
    color: {COLOR_WARNING_ACCENT} !important;
    fill: {COLOR_WARNING_ACCENT} !important;
}}
/* Streamlit nests warning notifications differently across versions; flatten the
   inner surface so warnings match the cleaner success/info/error shape. */
div[data-testid="stAlert"]:has([data-testid="stAlertContentWarning"]) {{
    background-color: {COLOR_WARNING_BACKGROUND} !important;
    background: {COLOR_WARNING_BACKGROUND} !important;
    border-color: transparent !important;
    border-left: 0 !important;
    border-radius: 0.45rem !important;
    box-shadow: none !important;
    overflow: hidden !important;
}}
div[data-testid="stAlert"]:has([data-testid="stAlertContentWarning"]) > div,
div[data-testid="stAlert"]:has([data-testid="stAlertContentWarning"]) [data-baseweb="notification"],
div[data-testid="stAlert"]:has([data-testid="stAlertContentWarning"]) [role="alert"],
div[data-testid="stAlert"] [data-testid="stAlertContentWarning"] {{
    background-color: transparent !important;
    background: transparent !important;
    border: 0 !important;
    box-shadow: none !important;
    color: inherit !important;
}}
div[data-testid="stAlert"]:has([data-testid="stAlertContentWarning"]) * {{
    background-color: transparent !important;
    background: transparent !important;
    box-shadow: none !important;
}}
div[data-testid="stAlert"]:has([data-testid="stAlertContentWarning"]) [data-testid="stAlertContentWarning"] *,
div[data-testid="stAlert"]:has([data-testid="stAlertContentWarning"]) [data-baseweb="notification"] * {{
    background-color: transparent !important;
    background: transparent !important;
}}
div[data-testid="stAlert"] [data-testid="stAlertContentWarning"] {{
    color: {COLOR_WARNING_TEXT} !important;
}}
/* Expander chevrons act as row arrows in dataset browsers. */
div[data-testid="stExpander"] details summary svg,
div[data-testid="stExpander"] details summary [data-testid="stExpanderToggleIcon"],
div[data-testid="stExpander"] details summary [data-testid="stExpanderToggleIcon"] svg,
div[data-testid="stExpander"] details summary button svg,
div[data-testid="stExpander"] details summary > span > :first-child,
div[data-testid="stExpander"] details summary > span > :first-child * {{
    color: {COLOR_PRIMARY} !important;
    fill: {COLOR_PRIMARY} !important;
    stroke: {COLOR_PRIMARY} !important;
}}
/* Dropdown chevrons use BaseWeb select icons; keep them aligned with entry arrows. */
div[data-baseweb="select"] [aria-hidden="true"] svg,
div[data-baseweb="select"] svg[title="open"],
div[data-testid="stSelectbox"] div[data-baseweb="select"] svg,
div[data-testid="stMultiSelect"] div[data-baseweb="select"] svg {{
    color: {COLOR_PRIMARY} !important;
    fill: {COLOR_PRIMARY} !important;
    stroke: {COLOR_PRIMARY} !important;
}}
/* Dropdown option hover/highlight only; button hover styling remains separate. */
div[data-baseweb="popover"] div[role="option"]:hover,
div[data-baseweb="popover"] li[role="option"]:hover,
div[data-baseweb="popover"] div[role="option"][aria-selected="true"],
div[data-baseweb="popover"] li[role="option"][aria-selected="true"],
div[data-baseweb="menu"] div[role="option"]:hover,
div[data-baseweb="menu"] li[role="option"]:hover,
div[data-baseweb="menu"] div[role="option"][aria-selected="true"],
div[data-baseweb="menu"] li[role="option"][aria-selected="true"] {{
    background-color: {COLOR_PRIMARY_HOVER_BACKGROUND} !important;
    color: {COLOR_PRIMARY} !important;
}}
</style>
""", unsafe_allow_html=True)


def _render_dev_webapp_launch_status_once() -> None:
    """Show the dev web-app launch status without cluttering every rerun."""

    status = st.session_state.get("_dev_webapp_launch_status")
    guidance = st.session_state.get("_dev_webapp_launch_guidance")
    if st.session_state.get("_dev_webapp_launch_status_rendered"):
        return
    if status is not None:
        if status.launched:
            st.success(status.message)
        else:
            st.info(status.message)
    if guidance is not None and guidance.warning:
        st.warning(guidance.message)
    if status is None and guidance is None:
        return
    st.session_state["_dev_webapp_launch_status_rendered"] = True


_render_dev_webapp_launch_status_once()

# ── Cloud backup startup hooks ────────────────────────────────────────────────
def _sync_cloud_backups_on_exit() -> None:
    """Best-effort cloud backup sync for Streamlit process shutdown."""

    result = sync_configured_backups_to_cloud()
    if not result.ok:
        print(result.message)


def _register_cloud_sync_on_exit() -> None:
    if st.session_state.get("_cloud_sync_atexit_registered"):
        return
    atexit.register(_sync_cloud_backups_on_exit)
    st.session_state["_cloud_sync_atexit_registered"] = True


def _render_cloud_restore_prompt() -> None:
    candidate = st.session_state.get("_cloud_restore_candidate")
    if candidate is None and not st.session_state.get("_cloud_restore_checked"):
        candidate_path = get_cloud_restore_candidate()
        st.session_state["_cloud_restore_checked"] = True
        if candidate_path is not None:
            candidate = str(candidate_path)
            st.session_state["_cloud_restore_candidate"] = candidate

    if not candidate or st.session_state.get("_cloud_restore_dismissed"):
        return

    st.info(f"Found LoreForge backup data at `{candidate}`. Restore settings and registry?")
    restore_col, skip_col = st.columns([1, 1])
    with restore_col:
        if st.button("Restore Cloud Backup", key="_restore_cloud_backup"):
            result = restore_cloud_backup(candidate)
            if result.ok:
                st.success(result.message)
                st.session_state["_cloud_restore_dismissed"] = True
                st.rerun()
            else:
                st.warning(result.message)
                for error in result.errors:
                    st.caption(error)
    with skip_col:
        if st.button("Skip Restore", key="_skip_cloud_restore"):
            st.session_state["_cloud_restore_dismissed"] = True
            st.rerun()


_register_cloud_sync_on_exit()
_render_cloud_restore_prompt()


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
    st.session_state.confirm_delete_entries = prefs.get("confirm_delete_entries", True)
    st.session_state.edit_entry_page = 0
    st.session_state.edit_entries_per_page = DEFAULT_PAGE_SIZE
    st.session_state.edit_filter_tags = []
    st.session_state.edit_filter_only_used = True
    st.session_state.edit_filter_match_mode = MATCH_MODE_ANY
    st.session_state.edit_entries_mode = "browser"
    init_editor_state("create")
    st.session_state.preview_user_name = prefs.get("preview_user_name", "Scott")
    st.session_state.preview_assistant_name = prefs.get("preview_assistant_name", "Nicole")
    st.session_state.default_dataset_directory = prefs.get("default_dataset_directory", "")
    st.session_state.auto_backups_enabled = prefs.get("auto_backups_enabled", True)
    st.session_state.backup_directory = prefs.get("backup_directory", "")
    st.session_state.backups_per_dataset = prefs.get("backups_per_dataset", 25)
    st.session_state.backup_destination_type = prefs.get(
        "backup_destination_type",
        "local",
    )
    st.session_state.backup_destination_custom_path = prefs.get(
        "backup_destination_custom_path",
        "",
    )
    st.session_state.auto_correct_validation_errors = prefs.get(
        "auto_correct_validation_errors",
        # Compatibility fallback for preference files created before the
        # validation setting was renamed from "auto normalize on load".
        prefs.get("auto_normalize_on_load", True),
    )
    set_current_page(get_default_page())

    last = prefs.get("last_loaded_dataset_path", "")
    if last:
        if Path(last).exists():
            normalization, errors = load_dataset_with_summary(
                last,
                auto_normalize=st.session_state.get(
                    "auto_correct_validation_errors",
                    True,
                ),
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
                if should_persist_loaded_normalization(
                    parse_errors=errors,
                    normalization_pending=st.session_state.get(
                        "normalization_pending",
                        False,
                    ),
                ):
                    persist_loaded_normalization(loaded_dataset_path)
        else:
            st.session_state.stale_last_path = last


# ── Navigation ─────────────────────────────────────────────────────────────────
_PAGE_RENDERERS = {
    PAGE_CREATE_ENTRY: render_create_page,
    PAGE_MANAGE_DATASET: render_manage_page,
    PAGE_EDIT_ENTRIES: render_edit_entries_page,
    PAGE_MERGE_DATASETS: render_merge_page,
    PAGE_EXPORT: render_export_page,
    PAGE_VALIDATION: render_validation_page,
    PAGE_TAG_MANAGEMENT: render_tag_management_page,
    PAGE_CHARACTER_MANAGEMENT: render_character_management_page,
    PAGE_SYSTEM_PROMPTS: render_system_prompts_page,
    PAGE_INSIGHTS: render_stats_page,
    PAGE_SETTINGS: render_settings_page,
    PAGE_HELP: render_help_page,
    PAGE_FAQ: render_faq_page,
}
render_navigation(_PAGE_RENDERERS)
