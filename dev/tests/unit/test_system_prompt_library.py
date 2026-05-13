import pytest
from sqlalchemy import create_engine, inspect as sa_inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

import core.system_prompt_library as system_prompt_library
from core.models import Base, SystemPromptTemplate
from core.system_prompt_library import (
    create_system_prompt_template,
    deactivate_system_prompt_template,
    delete_system_prompt_templates,
    get_all_system_prompt_templates,
    get_system_prompt_template_by_slug,
    normalize_system_prompt_name,
    reactivate_system_prompt_template,
    update_system_prompt_template,
)


@pytest.fixture
def prompt_db(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'system_prompts.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    monkeypatch.setattr(system_prompt_library, "SessionLocal", session_factory)
    return session_factory


def test_system_prompt_template_table_is_created_with_unique_slug(prompt_db):
    inspector = sa_inspect(prompt_db.kw["bind"])

    assert "system_prompt_templates" in inspector.get_table_names()
    constraints = inspector.get_unique_constraints("system_prompt_templates")
    assert any(
        constraint["name"] == "uq_system_prompt_slug"
        and constraint["column_names"] == ["slug"]
        for constraint in constraints
    )


def test_normalize_system_prompt_name_reuses_tag_normalization():
    assert normalize_system_prompt_name("  Group Scene Prompt  ") == (
        "group_scene_prompt",
        "Group Scene Prompt",
    )


def test_create_system_prompt_template_normalizes_and_persists(prompt_db):
    template = create_system_prompt_template(
        "  X-Men Group Scene  ",
        " Coordinate the scene. ",
        description="  Team setting  ",
    )

    assert template.slug == "x_men_group_scene"
    assert template.name == "X Men Group Scene"
    assert template.content == "Coordinate the scene."
    assert template.description == "Team setting"
    assert template.is_active is True
    assert template.created_at is not None
    assert template.updated_at is not None


def test_create_system_prompt_template_rejects_empty_and_duplicate(prompt_db):
    with pytest.raises(ValueError, match="name cannot be empty"):
        create_system_prompt_template(" ", "Prompt")
    with pytest.raises(ValueError, match="content cannot be empty"):
        create_system_prompt_template("Scene", " ")

    create_system_prompt_template("Group Scene", "Prompt")
    with pytest.raises(ValueError, match="already exists"):
        create_system_prompt_template("group_scene", "Other prompt")


def test_database_rejects_duplicate_system_prompt_slugs(prompt_db):
    session = prompt_db()
    try:
        session.add_all([
            SystemPromptTemplate(
                slug="group_scene",
                name="Group Scene",
                content="One",
            ),
            SystemPromptTemplate(
                slug="group_scene",
                name="Group Scene Duplicate",
                content="Two",
            ),
        ])
        with pytest.raises(IntegrityError):
            session.commit()
    finally:
        session.rollback()
        session.close()


def test_get_all_system_prompt_templates_filters_active_and_sorts(prompt_db):
    create_system_prompt_template("Zeta Prompt", "Z")
    create_system_prompt_template("Alpha Prompt", "A")
    create_system_prompt_template("Middle Prompt", "M")
    deactivate_system_prompt_template("middle_prompt")

    active = get_all_system_prompt_templates()
    all_templates = get_all_system_prompt_templates(active_only=False)

    assert [template.slug for template in active] == ["alpha_prompt", "zeta_prompt"]
    assert [template.slug for template in all_templates] == [
        "alpha_prompt",
        "middle_prompt",
        "zeta_prompt",
    ]


def test_get_system_prompt_template_by_slug_normalizes_and_excludes_inactive(prompt_db):
    create_system_prompt_template("Group Scene", "Prompt")

    assert get_system_prompt_template_by_slug("Group Scene").slug == "group_scene"
    assert get_system_prompt_template_by_slug("group-scene").slug == "group_scene"

    deactivate_system_prompt_template("group_scene")
    assert get_system_prompt_template_by_slug("group_scene") is None


def test_update_system_prompt_template_changes_fields_without_changing_slug(prompt_db):
    create_system_prompt_template("Group Scene", "Old content", description="Old")

    updated = update_system_prompt_template(
        "group_scene",
        name="Group Scene Revised",
        content="New content",
        description="New notes",
    )

    assert updated.slug == "group_scene"
    assert updated.name == "Group Scene Revised"
    assert updated.content == "New content"
    assert updated.description == "New notes"

    fetched = get_system_prompt_template_by_slug("group_scene")
    assert fetched.name == "Group Scene Revised"
    assert fetched.content == "New content"


def test_update_system_prompt_template_leaves_unprovided_fields_unchanged(prompt_db):
    create_system_prompt_template("Group Scene", "Original", description="Notes")

    updated = update_system_prompt_template("group_scene", content="Updated")

    assert updated.slug == "group_scene"
    assert updated.name == "Group Scene"
    assert updated.content == "Updated"
    assert updated.description == "Notes"


def test_update_system_prompt_template_rejects_missing_or_empty_fields(prompt_db):
    create_system_prompt_template("Group Scene", "Prompt")

    with pytest.raises(ValueError, match="not found"):
        update_system_prompt_template("missing", content="Prompt")
    with pytest.raises(ValueError, match="name cannot be empty"):
        update_system_prompt_template("group_scene", name=" ")
    with pytest.raises(ValueError, match="content cannot be empty"):
        update_system_prompt_template("group_scene", content=" ")


def test_deactivate_reactivate_and_bulk_delete(prompt_db):
    create_system_prompt_template("Group Scene", "Prompt")
    create_system_prompt_template("Solo Scene", "Prompt")
    create_system_prompt_template("Archive Scene", "Prompt")

    assert deactivate_system_prompt_template("group_scene") is True
    assert deactivate_system_prompt_template("missing") is False
    assert get_system_prompt_template_by_slug("group_scene") is None
    assert reactivate_system_prompt_template("group_scene") is True
    assert reactivate_system_prompt_template("missing") is False
    assert get_system_prompt_template_by_slug("group_scene").slug == "group_scene"

    deleted = delete_system_prompt_templates(["solo_scene", "archive scene", "missing"])

    assert deleted == ["archive_scene", "solo_scene"]
    assert [template.slug for template in get_all_system_prompt_templates()] == [
        "group_scene",
    ]
    inactive_slugs = {
        template.slug
        for template in get_all_system_prompt_templates(active_only=False)
        if not template.is_active
    }
    assert inactive_slugs == {"archive_scene", "solo_scene"}
