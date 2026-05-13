"""Framework-independent tag lifecycle mutation services."""
from dataclasses import dataclass, field
import copy
import json
from pathlib import Path
import traceback

from sqlalchemy import func

from core.backups import create_dataset_backup
from core.dataset import (
    TAGS,
    canonicalize_entry_tag_aliases,
    get_entry_tags,
    normalize_dataset_tags,
    save_dataset,
    set_entry_tags,
)
from core.loreforge_meta import stamp_entries
import core.tag_registry as tag_registry
from core.tag_metadata import (
    build_active_assigned_metadata,
    build_deleted_archive_metadata,
    build_rename_alias_metadata,
    clear_current_tag_lifecycle_metadata,
    clear_or_replace_tag_lifecycle_metadata,
    upsert_tag_lifecycle_metadata,
)
from core.tag_resolution import resolve_tag_lifecycle
from core.tag_constants import (
    ARCHIVE_ORIGIN_IMPORTED,
    LIFECYCLE_STATE_ACTIVE,
    TAG_ALIAS_METADATA_ACTIONS,
    TAG_CURRENT_METADATA_ACTIONS,
    TAG_LIFECYCLE_METADATA_ARCHIVE,
    TAG_LIFECYCLE_METADATA_ASSIGN_CATEGORY,
    TAG_LIFECYCLE_METADATA_RENAME,
    TAG_STATUS_ACTIVE,
    TAG_STATUS_ARCHIVED,
)
from core.models import (
    CategoryHistory,
    Tag,
    TagCategory,
    TagLifecycleMetadata,
)
from core.tag_normalization import normalize_tag
from core.text_helpers import count_phrase
from core.working_copy import canonical_training_dataset_path, migrate_training_dataset_to_subfolder
from services.registry_sidecar_service import export_registry_sidecar


@dataclass
class TagLifecycleOperationResult:
    """Structured result returned by tag lifecycle services."""

    ok: bool
    message: str
    errors: list[str] = field(default_factory=list)
    affected_count: int = 0
    tag_slugs: list[str] = field(default_factory=list)
    category_slug: str | None = None
    db_backup_path: str | None = None
    dataset_backup_path: str | None = None
    entries: list[dict] | None = None
    old_slug: str | None = None
    new_slug: str | None = None
    old_display_name: str | None = None
    new_display_name: str | None = None
    dataset_path: str | None = None


class LifecyclePipeline:
    """Context manager for protected lifecycle persistence operations."""

    def __init__(self, *, dataset_path: str | None = None):
        self.dataset_path = dataset_path
        self.session = None
        self.dataset_backup_path: Path | str | None = None
        self.db_backup_path: Path | str | None = None
        self.saved_entries: list[dict] | None = None

    def __enter__(self):
        self.session = tag_registry.SessionLocal()
        return self

    def __exit__(self, exc_type, exc, traceback):
        try:
            if exc_type is not None and self.session is not None:
                self.session.rollback()
        finally:
            if self.session is not None:
                self.session.close()
        return False

    def result(self, *, ok: bool, message: str, include_backups: bool = True, **fields):
        if self.dataset_path:
            fields.setdefault("dataset_path", self.dataset_path)
        if include_backups:
            fields.setdefault(
                "dataset_backup_path",
                str(Path(self.dataset_backup_path)) if self.dataset_backup_path else None,
            )
            fields.setdefault(
                "db_backup_path",
                str(Path(self.db_backup_path)) if self.db_backup_path else None,
            )
        return TagLifecycleOperationResult(ok=ok, message=message, **fields)

    def create_dataset_backup(self, *, reason: str, failure_fields: dict):
        try:
            self.dataset_backup_path = create_dataset_backup(self.dataset_path, reason)
            if self.dataset_backup_path is None:
                raise FileNotFoundError(
                    "Could not create dataset backup because the dataset file was not found."
                )
        except Exception as exc:
            traceback.print_exc()
            return self.result(
                ok=False,
                message=f"Failed to create dataset backup: {exc}",
                include_backups=False,
                **failure_fields,
            )
        return None

    def create_db_backup(self, *, failure_fields: dict):
        try:
            self.db_backup_path = tag_registry.create_db_backup(
                engine=tag_registry.engine
            )
        except Exception as exc:
            traceback.print_exc()
            return self.result(
                ok=False,
                message=f"Could not create database backup: {exc}",
                **failure_fields,
            )
        return None

    def save_jsonl(self, entries: list[dict], *, failure_fields: dict):
        try:
            self.dataset_path = _prepare_dataset_save_path(self.dataset_path)
            canonical_entries, _summary = canonicalize_entry_tag_aliases(
                entries,
                resolve_tag_lifecycle,
            )
            self.saved_entries = stamp_entries(canonical_entries)
            save_dataset(self.dataset_path, self.saved_entries)
            entries[:] = self.saved_entries
        except Exception as exc:
            traceback.print_exc()
            self.session.rollback()
            return self.result(
                ok=False,
                message=f"Failed to save dataset: {exc}",
                **failure_fields,
            )
        return None

    def commit_success(self, *, message: str, success_fields: dict, error_fields: dict):
        try:
            self.session.commit()
        except Exception as exc:
            traceback.print_exc()
            self.session.rollback()
            return self.result(
                ok=False,
                message=f"Database error: {exc}",
                include_backups=False,
                **error_fields,
            )
        self.refresh_sidecar()
        return self.result(ok=True, message=message, **success_fields)

    def refresh_sidecar(self) -> None:
        if not self.dataset_path or self.saved_entries is None:
            return
        try:
            result = export_registry_sidecar(
                dataset_path=self.dataset_path,
                entries=self.saved_entries,
            )
        except Exception:
            traceback.print_exc()
            return
        if not result.ok:
            print(result.message)

    def database_error(self, exc: Exception, *, fields: dict) -> TagLifecycleOperationResult:
        self.session.rollback()
        return self.result(
            ok=False,
            message=f"Database error: {exc}",
            include_backups=False,
            **fields,
        )


def _prepare_dataset_save_path(dataset_path: str | None) -> str:
    source = Path(dataset_path or "")
    if source.exists():
        return migrate_training_dataset_to_subfolder(source).working_path
    return str(canonical_training_dataset_path(source))


def _default_category_slugs() -> set[str]:
    """Return immutable built-in category slugs."""
    return {normalize_tag(name).slug for name in TAGS}


def _normalized_unique_slugs(tag_slugs: list[str]) -> tuple[list[str], list[str]]:
    normalized_slugs: list[str] = []
    errors: list[str] = []
    seen: set[str] = set()

    for raw_slug in tag_slugs:
        normalized = normalize_tag(raw_slug)
        if not normalized.slug:
            errors.append("Selected tags include an invalid tag slug.")
            continue
        if normalized.slug not in seen:
            seen.add(normalized.slug)
            normalized_slugs.append(normalized.slug)

    if not normalized_slugs:
        errors.append("No archived tags selected.")
    return normalized_slugs, errors


def _current_metadata(session, slug: str) -> dict:
    history = (
        session.query(TagLifecycleMetadata)
        .filter(
            TagLifecycleMetadata.old_slug == slug,
            TagLifecycleMetadata.action.in_(TAG_CURRENT_METADATA_ACTIONS),
        )
        .order_by(TagLifecycleMetadata.id.desc())
        .first()
    )
    if history is None or not history.metadata_json:
        return {}
    try:
        metadata = json.loads(history.metadata_json)
    except json.JSONDecodeError:
        return {}
    return metadata if isinstance(metadata, dict) else {}


def _is_imported_archived_tag(session, tag: Tag) -> bool:
    metadata = _current_metadata(session, tag.slug)
    archive_origin = metadata.get("archive_origin")
    if archive_origin is None and tag.category_id is None:
        archive_origin = ARCHIVE_ORIGIN_IMPORTED
    return archive_origin == ARCHIVE_ORIGIN_IMPORTED


def _tag_label(tag: Tag | None, slug: str) -> str:
    """Return a user-facing tag label for service messages."""
    return tag.name if tag is not None else tag_registry.prettify_tag_name(slug)


def _validate_dataset_path(dataset_path: str) -> list[str]:
    if not dataset_path:
        return ["No dataset loaded. Please load or create a dataset before saving."]
    if not Path(dataset_path).is_file():
        return ["Dataset file was not found."]
    return []


def _rewrite_entry_tag_slug(
    entries: list[dict],
    *,
    old_slug: str,
    new_slug: str,
) -> tuple[list[dict], int]:
    """Return entries with one canonical tag slug replaced and deduplicated."""
    proposed_entries = copy.deepcopy(entries)
    changed_entries = 0

    for entry in proposed_entries:
        if not isinstance(entry, dict):
            continue
        tags = get_entry_tags(entry)
        if old_slug not in tags:
            continue
        changed_entries += 1
        rewritten_tags = [new_slug if tag == old_slug else tag for tag in tags]
        set_entry_tags(entry, rewritten_tags)

    normalized = normalize_dataset_tags(proposed_entries).entries
    return normalized, changed_entries


def _remove_entry_tag_slug(
    entries: list[dict],
    *,
    tag_slug: str,
) -> tuple[list[dict], int]:
    """Return entries with one canonical tag slug removed from tag lists."""
    proposed_entries = copy.deepcopy(entries)
    changed_entries = 0

    for entry in proposed_entries:
        if not isinstance(entry, dict):
            continue
        tags = get_entry_tags(entry)
        if tag_slug not in tags:
            continue
        changed_entries += 1
        set_entry_tags(entry, [tag for tag in tags if tag != tag_slug])

    normalized = normalize_dataset_tags(proposed_entries).entries
    return normalized, changed_entries


def _alias_slug_is_reserved(session, slug: str, *, old_slug: str) -> bool:
    """Return True when slug is already an alias key for another lifecycle map."""
    if slug == old_slug:
        return False
    return (
        session.query(TagLifecycleMetadata)
        .filter(
            TagLifecycleMetadata.old_slug == slug,
            TagLifecycleMetadata.action.in_(TAG_ALIAS_METADATA_ACTIONS),
        )
        .first()
        is not None
    )


def create_custom_category(name: str) -> tuple[bool, str]:
    """Validate and insert a user-defined tag category."""
    name = name.strip()
    if not name:
        return False, "Category name cannot be empty."

    slug = tag_registry.slugify_tag_name(name)
    if not slug:
        return False, "Could not generate a valid slug from the provided name."

    display_name = tag_registry.prettify_tag_name(slug)

    with LifecyclePipeline() as pipeline:
        session = pipeline.session
        try:
            if session.query(TagCategory).filter_by(slug=slug).first() is not None:
                return False, f"A category with slug '{slug}' already exists."

            active_count = session.query(TagCategory).filter_by(is_active=True).count()
            if active_count >= tag_registry._MAX_ACTIVE_CATEGORIES:
                return (
                    False,
                    f"Category limit reached. "
                    f"This version supports {tag_registry._MAX_ACTIVE_CATEGORIES} active categories.",
                )

            max_order: int = session.query(func.max(TagCategory.sort_order)).scalar() or 0

            backup_error = pipeline.create_db_backup(failure_fields={})
            if backup_error is not None:
                return backup_error.ok, backup_error.message

            category = TagCategory(
                name=display_name,
                slug=slug,
                sort_order=max_order + 1,
                is_active=True,
            )
            session.add(category)
            result = pipeline.commit_success(
                message="Category created.",
                success_fields={},
                error_fields={},
            )
            return result.ok, result.message
        except Exception as exc:
            traceback.print_exc()
            result = pipeline.database_error(exc, fields={})
            return result.ok, result.message


def create_custom_tag(category_id: int, name: str) -> tuple[bool, str]:
    """Validate and insert a custom tag into an existing category."""
    name = name.strip()
    if not name:
        return False, "Tag name cannot be empty."

    slug = tag_registry.slugify_tag_name(name)
    if not slug:
        return False, "Could not generate a valid slug from the provided name."

    display_name = tag_registry.prettify_tag_name(slug)

    with LifecyclePipeline() as pipeline:
        session = pipeline.session
        try:
            category = (
                session.query(TagCategory)
                .filter_by(id=category_id, is_active=True)
                .first()
            )
            if category is None:
                return False, "Selected category does not exist or is inactive."

            if session.query(Tag).filter_by(slug=slug).first() is not None:
                return False, f"A tag with slug '{slug}' already exists."

            max_order: int = (
                session.query(func.max(Tag.sort_order))
                .filter_by(category_id=category_id)
                .scalar()
            ) or 0

            backup_error = pipeline.create_db_backup(failure_fields={})
            if backup_error is not None:
                return backup_error.ok, backup_error.message

            tag = Tag(
                category_id=category_id,
                name=display_name,
                slug=slug,
                sort_order=max_order + 1,
                is_active=True,
                is_builtin=False,
                status=TAG_STATUS_ACTIVE,
            )
            session.add(tag)
            result = pipeline.commit_success(
                message="Tag created.",
                success_fields={},
                error_fields={},
            )
            return result.ok, result.message
        except Exception as exc:
            traceback.print_exc()
            result = pipeline.database_error(exc, fields={})
            return result.ok, result.message


def assign_archived_imported_tags_to_category(
    *,
    tag_slugs: list[str],
    category_slug: str,
) -> TagLifecycleOperationResult:
    """Activate archived/imported tags under an active category."""
    normalized_tag_slugs, errors = _normalized_unique_slugs(tag_slugs)
    normalized_category = normalize_tag(category_slug).slug
    if not normalized_category:
        errors.append("Selected category does not exist or is inactive.")

    if errors:
        return TagLifecycleOperationResult(
            ok=False,
            message="Could not assign archived tags.",
            errors=errors,
            tag_slugs=normalized_tag_slugs,
            category_slug=normalized_category or None,
        )

    with LifecyclePipeline() as pipeline:
        session = pipeline.session
        category = (
            session.query(TagCategory)
            .filter_by(slug=normalized_category, is_active=True)
            .first()
        )
        if category is None:
            return TagLifecycleOperationResult(
                ok=False,
                message="Could not assign archived tags.",
                errors=["Selected category does not exist or is inactive."],
                tag_slugs=normalized_tag_slugs,
                category_slug=normalized_category,
            )

        tags: list[Tag] = []
        validation_errors: list[str] = []
        for slug in normalized_tag_slugs:
            tag = session.query(Tag).filter_by(slug=slug).order_by(Tag.id).first()
            if tag is None:
                validation_errors.append(f"Tag not found: {_tag_label(None, slug)}")
                continue
            tag_label = _tag_label(tag, slug)

            conflicting_active = (
                session.query(Tag)
                .join(TagCategory, Tag.category_id == TagCategory.id)
                .filter(
                    Tag.slug == slug,
                    Tag.id != tag.id,
                    Tag.status == TAG_STATUS_ACTIVE,
                    Tag.is_active.is_(True),
                    TagCategory.is_active.is_(True),
                )
                .first()
            )
            if conflicting_active is not None:
                validation_errors.append(
                    f"An active tag already exists for: {tag_label}"
                )
                continue

            if tag.status != TAG_STATUS_ARCHIVED:
                validation_errors.append(f"Tag is not archived: {tag_label}")
                continue
            if not _is_imported_archived_tag(session, tag):
                validation_errors.append(
                    f"Tag is not an imported archived tag: {tag_label}"
                )
                continue

            tags.append(tag)

        if validation_errors:
            return TagLifecycleOperationResult(
                ok=False,
                message="Could not assign archived tags.",
                errors=validation_errors,
                tag_slugs=normalized_tag_slugs,
                category_slug=normalized_category,
            )

        backup_error = pipeline.create_db_backup(
            failure_fields={
                "tag_slugs": normalized_tag_slugs,
                "category_slug": normalized_category,
            }
        )
        if backup_error is not None:
            return backup_error

        try:
            max_order = (
                session.query(Tag)
                .filter_by(category_id=category.id)
                .order_by(Tag.sort_order.desc())
                .first()
            )
            next_sort_order = (max_order.sort_order if max_order is not None else 0) + 1

            for offset, tag in enumerate(tags):
                tag.status = TAG_STATUS_ACTIVE
                tag.is_active = True
                tag.category_id = category.id
                tag.sort_order = next_sort_order + offset
                clear_or_replace_tag_lifecycle_metadata(
                    action=TAG_LIFECYCLE_METADATA_ASSIGN_CATEGORY,
                    old_slug=tag.slug,
                    old_display_name=tag.name,
                    old_category_slug=None,
                    new_slug=tag.slug,
                    new_display_name=tag.name,
                    new_category_slug=category.slug,
                    metadata=build_active_assigned_metadata(category.slug),
                    session=session,
                )

            return pipeline.commit_success(
                message=(
                    f"Assigned {count_phrase(len(tags), 'archived tag')} "
                    f"to {category.name}."
                ),
                success_fields={
                    "affected_count": len(tags),
                    "tag_slugs": [tag.slug for tag in tags],
                    "category_slug": category.slug,
                },
                error_fields={
                    "tag_slugs": normalized_tag_slugs,
                    "category_slug": normalized_category,
                },
            )
        except Exception as exc:
            traceback.print_exc()
            return pipeline.database_error(
                exc,
                fields={
                    "tag_slugs": normalized_tag_slugs,
                    "category_slug": normalized_category,
                },
            )


def assign_archived_imported_tag_to_category(
    *,
    tag_slug: str,
    category_slug: str,
) -> TagLifecycleOperationResult:
    """Activate one archived/imported tag under an active category."""
    return assign_archived_imported_tags_to_category(
        tag_slugs=[tag_slug],
        category_slug=category_slug,
    )


def rename_custom_category(
    *,
    category_slug: str,
    new_display_name: str,
) -> TagLifecycleOperationResult:
    """Rename one custom active category without touching dataset JSONL."""
    normalized_old = normalize_tag(category_slug).slug
    normalized_new = normalize_tag(new_display_name)
    errors: list[str] = []

    if not normalized_old:
        errors.append("Selected category is invalid.")
    if not normalized_new.slug:
        errors.append("Category name cannot be empty.")
    if errors:
        return TagLifecycleOperationResult(
            ok=False,
            message="Could not rename category.",
            errors=errors,
            category_slug=normalized_old or None,
            new_slug=normalized_new.slug or None,
            new_display_name=normalized_new.display_name or None,
        )

    with LifecyclePipeline() as pipeline:
        session = pipeline.session
        category = (
            session.query(TagCategory)
            .filter_by(slug=normalized_old)
            .order_by(TagCategory.id)
            .first()
        )
        if category is None:
            return TagLifecycleOperationResult(
                ok=False,
                message="Could not rename category.",
                errors=[
                    f"Category not found: {tag_registry.prettify_tag_name(normalized_old)}"
                ],
                category_slug=normalized_old,
                new_slug=normalized_new.slug,
                new_display_name=normalized_new.display_name,
            )

        old_display_name = category.name
        validation_errors: list[str] = []
        if not category.is_active:
            validation_errors.append(f"Category is inactive: {old_display_name}")
        if category.slug in _default_category_slugs():
            validation_errors.append(f"Built-in categories cannot be renamed: {old_display_name}")

        if validation_errors:
            return TagLifecycleOperationResult(
                ok=False,
                message="Could not rename category.",
                errors=validation_errors,
                category_slug=category.slug,
                new_slug=normalized_new.slug,
                old_display_name=old_display_name,
                new_display_name=normalized_new.display_name,
            )

        if normalized_new.slug == category.slug:
            return TagLifecycleOperationResult(
                ok=True,
                message="Rename canceled; category name is unchanged.",
                affected_count=0,
                category_slug=category.slug,
                old_slug=category.slug,
                new_slug=category.slug,
                old_display_name=old_display_name,
                new_display_name=category.name,
            )

        conflict = (
            session.query(TagCategory)
            .filter(TagCategory.slug == normalized_new.slug, TagCategory.id != category.id)
            .order_by(TagCategory.id)
            .first()
        )
        if conflict is not None:
            return TagLifecycleOperationResult(
                ok=False,
                message="Could not rename category.",
                errors=[f"A category named {conflict.name} already exists."],
                category_slug=category.slug,
                new_slug=normalized_new.slug,
                old_display_name=old_display_name,
                new_display_name=normalized_new.display_name,
            )

        backup_error = pipeline.create_db_backup(
            failure_fields={
                "category_slug": category.slug,
                "old_slug": category.slug,
                "new_slug": normalized_new.slug,
                "old_display_name": old_display_name,
                "new_display_name": normalized_new.display_name,
            }
        )
        if backup_error is not None:
            return backup_error

        try:
            old_slug = category.slug
            category.name = normalized_new.display_name
            category.slug = normalized_new.slug
            session.add(
                CategoryHistory(
                    action="rename",
                    old_slug=old_slug,
                    old_display_name=old_display_name,
                    new_slug=normalized_new.slug,
                    new_display_name=normalized_new.display_name,
                    metadata_json=json.dumps(
                        {
                            "lifecycle_state": "active",
                            "action": "rename",
                            "old_slug": old_slug,
                            "new_slug": normalized_new.slug,
                        },
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                )
            )
            return pipeline.commit_success(
                message=(
                    f'Renamed category "{old_display_name}" to '
                    f'"{normalized_new.display_name}".'
                ),
                success_fields={
                    "affected_count": 1,
                    "category_slug": normalized_new.slug,
                    "old_slug": old_slug,
                    "new_slug": normalized_new.slug,
                    "old_display_name": old_display_name,
                    "new_display_name": normalized_new.display_name,
                },
                error_fields={
                    "category_slug": normalized_old,
                    "new_slug": normalized_new.slug,
                    "new_display_name": normalized_new.display_name,
                },
            )
        except Exception as exc:
            traceback.print_exc()
            return pipeline.database_error(
                exc,
                fields={
                    "category_slug": normalized_old,
                    "new_slug": normalized_new.slug,
                    "new_display_name": normalized_new.display_name,
                },
            )


def delete_empty_custom_category(
    *,
    category_slug: str,
) -> TagLifecycleOperationResult:
    """Delete one empty custom active category without touching dataset JSONL."""
    normalized_slug = normalize_tag(category_slug).slug
    if not normalized_slug:
        return TagLifecycleOperationResult(
            ok=False,
            message="Could not delete category.",
            errors=["Selected category is invalid."],
            category_slug=None,
        )

    with LifecyclePipeline() as pipeline:
        session = pipeline.session
        category = (
            session.query(TagCategory)
            .filter_by(slug=normalized_slug)
            .order_by(TagCategory.id)
            .first()
        )
        if category is None:
            return TagLifecycleOperationResult(
                ok=False,
                message="Could not delete category.",
                errors=[
                    f"Category not found: {tag_registry.prettify_tag_name(normalized_slug)}"
                ],
                category_slug=normalized_slug,
            )

        category_name = category.name
        validation_errors: list[str] = []
        if not category.is_active:
            validation_errors.append(f"Category is inactive: {category_name}")
        if category.slug in _default_category_slugs():
            validation_errors.append(
                f"Built-in categories cannot be deleted: {category_name}"
            )

        attached_count = session.query(Tag).filter_by(category_id=category.id).count()
        if attached_count:
            validation_errors.append(
                "Move or delete all tags in this category before deleting it."
            )

        if validation_errors:
            return TagLifecycleOperationResult(
                ok=False,
                message="Could not delete category.",
                errors=validation_errors,
                category_slug=category.slug,
                old_slug=category.slug,
                old_display_name=category_name,
            )

        backup_error = pipeline.create_db_backup(
            failure_fields={
                "category_slug": category.slug,
                "old_slug": category.slug,
                "old_display_name": category_name,
            }
        )
        if backup_error is not None:
            return backup_error

        try:
            old_slug = category.slug
            session.add(
                CategoryHistory(
                    action="delete",
                    old_slug=old_slug,
                    old_display_name=category_name,
                    new_slug=None,
                    new_display_name=None,
                    metadata_json=json.dumps(
                        {
                            "lifecycle_state": "deleted",
                            "delete_reason": "user_deleted_empty_category",
                        },
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                )
            )
            session.delete(category)
            return pipeline.commit_success(
                message=f'Deleted category "{category_name}".',
                success_fields={
                    "affected_count": 1,
                    "category_slug": old_slug,
                    "old_slug": old_slug,
                    "old_display_name": category_name,
                },
                error_fields={"category_slug": normalized_slug},
            )
        except Exception as exc:
            traceback.print_exc()
            return pipeline.database_error(
                exc,
                fields={"category_slug": normalized_slug},
            )


def edit_active_tag(
    *,
    old_slug: str,
    new_display_name: str,
    category_slug: str,
    dataset_path: str,
    entries: list[dict],
) -> TagLifecycleOperationResult:
    """Edit one custom active tag's display name and/or active category."""
    normalized_old = normalize_tag(old_slug).slug
    normalized_new = normalize_tag(new_display_name)
    normalized_category = normalize_tag(category_slug).slug
    errors: list[str] = []

    if not normalized_old:
        errors.append("Selected tag is invalid.")
    if not normalized_new.slug:
        errors.append("Tag name cannot be empty.")
    if not normalized_category:
        errors.append("Selected category does not exist or is inactive.")
    if not isinstance(entries, list):
        errors.append("Loaded entries must be a list.")

    if errors:
        return TagLifecycleOperationResult(
            ok=False,
            message="Could not edit tag.",
            errors=errors,
            old_slug=normalized_old or None,
            new_slug=normalized_new.slug or None,
            category_slug=normalized_category or None,
            new_display_name=normalized_new.display_name or None,
        )

    with LifecyclePipeline(dataset_path=dataset_path) as pipeline:
        session = pipeline.session
        tag = session.query(Tag).filter_by(slug=normalized_old).order_by(Tag.id).first()
        if tag is None:
            return TagLifecycleOperationResult(
                ok=False,
                message="Could not edit tag.",
                errors=[f"Tag not found: {tag_registry.prettify_tag_name(normalized_old)}"],
                old_slug=normalized_old,
                new_slug=normalized_new.slug,
                category_slug=normalized_category,
                new_display_name=normalized_new.display_name,
            )

        old_display_name = tag.name
        old_category = tag.category
        new_category = (
            session.query(TagCategory)
            .filter_by(slug=normalized_category, is_active=True)
            .first()
        )
        validation_errors: list[str] = []
        if tag.status != TAG_STATUS_ACTIVE or not tag.is_active or old_category is None or not old_category.is_active:
            validation_errors.append(f"Tag is not an active custom tag: {old_display_name}")
        if tag.is_builtin:
            validation_errors.append(f"Built-in tags cannot be edited: {old_display_name}")
        if new_category is None:
            validation_errors.append("Selected category does not exist or is inactive.")

        slug_changed = normalized_new.slug != tag.slug
        category_changed = (
            new_category is not None
            and old_category is not None
            and new_category.id != old_category.id
        )

        if validation_errors:
            return TagLifecycleOperationResult(
                ok=False,
                message="Could not edit tag.",
                errors=validation_errors,
                old_slug=tag.slug,
                new_slug=normalized_new.slug,
                category_slug=normalized_category,
                old_display_name=old_display_name,
                new_display_name=normalized_new.display_name,
            )

        if not slug_changed and not category_changed:
            return TagLifecycleOperationResult(
                ok=True,
                message="Edit canceled; tag is unchanged.",
                affected_count=0,
                tag_slugs=[tag.slug],
                category_slug=old_category.slug if old_category is not None else None,
                entries=copy.deepcopy(entries),
                old_slug=tag.slug,
                new_slug=tag.slug,
                old_display_name=old_display_name,
                new_display_name=tag.name,
            )

        if slug_changed:
            conflicting_tag = (
                session.query(Tag)
                .filter(Tag.slug == normalized_new.slug, Tag.id != tag.id)
                .order_by(Tag.id)
                .first()
            )
            if conflicting_tag is not None:
                validation_errors.append(
                    f"A tag named {conflicting_tag.name} already exists."
                )
            if _alias_slug_is_reserved(session, normalized_new.slug, old_slug=tag.slug):
                validation_errors.append(
                    f"Canonical ID is reserved by lifecycle metadata: {normalized_new.display_name}"
                )

        if validation_errors:
            return TagLifecycleOperationResult(
                ok=False,
                message="Could not edit tag.",
                errors=validation_errors,
                old_slug=tag.slug,
                new_slug=normalized_new.slug,
                category_slug=normalized_category,
                old_display_name=old_display_name,
                new_display_name=normalized_new.display_name,
            )

        proposed_entries = copy.deepcopy(entries)
        changed_entries = 0
        if slug_changed:
            path_errors = _validate_dataset_path(dataset_path)
            if path_errors:
                return TagLifecycleOperationResult(
                    ok=False,
                    message="Could not edit tag.",
                    errors=path_errors,
                    old_slug=tag.slug,
                    new_slug=normalized_new.slug,
                    category_slug=normalized_category,
                    old_display_name=old_display_name,
                    new_display_name=normalized_new.display_name,
                )
            proposed_entries, changed_entries = _rewrite_entry_tag_slug(
                entries,
                old_slug=tag.slug,
                new_slug=normalized_new.slug,
            )

            backup_error = pipeline.create_dataset_backup(
                reason="before_tag_edit",
                failure_fields={
                    "old_slug": tag.slug,
                    "new_slug": normalized_new.slug,
                    "category_slug": normalized_category,
                    "old_display_name": old_display_name,
                    "new_display_name": normalized_new.display_name,
                },
            )
            if backup_error is not None:
                return backup_error

        backup_error = pipeline.create_db_backup(
            failure_fields={
                "old_slug": tag.slug,
                "new_slug": normalized_new.slug,
                "category_slug": normalized_category,
                "old_display_name": old_display_name,
                "new_display_name": normalized_new.display_name,
            }
        )
        if backup_error is not None:
            return backup_error

        try:
            old_category_slug = old_category.slug
            new_category_slug = new_category.slug
            tag.slug = normalized_new.slug
            tag.name = normalized_new.display_name
            if category_changed:
                max_order = (
                    session.query(Tag)
                    .filter_by(category_id=new_category.id)
                    .order_by(Tag.sort_order.desc())
                    .first()
                )
                tag.sort_order = (max_order.sort_order if max_order is not None else 0) + 1
            tag.category_id = new_category.id
            tag.status = TAG_STATUS_ACTIVE
            tag.is_active = True

            if slug_changed:
                clear_current_tag_lifecycle_metadata(
                    normalized_old, session=session
                )
            clear_or_replace_tag_lifecycle_metadata(
                action=TAG_LIFECYCLE_METADATA_ASSIGN_CATEGORY,
                old_slug=normalized_new.slug,
                old_display_name=normalized_new.display_name,
                old_category_slug=new_category_slug,
                new_slug=normalized_new.slug,
                new_display_name=normalized_new.display_name,
                new_category_slug=new_category_slug,
                metadata={
                    "lifecycle_state": LIFECYCLE_STATE_ACTIVE,
                    "activation_origin": "tag_edit",
                    "assigned_category_slug": new_category_slug,
                    "visible_badge": None,
                },
                session=session,
            )
            if slug_changed:
                upsert_tag_lifecycle_metadata(
                    action=TAG_LIFECYCLE_METADATA_RENAME,
                    old_slug=normalized_old,
                    old_display_name=old_display_name,
                    old_category_slug=old_category_slug,
                    new_slug=normalized_new.slug,
                    new_display_name=normalized_new.display_name,
                    new_category_slug=new_category_slug,
                    metadata=build_rename_alias_metadata(
                        old_slug=normalized_old,
                        new_slug=normalized_new.slug,
                    ),
                    session=session,
                )

                save_error = pipeline.save_jsonl(
                    proposed_entries,
                    failure_fields={
                        "old_slug": normalized_old,
                        "new_slug": normalized_new.slug,
                        "category_slug": new_category_slug,
                        "old_display_name": old_display_name,
                        "new_display_name": normalized_new.display_name,
                    },
                )
                if save_error is not None:
                    return save_error

            if slug_changed and category_changed:
                message = (
                    f'Edited tag "{old_display_name}" to '
                    f'"{normalized_new.display_name}" and moved it to {new_category.name}.'
                )
            elif slug_changed:
                message = (
                    f'Renamed tag "{old_display_name}" to '
                    f'"{normalized_new.display_name}".'
                )
            else:
                message = f'Moved tag "{old_display_name}" to {new_category.name}.'
            return pipeline.commit_success(
                message=message,
                success_fields={
                    "affected_count": changed_entries,
                    "tag_slugs": [normalized_new.slug],
                    "category_slug": new_category_slug,
                    "entries": proposed_entries if slug_changed else copy.deepcopy(entries),
                    "old_slug": normalized_old,
                    "new_slug": normalized_new.slug,
                    "old_display_name": old_display_name,
                    "new_display_name": normalized_new.display_name,
                },
                error_fields={
                    "old_slug": normalized_old,
                    "new_slug": normalized_new.slug,
                    "category_slug": normalized_category,
                    "new_display_name": normalized_new.display_name,
                },
            )
        except Exception as exc:
            traceback.print_exc()
            return pipeline.database_error(
                exc,
                fields={
                    "old_slug": normalized_old,
                    "new_slug": normalized_new.slug,
                    "category_slug": normalized_category,
                    "new_display_name": normalized_new.display_name,
                },
            )


def delete_active_tag(
    *,
    tag_slug: str,
    dataset_path: str,
    entries: list[dict],
) -> TagLifecycleOperationResult:
    """Soft-delete one custom active tag and remove it from loaded entries."""
    normalized_slug = normalize_tag(tag_slug).slug
    errors: list[str] = []

    if not normalized_slug:
        errors.append("Selected tag is invalid.")
    if not isinstance(entries, list):
        errors.append("Loaded entries must be a list.")

    path_errors = _validate_dataset_path(dataset_path)
    errors.extend(path_errors)

    if errors:
        return TagLifecycleOperationResult(
            ok=False,
            message="Could not delete tag.",
            errors=errors,
            old_slug=normalized_slug or None,
        )

    with LifecyclePipeline(dataset_path=dataset_path) as pipeline:
        session = pipeline.session
        tag = session.query(Tag).filter_by(slug=normalized_slug).order_by(Tag.id).first()
        if tag is None:
            return TagLifecycleOperationResult(
                ok=False,
                message="Could not delete tag.",
                errors=[f"Tag not found: {tag_registry.prettify_tag_name(normalized_slug)}"],
                old_slug=normalized_slug,
            )

        tag_label = tag.name
        old_category = tag.category
        validation_errors: list[str] = []
        if tag.status != TAG_STATUS_ACTIVE or not tag.is_active or old_category is None or not old_category.is_active:
            validation_errors.append(f"Tag is not an active custom tag: {tag_label}")
        if tag.is_builtin:
            validation_errors.append(f"Built-in tags cannot be deleted: {tag_label}")

        if validation_errors:
            return TagLifecycleOperationResult(
                ok=False,
                message="Could not delete tag.",
                errors=validation_errors,
                old_slug=tag.slug,
                old_display_name=tag_label,
            )

        proposed_entries, changed_entries = _remove_entry_tag_slug(
            entries,
            tag_slug=tag.slug,
        )

        backup_error = pipeline.create_dataset_backup(
            reason="before_tag_delete",
            failure_fields={
                "old_slug": tag.slug,
                "old_display_name": tag_label,
            },
        )
        if backup_error is not None:
            return backup_error

        backup_error = pipeline.create_db_backup(
            failure_fields={
                "old_slug": tag.slug,
                "old_display_name": tag_label,
            }
        )
        if backup_error is not None:
            return backup_error

        try:
            old_category_slug = old_category.slug
            tag.status = TAG_STATUS_ARCHIVED
            tag.is_active = False
            tag.category_id = None
            clear_or_replace_tag_lifecycle_metadata(
                action=TAG_LIFECYCLE_METADATA_ARCHIVE,
                old_slug=tag.slug,
                old_display_name=tag.name,
                old_category_slug=old_category_slug,
                new_slug=tag.slug,
                new_display_name=tag.name,
                new_category_slug=None,
                metadata=build_deleted_archive_metadata(old_category_slug),
                session=session,
            )

            save_error = pipeline.save_jsonl(
                proposed_entries,
                failure_fields={
                    "old_slug": tag.slug,
                    "old_display_name": tag_label,
                },
            )
            if save_error is not None:
                return save_error

            entry_word = "entry" if changed_entries == 1 else "entries"
            return pipeline.commit_success(
                message=(
                    f'Deleted tag "{tag_label}" and removed it from '
                    f"{changed_entries} {entry_word}."
                ),
                success_fields={
                    "affected_count": changed_entries,
                    "tag_slugs": [tag.slug],
                    "entries": proposed_entries,
                    "old_slug": tag.slug,
                    "old_display_name": tag_label,
                },
                error_fields={"old_slug": normalized_slug},
            )
        except Exception as exc:
            traceback.print_exc()
            return pipeline.database_error(
                exc,
                fields={"old_slug": normalized_slug},
            )
