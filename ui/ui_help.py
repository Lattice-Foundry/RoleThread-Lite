"""Help documentation browser for LoreForge Lite."""

from dataclasses import dataclass
from pathlib import Path

import streamlit as st

from ui.help_docs import (
    HELP_DIR,
    HelpDocument,
    get_help_articles_by_category,
    load_help_document,
    resolve_help_article_id,
    search_help_documents,
)


HELP_ACTIVE_ARTICLE_KEY = "help_active_article_id"


@dataclass(frozen=True)
class HelpTopic:
    """Legacy loaded help topic shape kept for helper compatibility."""

    title: str
    content: str
    path: Path


def clean_help_topic_title(path: Path) -> str:
    """Convert a Markdown filename into a readable help topic title."""

    return path.stem.replace("_", " ").replace("-", " ").title()


def load_help_topics(help_dir: Path | None = None) -> tuple[HelpTopic, ...]:
    """Load help topics from Markdown files in legacy filename order."""

    source_dir = help_dir or HELP_DIR
    if not source_dir.exists():
        return ()

    topics: list[HelpTopic] = []
    for path in sorted(source_dir.glob("*.md")):
        if not path.is_file():
            continue
        topics.append(
            HelpTopic(
                title=clean_help_topic_title(path),
                content=path.read_text(encoding="utf-8"),
                path=path,
            )
        )
    return tuple(topics)


def filter_help_topics(
    topics: tuple[HelpTopic, ...],
    query: str,
) -> tuple[HelpTopic, ...]:
    """Filter legacy help topics by title or content keyword match."""

    normalized_query = (query or "").strip().lower()
    if not normalized_query:
        return topics
    return tuple(
        topic
        for topic in topics
        if normalized_query in topic.title.lower()
        or normalized_query in topic.content.lower()
    )


def get_active_help_article_id() -> str:
    """Return the active Help article ID, repairing invalid state."""

    article_id = resolve_help_article_id(st.session_state.get(HELP_ACTIVE_ARTICLE_KEY))
    st.session_state[HELP_ACTIVE_ARTICLE_KEY] = article_id
    return article_id


def set_active_help_article(article_id: str) -> str:
    """Set the active Help article ID after safe fallback resolution."""

    resolved_article_id = resolve_help_article_id(article_id)
    st.session_state[HELP_ACTIVE_ARTICLE_KEY] = resolved_article_id
    return resolved_article_id


def _select_help_article(article_id: str) -> None:
    set_active_help_article(article_id)
    st.rerun()


def _render_help_sidebar(active_article_id: str) -> None:
    st.sidebar.markdown("**Help Documentation**")
    for category, articles in get_help_articles_by_category().items():
        expanded = any(
            article.article_id == active_article_id
            for article in articles
        )
        with st.sidebar.expander(category, expanded=expanded):
            for article in articles:
                if st.button(
                    article.title,
                    key=f"_help_article_{article.article_id}",
                    width="stretch",
                    type=(
                        "primary"
                        if article.article_id == active_article_id
                        else "secondary"
                    ),
                ):
                    _select_help_article(article.article_id)


def _render_search_results(
    query: str,
    matches: tuple[HelpDocument, ...],
) -> None:
    if not query.strip():
        return

    st.markdown("**Search Results**")
    if not matches:
        st.info("No Help articles matched your search.")
        st.divider()
        return

    for document in matches:
        article = document.article
        button_col, text_col = st.columns([0.18, 0.82])
        with button_col:
            if st.button(
                "Open",
                key=f"_help_search_{article.article_id}",
                width="stretch",
            ):
                _select_help_article(article.article_id)
        with text_col:
            st.markdown(f"**{article.title}**")
            st.caption(f"{article.category} - {article.summary}")
    st.divider()


def _render_active_article(document: HelpDocument) -> None:
    article = document.article
    st.caption(f"Help / {article.category}")
    if document.content:
        st.markdown(document.content)
    else:
        st.warning(f"Help article not found: `{article.file_name}`")


def render_help_page() -> None:
    """Render the Help documentation browser."""

    active_article_id = get_active_help_article_id()
    _render_help_sidebar(active_article_id)

    st.subheader("Help")
    query = st.text_input("Search help articles...", key="help_search_query")
    matches = search_help_documents(query)
    _render_search_results(query, matches)

    active_article = load_help_document(active_article_id)
    _render_active_article(active_article)
