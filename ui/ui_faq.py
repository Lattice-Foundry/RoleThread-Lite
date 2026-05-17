"""FAQ browser page for RoleThread Lite."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

import streamlit as st

from ui.help_docs import get_help_article, get_help_article_registry
from ui.navigation import PAGE_HELP, navigate_to_page, render_sidebar_branding
from ui.search_controls import render_document_search_controls
from ui.ui_help import select_help_article


DOCS_ROOT = Path(__file__).resolve().parents[1] / "docs"
FAQ_JSON = DOCS_ROOT / "faq.json"
FAQ_YAML = DOCS_ROOT / "faq.yaml"
FAQ_ACTIVE_CATEGORY_KEY = "faq_active_category"
FAQ_SEARCH_QUERY_KEY = "faq_search_query"
FAQ_SEARCH_RESULTS_VISIBLE_KEY = "faq_search_results_visible"

FAQ_CATEGORY_ORDER = (
    "Getting Started",
    "Workflow and Editing",
    "Metadata and Characters",
    "Validation, Export, and Training",
    "Safety, Backups, and Boundaries",
)

FAQ_CATEGORY_DESCRIPTIONS = {
    "Getting Started": "First-run questions, examples, and the basic app rhythm.",
    "Workflow and Editing": "Daily workflow, Deep Edit, split/join, and dataset craft.",
    "Metadata and Characters": "Tags, sidecars, character identity, and portable context.",
    "Validation, Export, and Training": "Quality review, clean export, and downstream use.",
    "Safety, Backups, and Boundaries": "Recovery, trust, local-first scope, and Lite limits.",
}

_FAQ_PREFIX_CATEGORY_MAP = {
    "getting started": "Getting Started",
    "included examples": "Getting Started",
    "workflow philosophy": "Workflow and Editing",
    "dataset craftsmanship": "Workflow and Editing",
    "working copies and sidecars": "Metadata and Characters",
    "tags and metadata": "Metadata and Characters",
    "group chat and characters": "Metadata and Characters",
    "metadata philosophy": "Metadata and Characters",
    "validation and insights": "Validation, Export, and Training",
    "export and training": "Validation, Export, and Training",
    "backups and recovery": "Safety, Backups, and Boundaries",
    "v1 boundaries": "Safety, Backups, and Boundaries",
    "safety and identity": "Safety, Backups, and Boundaries",
    "operational expectations": "Safety, Backups, and Boundaries",
    "lite boundaries": "Safety, Backups, and Boundaries",
}

_FAQ_PREFIX_HELP_RELATED = {
    "working copies and sidecars": (
        "loading-datasets-and-working-copies",
        "sidecars-and-portable-metadata",
    ),
    "tags and metadata": ("tags-categories-and-tag-lifecycle",),
    "group chat and characters": (
        "character-registry-and-character-mappings",
        "default-mode-vs-group-chat",
    ),
    "validation and insights": (
        "validation-and-repair",
        "insights-and-dataset-quality",
    ),
    "export and training": ("exporting-datasets", "dataset-formats"),
    "backups and recovery": ("backups-cloud-sync-and-recovery",),
    "workflow philosophy": ("understanding-the-main-workspaces", "editing-entries"),
    "dataset craftsmanship": (
        "splitting-and-joining-entries",
        "insights-and-dataset-quality",
    ),
    "metadata philosophy": ("sidecars-and-portable-metadata",),
    "safety and identity": (
        "loading-datasets-and-working-copies",
        "backups-cloud-sync-and-recovery",
    ),
}

_FAQ_QUESTION_HELP_RELATED = {
    "Where should I spend most of my time?": (
        "understanding-the-main-workspaces",
        "editing-entries",
    ),
    "Why did RoleThread create a working copy?": (
        "loading-datasets-and-working-copies",
    ),
    "Why is there a .registry.json file?": ("sidecars-and-portable-metadata",),
    "When should I use Group Chat mode?": (
        "default-mode-vs-group-chat",
        "character-registry-and-character-mappings",
    ),
    "Why does Validation show warnings if RoleThread validates before save?": (
        "validation-and-repair",
    ),
    "What is clean export?": ("exporting-datasets",),
    "Why did merge create a new dataset UUID?": ("merging-datasets",),
    "Why isn't Deep Edit the primary editing workspace?": (
        "understanding-the-main-workspaces",
        "editing-entries",
    ),
}


@dataclass(frozen=True)
class FAQEntry:
    """Loaded FAQ question, answer, and derived browser category."""

    question: str
    answer: str
    category: str = "Getting Started"
    source_prefix: str = ""
    related_help_ids: tuple[str, ...] = ()

    @property
    def display_question(self) -> str:
        """Return a question label without the legacy prefix when present."""

        if self.source_prefix and self.question.lower().startswith(
            f"{self.source_prefix.lower()}:"
        ):
            return self.question.split(":", 1)[1].strip()
        return self.question


def _load_yaml_faq(path: Path) -> list[dict[str, Any]]:
    try:
        import yaml
    except ImportError:
        return []

    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else []


def _split_question_prefix(question: str) -> tuple[str, str]:
    if ":" not in question:
        return "", question.strip()
    prefix, rest = question.split(":", 1)
    return prefix.strip(), rest.strip()


def resolve_faq_category(category: str | None) -> str:
    """Return a known FAQ category, falling back to the first category."""

    if category in FAQ_CATEGORY_ORDER:
        return str(category)
    return FAQ_CATEGORY_ORDER[0]


def derive_faq_category(question: str, explicit_category: str | None = None) -> str:
    """Derive the browser category for a FAQ entry."""

    if explicit_category:
        return resolve_faq_category(str(explicit_category).strip())
    prefix, _ = _split_question_prefix(question)
    return _FAQ_PREFIX_CATEGORY_MAP.get(prefix.lower(), FAQ_CATEGORY_ORDER[0])


def derive_related_help_ids(
    question: str,
    explicit_related_ids: tuple[str, ...] | list[str] | None = None,
) -> tuple[str, ...]:
    """Return lightweight related Help article IDs for a FAQ entry."""

    registry = get_help_article_registry()
    raw_ids = tuple(explicit_related_ids or ())
    if raw_ids:
        return tuple(help_id for help_id in raw_ids if help_id in registry)

    prefix, display_question = _split_question_prefix(question)
    related_ids = list(_FAQ_PREFIX_HELP_RELATED.get(prefix.lower(), ()))
    related_ids.extend(_FAQ_QUESTION_HELP_RELATED.get(display_question, ()))

    unique_ids: list[str] = []
    for help_id in related_ids:
        if help_id in registry and help_id not in unique_ids:
            unique_ids.append(help_id)
    return tuple(unique_ids[:3])


def _coerce_faq_entries(raw_entries: list[dict[str, Any]]) -> tuple[FAQEntry, ...]:
    entries: list[FAQEntry] = []
    for raw_entry in raw_entries:
        question = str(raw_entry.get("question", "")).strip()
        answer = str(raw_entry.get("answer", "")).strip()
        if not question or not answer:
            continue
        prefix, _ = _split_question_prefix(question)
        category = derive_faq_category(question, raw_entry.get("category"))
        raw_related_ids = raw_entry.get("related_help_ids")
        related_ids = (
            tuple(str(help_id) for help_id in raw_related_ids)
            if isinstance(raw_related_ids, list)
            else None
        )
        entries.append(
            FAQEntry(
                question=question,
                answer=answer,
                category=category,
                source_prefix=prefix,
                related_help_ids=derive_related_help_ids(question, related_ids),
            )
        )
    return tuple(entries)


def load_faq_entries(docs_dir: Path | None = None) -> tuple[FAQEntry, ...]:
    """Load FAQ entries from JSON or YAML documentation files."""

    source_dir = docs_dir or DOCS_ROOT
    json_path = source_dir / "faq.json"
    yaml_path = source_dir / "faq.yaml"
    if json_path.exists():
        data = json.loads(json_path.read_text(encoding="utf-8"))
        return _coerce_faq_entries(data if isinstance(data, list) else [])
    if yaml_path.exists():
        return _coerce_faq_entries(_load_yaml_faq(yaml_path))
    return ()


def get_faq_category_order() -> tuple[str, ...]:
    """Return FAQ sidebar category order."""

    return FAQ_CATEGORY_ORDER


def get_faq_category_description(category: str) -> str:
    """Return a short reader-facing description for a FAQ category."""

    return FAQ_CATEGORY_DESCRIPTIONS.get(resolve_faq_category(category), "")


def get_faq_entries_by_category(
    entries: tuple[FAQEntry, ...] | None = None,
) -> dict[str, tuple[FAQEntry, ...]]:
    """Group FAQ entries into the sidebar category model."""

    source_entries = entries if entries is not None else load_faq_entries()
    grouped: dict[str, list[FAQEntry]] = {
        category: []
        for category in FAQ_CATEGORY_ORDER
    }
    for entry in source_entries:
        grouped.setdefault(resolve_faq_category(entry.category), []).append(entry)
    return {
        category: tuple(grouped.get(category, ()))
        for category in FAQ_CATEGORY_ORDER
    }


def get_active_faq_category() -> str:
    """Return the active FAQ category, repairing invalid session state."""

    category = resolve_faq_category(st.session_state.get(FAQ_ACTIVE_CATEGORY_KEY))
    st.session_state[FAQ_ACTIVE_CATEGORY_KEY] = category
    return category


def select_faq_category(
    category: str,
    *,
    hide_search_results: bool = True,
    rerun: bool = True,
) -> str:
    """Select a FAQ category through one shared sidebar path."""

    resolved_category = resolve_faq_category(category)
    st.session_state[FAQ_ACTIVE_CATEGORY_KEY] = resolved_category
    if hide_search_results:
        st.session_state[FAQ_SEARCH_RESULTS_VISIBLE_KEY] = False
    if rerun:
        st.rerun()
    return resolved_category


def filter_faq_entries(
    entries: tuple[FAQEntry, ...],
    query: str,
) -> tuple[FAQEntry, ...]:
    """Filter FAQ entries by category, question, or answer keyword match."""

    normalized_query = (query or "").strip().lower()
    if not normalized_query:
        return entries
    return tuple(
        entry
        for entry in entries
        if normalized_query in entry.category.lower()
        or normalized_query in entry.question.lower()
        or normalized_query in entry.display_question.lower()
        or normalized_query in entry.answer.lower()
    )


def open_related_help_article(article_id: str, *, rerun: bool = True) -> str:
    """Open Help to a related article from FAQ."""

    selected_article_id = select_help_article(article_id, rerun=False)
    navigate_to_page(PAGE_HELP, rerun=rerun)
    return selected_article_id


def _faq_entry_key(entry: FAQEntry) -> str:
    digest = hashlib.sha1(entry.question.encode("utf-8")).hexdigest()[:12]
    return digest


def _render_faq_sidebar(active_category: str, entries: tuple[FAQEntry, ...]) -> None:
    render_sidebar_branding()
    st.sidebar.markdown("**FAQ Categories**")
    grouped_entries = get_faq_entries_by_category(entries)
    for category in FAQ_CATEGORY_ORDER:
        count = len(grouped_entries[category])
        if st.sidebar.button(
            f"{category} ({count})",
            key=f"_faq_category_{category}",
            width="stretch",
            type="primary" if category == active_category else "secondary",
        ):
            select_faq_category(category)


def _render_faq_entries(entries: tuple[FAQEntry, ...], *, key_prefix: str) -> None:
    if not entries:
        st.info("No FAQ entries are available yet.")
        return
    for index, entry in enumerate(entries):
        with st.expander(entry.display_question):
            st.caption(entry.category)
            st.markdown(entry.answer)
            _render_related_help_links(
                entry,
                key_prefix=f"{key_prefix}_{index}_{_faq_entry_key(entry)}",
            )


def _render_related_help_links(entry: FAQEntry, *, key_prefix: str) -> None:
    if not entry.related_help_ids:
        return

    st.markdown("**See also**")
    columns = st.columns(min(2, len(entry.related_help_ids)))
    for index, article_id in enumerate(entry.related_help_ids):
        article = get_help_article(article_id)
        with columns[index % len(columns)]:
            if st.button(
                article.title,
                key=f"_faq_help_{key_prefix}_{article.article_id}",
                width="stretch",
                icon=":material/article:",
            ):
                open_related_help_article(article.article_id)


def _render_search_results(
    query: str,
    entries: tuple[FAQEntry, ...],
) -> None:
    if not query.strip():
        return

    matches = filter_faq_entries(entries, query)
    st.markdown(f"**Search Results ({len(matches)})**")
    if not matches:
        st.info("No FAQ entries matched your search. Try a workflow, page, or concept name.")
        st.divider()
        return

    st.caption("Matching FAQ entries are shown below. Clear search to return to the selected category.")
    _render_faq_entries(matches, key_prefix="search")
    st.divider()


def _render_search_controls(entries: tuple[FAQEntry, ...]) -> None:
    search_state = render_document_search_controls(
        form_key="faq_search_form",
        input_label="Search FAQ...",
        query_key=FAQ_SEARCH_QUERY_KEY,
        results_visible_key=FAQ_SEARCH_RESULTS_VISIBLE_KEY,
        search_button_key="_faq_search_submit",
        clear_button_key="_faq_search_clear",
    )
    if search_state.results_visible:
        _render_search_results(search_state.query, entries)
    elif search_state.query.strip():
        st.caption("Search query preserved. Click Search to show results again.")


def render_faq_page() -> None:
    """Render the categorized FAQ browser."""

    entries = load_faq_entries()
    active_category = get_active_faq_category()
    _render_faq_sidebar(active_category, entries)

    st.subheader("FAQ")
    _render_search_controls(entries)

    active_category = get_active_faq_category()
    grouped_entries = get_faq_entries_by_category(entries)
    category_entries = grouped_entries[active_category]
    st.markdown(f"### {active_category}")
    description = get_faq_category_description(active_category)
    if description:
        st.caption(f"{description} {len(category_entries)} questions.")
    _render_faq_entries(category_entries, key_prefix="category")

