"""Help documentation page for LoreForge Lite."""
from dataclasses import dataclass
from pathlib import Path

import streamlit as st


DOCS_ROOT = Path(__file__).resolve().parents[1] / "docs"
HELP_DIR = DOCS_ROOT / "help"


@dataclass(frozen=True)
class HelpTopic:
    """Loaded help topic metadata and Markdown content."""

    title: str
    content: str
    path: Path


def clean_help_topic_title(path: Path) -> str:
    """Convert a Markdown filename into a readable help topic title."""

    return path.stem.replace("_", " ").replace("-", " ").title()


def load_help_topics(help_dir: Path | None = None) -> tuple[HelpTopic, ...]:
    """Load help topics from Markdown files."""

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
    """Filter help topics by title or content keyword match."""

    normalized_query = (query or "").strip().lower()
    if not normalized_query:
        return topics
    return tuple(
        topic
        for topic in topics
        if normalized_query in topic.title.lower()
        or normalized_query in topic.content.lower()
    )


def render_help_page() -> None:
    """Render the Help page."""

    st.subheader("Help")
    query = st.text_input("Search help topics...", key="help_search_query")

    topics = filter_help_topics(load_help_topics(), query)
    if not topics:
        st.info("Help documentation is coming soon.")
        return

    for topic in topics:
        with st.expander(topic.title):
            st.markdown(topic.content)
