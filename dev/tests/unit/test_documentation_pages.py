import json
from pathlib import Path

from ui.ui_faq import FAQEntry, filter_faq_entries, load_faq_entries
from ui.ui_help import HelpTopic, clean_help_topic_title, filter_help_topics, load_help_topics
from ui.help_docs import (
    HELP_DIR,
    build_help_search_results,
    extract_markdown_sections,
    format_section_outline,
    get_adjacent_help_articles,
    get_default_help_article_id,
    get_help_article,
    get_help_article_order,
    get_help_breadcrumb,
    get_help_article_registry,
    get_help_articles_by_category,
    get_help_category_order,
    get_related_help_articles,
    load_help_document,
    resolve_help_article_id,
    search_help_documents,
    slugify_heading,
    validate_help_article_registry,
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


def test_help_article_registry_validates_relationships():
    assert validate_help_article_registry() == ()


def test_help_article_order_is_global_reader_order():
    ordered_ids = [article.article_id for article in get_help_article_order()]

    assert ordered_ids[0] == "getting-started"
    assert ordered_ids[-1] == "v1-limitations-and-future-boundaries"
    assert ordered_ids.index("creating-entries") < ordered_ids.index("editing-entries")


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


def test_help_breadcrumb_uses_registry_metadata():
    assert get_help_breadcrumb("creating-entries") == (
        "Help",
        "Core Workflows",
        "Creating Entries",
    )


def test_adjacent_help_articles_follow_global_order():
    previous_article, next_article = get_adjacent_help_articles("creating-entries")

    assert previous_article.article_id == "understanding-the-main-workspaces"
    assert next_article.article_id == "default-mode-vs-group-chat"
    assert get_adjacent_help_articles("getting-started")[0] is None
    assert get_adjacent_help_articles("v1-limitations-and-future-boundaries")[1] is None


def test_related_help_articles_follow_registry_metadata():
    related_articles = get_related_help_articles("getting-started")

    assert [article.article_id for article in related_articles] == [
        "understanding-the-main-workspaces",
        "loading-datasets-and-working-copies",
        "creating-entries",
    ]


def test_help_related_ids_are_known_unique_and_not_self_referential():
    registry = get_help_article_registry()

    for article in registry.values():
        assert len(article.related_ids) == len(set(article.related_ids))
        assert article.article_id not in article.related_ids
        assert set(article.related_ids) <= set(registry)


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


def test_build_help_search_results_returns_compact_snippets(tmp_path):
    help_dir = tmp_path / "help"
    help_dir.mkdir()
    for article in get_help_article_registry().values():
        content = f"# {article.title}\n\nPlain article body."
        if article.article_id == "creating-entries":
            content += "\n\nThe hidden marker appears inside this article body."
        (help_dir / article.file_name).write_text(content, encoding="utf-8")

    summary_results = build_help_search_results("first-session workflow", help_dir)
    content_results = build_help_search_results("hidden marker", help_dir)

    assert summary_results[0].article.article_id == "getting-started"
    assert summary_results[0].snippet == "First-session workflow and the basic LoreForge rhythm."
    assert content_results[0].article.article_id == "creating-entries"
    assert "hidden marker" in content_results[0].snippet.lower()


def test_slugify_heading_normalizes_punctuation_and_spacing():
    assert slugify_heading("Clean Export: JSONL & Sidecars!") == "clean-export-jsonl-sidecars"
    assert slugify_heading("  `System Prompt` Template  ") == "system-prompt-template"


def test_slugify_heading_matches_expected_streamlit_style_examples():
    assert slugify_heading("The Short Version") == "the-short-version"
    assert slugify_heading("Included Example Datasets") == "included-example-datasets"
    assert (
        slugify_heading("Writing Effective Narrative Training Data")
        == "writing-effective-narrative-training-data"
    )
    assert (
        slugify_heading("Narrative-Heavy vs Dialogue-Heavy")
        == "narrative-heavy-vs-dialogue-heavy"
    )


def test_extract_markdown_sections_reads_level_two_and_three_headings():
    sections = extract_markdown_sections(
        "# Article Title\n\n"
        "## First Section\n\n"
        "### Nested Section\n\n"
        "#### Too Deep\n\n"
        "## Second Section\n"
    )

    assert [(section.level, section.title, section.anchor) for section in sections] == [
        (2, "First Section", "first-section"),
        (3, "Nested Section", "nested-section"),
        (2, "Second Section", "second-section"),
    ]


def test_extract_markdown_sections_ignores_code_fence_headings():
    sections = extract_markdown_sections(
        "## Real Section\n\n"
        "```markdown\n"
        "## Not A Section\n"
        "```\n"
        "~~~\n"
        "### Also Ignored\n"
        "~~~\n"
        "### Real Subsection\n"
    )

    assert [section.title for section in sections] == [
        "Real Section",
        "Real Subsection",
    ]


def test_extract_markdown_sections_deduplicates_anchors():
    sections = extract_markdown_sections(
        "## Repeat\n"
        "### Repeat\n"
        "## Repeat!\n"
    )

    assert [section.anchor for section in sections] == [
        "repeat",
        "repeat-2",
        "repeat-3",
    ]


def test_extract_markdown_sections_returns_empty_for_no_sections():
    assert extract_markdown_sections("# Only Title\n\nPlain text.") == ()


def test_format_section_outline_supports_informational_and_clickable_lines():
    sections = extract_markdown_sections("## Parent\n### Child")

    assert format_section_outline(sections) == (
        "- Parent",
        "  - Child",
    )
    assert format_section_outline(sections, clickable=True) == (
        "- [Parent](#parent)",
        "  - [Child](#child)",
    )


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
