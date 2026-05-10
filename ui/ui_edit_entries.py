"""Streamlit page for full-entry editing.

This module owns edit buffers, browser state, and widgets. Durable full-edit
saves delegate to services.
"""
import streamlit as st

from core.backups import auto_backups_enabled
from core.dataset import (
    count_exchanges,
    filter_entry_pairs_by_tags,
    get_entry_tags,
    make_entry,
    validate_entry,
)
from core.tag_registry import (
    get_all_tag_slugs,
    get_tag_label_map,
    get_tag_registry_dict,
    prettify_tag_name,
)
from ui.session_state import (
    ensure_entry_registry,
    get_all_entry_pairs,
    get_loaded_entry_by_id,
    get_loaded_entry_index_by_id,
)
from services.dataset_service import save_full_edit_service
from ui.browser_helpers import (
    DEFAULT_PAGE_SIZE,
    MATCH_MODE_OPTIONS,
    PAGE_SIZE_OPTIONS,
    build_filter_tag_state,
    calculate_pagination,
    format_browser_status_caption,
    format_entry_summary_label,
    normalize_untagged_selection,
    slice_visible_pairs,
)
from ui.ui_components import (
    calculate_exchange_metrics,
    render_conversation_preview,
    render_json_preview,
    render_message_preview,
    render_tag_multiselects,
)
from ui.ui_create import render_turn_builder

_UNTAGGED = "__untagged__"

# Filter/page keys that must survive the browser → workspace → browser round-trip.
# Snapshotted on entry, restored on exit so Streamlit widget state is correct
# even if the browser widgets were not rendered during workspace mode.
_BROWSER_STATE_KEYS = (
    "edit_filter_tags",
    "edit_filter_only_used",
    "edit_filter_match_mode",
    "edit_entry_page",
    "edit_entries_per_page",
)


# ── Edit buffer helpers ────────────────────────────────────────────────────────

def entry_to_edit_buffer(entry: dict) -> dict:
    """Extract editable fields from an entry into a plain buffer dict."""
    msgs = entry.get("messages", [])
    if not isinstance(msgs, list):
        msgs = []

    system_prompt = ""
    turns: list[dict] = []
    for msg in msgs:
        if not isinstance(msg, dict):
            continue
        role = msg.get("role")
        content = msg.get("content", "")
        if role == "system" and not system_prompt:
            system_prompt = content
        elif role in ("user", "assistant"):
            turns.append({"role": role, "content": content})

    tags = get_entry_tags(entry)
    planned_exchanges = max(1, count_exchanges(entry))

    return {
        "system_prompt": system_prompt,
        "turns": turns,
        "tags": tags,
        "planned_exchanges": planned_exchanges,
    }


def load_full_edit_buffer(entry_id: str) -> bool:
    """Load entry data into full_edit_* session-state keys.

    Returns True on success, False if the entry cannot be found.
    Unknown tags (not found in any DB registry category) are stored separately
    in full_edit_unknown_tags and are never discarded.
    """
    entry = get_loaded_entry_by_id(entry_id)
    if entry is None:
        return False

    buf = entry_to_edit_buffer(entry)

    # ── Scalar keys ───────────────────────────────────────────────────────────
    st.session_state["full_edit_entry_id"] = entry_id
    st.session_state["full_edit_system_prompt"] = buf["system_prompt"]
    st.session_state["full_edit_turns"] = [{"role": t["role"]} for t in buf["turns"]]
    st.session_state["full_edit_planned_exchanges"] = buf["planned_exchanges"]

    # ── Per-turn content keys ─────────────────────────────────────────────────
    for i, turn in enumerate(buf["turns"]):
        st.session_state[f"full_edit_turn_{i}"] = turn["content"]

    # ── Tag category keys (DB-backed registry) ─────────────────────────────────
    _registry = get_tag_registry_dict()
    all_known: set[str] = set()
    for category, options in _registry.items():
        cat_tags = [t for t in buf["tags"] if t in options]
        st.session_state[f"full_edit_tags_{category}"] = cat_tags
        all_known.update(options)

    st.session_state["full_edit_unknown_tags"] = [
        t for t in buf["tags"] if t not in all_known
    ]

    return True


# ── Full-edit mode helpers ─────────────────────────────────────────────────────

def start_full_edit(entry_id: str) -> None:
    """Load edit buffer, snapshot browser state, enter workspace, and rerun.

    If the entry cannot be loaded, shows an inline error and does not enter
    workspace mode — the browser continues rendering normally below.
    """
    if not load_full_edit_buffer(entry_id):
        st.error(f"Could not load entry `{entry_id}` for editing.")
        return

    st.session_state["_ee_browser_snapshot"] = {
        k: st.session_state.get(k) for k in _BROWSER_STATE_KEYS
    }
    st.session_state.editing_entry_id = entry_id
    st.session_state.edit_entries_mode = "workspace"
    st.rerun()


def cancel_full_edit() -> None:
    """Clear the edit buffer, restore browser state, and return to browser mode."""
    # ── Clear fixed full_edit keys ─────────────────────────────────────────────
    for _k in (
        "full_edit_entry_id",
        "full_edit_system_prompt",
        "full_edit_turns",
        "full_edit_planned_exchanges",
        "full_edit_unknown_tags",
        "editing_entry_id",
    ):
        st.session_state.pop(_k, None)

    # ── Clear per-turn content keys ────────────────────────────────────────────
    for _k in [k for k in st.session_state if k.startswith("full_edit_turn_")]:
        del st.session_state[_k]

    # ── Clear per-category tag keys ────────────────────────────────────────────
    for _k in [k for k in st.session_state if k.startswith("full_edit_tags_")]:
        del st.session_state[_k]

    # ── Restore browser filter/page state ─────────────────────────────────────
    snapshot = st.session_state.pop("_ee_browser_snapshot", {})
    for _k, _v in snapshot.items():
        if _v is not None:
            st.session_state[_k] = _v

    st.session_state.edit_entries_mode = "browser"
    st.rerun()


def save_full_edit() -> bool:
    """Build the edited entry from the workspace buffer, validate, replace, and save.

    On success: sets flash message, clears buffer, returns to browser via
    cancel_full_edit() (which calls st.rerun() — the function never returns True
    in that path).  On any failure: shows an error, leaves workspace open,
    returns False.
    """
    entry_id = st.session_state.get("full_edit_entry_id") or st.session_state.get(
        "editing_entry_id"
    )
    if not entry_id:
        st.error("No entry selected for editing.")
        return False

    # ── Rebuild turns from live widget keys ────────────────────────────────────
    turns_now = [
        {
            "role": t["role"],
            "content": st.session_state.get(f"full_edit_turn_{i}", ""),
        }
        for i, t in enumerate(st.session_state.get("full_edit_turns", []))
    ]

    # ── Read system prompt and tags from live widget keys ──────────────────────
    system_prompt: str = st.session_state.get("full_edit_system_prompt", "")

    selected_tags: list[str] = []
    for _cat in get_tag_registry_dict():
        selected_tags.extend(st.session_state.get(f"full_edit_tags_{_cat}", []))
    unknown_tags: list[str] = st.session_state.get("full_edit_unknown_tags", [])

    # ── Build edited entry (does NOT mutate loaded_entries yet) ────────────────
    edited_entry = make_entry(
        turns=turns_now,
        system_prompt=system_prompt,
        tags=selected_tags + unknown_tags,
    )

    # ── Validate ───────────────────────────────────────────────────────────────
    errors = validate_entry(edited_entry)
    if errors:
        for err in errors:
            st.error(err)
        return False

    entry_index = get_loaded_entry_index_by_id(entry_id)
    if entry_index is None:
        st.error("Could not find the selected entry.")
        return False

    result = save_full_edit_service(
        dataset_path=st.session_state.get("loaded_path", ""),
        entries=st.session_state.loaded_entries,
        entry_index=entry_index,
        updated_entry=edited_entry,
        backup_enabled=auto_backups_enabled(st.session_state.get("prefs", {})),
    )
    if not result.ok:
        for err in result.errors:
            st.error(err)
        if not result.errors:
            st.error(result.message)
        return False

    if result.entries is not None:
        st.session_state.loaded_entries = result.entries
        ensure_entry_registry()

    # ── Success: flash message + cleanup + return to browser ──────────────────
    _backup_note = " Backup created." if result.backup_path else ""
    st.session_state["full_edit_success"] = f"{result.message}{_backup_note}"
    cancel_full_edit()  # clears buffer, restores browser state, calls st.rerun()
    return True          # unreachable after rerun, kept for type correctness


# ── Full edit workspace ────────────────────────────────────────────────────────

def render_full_edit_workspace() -> None:
    """Full-edit workspace rendered when edit_entries_mode == 'workspace'.

    Renders the system prompt, turn builder, conversation preview, tag
    selectors, JSON preview, planning warnings, and validation — all
    populated from the full_edit_* session-state buffer.  Includes Save Edits
    and Cancel / Back buttons.
    """
    entry_id = st.session_state.get("editing_entry_id")

    # ── Guard: no entry selected ───────────────────────────────────────────────
    if not entry_id:
        st.warning("No entry selected for editing.")
        if st.button("Back to Edit Entries", key="btn_back_no_id"):
            cancel_full_edit()
        return

    # ── Guard: entry disappeared from registry ─────────────────────────────────
    if get_loaded_entry_by_id(entry_id) is None:
        st.error("Selected entry could not be found.")
        if st.button("Back to Edit Entries", key="btn_back_not_found"):
            cancel_full_edit()
        return

    # ── Header ─────────────────────────────────────────────────────────────────
    st.subheader("Full Edit Entry")
    st.caption(f"Temp ID: {entry_id}")

    # ── System prompt ──────────────────────────────────────────────────────────
    st.divider()
    st.subheader("System Prompt")
    st.text_area(
        "System Prompt",
        key="full_edit_system_prompt",
        height=120,
        label_visibility="collapsed",
    )

    # ── Turn builder (includes planned exchanges input + turn text areas) ───────
    st.divider()
    turns_now = render_turn_builder("full_edit")

    # ── Conversation preview ───────────────────────────────────────────────────
    st.subheader("Conversation Preview")
    render_conversation_preview(turns_now, "full_edit")

    # ── Tags ───────────────────────────────────────────────────────────────────
    st.divider()
    st.subheader("Tag & Complete Exchange")
    selected_tags = render_tag_multiselects("full_edit")

    _unknown_tags: list[str] = st.session_state.get("full_edit_unknown_tags", [])
    if _unknown_tags:
        st.warning(
            "This entry contains unknown tags not currently in the tag registry: "
            + ", ".join(_unknown_tags)
        )

    # ── Planning metrics (needed for warnings + save gating) ──────────────────
    _planned_exchanges = st.session_state.get("full_edit_planned_exchanges", 1)
    _m = calculate_exchange_metrics(turns_now, _planned_exchanges)
    _current_exchanges = _m["current_exchanges"]

    # ── JSON preview + validation ──────────────────────────────────────────────
    _has_content = any(t["content"].strip() for t in turns_now)
    _entry_valid = False
    if _has_content:
        _entry_preview = make_entry(
            turns=turns_now,
            system_prompt=st.session_state.get("full_edit_system_prompt", ""),
            tags=selected_tags + _unknown_tags,
        )
        render_json_preview(_entry_preview, expanded=False)
        _errors = validate_entry(_entry_preview)
        if _errors:
            for _err in _errors:
                st.error(_err)
        else:
            st.success("Entry looks valid.")
            _entry_valid = True

    # ── Planning warnings (matches Create Entry messaging exactly) ─────────────
    if _planned_exchanges > 1 and _current_exchanges < _planned_exchanges:
        st.warning("You have not reached your planned number of exchanges yet.")
    if _m["overage"] > 0:
        st.info(
            f"You are {_m['overage']} exchange(s) over your planned count. "
            "You can still save this exchange."
        )
    if _planned_exchanges > 1 and _m["blank_pairs"] > 0:
        st.warning(
            f"{_m['blank_pairs']} exchange pair(s) have empty fields and will not be saved. "
            "Fill them in or remove them before completing."
        )

    # ── Save / Cancel ──────────────────────────────────────────────────────────
    st.divider()
    _col_save, _col_cancel = st.columns(2)
    with _col_save:
        if st.button(
            "Save Edits",
            key="btn_save_full_edit",
            type="primary",
            disabled=not _entry_valid or _current_exchanges < _planned_exchanges,
            width="stretch",
        ):
            save_full_edit()
    with _col_cancel:
        if st.button("Cancel / Back to Edit Entries", key="btn_cancel_full_edit",
                     width="stretch"):
            cancel_full_edit()


def render_edit_entries_page() -> None:
    """Render the Edit Entries page.

    Routes to the full-edit workspace when edit_entries_mode == 'workspace',
    otherwise renders the existing browser view.
    """
    ensure_entry_registry()

    if st.session_state.get("edit_entries_mode") == "workspace":
        render_full_edit_workspace()
        return

    _ee_entries = st.session_state.loaded_entries
    _ee_all_pairs = get_all_entry_pairs()

    if not _ee_all_pairs:
        st.info("Load a dataset in Manage Dataset to edit entries.")
        return

    st.subheader(f"Browse Entries ({len(_ee_all_pairs)})")

    if "full_edit_success" in st.session_state:
        st.success(st.session_state.pop("full_edit_success"))

    # ── Filter controls ────────────────────────────────────────────────────────
    # DB-backed label map and known-slug list for filter multiselect
    _ee_label_map = get_tag_label_map(untagged_key=_UNTAGGED)
    _ee_all_known_slugs = get_all_tag_slugs()

    def _ee_reset_page() -> None:
        st.session_state.edit_entry_page = 0

    def _ee_reset_page_and_selection() -> None:
        st.session_state.edit_entry_page = 0
        st.session_state.edit_filter_tags = []

    _ee_only_used = st.checkbox(
        "Only show used tags",
        key="edit_filter_only_used",
        on_change=_ee_reset_page_and_selection,
    )

    # Apply pending correction before the multiselect widget renders
    if "edit_filter_tags_pending" in st.session_state:
        st.session_state["edit_filter_tags"] = st.session_state.pop(
            "edit_filter_tags_pending"
        )

    _ee_filter_state = build_filter_tag_state(
        entries=_ee_entries,
        selected_tags=st.session_state.get("edit_filter_tags", []),
        only_used_tags=_ee_only_used,
        all_known_tags=_ee_all_known_slugs,
        untagged_key=_UNTAGGED,
    )
    _ee_available = _ee_filter_state.available_tags
    if _ee_filter_state.selected_tags_changed:
        st.session_state["edit_filter_tags"] = (
            _ee_filter_state.clamped_selected_tags
        )

    _ee_filter_col, _ee_mode_col = st.columns([3, 1])
    with _ee_filter_col:
        _ee_filter_tags = st.multiselect(
            "Filter entries by tag",
            options=_ee_available,
            # Known slugs → "Category / Pretty Name"; unknown slugs → prettified
            format_func=lambda x: _ee_label_map.get(x, prettify_tag_name(x)),
            key="edit_filter_tags",
            on_change=_ee_reset_page,
        )

    # Guard against "Select all" accidentally including __untagged__
    _ee_normalized_filter_tags = normalize_untagged_selection(
        selected_tags=_ee_filter_tags,
        available_tags=_ee_available,
        untagged_key=_UNTAGGED,
    )
    if _ee_normalized_filter_tags != _ee_filter_tags:
        st.session_state["edit_filter_tags_pending"] = _ee_normalized_filter_tags
        st.rerun()

    with _ee_mode_col:
        _ee_match_mode = st.radio(
            "Match mode",
            options=MATCH_MODE_OPTIONS,
            key="edit_filter_match_mode",
            on_change=_ee_reset_page,
        )

    # ── Apply filter ───────────────────────────────────────────────────────────
    _ee_filtered_pairs = filter_entry_pairs_by_tags(
        _ee_all_pairs,
        selected_tags=_ee_filter_tags,
        match_mode=_ee_match_mode,
    )

    # ── Pagination ─────────────────────────────────────────────────────────────
    _ee_saved_per_page = st.session_state.get("edit_entries_per_page", DEFAULT_PAGE_SIZE)
    _ee_default_idx = (
        PAGE_SIZE_OPTIONS.index(_ee_saved_per_page)
        if _ee_saved_per_page in PAGE_SIZE_OPTIONS
        else PAGE_SIZE_OPTIONS.index(DEFAULT_PAGE_SIZE)
    )
    _ee_col_per_page, _ee_col_per_page_spacer = st.columns([1, 3])
    with _ee_col_per_page:
        _ee_selected_per_page = st.selectbox(
            "Entries per page",
            options=PAGE_SIZE_OPTIONS,
            index=_ee_default_idx,
            key="_ee_entries_per_page_select",
        )
    if _ee_selected_per_page != st.session_state.get("edit_entries_per_page"):
        st.session_state.edit_entries_per_page = _ee_selected_per_page
        st.session_state.edit_entry_page = 0
        st.rerun()

    _ee_total_filtered = len(_ee_filtered_pairs)
    _ee_total_all = len(_ee_all_pairs)

    if _ee_total_filtered == 0:
        st.info("No entries match the current filters.")
        return

    _ee_pagination = calculate_pagination(
        total_items=_ee_total_filtered,
        requested_page=st.session_state.get("edit_entry_page", 0),
        per_page_setting=st.session_state.edit_entries_per_page,
    )
    _ee_cur_page = _ee_pagination.page
    _ee_last_page = _ee_pagination.last_page
    _ee_start = _ee_pagination.start
    _ee_end = _ee_pagination.end
    _ee_visible_pairs = slice_visible_pairs(_ee_filtered_pairs, _ee_pagination)

    # ── Status line ────────────────────────────────────────────────────────────
    st.caption(
        format_browser_status_caption(
            start=_ee_start,
            end=_ee_end,
            total_filtered=_ee_total_filtered,
            total_all=_ee_total_all,
            filtered=bool(_ee_filter_tags),
        )
    )

    # ── Entry list ─────────────────────────────────────────────────────────────
    for _ee_i, (_ee_entry_id, _ee_entry) in enumerate(
        _ee_visible_pairs, start=_ee_start
    ):
        _ee_errs = validate_entry(_ee_entry)
        _ee_label = format_entry_summary_label(
            display_index=_ee_i,
            entry=_ee_entry,
            dataset_format=st.session_state.dataset_format,
            errors=_ee_errs,
            tag_label_map=_ee_label_map,
        )
        with st.expander(_ee_label):
            st.caption(f"Temp ID: {_ee_entry_id}")
            if st.button("Edit Entry", key=f"btn_full_edit_{_ee_entry_id}"):
                start_full_edit(_ee_entry_id)
            if _ee_errs:
                for _ee_err in _ee_errs:
                    st.error(_ee_err)
            render_message_preview(
                _ee_entry.get("messages", []), include_system=True
            )

    # ── Pagination buttons ─────────────────────────────────────────────────────
    _ee_col_prev, _ee_col_next = st.columns(2)
    with _ee_col_prev:
        if st.button(
            "Previous",
            disabled=(_ee_cur_page == 0),
            width="stretch",
            key="ee_btn_prev",
        ):
            st.session_state.edit_entry_page = _ee_cur_page - 1
            st.rerun()
    with _ee_col_next:
        if st.button(
            "Next",
            disabled=(_ee_cur_page >= _ee_last_page),
            width="stretch",
            key="ee_btn_next",
        ):
            st.session_state.edit_entry_page = _ee_cur_page + 1
            st.rerun()
