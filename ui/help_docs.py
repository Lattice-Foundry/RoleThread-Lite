"""Help article registry and loading helpers."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
import re


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


@dataclass(frozen=True)
class HelpSearchResult:
    """Compact search result for the Help browser."""

    article: HelpArticle
    snippet: str


@dataclass(frozen=True)
class DocSection:
    """Parsed Markdown section heading for a Help article."""

    level: int
    title: str
    anchor: str


HELP_CATEGORY_ORDER = (
    "Getting Started",
    "Core Workflows",
    "Metadata and Organization",
    "Quality and Review",
    "Output and Recovery",
    "Reference",
    "For Developers",
)


HELP_ARTICLES: tuple[HelpArticle, ...] = (
    HelpArticle(
        "getting-started",
        "01_getting_started.md",
        "Getting Started",
        "Getting Started",
        10,
        "First-session workflow and the basic RoleThread rhythm.",
        (
            "understanding-the-main-workspaces",
            "loading-datasets-and-working-copies",
            "creating-entries",
        ),
    ),
    HelpArticle(
        "what-rolethread-lite-does",
        "02_what_rolethread_lite_does.md",
        "What RoleThread Lite Does",
        "Getting Started",
        20,
        "The app's purpose, file-owned workflow, and practical boundaries.",
        (
            "getting-started",
            "dataset-formats",
            "v1-limitations-and-future-boundaries",
            "rolethread-studio-vision",
        ),
    ),
    HelpArticle(
        "dataset-formats",
        "03_dataset_formats.md",
        "Dataset Formats",
        "Getting Started",
        30,
        "JSONL, ChatML, ShareGPT, native metadata, and clean export basics.",
        (
            "exporting-datasets",
            "default-mode-vs-group-chat",
            "sidecars-and-portable-metadata",
        ),
    ),
    HelpArticle(
        "loading-datasets-and-working-copies",
        "04_loading_datasets_and_working_copies.md",
        "Loading Datasets and Working Copies",
        "Getting Started",
        40,
        "How loading, trust checks, protected copies, and sidecars work.",
        (
            "sidecars-and-portable-metadata",
            "validation-and-repair",
            "backups-cloud-sync-and-recovery",
        ),
    ),
    HelpArticle(
        "creating-a-new-dataset",
        "05_creating_a_new_dataset.md",
        "Creating a New Dataset",
        "Getting Started",
        50,
        "Starting a fresh dataset file and understanding first-save behavior.",
        (
            "getting-started",
            "loading-datasets-and-working-copies",
            "creating-entries",
        ),
    ),
    HelpArticle(
        "understanding-the-main-workspaces",
        "06_understanding_the_main_workspaces.md",
        "Understanding the Main Workspaces",
        "Core Workflows",
        60,
        "How the main RoleThread pages fit together during normal work.",
        (
            "creating-entries",
            "editing-entries",
            "validation-and-repair",
            "insights-and-dataset-quality",
        ),
    ),
    HelpArticle(
        "creating-entries",
        "07_creating_entries.md",
        "Creating Entries",
        "Core Workflows",
        70,
        "Writing training examples, prompts, exchanges, tags, and quality cues.",
        (
            "editing-entries",
            "insights-and-dataset-quality",
            "system-prompt-library",
        ),
    ),
    HelpArticle(
        "default-mode-vs-group-chat",
        "08_default_mode_vs_group_chat.md",
        "Default Mode vs Group Chat",
        "Core Workflows",
        80,
        "Choosing entry mode and preserving character identity safely.",
        (
            "character-registry-and-character-mappings",
            "dataset-formats",
            "exporting-datasets",
        ),
    ),
    HelpArticle(
        "editing-entries",
        "09_editing_entries.md",
        "Deep Edit",
        "Core Workflows",
        90,
        "Deep editing, Full Edit, duplicate workflows, and save behavior.",
        (
            "searching-and-filtering-entries",
            "splitting-and-joining-entries",
            "validation-and-repair",
        ),
    ),
    HelpArticle(
        "searching-and-filtering-entries",
        "10_searching_and_filtering_entries.md",
        "Searching and Filtering Entries",
        "Core Workflows",
        100,
        "Finding focused subsets of a loaded dataset.",
        (
            "understanding-the-main-workspaces",
            "insights-and-dataset-quality",
            "validation-and-repair",
        ),
    ),
    HelpArticle(
        "splitting-and-joining-entries",
        "11_splitting_and_joining_entries.md",
        "Splitting and Joining Entries",
        "Core Workflows",
        110,
        "Reshaping entries while preserving useful context.",
        (
            "editing-entries",
            "validation-and-repair",
            "merging-datasets",
        ),
    ),
    HelpArticle(
        "tags-categories-and-tag-lifecycle",
        "12_tags_categories_and_tag_lifecycle.md",
        "Tags, Categories, and Tag Lifecycle",
        "Metadata and Organization",
        120,
        "Using tags and categories as durable organizational metadata.",
        (
            "understanding-default-tags",
            "archived-and-imported-tags",
            "insights-and-dataset-quality",
            "exporting-datasets",
        ),
    ),
    HelpArticle(
        "understanding-default-tags",
        "27_understanding_default_tags.md",
        "Understanding Default Tags",
        "Metadata and Organization",
        125,
        "The V1 built-in tag taxonomy and how to use defaults versus custom tags.",
        (
            "tags-categories-and-tag-lifecycle",
            "archived-and-imported-tags",
            "insights-and-dataset-quality",
        ),
    ),
    HelpArticle(
        "archived-and-imported-tags",
        "13_archived_and_imported_tags.md",
        "Archived and Imported Tags",
        "Metadata and Organization",
        130,
        "Handling unknown, inactive, and imported tag vocabulary safely.",
        (
            "understanding-default-tags",
            "tags-categories-and-tag-lifecycle",
            "loading-datasets-and-working-copies",
            "sidecars-and-portable-metadata",
        ),
    ),
    HelpArticle(
        "character-registry-and-character-mappings",
        "14_character_registry_and_character_mappings.md",
        "Character Registry and Character Mappings",
        "Metadata and Organization",
        140,
        "Preserving speaker identity without changing training roles.",
        (
            "default-mode-vs-group-chat",
            "sidecars-and-portable-metadata",
            "validation-and-repair",
        ),
    ),
    HelpArticle(
        "system-prompt-library",
        "15_system_prompt_library.md",
        "System Prompt Library",
        "Metadata and Organization",
        150,
        "Creating, loading, editing, and reusing system prompt templates.",
        (
            "creating-entries",
            "insights-and-dataset-quality",
            "default-mode-vs-group-chat",
        ),
    ),
    HelpArticle(
        "sidecars-and-portable-metadata",
        "16_sidecars_and_portable_metadata.md",
        "Sidecars and Portable Metadata",
        "Metadata and Organization",
        160,
        "Keeping RoleThread metadata portable beside clean training files.",
        (
            "loading-datasets-and-working-copies",
            "exporting-datasets",
            "backups-cloud-sync-and-recovery",
        ),
    ),
    HelpArticle(
        "validation-and-repair",
        "17_validation_and_repair.md",
        "Validation and Repair",
        "Quality and Review",
        170,
        "Finding structural and quality issues before export.",
        (
            "loading-datasets-and-working-copies",
            "insights-and-dataset-quality",
            "backups-cloud-sync-and-recovery",
        ),
    ),
    HelpArticle(
        "insights-and-dataset-quality",
        "18_insights_and_dataset_quality.md",
        "Insights and Dataset Quality",
        "Quality and Review",
        180,
        "Understanding dataset shape, health, and review priorities.",
        (
            "validation-and-repair",
            "searching-and-filtering-entries",
            "creating-entries",
        ),
    ),
    HelpArticle(
        "merging-datasets",
        "19_merging_datasets.md",
        "Merging Datasets",
        "Output and Recovery",
        190,
        "Combining datasets while preserving identity and metadata.",
        (
            "validation-and-repair",
            "sidecars-and-portable-metadata",
            "backups-cloud-sync-and-recovery",
        ),
    ),
    HelpArticle(
        "exporting-datasets",
        "20_exporting_datasets.md",
        "Exporting Datasets",
        "Output and Recovery",
        200,
        "Producing training, archive, and selected export files.",
        (
            "dataset-formats",
            "sidecars-and-portable-metadata",
            "backups-cloud-sync-and-recovery",
        ),
    ),
    HelpArticle(
        "backups-cloud-sync-and-recovery",
        "21_backups_cloud_sync_and_recovery.md",
        "Backups, Cloud Sync, and Recovery",
        "Output and Recovery",
        210,
        "Local backups, cloud sync expectations, and restore behavior.",
        (
            "loading-datasets-and-working-copies",
            "sidecars-and-portable-metadata",
            "settings-and-preferences",
        ),
    ),
    HelpArticle(
        "settings-and-preferences",
        "22_settings_and_preferences.md",
        "Settings and Preferences",
        "Output and Recovery",
        220,
        "Configuration, backup settings, safety controls, and portability.",
        (
            "backups-cloud-sync-and-recovery",
            "os-compatibility-and-storage-policy",
            "getting-started",
        ),
    ),
    HelpArticle(
        "glossary",
        "23_glossary.md",
        "Glossary",
        "Reference",
        230,
        "Key RoleThread terms and workflow vocabulary.",
        (
            "getting-started",
            "what-rolethread-lite-does",
            "understanding-the-main-workspaces",
        ),
    ),
    HelpArticle(
        "os-compatibility-and-storage-policy",
        "25_os_compatibility_and_storage.md",
        "OS Compatibility and Storage Policy",
        "Reference",
        235,
        "Official V1 platform support, runtime, storage, and launch policy.",
        (
            "settings-and-preferences",
            "backups-cloud-sync-and-recovery",
            "v1-limitations-and-future-boundaries",
        ),
    ),
    HelpArticle(
        "v1-limitations-and-future-boundaries",
        "24_v1_limitations_and_future_boundaries.md",
        "V1 Limitations and Future Boundaries",
        "Reference",
        240,
        "What Lite intentionally does and does not try to be.",
        (
            "what-rolethread-lite-does",
            "settings-and-preferences",
            "glossary",
            "rolethread-studio-vision",
        ),
    ),
    HelpArticle(
        "rolethread-studio-vision",
        "28_rolethread_studio_vision.md",
        "RoleThread Studio Vision",
        "Reference",
        245,
        "How Lite and future Studio workflows are philosophically separated.",
        (
            "what-rolethread-lite-does",
            "v1-limitations-and-future-boundaries",
            "developer-launch-flags",
        ),
    ),
    HelpArticle(
        "developer-launch-flags",
        "26_developer_launch_flags.md",
        "Developer Launch Flags",
        "For Developers",
        250,
        "Developer/tester launch flags for diagnostics and webapp startup.",
        (
            "codebase-architecture",
            "platform-support-philosophy",
            "testing-philosophy",
            "os-compatibility-and-storage-policy",
        ),
    ),
    HelpArticle(
        "codebase-architecture",
        "29_codebase_architecture.md",
        "Codebase Architecture",
        "For Developers",
        260,
        "The major codebase layers and why RoleThread keeps Streamlit as a UI shell.",
        (
            "layer-boundaries-and-responsibilities",
            "data-safety-philosophy",
            "developer-launch-flags",
            "rolethread-studio-vision",
        ),
    ),
    HelpArticle(
        "layer-boundaries-and-responsibilities",
        "30_layer_boundaries_and_responsibilities.md",
        "Layer Boundaries and Responsibilities",
        "For Developers",
        270,
        "What belongs in UI, services, and core modules.",
        (
            "codebase-architecture",
            "platform-support-philosophy",
            "data-safety-philosophy",
            "rolethread-studio-vision",
        ),
    ),
    HelpArticle(
        "platform-support-philosophy",
        "31_platform_support_philosophy.md",
        "Platform Support Philosophy",
        "For Developers",
        280,
        "How Windows, Linux, macOS, webapp mode, and storage support are scoped.",
        (
            "developer-launch-flags",
            "os-compatibility-and-storage-policy",
            "codebase-architecture",
        ),
    ),
    HelpArticle(
        "data-safety-philosophy",
        "32_data_safety_philosophy.md",
        "Data Safety Philosophy",
        "For Developers",
        290,
        "How RoleThread protects local datasets, metadata, backups, and repair workflows.",
        (
            "testing-philosophy",
            "layer-boundaries-and-responsibilities",
            "backups-cloud-sync-and-recovery",
        ),
    ),
    HelpArticle(
        "testing-philosophy",
        "33_testing_philosophy.md",
        "Testing Philosophy",
        "For Developers",
        300,
        "Why RoleThread emphasizes deterministic core and service tests.",
        (
            "data-safety-philosophy",
            "codebase-architecture",
            "developer-launch-flags",
        ),
    ),
    HelpArticle(
        "naming-and-terminology-guide",
        "34_naming_and_terminology_guide.md",
        "Naming and Terminology Guide",
        "For Developers",
        310,
        "Shared vocabulary for datasets, tags, sidecars, and product names.",
        (
            "understanding-default-tags",
            "glossary",
            "rolethread-studio-vision",
        ),
    ),
    HelpArticle(
        "ui-and-theme-style-guide",
        "35_ui_and_theme_style_guide.md",
        "UI and Theme Style Guide",
        "For Developers",
        320,
        "Design guidance for RoleThread's calm dark-theme interface.",
        (
            "settings-and-preferences",
            "codebase-architecture",
            "naming-and-terminology-guide",
        ),
    ),
)


def get_default_help_article_id() -> str:
    """Return the default Help article ID."""

    return DEFAULT_HELP_ARTICLE_ID


def get_help_article_registry() -> dict[str, HelpArticle]:
    """Return Help article metadata keyed by article ID."""

    return {article.article_id: article for article in HELP_ARTICLES}


def get_help_article_order() -> tuple[HelpArticle, ...]:
    """Return registered Help articles in reader order."""

    return tuple(sorted(HELP_ARTICLES, key=lambda item: item.order))


def get_help_category_order() -> tuple[str, ...]:
    """Return Help category display order."""

    return HELP_CATEGORY_ORDER


def get_help_articles_by_category() -> "OrderedDict[str, tuple[HelpArticle, ...]]":
    """Return registered articles grouped by category in display order."""

    grouped: "OrderedDict[str, list[HelpArticle]]" = OrderedDict(
        (category, []) for category in HELP_CATEGORY_ORDER
    )
    for article in get_help_article_order():
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


def get_help_breadcrumb(article_id: str | None) -> tuple[str, str, str]:
    """Return the display breadcrumb for one Help article."""

    article = get_help_article(article_id)
    return ("Help", article.category, article.title)


def get_adjacent_help_articles(
    article_id: str | None,
) -> tuple[HelpArticle | None, HelpArticle | None]:
    """Return previous and next articles in global registry order."""

    active_id = resolve_help_article_id(article_id)
    articles = get_help_article_order()
    for index, article in enumerate(articles):
        if article.article_id == active_id:
            previous_article = articles[index - 1] if index > 0 else None
            next_article = articles[index + 1] if index < len(articles) - 1 else None
            return previous_article, next_article
    return None, None


def get_related_help_articles(article_id: str | None) -> tuple[HelpArticle, ...]:
    """Return related articles for the given Help article."""

    article = get_help_article(article_id)
    registry = get_help_article_registry()
    return tuple(
        registry[related_id]
        for related_id in article.related_ids
        if related_id in registry
    )


def validate_help_article_registry() -> tuple[str, ...]:
    """Return registry integrity issues, if any."""

    issues: list[str] = []
    registry = get_help_article_registry()
    if len(registry) != len(HELP_ARTICLES):
        issues.append("Duplicate article IDs are registered.")

    file_names = [article.file_name for article in HELP_ARTICLES]
    if len(file_names) != len(set(file_names)):
        issues.append("Duplicate article file names are registered.")

    orders = [article.order for article in HELP_ARTICLES]
    if len(orders) != len(set(orders)):
        issues.append("Duplicate article order values are registered.")

    category_names = set(HELP_CATEGORY_ORDER)
    for article in HELP_ARTICLES:
        if article.category not in category_names:
            issues.append(f"{article.article_id} uses unknown category {article.category}.")
        if article.article_id in article.related_ids:
            issues.append(f"{article.article_id} relates to itself.")
        if len(article.related_ids) != len(set(article.related_ids)):
            issues.append(f"{article.article_id} has duplicate related articles.")
        for related_id in article.related_ids:
            if related_id not in registry:
                issues.append(
                    f"{article.article_id} references unknown related article {related_id}."
                )
    return tuple(issues)


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
        for article in get_help_article_order()
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


def _compact_text(value: str) -> str:
    return " ".join(value.split())


def _content_snippet(content: str, query: str, *, width: int = 150) -> str:
    compact_content = _compact_text(content)
    normalized_query = query.lower()
    match_index = compact_content.lower().find(normalized_query)
    if match_index < 0:
        return compact_content[:width].rstrip()

    start = max(0, match_index - 45)
    end = min(len(compact_content), match_index + len(query) + 95)
    snippet = compact_content[start:end].strip()
    if start > 0:
        snippet = f"... {snippet}"
    if end < len(compact_content):
        snippet = f"{snippet} ..."
    return snippet


def build_help_search_results(
    query: str,
    help_dir: Path | None = None,
) -> tuple[HelpSearchResult, ...]:
    """Return compact search results with display snippets."""

    normalized_query = (query or "").strip().lower()
    if not normalized_query:
        return ()

    results: list[HelpSearchResult] = []
    for document in search_help_documents(query, help_dir):
        article = document.article
        if normalized_query in article.title.lower():
            snippet = article.summary
        elif normalized_query in article.summary.lower():
            snippet = article.summary
        else:
            snippet = _content_snippet(document.content, query)
        results.append(HelpSearchResult(article=article, snippet=snippet))
    return tuple(results)


_HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_FENCE_PATTERN = re.compile(r"^\s*(```|~~~)")


def slugify_heading(value: str) -> str:
    """Return a stable lowercase anchor slug for a Markdown heading."""

    cleaned_value = _clean_heading_title(value).lower()
    cleaned_value = re.sub(r"[^\w\s-]", "", cleaned_value)
    cleaned_value = cleaned_value.replace("_", " ")
    cleaned_value = re.sub(r"[\s-]+", "-", cleaned_value).strip("-")
    return cleaned_value or "section"


def _clean_heading_title(value: str) -> str:
    title = value.strip()
    title = re.sub(r"\s+#+\s*$", "", title)
    title = re.sub(r"`([^`]*)`", r"\1", title)
    title = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", title)
    title = title.replace("*", "").replace("_", "")
    return title.strip()


def extract_markdown_sections(markdown: str) -> tuple[DocSection, ...]:
    """Extract level-two and level-three headings from Markdown content."""

    sections: list[DocSection] = []
    anchor_counts: dict[str, int] = {}
    in_fence = False
    for line in markdown.splitlines():
        if _FENCE_PATTERN.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue

        match = _HEADING_PATTERN.match(line)
        if match is None:
            continue
        level = len(match.group(1))
        if level not in (2, 3):
            continue

        title = _clean_heading_title(match.group(2))
        anchor_base = slugify_heading(title)
        anchor_counts[anchor_base] = anchor_counts.get(anchor_base, 0) + 1
        anchor = (
            anchor_base
            if anchor_counts[anchor_base] == 1
            else f"{anchor_base}-{anchor_counts[anchor_base]}"
        )
        sections.append(DocSection(level=level, title=title, anchor=anchor))
    return tuple(sections)


def format_section_outline(
    sections: tuple[DocSection, ...],
    *,
    clickable: bool = False,
) -> tuple[str, ...]:
    """Return compact Markdown lines for an article outline."""

    lines: list[str] = []
    for section in sections:
        indent = "  " if section.level == 3 else ""
        if clickable:
            lines.append(f"{indent}- [{section.title}](#{section.anchor})")
        else:
            lines.append(f"{indent}- {section.title}")
    return tuple(lines)

