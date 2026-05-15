import json
from pathlib import Path

from ui.ui_faq import FAQEntry, filter_faq_entries, load_faq_entries
from ui.ui_help import HelpTopic, clean_help_topic_title, filter_help_topics, load_help_topics
from ui.help_docs import (
    HELP_DIR,
    get_default_help_article_id,
    get_help_article,
    get_help_article_registry,
    get_help_articles_by_category,
    get_help_category_order,
    load_help_document,
    resolve_help_article_id,
    search_help_documents,
)


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


def test_help_article_registry_has_expected_articles():
    registry = get_help_article_registry()

    assert len(registry) == 24
    assert get_default_help_article_id() == "getting-started"
    assert registry["getting-started"].file_name == "01_getting_started.md"
    assert registry["glossary"].category == "Reference"
    assert len(registry) == len(set(registry))


def test_help_article_registry_files_exist():
    for article in get_help_article_registry().values():
        assert (HELP_DIR / article.file_name).is_file()


def test_help_article_registry_has_unique_file_names_and_orders():
    articles = tuple(get_help_article_registry().values())
    file_names = [article.file_name for article in articles]
    orders = [article.order for article in articles]

    assert len(file_names) == len(set(file_names))
    assert len(orders) == len(set(orders))


def test_help_article_category_order_and_grouping():
    grouped = get_help_articles_by_category()

    assert tuple(grouped) == get_help_category_order()
    assert [article.article_id for article in grouped["Getting Started"]] == [
        "getting-started",
        "what-loreforge-lite-does",
        "dataset-formats",
        "loading-datasets-and-working-copies",
        "creating-a-new-dataset",
    ]
    assert [article.article_id for article in grouped["Reference"]] == [
        "glossary",
        "v1-limitations-and-future-boundaries",
    ]


def test_help_article_lookup_falls_back_to_default():
    assert resolve_help_article_id(None) == "getting-started"
    assert resolve_help_article_id("missing") == "getting-started"
    assert get_help_article("missing").article_id == "getting-started"
    assert get_help_article("exporting-datasets").title == "Exporting Datasets"


def test_load_help_document_reads_registered_markdown():
    document = load_help_document("getting-started")

    assert document.article.article_id == "getting-started"
    assert document.path.name == "01_getting_started.md"
    assert document.content.startswith("# Getting Started")


def test_search_help_documents_matches_title_summary_and_content(tmp_path):
    help_dir = tmp_path / "help"
    help_dir.mkdir()
    for article in get_help_article_registry().values():
        content = f"# {article.title}\n\nPlain article body."
        if article.article_id == "creating-entries":
            content += "\n\nNeedle content marker."
        (help_dir / article.file_name).write_text(content, encoding="utf-8")

    title_matches = search_help_documents("Exporting Datasets", help_dir)
    summary_matches = search_help_documents("first-session workflow", help_dir)
    content_matches = search_help_documents("needle content", help_dir)

    assert [doc.article.article_id for doc in title_matches] == ["exporting-datasets"]
    assert [doc.article.article_id for doc in summary_matches] == ["getting-started"]
    assert [doc.article.article_id for doc in content_matches] == ["creating-entries"]


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
