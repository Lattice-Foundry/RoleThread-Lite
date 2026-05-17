import dataclasses
import json

import pytest

from core.registry_sidecar import (
    SIDECAR_KIND,
    SIDECAR_SCHEMA_VERSION,
    SidecarAlias,
    SidecarCategory,
    SidecarCharacter,
    SidecarDatasetInfo,
    SidecarEntryCharacterMapping,
    SidecarMetadata,
    SidecarRegistry,
    SidecarSystemPrompt,
    SidecarTag,
    SidecarValidationError,
    build_sidecar_registry,
    parse_sidecar_dict,
    read_sidecar,
    sidecar_path_for_dataset,
    sidecar_to_dict,
    write_sidecar,
)
from core.version import ROLETHREAD_VERSION


def _sample_registry() -> SidecarRegistry:
    return build_sidecar_registry(
        dataset_uuid="dataset-uuid-1",
        dataset_filename="training_set.jsonl",
        entry_count=3,
        tag_usage_counts={"slow_burn": 2, "deleted_tag": 1},
        categories=[
            {
                "slug": "behavior",
                "name": "Behavior",
                "sort_order": 0,
                "is_active": True,
                "is_builtin": True,
            },
            SidecarCategory(
                slug="custom",
                name="Custom",
                sort_order=5,
                is_active=True,
                is_builtin=False,
            ),
        ],
        tags=[
            {
                "slug": "slow_burn",
                "name": "Slow Burn",
                "category_slug": "behavior",
                "sort_order": 4,
                "status": "active",
                "is_active": True,
                "is_builtin": False,
                "lifecycle": {"lifecycle_state": "active"},
            },
            SidecarTag(
                slug="deleted_tag",
                name="Deleted Tag",
                category_slug=None,
                sort_order=0,
                status="archived",
                is_active=False,
                is_builtin=False,
                lifecycle={
                    "archive_origin": "deleted",
                    "visible_badge": "Deleted",
                },
            ),
        ],
        aliases=[
            {
                "old_slug": "slowburn",
                "new_slug": "slow_burn",
                "action": "rename",
                "metadata": {"resolver_behavior": "map_to_target"},
            },
            SidecarAlias(
                old_slug="retired_tag",
                new_slug=None,
                action="hide",
                metadata={"lifecycle_state": "hidden"},
            ),
        ],
        characters=[
            SidecarCharacter(
                slug="scott",
                display_name="Scott",
                description=None,
                is_active=True,
            )
        ],
        entry_character_mappings=[
            SidecarEntryCharacterMapping(
                entry_uuid="entry-1",
                turns=(
                    {
                        "turn_index": 1,
                        "character_slug": "scott",
                        "training_role": "user",
                        "source_role_label": "Scott",
                    },
                ),
            )
        ],
        system_prompts=[
            SidecarSystemPrompt(
                slug="group_scene_intro",
                name="Group Scene Intro",
                content="You are playing Emma in a group scene.",
                description="Standard group RP opening",
                is_active=True,
            )
        ],
    )


def test_build_sidecar_registry_and_to_dict_shape():
    registry = _sample_registry()
    data = sidecar_to_dict(registry)

    assert data["metadata"]["schema_version"] == SIDECAR_SCHEMA_VERSION
    assert data["metadata"]["kind"] == SIDECAR_KIND
    assert data["metadata"]["exported_at"]
    assert data["metadata"]["app_name"] == "RoleThread Lite"
    assert data["metadata"]["app_version"] == ROLETHREAD_VERSION
    assert data["dataset"] == {
        "dataset_uuid": "dataset-uuid-1",
        "filename": "training_set.jsonl",
        "entry_count": 3,
        "tag_usage_counts": {"slow_burn": 2, "deleted_tag": 1},
    }
    assert data["categories"][0] == {
        "slug": "behavior",
        "name": "Behavior",
        "sort_order": 0,
        "is_active": True,
        "is_builtin": True,
    }
    assert data["tags"][0]["slug"] == "slow_burn"
    assert data["tags"][0]["lifecycle"] == {"lifecycle_state": "active"}
    assert data["aliases"][0]["old_slug"] == "slowburn"
    assert data["characters"] == [
        {
            "slug": "scott",
            "display_name": "Scott",
            "description": None,
            "is_active": True,
        }
    ]
    assert data["entry_character_mappings"] == [
        {
            "entry_uuid": "entry-1",
            "turns": [
                {
                    "turn_index": 1,
                    "character_slug": "scott",
                    "training_role": "user",
                    "source_role_label": "Scott",
                }
            ],
        }
    ]
    assert data["system_prompts"] == [
        {
            "slug": "group_scene_intro",
            "name": "Group Scene Intro",
            "content": "You are playing Emma in a group scene.",
            "description": "Standard group RP opening",
            "is_active": True,
        }
    ]


def test_sidecar_round_trips_through_dict_parser():
    registry = _sample_registry()

    parsed = parse_sidecar_dict(sidecar_to_dict(registry))

    assert parsed == registry


def test_sidecar_round_trips_through_file(tmp_path):
    registry = _sample_registry()
    path = tmp_path / "training_set.registry.json"

    write_sidecar(registry, path)
    parsed = read_sidecar(path)

    assert parsed == registry


def test_write_sidecar_outputs_human_readable_json(tmp_path):
    registry = _sample_registry()
    path = tmp_path / "pretty.registry.json"

    write_sidecar(registry, path)
    text = path.read_text(encoding="utf-8")

    assert text.endswith("\n")
    assert '\n  "metadata": {' in text
    assert '\n    "schema_version": 1,' in text
    assert json.loads(text) == sidecar_to_dict(registry)


def test_parse_sidecar_rejects_wrong_kind():
    data = sidecar_to_dict(_sample_registry())
    data["metadata"]["kind"] = "someone.else"

    with pytest.raises(SidecarValidationError, match="Unsupported sidecar kind"):
        parse_sidecar_dict(data)


def test_parse_sidecar_rejects_unsupported_schema_version():
    data = sidecar_to_dict(_sample_registry())
    data["metadata"]["schema_version"] = 999

    with pytest.raises(SidecarValidationError, match="Unsupported registry sidecar"):
        parse_sidecar_dict(data)


def test_parse_sidecar_rejects_missing_required_fields():
    data = sidecar_to_dict(_sample_registry())
    del data["dataset"]["filename"]

    with pytest.raises(SidecarValidationError, match="filename"):
        parse_sidecar_dict(data)


def test_parse_sidecar_rejects_legacy_dataset_without_uuid():
    data = sidecar_to_dict(_sample_registry())
    del data["dataset"]["dataset_uuid"]

    with pytest.raises(SidecarValidationError, match="dataset_uuid"):
        parse_sidecar_dict(data)


def test_parse_sidecar_defaults_optional_collections_and_metadata():
    data = {
        "metadata": {
            "schema_version": 1,
            "kind": SIDECAR_KIND,
            "exported_at": "2026-05-11T00:00:00+00:00",
        },
        "dataset": {
            "dataset_uuid": "dataset-uuid-1",
            "filename": "training_set.jsonl",
        },
        "tags": [
            {
                "slug": "slow_burn",
                "name": "Slow Burn",
            }
        ],
    }

    parsed = parse_sidecar_dict(data)

    assert parsed.metadata == SidecarMetadata(
        schema_version=1,
        kind=SIDECAR_KIND,
        exported_at="2026-05-11T00:00:00+00:00",
    )
    assert parsed.dataset_info == SidecarDatasetInfo(
        dataset_uuid="dataset-uuid-1",
        filename="training_set.jsonl",
        entry_count=0,
        tag_usage_counts={},
    )
    assert parsed.categories == ()
    assert parsed.tags == (
        SidecarTag(
            slug="slow_burn",
            name="Slow Burn",
            category_slug=None,
            sort_order=0,
            status="active",
            is_active=True,
            is_builtin=False,
            lifecycle={},
        ),
    )
    assert parsed.aliases == ()
    assert parsed.characters == ()
    assert parsed.entry_character_mappings == ()
    assert parsed.system_prompts == ()


def test_build_sidecar_registry_defaults_optional_tag_and_alias_fields():
    registry = build_sidecar_registry(
        categories=[],
        tags=[{"slug": "slow_burn", "name": "Slow Burn"}],
        aliases=[{"old_slug": "old_tag", "action": "hide"}],
        dataset_uuid="dataset-uuid-1",
        dataset_filename="training_set.jsonl",
        entry_count=0,
        tag_usage_counts={},
    )

    assert registry.tags == (
        SidecarTag(slug="slow_burn", name="Slow Burn"),
    )
    assert registry.aliases == (
        SidecarAlias(old_slug="old_tag", new_slug=None, action="hide"),
    )


def test_sidecar_registry_coerces_character_sections():
    registry = build_sidecar_registry(
        categories=[],
        tags=[],
        aliases=[],
        characters=[
            {
                "slug": "emma",
                "display_name": "Emma",
                "description": "Telepath",
                "is_active": True,
            }
        ],
        entry_character_mappings=[
            {
                "entry_uuid": "entry-1",
                "turns": [
                    {
                        "turn_index": 2,
                        "character_slug": "emma",
                        "training_role": "assistant",
                        "source_role_label": "Emma",
                    }
                ],
            }
        ],
        dataset_uuid="dataset-uuid-1",
        dataset_filename="training_set.jsonl",
        entry_count=1,
        tag_usage_counts={},
    )

    assert registry.characters == (
        SidecarCharacter(
            slug="emma",
            display_name="Emma",
            description="Telepath",
            is_active=True,
        ),
    )
    assert registry.entry_character_mappings == (
        SidecarEntryCharacterMapping(
            entry_uuid="entry-1",
            turns=(
                {
                    "turn_index": 2,
                    "character_slug": "emma",
                    "training_role": "assistant",
                    "source_role_label": "Emma",
                },
            ),
        ),
    )


def test_sidecar_registry_coerces_system_prompt_sections():
    registry = build_sidecar_registry(
        categories=[],
        tags=[],
        aliases=[],
        system_prompts=[
            {
                "slug": "group_scene_intro",
                "name": "Group Scene Intro",
                "content": "Prompt content",
                "description": "Reusable group opener",
                "is_active": True,
            }
        ],
        dataset_uuid="dataset-uuid-1",
        dataset_filename="training_set.jsonl",
        entry_count=0,
        tag_usage_counts={},
    )

    assert registry.system_prompts == (
        SidecarSystemPrompt(
            slug="group_scene_intro",
            name="Group Scene Intro",
            content="Prompt content",
            description="Reusable group opener",
            is_active=True,
        ),
    )


def test_parse_sidecar_rejects_invalid_character_mapping_turn():
    data = sidecar_to_dict(_sample_registry())
    data["entry_character_mappings"] = [
        {
            "entry_uuid": "entry-2",
            "turns": [{"turn_index": 1, "training_role": "user"}],
        }
    ]

    with pytest.raises(SidecarValidationError, match="character_slug"):
        parse_sidecar_dict(data)


def test_parse_sidecar_rejects_invalid_system_prompt():
    data = sidecar_to_dict(_sample_registry())
    data["system_prompts"] = [
        {
            "slug": "group_scene_intro",
            "name": "Group Scene Intro",
        }
    ]

    with pytest.raises(SidecarValidationError, match="content"):
        parse_sidecar_dict(data)


@pytest.mark.parametrize(
    ("dataset_path", "expected"),
    [
        ("training_set.jsonl", "training_set.registry.json"),
        ("training_set.v2.jsonl", "training_set.v2.registry.json"),
        ("dataset", "dataset.registry.json"),
    ],
)
def test_sidecar_path_for_dataset(dataset_path, expected, tmp_path):
    path = tmp_path / dataset_path

    assert sidecar_path_for_dataset(path) == tmp_path / expected


def test_sidecar_dataclasses_are_frozen():
    category = SidecarCategory(slug="custom", name="Custom")

    with pytest.raises(dataclasses.FrozenInstanceError):
        category.name = "Changed"

