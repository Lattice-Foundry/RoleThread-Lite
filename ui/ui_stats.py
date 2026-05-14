"""Insights and dataset quality analysis page."""

from __future__ import annotations

from hashlib import sha1
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from core.dataset import build_dataset_stats
from core.format_conversion import FORMAT_CHATML, FORMAT_SHAREGPT, FORMAT_UNKNOWN
from core.loreforge_meta import get_entry_uuid
from core.qualitative_analysis import DatasetQualityReport, analyze_dataset_quality
from core.tag_registry import get_tag_registry_snapshot
from ui.guidance import render_manage_dataset_cta
from ui.session_state import ensure_entry_indexes
from ui.stats_navigation import navigate_to_entries
from ui.theme import score_color


def _format_source_format(source_format: str) -> str:
    labels = {
        FORMAT_CHATML: "ChatML",
        FORMAT_SHAREGPT: "ShareGPT",
        FORMAT_UNKNOWN: "Unknown",
    }
    return labels.get(source_format, source_format or "Unknown")


def render_stats_page() -> None:
    """Render the Insights page."""

    ensure_entry_indexes()
    entries = st.session_state.loaded_entries

    if not entries:
        st.info("Load a dataset to view quality analysis.")
        render_manage_dataset_cta(key="stats_go_to_manage_empty")
        return

    tag_snapshot = get_tag_registry_snapshot()
    dataset_path = _loaded_dataset_path()
    report = analyze_dataset_quality(
        entries,
        dataset_path=dataset_path,
        tag_snapshot=tag_snapshot,
    )
    legacy_stats = build_dataset_stats(
        entries,
        tag_category_map=tag_snapshot.tag_category_map,
    )

    _render_quality_header(report)
    _render_subscore_cards(report)
    _render_recommended_insight_actions(report)
    _render_insights(report, entries)
    _render_dataset_overview(legacy_stats, entries)


def _loaded_dataset_path() -> Path | None:
    loaded_path = st.session_state.get("loaded_path")
    return Path(loaded_path) if loaded_path else None


def _render_quality_header(report: DatasetQualityReport) -> None:
    color = score_color(report.composite_score, 100)
    st.markdown(
        f"""
        <div style="
            border-left: 6px solid {color};
            padding: 0.9rem 1rem;
            background: rgba(127, 127, 127, 0.08);
            border-radius: 8px;
            margin-bottom: 1rem;
        ">
            <div style="font-size: 0.85rem; opacity: 0.75;">Dataset Health Score</div>
            <div style="display: flex; align-items: baseline; gap: 0.75rem;">
                <span style="font-size: 3rem; font-weight: 700; color: {color};">
                    {report.composite_score:.0f}
                </span>
                <span style="font-size: 1.35rem; font-weight: 600; color: {color};">
                    {report.grade}
                </span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Entries", report.total_entries)
    c2.metric("Total Messages", report.total_messages)
    c3.metric("Composite", f"{report.composite_score:.1f} / 100")


def _render_recommended_insight_actions(report: DatasetQualityReport) -> None:
    if report.composite_score >= 70:
        return

    recommendations = _quality_recommendations(report)
    if not recommendations:
        return

    st.info("Recommended next actions:\n\n" + "\n".join(
        f"- {recommendation}" for recommendation in recommendations[:3]
    ))


def _quality_recommendations(report: DatasetQualityReport) -> list[str]:
    scored_actions = [
        (
            report.response_quality.score,
            "Response Quality is low - consider writing longer, more detailed assistant responses.",
        ),
        (
            report.diversity.score,
            "Diversity is low - add varied system prompts, tags, or reduce near-duplicate entries.",
        ),
        (
            report.structure.score,
            "Structure needs attention - run Validation and review entries outside the 3-7 exchange range.",
        ),
        (
            report.metadata_integrity.score,
            "Metadata Integrity is low - tag untagged entries and save through LoreForge to refresh trusted metadata.",
        ),
    ]
    return [
        action
        for score, action in sorted(scored_actions, key=lambda item: item[0])
        if score < 18
    ]


def _render_subscore_cards(report: DatasetQualityReport) -> None:
    st.subheader("Quality Breakdown")
    c1, c2, c3, c4 = st.columns(4)

    with c1:
        _render_response_quality_card(report)
    with c2:
        _render_diversity_card(report)
    with c3:
        _render_structure_card(report)
    with c4:
        _render_metadata_card(report)


def _render_response_quality_card(report: DatasetQualityReport) -> None:
    score = report.response_quality
    _render_subscore_value("Response Quality", score.score)
    with st.expander("Metrics", expanded=False):
        st.write(f"Average response length: **{score.avg_response_length:.1f} words**")
        st.write(f"Median response length: **{score.median_response_length:.1f} words**")
        st.write(f"Short responses: **{score.short_response_count}**")
        st.write(f"Empty responses: **{score.empty_response_count}**")
        st.write(f"Placeholder responses: **{score.placeholder_count}**")
        st.write(f"User/assistant length ratio: **{score.user_assistant_length_ratio:.2f}**")
        _render_affected_count(
            score.flagged_entry_uuids,
            label="Response Quality flagged entries",
            key="response_quality",
        )


def _render_diversity_card(report: DatasetQualityReport) -> None:
    score = report.diversity
    _render_subscore_value("Diversity", score.score)
    with st.expander("Metrics", expanded=False):
        st.write(f"Unique system prompts: **{score.unique_system_prompts}**")
        st.write(f"Prompt diversity ratio: **{score.system_prompt_diversity_ratio:.2f}**")
        st.write(f"Tag coverage: **{score.tag_coverage_percent:.1f}%**")
        st.write(f"Tag entropy: **{score.tag_entropy:.2f}**")
        st.write(f"Categories represented: **{score.category_coverage_count}**")
        st.write(f"Near-duplicate pairs: **{score.near_duplicate_count}**")
        _render_affected_count(
            score.flagged_entry_uuids,
            label="Diversity flagged entries",
            key="diversity",
        )


def _render_structure_card(report: DatasetQualityReport) -> None:
    score = report.structure
    _render_subscore_value("Structure", score.score)
    with st.expander("Metrics", expanded=False):
        st.write(f"Validation pass rate: **{score.validation_pass_rate:.1f}%**")
        st.write(f"Invalid entries: **{score.invalid_entry_count}**")
        st.write(f"Average exchanges: **{score.avg_exchange_count:.1f}**")
        st.write(f"Entries in 3-7 exchange range: **{score.in_optimal_range_percent:.1f}%**")
        st.write(f"Short system prompts: **{score.short_system_prompt_count}**")
        st.write(f"Missing system prompts: **{score.missing_system_prompt_count}**")
        _render_affected_count(
            score.flagged_entry_uuids,
            label="Structure flagged entries",
            key="structure",
        )


def _render_metadata_card(report: DatasetQualityReport) -> None:
    score = report.metadata_integrity
    _render_subscore_value("Metadata", score.score)
    with st.expander("Metrics", expanded=False):
        st.write(f"Trusted stamp coverage: **{score.native_stamp_percent:.1f}%**")
        st.write(f"Tagged entries: **{score.tagged_entry_percent:.1f}%**")
        st.write(f"Character mapping completeness: **{score.character_mapping_percent:.1f}%**")
        st.write(f"Sidecar present: **{_yes_no(score.sidecar_present)}**")
        st.write(f"Sidecar current: **{_yes_no(score.sidecar_current)}**")
        _render_affected_count(
            score.flagged_entry_uuids,
            label="Metadata flagged entries",
            key="metadata",
        )


def _render_affected_count(
    entry_uuids: tuple[str, ...],
    *,
    label: str,
    key: str,
) -> None:
    if entry_uuids:
        count = len(entry_uuids)
        if st.button(
            f"View {count} affected entr{'y' if count == 1 else 'ies'}",
            key=f"stats_deeplink_{key}",
        ):
            navigate_to_entries(entry_uuids, label)


def _render_subscore_value(label: str, score: float) -> None:
    color = score_color(score, 25)
    status = _subscore_status(score)
    st.markdown(
        f"""
        <div style="
            border-left: 4px solid {color};
            padding: 0.45rem 0 0.45rem 0.7rem;
            margin-bottom: 0.35rem;
        ">
            <div style="font-size: 0.85rem; opacity: 0.78;">{label}</div>
            <div style="display:flex; align-items:baseline; gap:0.45rem; flex-wrap:wrap;">
                <span style="font-size:1.7rem; font-weight:700; color:{color};">
                    {score:.1f}
                </span>
                <span style="font-size:0.85rem; opacity:0.75;">/ 25</span>
                <span style="
                    color:{color};
                    border:1px solid {color};
                    border-radius:999px;
                    padding:0.08rem 0.45rem;
                    font-size:0.78rem;
                    font-weight:600;
                    white-space:nowrap;
                ">
                    {status}
                </span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_insights(report: DatasetQualityReport, entries: list[dict]) -> None:
    st.divider()
    st.subheader("Insights")
    _render_narrative_spectrum(report)
    _render_exchange_depth_distribution(report)
    _render_response_length_distribution(report)
    _render_system_prompt_concentration(report, entries)


def _render_narrative_spectrum(report: DatasetQualityReport) -> None:
    insight = report.narrative_insight
    st.markdown("#### Narrative Style Spectrum")
    left, middle, right = st.columns([1, 3, 1])
    left.caption("Pure Narrative")
    middle.progress(min(max(insight.dialogue_ratio, 0.0), 1.0))
    right.caption("Pure Dialogue")
    st.write(
        f"**{insight.spectrum_label}** · {insight.dialogue_ratio * 100:.0f}% dialogue density"
    )
    st.caption(insight.spectrum_description)


def _render_exchange_depth_distribution(report: DatasetQualityReport) -> None:
    st.markdown("#### Exchange Depth Distribution")
    rows = _exchange_depth_rows(report.exchange_depth_distribution)
    if not rows:
        st.info("No exchange depth data available.")
        return

    df = pd.DataFrame(rows)
    fig = px.bar(
        df,
        x="Exchange Count",
        y="Entries",
        color="Range",
        color_discrete_map={"Optimal 3-7": "#2E7D32", "Review": "#78909C"},
    )
    fig.update_layout(showlegend=True, yaxis_title="Entries")
    st.plotly_chart(fig, width="stretch")
    st.caption("The 3-7 exchange range is the target conversational depth for most entries.")


def _render_response_length_distribution(report: DatasetQualityReport) -> None:
    st.markdown("#### Response Length Distribution")
    lengths = list(report.response_length_distribution)
    if not lengths:
        st.info("No assistant responses found for response length analysis.")
        return

    df = pd.DataFrame({"Assistant Response Words": lengths})
    fig = px.histogram(
        df,
        x="Assistant Response Words",
        nbins=min(20, max(5, len(set(lengths)))),
    )
    fig.update_layout(yaxis_title="Responses")
    st.plotly_chart(fig, width="stretch")


def _render_system_prompt_concentration(
    report: DatasetQualityReport,
    entries: list[dict],
) -> None:
    st.markdown("#### System Prompt Concentration")
    prompt_rows = _system_prompt_rows(entries, report)
    if not prompt_rows:
        st.info("No system prompts found.")
        return

    if len(prompt_rows) == 1:
        st.caption("One system prompt is used across the loaded dataset.")
    else:
        st.caption(f"{len(prompt_rows)} unique system prompts found. Showing the most common prompts.")

    top_rows = prompt_rows[:5]
    st.dataframe(
        pd.DataFrame(top_rows),
        width="stretch",
        hide_index=True,
    )

    dominant = top_rows[0]
    if report.total_entries and dominant["Entries"] / report.total_entries > 0.8:
        st.info(
            "One system prompt covers more than 80% of entries. That can be perfect "
            "for a focused character or scenario, but it will strongly specialize the model."
        )


def _render_dataset_overview(legacy_stats: dict, entries: list[dict]) -> None:
    st.divider()
    st.subheader("Dataset Overview")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Exchanges", legacy_stats["total_exchanges"])
    c2.metric("Avg Exchanges / Entry", f"{legacy_stats['avg_exchanges']:.1f}")
    c3.metric("Unique Tags", legacy_stats["unique_tags"])
    c4.metric("Untagged Entries", legacy_stats["untagged_count"])

    _render_tag_balance(legacy_stats)
    _render_source_format(legacy_stats)
    _render_validation_table(legacy_stats, entries)


def _render_tag_balance(stats: dict) -> None:
    st.markdown("#### Tag Balance")
    if not stats["tag_counts"]:
        st.info("No tags found in this dataset.")
        return

    tb1, tb2 = st.columns(2)
    with tb1:
        df_tags = (
            pd.DataFrame(stats["tag_counts"].items(), columns=["Tag", "Count"])
            .sort_values("Count", ascending=False)
            .reset_index(drop=True)
        )
        st.plotly_chart(
            px.bar(df_tags, x="Tag", y="Count", title="Tag Counts"),
            width="stretch",
        )

    with tb2:
        df_cat = (
            pd.DataFrame(stats["tag_category_counts"].items(), columns=["Category", "Count"])
            .sort_values("Count", ascending=False)
            .reset_index(drop=True)
        )
        st.plotly_chart(
            px.bar(df_cat, x="Category", y="Count", title="Tag Category Counts"),
            width="stretch",
        )

    st.dataframe(
        df_tags.rename(columns={"Count": "Entries using tag"}),
        width="stretch",
        hide_index=True,
    )


def _render_source_format(stats: dict) -> None:
    st.markdown("#### Source Format")
    source_format = _format_source_format(
        st.session_state.get("dataset_source_format", FORMAT_UNKNOWN)
    )
    c1, c2 = st.columns([1, 2])
    c1.metric(source_format, stats["total"], help="Detected source format for the loaded dataset.")
    with c2:
        st.plotly_chart(
            px.bar(
                pd.DataFrame([{"Format": source_format, "Entries": stats["total"]}]),
                x="Format",
                y="Entries",
                title="Source Format",
            ),
            width="stretch",
        )


def _render_validation_table(stats: dict, entries: list[dict]) -> None:
    st.markdown("#### Validation")
    c1, c2 = st.columns(2)
    c1.metric("Valid Entries", stats["valid_count"])
    c2.metric("Invalid Entries", stats["invalid_count"])

    if not stats["invalid_rows"]:
        return

    df_val = pd.DataFrame(
        [
            {
                "Entry UUID": (
                    get_entry_uuid(entries[row["entry"] - 1])
                    if row["entry"] - 1 < len(entries)
                    else "-"
                ),
                "Entry": row["entry"],
                "Error Count": row["error_count"],
                "Errors": "; ".join(row["errors"]),
            }
            for row in stats["invalid_rows"]
        ]
    )
    st.dataframe(df_val, width="stretch", hide_index=True)


def _exchange_depth_rows(distribution: dict[int, int]) -> list[dict]:
    rows: list[dict] = []
    eight_plus = 0
    for exchange_count, count in sorted(distribution.items()):
        if exchange_count >= 8:
            eight_plus += count
            continue
        rows.append(
            {
                "Exchange Count": str(exchange_count),
                "Entries": count,
                "Range": "Optimal 3-7" if 3 <= exchange_count <= 7 else "Review",
            }
        )
    if eight_plus:
        rows.append({"Exchange Count": "8+", "Entries": eight_plus, "Range": "Review"})
    return rows


def _system_prompt_rows(entries: list[dict], report: DatasetQualityReport) -> list[dict]:
    prompts_by_hash: dict[str, str] = {}
    for entry in entries:
        prompt = _system_prompt(entry)
        if not prompt:
            continue
        prompt_hash = _prompt_hash(prompt)
        prompts_by_hash.setdefault(prompt_hash, prompt)

    rows = [
        {
            "Prompt": _truncate(prompts_by_hash.get(prompt_hash, prompt_hash), 100),
            "Entries": count,
            "Share": f"{(count / report.total_entries * 100):.1f}%" if report.total_entries else "0.0%",
        }
        for prompt_hash, count in report.system_prompt_concentration.items()
    ]
    return sorted(rows, key=lambda row: row["Entries"], reverse=True)


def _system_prompt(entry: dict) -> str:
    messages = entry.get("messages") if isinstance(entry, dict) else None
    if not isinstance(messages, list) or not messages:
        return ""
    first = messages[0]
    if isinstance(first, dict) and first.get("role") == "system":
        return str(first.get("content", ""))
    return ""


def _prompt_hash(prompt: str) -> str:
    normalized = " ".join(prompt.casefold().split())
    return sha1(normalized.encode("utf-8")).hexdigest()[:12]


def _truncate(text: str, max_length: int) -> str:
    clean = " ".join((text or "").split())
    if len(clean) <= max_length:
        return clean
    return f"{clean[: max_length - 1].rstrip()}..."


def _subscore_status(score: float) -> str:
    if score >= 23:
        return "Excellent"
    if score >= 18:
        return "Good"
    if score >= 13:
        return "Fair"
    if score >= 7:
        return "Needs Attention"
    return "Significant Issues"


def _yes_no(value: bool) -> str:
    return "Yes" if value else "No"
