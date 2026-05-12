import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import core.tag_registry as tag_registry
from core.models import Base, Tag, TagCategory, TagLifecycleMetadata
from core.registry_sidecar import (
    SidecarAlias,
    SidecarCategory,
    SidecarMetadata,
    SidecarDatasetInfo,
    SidecarRegistry,
    SidecarTag,
    read_sidecar,
    sidecar_path_for_dataset,
)
from core.tag_constants import (
    TAG_LIFECYCLE_METADATA_ARCHIVE,
    TAG_LIFECYCLE_METADATA_ASSIGN_CATEGORY,
    TAG_LIFECYCLE_METADATA_IMPORT_ARCHIVED,
    TAG_LIFECYCLE_METADATA_RENAME,
    TAG_STATUS_ACTIVE,
    TAG_STATUS_ARCHIVED,
)
from core.version import LOREFORGE_VERSION
import services.registry_sidecar_service as registry_sidecar_service
from services.registry_sidecar_service import export_registry_sidecar, import_registry_sidecar


def _session_factory(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'registry_sidecar.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    monkeypatch.setattr(tag_registry, "engine", engine)
    monkeypatch.setattr(tag_registry, "SessionLocal", session_factory)
    monkeypatch.setattr(
        tag_registry,
        "create_db_backup",
        lambda *, engine: tmp_path / "db_backup.sqlite",
    )
    return session_factory


def _registry(
    *,
    categories=None,
    tags=None,
    aliases=None,
) -> SidecarRegistry:
    return SidecarRegistry(
        metadata=SidecarMetadata(exported_at="2026-05-11T00:00:00+00:00"),
        dataset_info=SidecarDatasetInfo(filename="training_set.jsonl"),
        categories=tuple(categories or []),
        tags=tuple(tags or []),
        aliases=tuple(aliases or []),
    )


def _category(slug="behavior", name="Behavior", builtin=True):
    return SidecarCategory(
        slug=slug,
        name=name,
        sort_order=0,
        is_active=True,
        is_builtin=builtin,
    )


def _tag(
    slug="slow_burn",
    name="Slow Burn",
    category_slug="behavior",
    status=TAG_STATUS_ACTIVE,
    active=True,
    lifecycle=None,
):
    return SidecarTag(
        slug=slug,
        name=name,
        category_slug=category_slug,
        sort_order=0,
        status=status,
        is_active=active,
        is_builtin=False,
        lifecycle=lifecycle or {"lifecycle_state": status},
    )


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
    assert sidecar.metadata.app_version == LOREFORGE_VERSION
    assert [category.slug for category in sidecar.categories] == ["behavior"]
    behavior_category = sidecar.categories[0]
    assert behavior_category.is_builtin is True
    tags_by_slug = {tag.slug: tag for tag in sidecar.tags}
    assert set(tags_by_slug) == {"slow_burn", "deleted_tag"}
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


def test_import_registry_sidecar_creates_categories_tags_and_aliases(tmp_path, monkeypatch):
    session_factory = _session_factory(tmp_path, monkeypatch)
    registry = _registry(
        categories=[
            _category("behavior", "Behavior", builtin=True),
            _category("custom", "Custom", builtin=False),
        ],
        tags=[
            _tag("slow_burn", "Slow Burn", "behavior"),
            _tag("custom_tag", "Custom Tag", "custom"),
        ],
        aliases=[
            SidecarAlias(
                old_slug="slowburn",
                new_slug="slow_burn",
                action=TAG_LIFECYCLE_METADATA_RENAME,
                metadata={"resolver_behavior": "map_to_target"},
            )
        ],
    )

    result = import_registry_sidecar(registry=registry)

    assert result.ok is True
    assert result.categories_created == ["behavior", "custom"]
    assert result.tags_created == ["slow_burn", "custom_tag"]
    assert result.tags_promoted == []
    assert result.aliases_imported == ["slowburn"]
    assert result.db_backup_path == str(tmp_path / "db_backup.sqlite")

    session = session_factory()
    try:
        categories = {category.slug: category for category in session.query(TagCategory)}
        assert categories["behavior"].name == "Behavior"
        assert categories["custom"].name == "Custom"
        tags = {tag.slug: tag for tag in session.query(Tag)}
        assert tags["slow_burn"].status == TAG_STATUS_ACTIVE
        assert tags["slow_burn"].category.slug == "behavior"
        assert tags["custom_tag"].category.slug == "custom"
        alias = session.query(TagLifecycleMetadata).filter_by(old_slug="slowburn").one()
        assert alias.new_slug == "slow_burn"
        assert json.loads(alias.metadata_json) == {"resolver_behavior": "map_to_target"}
    finally:
        session.close()


def test_import_registry_sidecar_matching_registry_is_noop(tmp_path, monkeypatch):
    session_factory = _session_factory(tmp_path, monkeypatch)
    session = session_factory()
    try:
        category = TagCategory(name="Behavior", slug="behavior", sort_order=0)
        session.add(category)
        session.flush()
        session.add(Tag(
            category_id=category.id,
            name="Slow Burn",
            slug="slow_burn",
            sort_order=0,
            status=TAG_STATUS_ACTIVE,
            is_active=True,
        ))
        session.commit()
    finally:
        session.close()

    result = import_registry_sidecar(registry=_registry(
        categories=[_category()],
        tags=[_tag()],
    ))

    assert result.ok is True
    assert result.categories_created == []
    assert result.tags_created == []
    assert result.tags_promoted == []
    assert result.conflicts == []
    assert result.message == "Registry sidecar already matches the current registry."


def test_import_registry_sidecar_promotes_archived_imported_tag(tmp_path, monkeypatch):
    session_factory = _session_factory(tmp_path, monkeypatch)
    session = session_factory()
    try:
        category = TagCategory(name="Behavior", slug="behavior", sort_order=0)
        session.add(category)
        session.add(Tag(
            category_id=None,
            name="Slow Burn",
            slug="slow_burn",
            sort_order=0,
            status=TAG_STATUS_ARCHIVED,
            is_active=False,
        ))
        session.add(TagLifecycleMetadata(
            action=TAG_LIFECYCLE_METADATA_IMPORT_ARCHIVED,
            old_slug="slow_burn",
            old_display_name="Slow Burn",
            metadata_json=json.dumps({
                "archive_origin": "imported",
                "visible_badge": "Imported",
            }),
        ))
        session.commit()
    finally:
        session.close()

    result = import_registry_sidecar(registry=_registry(
        categories=[_category()],
        tags=[_tag("slow_burn", "Slow Burn", "behavior")],
    ))

    assert result.ok is True
    assert result.tags_created == []
    assert result.tags_promoted == ["slow_burn"]

    session = session_factory()
    try:
        tag = session.query(Tag).filter_by(slug="slow_burn").one()
        assert tag.status == TAG_STATUS_ACTIVE
        assert tag.is_active is True
        assert tag.category.slug == "behavior"
    finally:
        session.close()


def test_import_registry_sidecar_records_active_category_conflict(tmp_path, monkeypatch):
    session_factory = _session_factory(tmp_path, monkeypatch)
    session = session_factory()
    try:
        behavior = TagCategory(name="Behavior", slug="behavior", sort_order=0)
        scene = TagCategory(name="Scene", slug="scene", sort_order=1)
        session.add_all([behavior, scene])
        session.flush()
        session.add(Tag(
            category_id=behavior.id,
            name="Slow Burn",
            slug="slow_burn",
            sort_order=0,
            status=TAG_STATUS_ACTIVE,
            is_active=True,
        ))
        session.commit()
    finally:
        session.close()

    result = import_registry_sidecar(registry=_registry(
        categories=[_category("scene", "Scene", builtin=True)],
        tags=[_tag("slow_burn", "Slow Burn", "scene")],
    ))

    assert result.ok is True
    assert result.conflicts == [
        "Active tag 'slow_burn' is already in category 'behavior', not 'scene'."
    ]
    session = session_factory()
    try:
        tag = session.query(Tag).filter_by(slug="slow_burn").one()
        assert tag.category.slug == "behavior"
    finally:
        session.close()


def test_import_registry_sidecar_warns_on_category_name_mismatch(tmp_path, monkeypatch):
    session_factory = _session_factory(tmp_path, monkeypatch)
    session = session_factory()
    try:
        session.add(TagCategory(name="Behavior DB", slug="behavior", sort_order=0))
        session.commit()
    finally:
        session.close()

    result = import_registry_sidecar(registry=_registry(categories=[_category()]))

    assert result.ok is True
    assert result.warnings == [
        "Category 'behavior' already exists as 'Behavior DB'; sidecar name 'Behavior' was skipped."
    ]
    session = session_factory()
    try:
        assert session.query(TagCategory).filter_by(slug="behavior").one().name == "Behavior DB"
    finally:
        session.close()


def test_import_registry_sidecar_skips_alias_when_target_missing(tmp_path, monkeypatch):
    session_factory = _session_factory(tmp_path, monkeypatch)

    result = import_registry_sidecar(registry=_registry(
        aliases=[
            SidecarAlias(
                old_slug="old_tag",
                new_slug="missing_tag",
                action=TAG_LIFECYCLE_METADATA_RENAME,
            )
        ]
    ))

    assert result.ok is True
    assert result.aliases_imported == []
    assert result.warnings == [
        "Alias 'old_tag' -> 'missing_tag' was skipped because the target tag does not exist."
    ]
    session = session_factory()
    try:
        assert session.query(TagLifecycleMetadata).count() == 0
    finally:
        session.close()


def test_import_registry_sidecar_creates_backup_before_mutation(tmp_path, monkeypatch):
    session_factory = _session_factory(tmp_path, monkeypatch)
    calls = []

    def fake_backup(*, engine):
        session = session_factory()
        try:
            calls.append(session.query(TagCategory).count())
        finally:
            session.close()
        return tmp_path / "db_backup.sqlite"

    monkeypatch.setattr(tag_registry, "create_db_backup", fake_backup)

    result = import_registry_sidecar(registry=_registry(categories=[_category()]))

    assert result.ok is True
    assert calls == [0]
    session = session_factory()
    try:
        assert session.query(TagCategory).count() == 1
    finally:
        session.close()


def test_import_registry_sidecar_backup_failure_fails_closed(tmp_path, monkeypatch):
    session_factory = _session_factory(tmp_path, monkeypatch)

    def fail_backup(*, engine):
        raise OSError("backup failed")

    monkeypatch.setattr(tag_registry, "create_db_backup", fail_backup)

    result = import_registry_sidecar(registry=_registry(categories=[_category()]))

    assert result.ok is False
    assert result.errors == ["Could not create database backup: backup failed"]
    session = session_factory()
    try:
        assert session.query(TagCategory).count() == 0
    finally:
        session.close()


def test_import_registry_sidecar_rolls_back_on_failure(tmp_path, monkeypatch):
    session_factory = _session_factory(tmp_path, monkeypatch)

    def fail_metadata(session, sidecar_tag):
        raise RuntimeError("boom")

    monkeypatch.setattr(
        registry_sidecar_service,
        "_write_current_metadata",
        fail_metadata,
    )

    result = import_registry_sidecar(registry=_registry(
        categories=[_category()],
        tags=[_tag()],
    ))

    assert result.ok is False
    assert "boom" in result.errors
    session = session_factory()
    try:
        assert session.query(TagCategory).count() == 0
        assert session.query(Tag).count() == 0
    finally:
        session.close()


def test_import_registry_sidecar_skips_stale_builtin_category(tmp_path, monkeypatch):
    session_factory = _session_factory(tmp_path, monkeypatch)

    result = import_registry_sidecar(registry=_registry(categories=[
        SidecarCategory(
            slug="legacy_builtin",
            name="Legacy Builtin",
            is_builtin=True,
        )
    ]))

    assert result.ok is True
    assert result.categories_created == []
    assert result.warnings == [
        "Built-in category 'Legacy Builtin' is not a current LoreForge default and was skipped."
    ]
    session = session_factory()
    try:
        assert session.query(TagCategory).count() == 0
    finally:
        session.close()


def test_import_registry_sidecar_reads_from_file(tmp_path, monkeypatch):
    _session_factory(tmp_path, monkeypatch)
    path = tmp_path / "training_set.registry.json"
    path.write_text(
        json.dumps({
            "metadata": {
                "schema_version": 1,
                "kind": "loreforge.tag_registry",
                "exported_at": "2026-05-11T00:00:00+00:00",
            },
            "dataset": {"filename": "training_set.jsonl"},
            "categories": [
                {
                    "slug": "behavior",
                    "name": "Behavior",
                    "sort_order": 0,
                    "is_active": True,
                    "is_builtin": True,
                }
            ],
            "tags": [],
            "aliases": [],
        }),
        encoding="utf-8",
    )

    result = import_registry_sidecar(sidecar_path=path)

    assert result.ok is True
    assert result.categories_created == ["behavior"]
