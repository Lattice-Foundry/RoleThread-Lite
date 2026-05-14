"""FAQ documentation page for LoreForge Lite."""
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

import streamlit as st


DOCS_ROOT = Path(__file__).resolve().parents[1] / "docs"
FAQ_JSON = DOCS_ROOT / "faq.json"
FAQ_YAML = DOCS_ROOT / "faq.yaml"


@dataclass(frozen=True)
class FAQEntry:
    """Loaded FAQ question and answer."""

    question: str
    answer: str


def _load_yaml_faq(path: Path) -> list[dict[str, Any]]:
    try:
        import yaml
    except ImportError:
        return []

    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else []


def _coerce_faq_entries(raw_entries: list[dict[str, Any]]) -> tuple[FAQEntry, ...]:
    entries: list[FAQEntry] = []
    for raw_entry in raw_entries:
        question = str(raw_entry.get("question", "")).strip()
        answer = str(raw_entry.get("answer", "")).strip()
        if question and answer:
            entries.append(FAQEntry(question=question, answer=answer))
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


def filter_faq_entries(
    entries: tuple[FAQEntry, ...],
    query: str,
) -> tuple[FAQEntry, ...]:
    """Filter FAQ entries by question or answer keyword match."""

    normalized_query = (query or "").strip().lower()
    if not normalized_query:
        return entries
    return tuple(
        entry
        for entry in entries
        if normalized_query in entry.question.lower()
        or normalized_query in entry.answer.lower()
    )


def render_faq_page() -> None:
    """Render the FAQ page."""

    st.subheader("FAQ")
    query = st.text_input("Search FAQ...", key="faq_search_query")

    entries = filter_faq_entries(load_faq_entries(), query)
    if not entries:
        st.info("FAQ is coming soon.")
        return

    for entry in entries:
        with st.expander(entry.question):
            st.markdown(entry.answer)
