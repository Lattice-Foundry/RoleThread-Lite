import json
from pathlib import Path

from ui.ui_faq import FAQEntry, filter_faq_entries, load_faq_entries
from ui.ui_help import HelpTopic, clean_help_topic_title, filter_help_topics, load_help_topics


def test_clean_help_topic_title_formats_filename():
    assert clean_help_topic_title(Path("getting_started.md")) == "Getting Started"


def test_load_help_topics_reads_markdown_files(tmp_path):
    help_dir = tmp_path / "help"
    help_dir.mkdir()
    (help_dir / "getting_started.md").write_text("# Welcome", encoding="utf-8")
    (help_dir / "ignore.txt").write_text("Nope", encoding="utf-8")

    topics = load_help_topics(help_dir)

    assert len(topics) == 1
    assert topics[0].title == "Getting Started"
    assert topics[0].content == "# Welcome"


def test_filter_help_topics_matches_title_and_content():
    topics = (
        HelpTopic(title="Getting Started", content="Welcome guide", path=Path("a.md")),
        HelpTopic(title="Export", content="Create JSONL files", path=Path("b.md")),
    )

    assert filter_help_topics(topics, "export") == (topics[1],)
    assert filter_help_topics(topics, "welcome") == (topics[0],)
    assert filter_help_topics(topics, "   ") == topics


def test_load_faq_entries_reads_json(tmp_path):
    (tmp_path / "faq.json").write_text(
        json.dumps([
            {"question": "What is this?", "answer": "A FAQ."},
            {"question": "", "answer": "Skipped."},
        ]),
        encoding="utf-8",
    )

    entries = load_faq_entries(tmp_path)

    assert entries == (FAQEntry(question="What is this?", answer="A FAQ."),)


def test_filter_faq_entries_matches_question_and_answer():
    entries = (
        FAQEntry(question="What is Lite?", answer="A local-first app."),
        FAQEntry(question="How do I export?", answer="Use the Export page."),
    )

    assert filter_faq_entries(entries, "export") == (entries[1],)
    assert filter_faq_entries(entries, "local") == (entries[0],)
    assert filter_faq_entries(entries, "") == entries
