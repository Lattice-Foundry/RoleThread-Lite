"""Help documentation browser for LoreForge Lite."""

from dataclasses import dataclass
from pathlib import Path

import streamlit as st

from ui.help_docs import (
    HELP_DIR,
    HelpSearchResult,
    build_help_search_results,
    extract_markdown_sections,
    format_section_outline,
    get_adjacent_help_articles,
    get_help_breadcrumb,
    get_help_articles_by_category,
    get_related_help_articles,
    load_help_document,
    resolve_help_article_id,
)


HELP_ACTIVE_ARTICLE_KEY = "help_active_article_id"
CLICKABLE_ARTICLE_OUTLINE = False


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
    matches: tuple[HelpSearchResult, ...],
) -> None:
    if not query.strip():
        return

    result_count = len(matches)
    st.markdown(f"**Search Results ({result_count})**")
    if not matches:
        st.info("No Help articles matched your search. Try a workflow, page, or concept name.")
        st.divider()
        return

    for result in matches:
        article = result.article
        button_col, text_col = st.columns([0.16, 0.84])
        with button_col:
            if st.button(
                "Open",
                key=f"_help_search_{article.article_id}",
                width="stretch",
            ):
                _select_help_article(article.article_id)
        with text_col:
            st.markdown(f"**{article.title}**")
            st.caption(f"{article.category} - {result.snippet}")
    st.divider()


def _render_related_articles(article_id: str) -> None:
    related_articles = get_related_help_articles(article_id)
    if not related_articles:
        return

    st.divider()
    st.markdown("**Related Articles**")
    columns = st.columns(2)
    for index, article in enumerate(related_articles):
        with columns[index % 2]:
            if st.button(
                article.title,
                key=f"_help_related_{article.article_id}",
                width="stretch",
            ):
                _select_help_article(article.article_id)
            st.caption(article.summary)


def _render_article_navigation(article_id: str) -> None:
    previous_article, next_article = get_adjacent_help_articles(article_id)
    if previous_article is None and next_article is None:
        return

    st.divider()
    previous_col, next_col = st.columns(2)
    with previous_col:
        if previous_article is not None and st.button(
            previous_article.title,
            key=f"_help_previous_{previous_article.article_id}",
            width="stretch",
            icon=":material/arrow_back:",
        ):
            _select_help_article(previous_article.article_id)
    with next_col:
        if next_article is not None and st.button(
            next_article.title,
            key=f"_help_next_{next_article.article_id}",
            width="stretch",
            icon=":material/arrow_forward:",
        ):
            _select_help_article(next_article.article_id)


def _render_active_article(article_id: str) -> None:
    document = load_help_document(article_id)
    article = document.article
    st.caption(" / ".join(get_help_breadcrumb(article.article_id)))
    if document.content:
        _render_article_outline(document.content)
        st.markdown(document.content)
    else:
        st.warning(f"Help article not found: `{article.file_name}`")
    _render_related_articles(article.article_id)
    _render_article_navigation(article.article_id)


def _render_article_outline(content: str) -> None:
    sections = extract_markdown_sections(content)
    if len(sections) < 2:
        return

    st.markdown("**On this page**")
    # Keep section links informational until Streamlit heading anchors can be
    # verified in a live browser reliably; the generated anchors are ready.
    st.markdown(
        "\n".join(
            format_section_outline(sections, clickable=CLICKABLE_ARTICLE_OUTLINE)
        )
    )
    st.divider()


def render_help_page() -> None:
    """Render the Help documentation browser."""

    active_article_id = get_active_help_article_id()
    _render_help_sidebar(active_article_id)

    st.subheader("Help")
    query = st.text_input("Search help articles...", key="help_search_query")
    matches = build_help_search_results(query)
    _render_search_results(query, matches)
    _render_active_article(active_article_id)
