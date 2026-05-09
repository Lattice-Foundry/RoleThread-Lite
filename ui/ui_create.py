"""Streamlit page for creating dataset entries.

This module owns widgets and form state. Durable entry appends delegate to
services.
"""
from pathlib import Path

import streamlit as st

from core.dataset import make_entry, save_dataset, validate_entry
from core.tag_registry import get_tag_registry_dict
from ui.session_state import _update_prefs, ensure_entry_registry
from services.dataset_service import create_entry_service
from ui.ui_components import (
    _ROLE_COLOR,
    calculate_exchange_metrics,
    render_conversation_preview,
    render_json_preview,
    render_tag_multiselects,
)

_ROLE_PLACEHOLDER = {
    "user": "What the user says…",
    "assistant": "What the assistant replies…",
}


# ── Editor state ───────────────────────────────────────────────────────────────

def init_editor_state(prefix: str) -> None:
    """Initialise session state keys for an entry editor instance.

    Safe to call multiple times — only sets keys that don't exist yet.
    """
    if f"{prefix}_turns" not in st.session_state:
        st.session_state[f"{prefix}_turns"] = [
            {"role": "user"}, {"role": "assistant"}
        ]
    if f"{prefix}_planned_exchanges" not in st.session_state:
        st.session_state[f"{prefix}_planned_exchanges"] = 1
    if f"{prefix}_clear" not in st.session_state:
        st.session_state[f"{prefix}_clear"] = False


# ── Turn builder ───────────────────────────────────────────────────────────────

def render_turn_builder(prefix: str) -> list[dict]:
    """Render the multi-turn conversation builder for an editor instance.

    Handles the pending-clear logic, tag-backup restore, planned-exchanges
    input, planning metrics, turn pair widgets, Add/Remove buttons, and the
    exchange-count caption.  Returns _turns_now — the list of
    {role, content} dicts reflecting the current widget values.
    """
    # ── DB-backed category names (used for tag backup/restore/clear loops) ───────
    # Fetched once per render; falls back to hardcoded TAGS if DB not seeded.
    _tag_registry = get_tag_registry_dict()
    if not _tag_registry:
        from core.dataset import TAGS as _TAGS_FB
        _tag_registry = _TAGS_FB
    _tag_cat_names = list(_tag_registry.keys())

    # ── Pending clear ──────────────────────────────────────────────────────────
    if st.session_state.pop(f"{prefix}_clear", False):
        _old_turn_count = len(st.session_state.get(f"{prefix}_turns", []))
        st.session_state[f"{prefix}_turns"] = [{"role": "user"}, {"role": "assistant"}]
        st.session_state[f"{prefix}_turn_0"] = ""
        st.session_state[f"{prefix}_turn_1"] = ""
        for _i in range(2, _old_turn_count):
            st.session_state.pop(f"{prefix}_turn_{_i}", None)
        for _cat in _tag_cat_names:
            st.session_state[f"{prefix}_tags_{_cat}"] = []

    # ── Tag backup restore ─────────────────────────────────────────────────────
    for _cat in _tag_cat_names:
        _bk = f"_{prefix}_tags_backup_{_cat}"
        if _bk in st.session_state:
            st.session_state[f"{prefix}_tags_{_cat}"] = st.session_state.pop(_bk)

    # ── _turns_now snapshot (read before widgets render) ──────────────────────
    _turns_now = [
        {"role": t["role"], "content": st.session_state.get(f"{prefix}_turn_{i}", "")}
        for i, t in enumerate(st.session_state[f"{prefix}_turns"])
    ]

    # ── Planned exchanges number input ────────────────────────────────────────
    _col_planned, _col_planned_spacer = st.columns([1, 3])
    with _col_planned:
        st.number_input(
            "Planned exchanges",
            min_value=1,
            step=1,
            key=f"{prefix}_planned_exchanges",
        )

    # ── Planning metrics (recomputed every run) ────────────────────────────────
    # Only count an exchange as complete when BOTH turns are filled in.
    _current_exchanges = sum(
        1
        for _pi in range(0, len(_turns_now), 2)
        if (
            _pi + 1 < len(_turns_now)
            and _turns_now[_pi]["content"].strip()
            and _turns_now[_pi + 1]["content"].strip()
        )
    )
    _planned_exchanges = st.session_state[f"{prefix}_planned_exchanges"]
    _remaining = max(0, _planned_exchanges - len(_turns_now) // 2)
    _overage = max(0, _current_exchanges - _planned_exchanges)

    # ── Turn pair rendering loop ───────────────────────────────────────────────
    for _pair in range(0, len(st.session_state[f"{prefix}_turns"]), 2):
        _col_user, _col_asst = st.columns(2)
        for _col, _idx in ((_col_user, _pair), (_col_asst, _pair + 1)):
            if _idx >= len(st.session_state[f"{prefix}_turns"]):
                break
            _turn = st.session_state[f"{prefix}_turns"][_idx]
            _role = _turn["role"]
            _color = _ROLE_COLOR.get(_role, "#000")
            with _col:
                st.markdown(
                    f"<span style='color:{_color};font-weight:bold;"
                    f"text-transform:uppercase'>{_role}</span>",
                    unsafe_allow_html=True,
                )
                st.text_area(
                    label=f"{prefix}_turn_{_idx}",
                    placeholder=_ROLE_PLACEHOLDER.get(_role, ""),
                    key=f"{prefix}_turn_{_idx}",
                    height=150,
                    label_visibility="collapsed",
                )

    # ── Add / Remove Exchange buttons ─────────────────────────────────────────
    _add_label = (
        f"Add Exchange ({_remaining} Remaining)"
        if _remaining > 0 and _planned_exchanges >= 2
        else "Add Exchange"
    )
    _btn_add, _btn_remove = st.columns(2)
    with _btn_add:
        if st.button(_add_label, key=f"{prefix}_btn_add", width="stretch"):
            for _cat in _tag_cat_names:
                st.session_state[f"_{prefix}_tags_backup_{_cat}"] = list(
                    st.session_state.get(f"{prefix}_tags_{_cat}", [])
                )
            st.session_state[f"{prefix}_turns"] += [{"role": "user"}, {"role": "assistant"}]
            st.rerun()
    with _btn_remove:
        if st.button(
            "Remove Last Exchange",
            key=f"{prefix}_btn_remove",
            disabled=len(st.session_state[f"{prefix}_turns"]) <= 2,
            width="stretch",
        ):
            for _cat in _tag_cat_names:
                st.session_state[f"_{prefix}_tags_backup_{_cat}"] = list(
                    st.session_state.get(f"{prefix}_tags_{_cat}", [])
                )
            _n = len(st.session_state[f"{prefix}_turns"])
            st.session_state[f"{prefix}_turns"] = st.session_state[f"{prefix}_turns"][:-2]
            for _k in [f"{prefix}_turn_{_n - 2}", f"{prefix}_turn_{_n - 1}"]:
                st.session_state.pop(_k, None)
            st.rerun()

    # ── Exchange count caption ─────────────────────────────────────────────────
    st.caption(f"Current exchanges: {_current_exchanges} / Planned: {_planned_exchanges}")

    return _turns_now


# ── Entry actions ──────────────────────────────────────────────────────────────

def render_entry_actions(
    turns_now: list[dict],
    prefix: str,
    mode: str,
    entry_index: int | None = None,
) -> None:
    """Render the tag selector, JSON preview, validation, planning warnings,
    and save button for an entry editor instance.

    mode — "create" appends to the dataset file;
           "edit"   overwrites loaded_entries[entry_index] in place.
    entry_index — required when mode == "edit"; ignored for "create".
    """
    st.divider()
    st.subheader("Tag & Complete Exchange")

    # ── Tag selectors ──────────────────────────────────────────────────────────
    selected_tags = render_tag_multiselects(prefix)

    # ── Entry preview & validation ─────────────────────────────────────────────
    _has_content = any(t["content"].strip() for t in turns_now)

    entry_preview = None
    _entry_valid = False
    if _has_content:
        entry_preview = make_entry(
            turns=turns_now,
            system_prompt=st.session_state.system_prompt,
            tags=selected_tags,
        )
        errors = validate_entry(entry_preview)

        render_json_preview(entry_preview, expanded=False)

        if errors:
            for err in errors:
                st.error(err)
        else:
            st.success("Entry looks valid.")
            _entry_valid = True

    # ── Planning warnings ──────────────────────────────────────────────────────
    _planned_exchanges = st.session_state.get(f"{prefix}_planned_exchanges", 1)
    _m = calculate_exchange_metrics(turns_now, _planned_exchanges)
    _current_exchanges = _m["current_exchanges"]

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

    # ── Save button ────────────────────────────────────────────────────────────
    _btn_label = "Complete Exchange" if mode == "create" else "Save Changes"
    _complete_disabled = not _entry_valid or _current_exchanges < _planned_exchanges
    if st.button(_btn_label, disabled=_complete_disabled, type="primary", width="stretch"):
        save_path = st.session_state.get("loaded_path", "").strip()
        if not save_path:
            st.error("No dataset loaded. Please load or create a dataset before saving an exchange.")
        elif mode == "create":
            result = create_entry_service(
                dataset_path=save_path,
                entries=st.session_state.loaded_entries,
                new_entry=entry_preview,
            )
            if result.ok and result.entries is not None:
                st.session_state.loaded_entries = result.entries
                ensure_entry_registry()
                _update_prefs({
                    "last_loaded_dataset_path": save_path,
                })
                st.session_state["manage_load_path_pending"] = save_path
                st.session_state[f"{prefix}_clear"] = True
                st.success(f"Entry appended to `{Path(save_path).resolve()}`.")
                st.rerun()
            else:
                for err in result.errors:
                    st.error(err)
                if not result.errors:
                    st.error(result.message)
        elif mode == "edit":
            if entry_index is None:
                st.warning("edit mode requires entry_index — nothing saved.")
            else:
                try:
                    _proposed_entries = list(st.session_state.loaded_entries)
                    _proposed_entries[entry_index] = entry_preview
                    save_dataset(save_path, _proposed_entries)
                    st.session_state.loaded_entries = _proposed_entries
                    st.success(f"Entry {entry_index + 1} updated.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Failed to save: {exc}")


# ── Page renderer ──────────────────────────────────────────────────────────────

def render_create_page() -> None:
    """Render the Create Entry page."""
    st.subheader("System Prompt")

    def _persist_system_prompt():
        _update_prefs({"last_system_prompt": st.session_state.sys_prompt_input})

    st.session_state.system_prompt = st.text_area(
        "Default system prompt (applied to every entry)",
        value=st.session_state.system_prompt,
        height=100,
        key="sys_prompt_input",
        on_change=_persist_system_prompt,
    )

    st.divider()
    st.subheader("New Entry")
    turns_now = render_turn_builder("create")

    # ── Conversation preview (full width, below Add/Remove buttons) ────────────
    st.subheader("Conversation Preview")
    render_conversation_preview(turns_now, "create")

    render_entry_actions(turns_now, "create", mode="create")
