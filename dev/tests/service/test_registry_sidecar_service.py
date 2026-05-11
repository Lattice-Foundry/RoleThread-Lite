import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import core.tag_registry as tag_registry
from core.models import Base, Tag, TagCategory, TagLifecycleMetadata
from core.registry_sidecar import read_sidecar, sidecar_path_for_dataset
from core.tag_constants import (
    TAG_LIFECYCLE_METADATA_ARCHIVE,
    TAG_LIFECYCLE_METADATA_RENAME,
    TAG_STATUS_ACTIVE,
    TAG_STATUS_ARCHIVED,
)
import services.registry_sidecar_service as registry_sidecar_service
from services.registry_sidecar_service import export_registry_sidecar


def _session_factory(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'registry_sidecar.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    monkeypatch.setattr(tag_registry, "SessionLocal", session_factory)
    return session_factory


def test_export_registry_sidecar_writes_registry_file(tmp_path, monkeypatch):
    session_factory = _session_factory(tmp_path, monkeypatch)
    session = session_factory()
    try:
        behavior = TagCategory(
            name="Behavior",
            slug="behavior",
            sort_order=0,
            is_active=True,
        )
        custom = TagCategory(
            name="Custom",
            slug="custom",
            sort_order=5,
            is_active=True,
        )
        session.add_all([behavior, custom])
        session.flush()
        session.add_all([
            Tag(
                category_id=behavior.id,
                name="Slow Burn",
                slug="slow_burn",
                sort_order=2,
                is_active=True,
                is_builtin=False,
                status=TAG_STATUS_ACTIVE,
            ),
            Tag(
                category_id=None,
                name="Deleted Tag",
                slug="deleted_tag",
                sort_order=0,
                is_active=False,
                is_builtin=False,
                status=TAG_STATUS_ARCHIVED,
            ),
            TagLifecycleMetadata(
                action=TAG_LIFECYCLE_METADATA_ARCHIVE,
                old_slug="deleted_tag",
                old_display_name="Deleted Tag",
                metadata_json=json.dumps({
                    "archive_origin": "deleted",
                    "visible_badge": "Deleted",
                }),
            ),
            TagLifecycleMetadata(
                action=TAG_LIFECYCLE_METADATA_RENAME,
                old_slug="slowburn",
                new_slug="slow_burn",
                metadata_json=json.dumps({"resolver_behavior": "map_to_target"}),
            ),
        ])
        session.commit()
    finally:
        session.close()

    dataset_path = tmp_path / "training_set.jsonl"
    result = export_registry_sidecar(
        dataset_path=str(dataset_path),
        entries=[
            {"tags": ["slow_burn", "deleted_tag"]},
            {"tags": ["slow_burn"]},
        ],
    )

    assert result.ok is True
    assert result.path == str(sidecar_path_for_dataset(dataset_path))
    assert result.message == "Registry sidecar written to training_set.registry.json."

    sidecar = read_sidecar(sidecar_path_for_dataset(dataset_path))
    assert sidecar.dataset_info.filename == "training_set.jsonl"
    assert sidecar.dataset_info.entry_count == 2
    assert sidecar.dataset_info.tag_usage_counts == {
        "slow_burn": 2,
        "deleted_tag": 1,
    }
    assert [category.slug for category in sidecar.categories] == [
        "behavior",
        "custom",
    ]
    behavior_category = sidecar.categories[0]
    assert behavior_category.is_builtin is True
    custom_category = sidecar.categories[1]
    assert custom_category.is_builtin is False
    tags_by_slug = {tag.slug: tag for tag in sidecar.tags}
    assert tags_by_slug["slow_burn"].category_slug == "behavior"
    assert tags_by_slug["slow_burn"].status == TAG_STATUS_ACTIVE
    assert tags_by_slug["deleted_tag"].category_slug is None
    assert tags_by_slug["deleted_tag"].lifecycle == {
        "archive_origin": "deleted",
        "visible_badge": "Deleted",
    }
    assert sidecar.aliases[0].old_slug == "slowburn"
    assert sidecar.aliases[0].new_slug == "slow_burn"
    assert sidecar.aliases[0].metadata == {"resolver_behavior": "map_to_target"}


def test_export_registry_sidecar_failure_is_structured(tmp_path, monkeypatch):
    _session_factory(tmp_path, monkeypatch)

    def fail_write(registry, path):
        raise OSError("disk full")

    monkeypatch.setattr(registry_sidecar_service, "write_sidecar", fail_write)

    result = export_registry_sidecar(
        dataset_path=str(tmp_path / "training_set.jsonl"),
        entries=[],
    )

    assert result.ok is False
    assert result.message == "Could not export registry sidecar: disk full"
    assert result.errors == ["disk full"]
    assert result.path is None


def test_export_registry_sidecar_rejects_missing_dataset_path():
    result = export_registry_sidecar(dataset_path="", entries=[])

    assert result.ok is False
    assert result.message == "Could not export registry sidecar."
    assert result.errors == ["No export dataset path was provided."]
