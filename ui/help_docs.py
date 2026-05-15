"""Help article registry and loading helpers."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path


DOCS_ROOT = Path(__file__).resolve().parents[1] / "docs"
HELP_DIR = DOCS_ROOT / "help"
DEFAULT_HELP_ARTICLE_ID = "getting-started"


@dataclass(frozen=True)
class HelpArticle:
    """Metadata for one Help documentation article."""

    article_id: str
    file_name: str
    title: str
    category: str
    order: int
    summary: str
    related_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class HelpDocument:
    """Loaded Help article content."""

    article: HelpArticle
    content: str
    path: Path


HELP_CATEGORY_ORDER = (
    "Getting Started",
    "Core Workflows",
    "Metadata and Organization",
    "Quality and Review",
    "Output and Recovery",
    "Reference",
)


HELP_ARTICLES: tuple[HelpArticle, ...] = (
    HelpArticle(
        "getting-started",
        "01_getting_started.md",
        "Getting Started",
        "Getting Started",
        10,
        "First-session workflow and the basic LoreForge rhythm.",
    ),
    HelpArticle(
        "what-loreforge-lite-does",
        "02_what_loreforge_lite_does.md",
        "What LoreForge Lite Does",
        "Getting Started",
        20,
        "The app's purpose, local-first scope, and practical boundaries.",
    ),
    HelpArticle(
        "dataset-formats",
        "03_dataset_formats.md",
        "Dataset Formats",
        "Getting Started",
        30,
        "JSONL, ChatML, ShareGPT, native metadata, and clean export basics.",
    ),
    HelpArticle(
        "loading-datasets-and-working-copies",
        "04_loading_datasets_and_working_copies.md",
        "Loading Datasets and Working Copies",
        "Getting Started",
        40,
        "How loading, trust checks, protected copies, and sidecars work.",
    ),
    HelpArticle(
        "creating-a-new-dataset",
        "05_creating_a_new_dataset.md",
        "Creating a New Dataset",
        "Getting Started",
        50,
        "Starting a fresh dataset file and understanding first-save behavior.",
    ),
    HelpArticle(
        "understanding-the-main-workspaces",
        "06_understanding_the_main_workspaces.md",
        "Understanding the Main Workspaces",
        "Core Workflows",
        60,
        "How the main LoreForge pages fit together during normal work.",
    ),
    HelpArticle(
        "creating-entries",
        "07_creating_entries.md",
        "Creating Entries",
        "Core Workflows",
        70,
        "Writing training examples, prompts, exchanges, tags, and quality cues.",
    ),
    HelpArticle(
        "default-mode-vs-group-chat",
        "08_default_mode_vs_group_chat.md",
        "Default Mode vs Group Chat",
        "Core Workflows",
        80,
        "Choosing entry mode and preserving character identity safely.",
    ),
    HelpArticle(
        "editing-entries",
        "09_editing_entries.md",
        "Editing Entries",
        "Core Workflows",
        90,
        "Quick Edit, Full Edit, duplicate workflows, and save behavior.",
    ),
    HelpArticle(
        "searching-and-filtering-entries",
        "10_searching_and_filtering_entries.md",
        "Searching and Filtering Entries",
        "Core Workflows",
        100,
        "Finding focused subsets of a loaded dataset.",
    ),
    HelpArticle(
        "splitting-and-joining-entries",
        "11_splitting_and_joining_entries.md",
        "Splitting and Joining Entries",
        "Core Workflows",
        110,
        "Reshaping entries while preserving useful context.",
    ),
    HelpArticle(
        "tags-categories-and-tag-lifecycle",
        "12_tags_categories_and_tag_lifecycle.md",
        "Tags, Categories, and Tag Lifecycle",
        "Metadata and Organization",
        120,
        "Using tags and categories as durable organizational metadata.",
    ),
    HelpArticle(
        "archived-and-imported-tags",
        "13_archived_and_imported_tags.md",
        "Archived and Imported Tags",
        "Metadata and Organization",
        130,
        "Handling unknown, inactive, and imported tag vocabulary safely.",
    ),
    HelpArticle(
        "character-registry-and-character-mappings",
        "14_character_registry_and_character_mappings.md",
        "Character Registry and Character Mappings",
        "Metadata and Organization",
        140,
        "Preserving speaker identity without changing training roles.",
    ),
    HelpArticle(
        "system-prompt-library",
        "15_system_prompt_library.md",
        "System Prompt Library",
        "Metadata and Organization",
        150,
        "Creating, loading, editing, and reusing system prompt templates.",
    ),
    HelpArticle(
        "sidecars-and-portable-metadata",
        "16_sidecars_and_portable_metadata.md",
        "Sidecars and Portable Metadata",
        "Metadata and Organization",
        160,
        "Keeping LoreForge metadata portable beside clean training files.",
    ),
    HelpArticle(
        "validation-and-repair",
        "17_validation_and_repair.md",
        "Validation and Repair",
        "Quality and Review",
        170,
        "Finding structural and quality issues before export.",
    ),
    HelpArticle(
        "insights-and-dataset-quality",
        "18_insights_and_dataset_quality.md",
        "Insights and Dataset Quality",
        "Quality and Review",
        180,
        "Understanding dataset shape, health, and review priorities.",
    ),
    HelpArticle(
        "merging-datasets",
        "19_merging_datasets.md",
        "Merging Datasets",
        "Output and Recovery",
        190,
        "Combining datasets while preserving identity and metadata.",
    ),
    HelpArticle(
        "exporting-datasets",
        "20_exporting_datasets.md",
        "Exporting Datasets",
        "Output and Recovery",
        200,
        "Producing training, archive, and selected export files.",
    ),
    HelpArticle(
        "backups-cloud-sync-and-recovery",
        "21_backups_cloud_sync_and_recovery.md",
        "Backups, Cloud Sync, and Recovery",
        "Output and Recovery",
        210,
        "Local backups, cloud sync expectations, and restore behavior.",
    ),
    HelpArticle(
        "settings-and-preferences",
        "22_settings_and_preferences.md",
        "Settings and Preferences",
        "Output and Recovery",
        220,
        "Configuration, backup settings, safety controls, and portability.",
    ),
    HelpArticle(
        "glossary",
        "23_glossary.md",
        "Glossary",
        "Reference",
        230,
        "Key LoreForge terms and workflow vocabulary.",
    ),
    HelpArticle(
        "v1-limitations-and-future-boundaries",
        "24_v1_limitations_and_future_boundaries.md",
        "V1 Limitations and Future Boundaries",
        "Reference",
        240,
        "What Lite intentionally does and does not try to be.",
    ),
)


def get_default_help_article_id() -> str:
    """Return the default Help article ID."""

    return DEFAULT_HELP_ARTICLE_ID


def get_help_article_registry() -> dict[str, HelpArticle]:
    """Return Help article metadata keyed by article ID."""

    return {article.article_id: article for article in HELP_ARTICLES}


def get_help_category_order() -> tuple[str, ...]:
    """Return Help category display order."""

    return HELP_CATEGORY_ORDER


def get_help_articles_by_category() -> "OrderedDict[str, tuple[HelpArticle, ...]]":
    """Return registered articles grouped by category in display order."""

    grouped: "OrderedDict[str, list[HelpArticle]]" = OrderedDict(
        (category, []) for category in HELP_CATEGORY_ORDER
    )
    for article in sorted(HELP_ARTICLES, key=lambda item: item.order):
        grouped.setdefault(article.category, []).append(article)
    return OrderedDict(
        (category, tuple(articles))
        for category, articles in grouped.items()
        if articles
    )


def resolve_help_article_id(article_id: str | None) -> str:
    """Return a known article ID, falling back to the default article."""

    if article_id in get_help_article_registry():
        return str(article_id)
    return DEFAULT_HELP_ARTICLE_ID


def get_help_article(article_id: str | None) -> HelpArticle:
    """Return article metadata, falling back safely for unknown IDs."""

    registry = get_help_article_registry()
    return registry[resolve_help_article_id(article_id)]


def load_help_document(
    article_id: str | None,
    help_dir: Path | None = None,
) -> HelpDocument:
    """Load one Help document by article ID."""

    article = get_help_article(article_id)
    source_dir = help_dir or HELP_DIR
    path = source_dir / article.file_name
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        content = ""
    return HelpDocument(article=article, content=content, path=path)


def load_help_documents(help_dir: Path | None = None) -> tuple[HelpDocument, ...]:
    """Load all registered Help documents in article order."""

    return tuple(
        load_help_document(article.article_id, help_dir)
        for article in sorted(HELP_ARTICLES, key=lambda item: item.order)
    )


def search_help_documents(
    query: str,
    help_dir: Path | None = None,
) -> tuple[HelpDocument, ...]:
    """Search registered Help docs by title, summary, or Markdown content."""

    normalized_query = (query or "").strip().lower()
    documents = load_help_documents(help_dir)
    if not normalized_query:
        return documents
    return tuple(
        document
        for document in documents
        if normalized_query in document.article.title.lower()
        or normalized_query in document.article.summary.lower()
        or normalized_query in document.content.lower()
    )
