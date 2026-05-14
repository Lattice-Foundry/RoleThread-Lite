import json
import shutil

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import core.tag_registry as tag_registry
import core.tag_metadata as tag_metadata
import core.tag_resolution as tag_resolution
from core.dataset import load_dataset, save_dataset
from core.loreforge_meta import LOREFORGE_META_KEY, get_entry_uuid
from core.tag_constants import (
    TAG_LIFECYCLE_METADATA_ARCHIVE,
    TAG_LIFECYCLE_METADATA_IMPORT_ARCHIVED,
    TAG_LIFECYCLE_METADATA_RENAME,
    TAG_RESOLUTION_ALIAS_MAPPED,
    TAG_RESOLUTION_ARCHIVED,
    TAG_STATUS_ACTIVE,
    TAG_STATUS_ARCHIVED,
    TAG_STATUS_HIDDEN,
)
from core.version import LOREFORGE_VERSION
from core.models import (
    Base,
    CategoryHistory,
    Tag,
    TagCategory,
    TagLifecycleMetadata,
)
import services.tag_lifecycle_service as tag_lifecycle_service
from services.tag_lifecycle_service import (
    assign_archived_imported_tags_to_category,
    delete_active_tag,
    delete_empty_custom_category,
    edit_active_tag,
    rename_custom_category,
)


@pytest.fixture
def tag_lifecycle_db(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'tag_lifecycle.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    monkeypatch.setattr(tag_registry, "engine", engine)
    monkeypatch.setattr(tag_registry, "SessionLocal", session_factory)
    monkeypatch.setattr(tag_lifecycle_service, "engine", engine)
    monkeypatch.setattr(tag_lifecycle_service, "SessionLocal", session_factory)
    monkeypatch.setattr(tag_metadata, "SessionLocal", session_factory)
    monkeypatch.setattr(tag_resolution, "SessionLocal", session_factory)
    monkeypatch.setattr(
        tag_lifecycle_service,
        "create_db_backup",
        lambda *, engine: tmp_path / "db_backup.sqlite",
    )
    monkeypatch.setattr(
        tag_registry,
        "create_db_backup",
        lambda *, engine: tmp_path / "db_backup.sqlite",
    )
    return session_factory


def _add_category(session, *, slug="behavior", name="Behavior", active=True):
    category = TagCategory(
        name=name,
        slug=slug,
        sort_order=0,
        is_active=active,
    )
    session.add(category)
    session.flush()
    return category


def _add_tag(
    session,
    *,
    slug,
    name=None,
    category=None,
    status=TAG_STATUS_ACTIVE,
    active=True,
):
    tag = Tag(
        category_id=category.id if category is not None else None,
        name=name or tag_registry.prettify_tag_name(slug),
        slug=slug,
        sort_order=0,
        is_active=active,
        is_builtin=False,
        status=status,
    )
    session.add(tag)
    session.flush()
    return tag


def _add_imported_archived_tag(session, slug):
    tag = _add_tag(
        session,
        slug=slug,
        status=TAG_STATUS_ARCHIVED,
        active=False,
    )
    tag_metadata.upsert_tag_lifecycle_metadata(
        action=TAG_LIFECYCLE_METADATA_IMPORT_ARCHIVED,
        old_slug=slug,
        old_display_name=tag.name,
        new_slug=slug,
        new_display_name=tag.name,
        metadata=tag_metadata.build_imported_archive_metadata(),
        session=session,
    )
    return tag


def _metadata_for(session, slug):
    history = session.query(TagLifecycleMetadata).filter_by(old_slug=slug).one()
    return json.loads(history.metadata_json)


def _entry(tags):
    return {
        "messages": [
            {"role": "system", "content": "System"},
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello"},
        ],
        "tags": tags,
    }


def _without_loreforge_meta(value):
    if isinstance(value, list):
        return [_without_loreforge_meta(item) for item in value]
    if isinstance(value, dict):
        return {
            key: _without_loreforge_meta(item)
            for key, item in value.items()
            if key != LOREFORGE_META_KEY
        }
    return value


def _assert_stamped(entries):
    assert entries
    for entry in entries:
        assert entry[LOREFORGE_META_KEY]["version"] == LOREFORGE_VERSION
        assert entry[LOREFORGE_META_KEY]["native"] is True
        assert entry[LOREFORGE_META_KEY]["validated_at"].endswith("Z")
        assert get_entry_uuid(entry) is not None


def _write_dataset(tmp_path, entries):
    path = tmp_path / "dataset.jsonl"
    save_dataset(path, entries)
    return path


def _fake_dataset_backup(tmp_path, monkeypatch):
    backups = []

    def fake_create_dataset_backup(dataset_path, reason):
        backup_path = tmp_path / f"{len(backups):03d}_{reason}.jsonl"
        shutil.copyfile(dataset_path, backup_path)
        backups.append(backup_path)
        return backup_path

    monkeypatch.setattr(
        tag_lifecycle_service,
        "create_dataset_backup",
        fake_create_dataset_backup,
    )
    return backups
