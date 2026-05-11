"""Framework-independent registry sidecar export service."""
from dataclasses import dataclass, field
import json
from pathlib import Path
import traceback

from core.dataset import TAGS, get_entry_tags
from core.models import Tag, TagCategory, TagLifecycleMetadata
from core.registry_sidecar import (
    sidecar_path_for_dataset,
    build_sidecar_registry,
    write_sidecar,
)
from core.tag_constants import TAG_ALIAS_METADATA_ACTIONS, TAG_CURRENT_METADATA_ACTIONS
from core.tag_normalization import normalize_tag
import core.tag_registry as tag_registry


@dataclass
class RegistrySidecarExportResult:
    """Structured result returned by registry sidecar export."""

    ok: bool
    message: str
    path: str | None = None
    errors: list[str] = field(default_factory=list)


def export_registry_sidecar(
    *,
    dataset_path: str,
    entries: list[dict],
) -> RegistrySidecarExportResult:
    """Export the current DB tag registry as a sidecar next to a dataset path."""
    if not dataset_path:
        return RegistrySidecarExportResult(
            ok=False,
            message="Could not export registry sidecar.",
            errors=["No export dataset path was provided."],
        )

    try:
        output_path = sidecar_path_for_dataset(Path(dataset_path))
        registry = build_sidecar_registry(
            categories=_query_categories(),
            tags=_query_tags(),
            aliases=_query_aliases(),
            dataset_filename=Path(dataset_path).name,
            entry_count=len(entries),
            tag_usage_counts=_tag_usage_counts(entries),
        )
        write_sidecar(registry, output_path)
        return RegistrySidecarExportResult(
            ok=True,
            message=f"Registry sidecar written to {output_path.name}.",
            path=str(output_path),
        )
    except Exception as exc:
        traceback.print_exc()
        return RegistrySidecarExportResult(
            ok=False,
            message=f"Could not export registry sidecar: {exc}",
            errors=[str(exc)],
        )


def _query_categories() -> list[dict]:
    default_slugs = {normalize_tag(category_name).slug for category_name in TAGS}
    session = tag_registry.SessionLocal()
    try:
        categories = (
            session.query(TagCategory)
            .order_by(TagCategory.sort_order, TagCategory.name, TagCategory.slug)
            .all()
        )
        return [
            {
                "slug": category.slug,
                "name": category.name,
                "sort_order": category.sort_order,
                "is_active": category.is_active,
                "is_builtin": category.slug in default_slugs,
            }
            for category in categories
        ]
    finally:
        session.close()


def _query_tags() -> list[dict]:
    session = tag_registry.SessionLocal()
    try:
        tags = (
            session.query(Tag)
            .outerjoin(TagCategory, Tag.category_id == TagCategory.id)
            .order_by(Tag.sort_order, Tag.name, Tag.slug)
            .all()
        )
        metadata_by_slug = _current_metadata_by_slug(session)
        return [
            {
                "slug": tag.slug,
                "name": tag.name,
                "category_slug": tag.category.slug if tag.category is not None else None,
                "sort_order": tag.sort_order,
                "status": tag.status,
                "is_active": tag.is_active,
                "is_builtin": tag.is_builtin,
                "lifecycle": metadata_by_slug.get(tag.slug, {}),
            }
            for tag in tags
        ]
    finally:
        session.close()


def _query_aliases() -> list[dict]:
    session = tag_registry.SessionLocal()
    try:
        rows = (
            session.query(TagLifecycleMetadata)
            .filter(TagLifecycleMetadata.action.in_(TAG_ALIAS_METADATA_ACTIONS))
            .order_by(TagLifecycleMetadata.id)
            .all()
        )
        return [
            {
                "old_slug": row.old_slug or "",
                "new_slug": row.new_slug,
                "action": row.action,
                "metadata": _parse_metadata(row.metadata_json),
            }
            for row in rows
            if row.old_slug
        ]
    finally:
        session.close()


def _current_metadata_by_slug(session) -> dict[str, dict]:
    rows = (
        session.query(TagLifecycleMetadata)
        .filter(TagLifecycleMetadata.action.in_(TAG_CURRENT_METADATA_ACTIONS))
        .order_by(TagLifecycleMetadata.id.desc())
        .all()
    )
    metadata_by_slug: dict[str, dict] = {}
    for row in rows:
        if not row.old_slug or row.old_slug in metadata_by_slug:
            continue
        metadata_by_slug[row.old_slug] = _parse_metadata(row.metadata_json)
    return metadata_by_slug


def _parse_metadata(metadata_json: str | None) -> dict:
    if not metadata_json:
        return {}
    try:
        metadata = json.loads(metadata_json)
    except json.JSONDecodeError:
        return {}
    return metadata if isinstance(metadata, dict) else {}


def _tag_usage_counts(entries: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for entry in entries:
        for tag in get_entry_tags(entry):
            counts[tag] = counts.get(tag, 0) + 1
    return counts
