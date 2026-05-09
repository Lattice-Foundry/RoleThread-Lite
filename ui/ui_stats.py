"""Statistics page."""
import pandas as pd
import plotly.express as px
import streamlit as st

from core.dataset import build_dataset_stats
from ui.session_state import ensure_entry_registry
from core.tag_registry import get_tag_category_map


def render_stats_page() -> None:
    """Render the Statistics page."""
    ensure_entry_registry()
    _stat_entries = st.session_state.loaded_entries

    if not _stat_entries:
        st.info("Load a dataset in Manage Dataset to see statistics.")
        return

    _s = build_dataset_stats(_stat_entries, tag_category_map=get_tag_category_map())

    # ── Summary cards ──────────────────────────────────────────────────────────
    _c1, _c2, _c3, _c4, _c5, _c6 = st.columns(6)
    _c1.metric("Total Entries", _s["total"])
    _c2.metric("Total Exchanges", _s["total_exchanges"])
    _c3.metric("Avg Exchanges / Entry", f"{_s['avg_exchanges']:.1f}")
    _c4.metric("Invalid Entries", _s["invalid_count"])
    _c5.metric("Untagged Entries", _s["untagged_count"])
    _c6.metric("Unique Tags", _s["unique_tags"])

    # ── Message Lengths ────────────────────────────────────────────────────────
    st.divider()
    st.subheader("Message Lengths")
    _l1, _l2, _l3, _l4, _l5 = st.columns(5)
    _l1.metric("Avg User Message", f"{_s['avg_user_len']:.0f} chars")
    _l2.metric("Avg Assistant Message", f"{_s['avg_asst_len']:.0f} chars")
    _l3.metric("Avg Entry Length", f"{_s['avg_entry_len']:.0f} chars")
    _l4.metric("Shortest Assistant Response", f"{_s['min_asst_len']} chars")
    _l5.metric("Longest Assistant Response", f"{_s['max_asst_len']} chars")

    # ── Tag Balance ────────────────────────────────────────────────────────────
    st.divider()
    st.subheader("Tag Balance")
    if not _s["tag_counts"]:
        st.info("No tags found in this dataset.")
    else:
        _tb1, _tb2 = st.columns(2)

        with _tb1:
            _df_tags = (
                pd.DataFrame(
                    _s["tag_counts"].items(), columns=["Tag", "Count"]
                )
                .sort_values("Count", ascending=False)
                .reset_index(drop=True)
            )
            st.plotly_chart(
                px.bar(_df_tags, x="Tag", y="Count", title="Tag Counts"),
                width="stretch",
            )

        with _tb2:
            _df_cat = (
                pd.DataFrame(
                    _s["tag_category_counts"].items(), columns=["Category", "Count"]
                )
                .sort_values("Count", ascending=False)
                .reset_index(drop=True)
            )
            st.plotly_chart(
                px.bar(_df_cat, x="Category", y="Count", title="Tag Category Counts"),
                width="stretch",
            )

        st.dataframe(
            _df_tags.rename(columns={"Tag": "Tag", "Count": "Entries using tag"}),
            width="stretch",
            hide_index=True,
        )

    # ── Exchange Depth ─────────────────────────────────────────────────────────
    st.divider()
    st.subheader("Exchange Depth")
    _ed1, _ed2 = st.columns([3, 1])

    with _ed1:
        _df_exc = pd.DataFrame(
            sorted(_s["exchange_dist"].items()), columns=["Exchanges", "Entries"]
        )
        st.plotly_chart(
            px.bar(_df_exc, x="Exchanges", y="Entries", title="Entries by Exchange Count"),
            width="stretch",
        )

    with _ed2:
        st.metric("Single-turn entries", _s["single_turn"])
        st.metric("Multi-turn entries", _s["multi_turn"])

    # ── Format Distribution ────────────────────────────────────────────────────
    st.divider()
    st.subheader("Format Distribution")
    _fmt = st.session_state.dataset_format
    _f1, _f2 = st.columns(2)
    _f1.metric(_fmt, _s["total"], help="All entries are treated as this format.")
    with _f2:
        st.plotly_chart(
            px.bar(
                pd.DataFrame([{"Format": _fmt, "Entries": _s["total"]}]),
                x="Format",
                y="Entries",
                title="Format Distribution",
            ),
            width="stretch",
        )

    # ── Validation ─────────────────────────────────────────────────────────────
    st.divider()
    st.subheader("Validation")
    _v1, _v2 = st.columns(2)
    _v1.metric("Valid Entries", _s["valid_count"])
    _v2.metric("Invalid Entries", _s["invalid_count"])

    if _s["invalid_rows"]:
        _stat_ids = st.session_state.entry_registry.get("ids", [])
        _df_val = pd.DataFrame([
            {
                "Temp ID": _stat_ids[r["entry"] - 1] if r["entry"] - 1 < len(_stat_ids) else "—",
                "Entry": r["entry"],
                "Error Count": r["error_count"],
                "Errors": "; ".join(r["errors"]),
            }
            for r in _s["invalid_rows"]
        ])
        st.dataframe(_df_val, width="stretch", hide_index=True)
