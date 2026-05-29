"""Help article registry and loading helpers."""

from __future__ import annotations

from collections import OrderedDict
import json
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any


DOCS_ROOT = Path(__file__).resolve().parents[1] / "docs"
HELP_DIR = DOCS_ROOT / "help"


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
    source_path: str = ""
    public: bool = True
    audience: str = "user"


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


HELP_MANIFEST_PATH = DOCS_ROOT / "help_manifest.json"
HELP_MANIFEST_SCHEMA_VERSION = 1


class HelpManifestError(ValueError):
    """Raised when the Help taxonomy manifest is invalid."""


@dataclass(frozen=True)
class HelpCategory:
    """One display category from the Help taxonomy manifest."""

    category_id: str
    title: str
    order: int


@dataclass(frozen=True)
class HelpManifest:
    """Loaded Help documentation taxonomy manifest."""

    schema_version: int
    product: str
    default_article_id: str
    categories: tuple[HelpCategory, ...]
    articles: tuple[HelpArticle, ...]


_REQUIRED_MANIFEST_FIELDS = (
    "schema_version",
    "product",
    "default_article_id",
    "categories",
    "articles",
)
_REQUIRED_CATEGORY_FIELDS = ("id", "title", "order")
_REQUIRED_ARTICLE_FIELDS = (
    "id",
    "title",
    "source_path",
    "category",
    "order",
    "summary",
    "related_ids",
)


def load_help_manifest(
    manifest_path: Path | None = None,
    *,
    project_root: Path | None = None,
) -> HelpManifest:
    """Load and validate the repo-owned Help taxonomy manifest."""

    path = Path(manifest_path) if manifest_path is not None else HELP_MANIFEST_PATH
    root = Path(project_root or DOCS_ROOT.parent).resolve()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise HelpManifestError(f"Could not read Help manifest: {path}") from exc
    except json.JSONDecodeError as exc:
        raise HelpManifestError(f"Help manifest is not valid JSON: {path}") from exc

    manifest = _require_mapping(data, "Help manifest")
    _require_fields(manifest, _REQUIRED_MANIFEST_FIELDS, "Help manifest")

    schema_version = manifest["schema_version"]
    if (
        isinstance(schema_version, bool)
        or not isinstance(schema_version, int)
        or schema_version != HELP_MANIFEST_SCHEMA_VERSION
    ):
        raise HelpManifestError(
            "Help manifest schema_version must be "
            f"{HELP_MANIFEST_SCHEMA_VERSION}."
        )

    product = _require_text(manifest["product"], "Help manifest product")
    default_article_id = _require_text(
        manifest["default_article_id"],
        "Help manifest default_article_id",
    )
    categories = _parse_manifest_categories(manifest["categories"])
    articles = _parse_manifest_articles(
        manifest["articles"],
        categories=categories,
        project_root=root,
    )

    article_ids = {article.article_id for article in articles}
    if default_article_id not in article_ids:
        raise HelpManifestError(
            "Help manifest default_article_id references an unknown article: "
            f"{default_article_id}."
        )

    _validate_related_articles(articles, article_ids)
    return HelpManifest(
        schema_version=HELP_MANIFEST_SCHEMA_VERSION,
        product=product,
        default_article_id=default_article_id,
        categories=categories,
        articles=articles,
    )


def get_help_manifest() -> HelpManifest:
    """Return the loaded Help taxonomy manifest."""

    return HELP_MANIFEST


def get_help_categories() -> tuple[HelpCategory, ...]:
    """Return manifest Help categories in display order."""

    return HELP_MANIFEST.categories


def _parse_manifest_categories(value: object) -> tuple[HelpCategory, ...]:
    records = _require_list(value, "Help manifest categories")
    categories: list[HelpCategory] = []
    category_ids: set[str] = set()
    category_orders: set[int] = set()
    for index, raw_record in enumerate(records, start=1):
        label = f"Help manifest category #{index}"
        record = _require_mapping(raw_record, label)
        _require_fields(record, _REQUIRED_CATEGORY_FIELDS, label)
        category_id = _require_text(record["id"], f"{label} id")
        title = _require_text(record["title"], f"{label} title")
        order = _require_order(record["order"], f"{label} order")
        if category_id in category_ids:
            raise HelpManifestError(f"Duplicate Help category id: {category_id}.")
        if order in category_orders:
            raise HelpManifestError(f"Duplicate Help category order: {order}.")
        category_ids.add(category_id)
        category_orders.add(order)
        categories.append(HelpCategory(category_id, title, order))
    return tuple(sorted(categories, key=lambda category: category.order))


def _parse_manifest_articles(
    value: object,
    *,
    categories: tuple[HelpCategory, ...],
    project_root: Path,
) -> tuple[HelpArticle, ...]:
    records = _require_list(value, "Help manifest articles")
    category_titles = {category.category_id: category.title for category in categories}
    article_ids: set[str] = set()
    article_orders: set[int] = set()
    source_paths: set[str] = set()
    articles: list[HelpArticle] = []
    for index, raw_record in enumerate(records, start=1):
        label = f"Help manifest article #{index}"
        record = _require_mapping(raw_record, label)
        _require_fields(record, _REQUIRED_ARTICLE_FIELDS, label)
        article_id = _require_text(record["id"], f"{label} id")
        title = _require_text(record["title"], f"{label} title")
        source_path = _require_text(record["source_path"], f"{label} source_path")
        category_id = _require_text(record["category"], f"{label} category")
        order = _require_order(record["order"], f"{label} order")
        summary = _require_text(record["summary"], f"{label} summary")
        related_ids = _parse_related_ids(record["related_ids"], label)
        public = _parse_public_flag(record, label)
        audience = _parse_audience(record, label)

        if article_id in article_ids:
            raise HelpManifestError(f"Duplicate Help article id: {article_id}.")
        if source_path in source_paths:
            raise HelpManifestError(f"Duplicate Help article source_path: {source_path}.")
        if order in article_orders:
            raise HelpManifestError(f"Duplicate Help article order: {order}.")
        if category_id not in category_titles:
            raise HelpManifestError(
                f"{article_id} uses unknown Help category id: {category_id}."
            )

        source_file = _resolve_help_source_path(source_path, project_root)
        article_ids.add(article_id)
        article_orders.add(order)
        source_paths.add(source_path)
        articles.append(
            HelpArticle(
                article_id=article_id,
                file_name=source_file.name,
                title=title,
                category=category_titles[category_id],
                order=order,
                summary=summary,
                related_ids=related_ids,
                source_path=source_path,
                public=public,
                audience=audience,
            )
        )
    return tuple(sorted(articles, key=lambda article: article.order))


def _validate_related_articles(
    articles: tuple[HelpArticle, ...],
    article_ids: set[str],
) -> None:
    for article in articles:
        if article.article_id in article.related_ids:
            raise HelpManifestError(f"{article.article_id} relates to itself.")
        if len(article.related_ids) != len(set(article.related_ids)):
            raise HelpManifestError(
                f"{article.article_id} has duplicate related articles."
            )
        for related_id in article.related_ids:
            if related_id not in article_ids:
                raise HelpManifestError(
                    f"{article.article_id} references unknown related article "
                    f"{related_id}."
                )


def _resolve_help_source_path(source_path: str, project_root: Path) -> Path:
    path = Path(source_path)
    if path.is_absolute() or ".." in path.parts:
        raise HelpManifestError(
            f"Help article source_path must stay inside docs/help: {source_path}."
        )
    if len(path.parts) < 3 or path.parts[0] != "docs" or path.parts[1] != "help":
        raise HelpManifestError(
            f"Help article source_path must start with docs/help: {source_path}."
        )

    help_dir = (project_root / "docs" / "help").resolve()
    resolved_path = (project_root / path).resolve()
    try:
        resolved_path.relative_to(help_dir)
    except ValueError as exc:
        raise HelpManifestError(
            f"Help article source_path escapes docs/help: {source_path}."
        ) from exc
    if not resolved_path.is_file():
        raise HelpManifestError(
            f"Help article source_path does not exist: {source_path}."
        )
    return resolved_path


def _parse_related_ids(value: object, label: str) -> tuple[str, ...]:
    related_records = _require_list(value, f"{label} related_ids")
    return tuple(
        _require_text(related_id, f"{label} related_id")
        for related_id in related_records
    )


def _parse_public_flag(record: dict[str, Any], label: str) -> bool:
    value = record.get("public", True)
    if not isinstance(value, bool):
        raise HelpManifestError(f"{label} public must be a boolean.")
    return value


def _parse_audience(record: dict[str, Any], label: str) -> str:
    value = record.get("audience", "user")
    return _require_text(value, f"{label} audience")


def _require_fields(
    record: dict[str, Any],
    fields: tuple[str, ...],
    label: str,
) -> None:
    missing = [field for field in fields if field not in record]
    if missing:
        raise HelpManifestError(
            f"{label} is missing required field(s): {', '.join(missing)}."
        )


def _require_mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise HelpManifestError(f"{label} must be an object.")
    return value


def _require_list(value: object, label: str) -> list[object]:
    if not isinstance(value, list):
        raise HelpManifestError(f"{label} must be a list.")
    return value


def _require_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise HelpManifestError(f"{label} must be a non-empty string.")
    return value.strip()


def _require_order(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise HelpManifestError(f"{label} must be numeric.")
    return value


HELP_MANIFEST = load_help_manifest()
DEFAULT_HELP_ARTICLE_ID = HELP_MANIFEST.default_article_id
HELP_CATEGORIES = HELP_MANIFEST.categories
HELP_CATEGORY_ORDER = tuple(category.title for category in HELP_CATEGORIES)
HELP_ARTICLES = HELP_MANIFEST.articles


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

