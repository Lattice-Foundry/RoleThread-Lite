from copy import deepcopy

from core.loreforge_meta import get_entry_uuid, stamp_entries
from core.qualitative_analysis import analyze_dataset_quality
from core.registry_sidecar import build_sidecar_registry, write_sidecar
from core.tag_registry import TagRegistrySnapshot


def _entry(
    *,
    system: str = "You are a vivid character in a grounded, emotionally aware scene.",
    exchanges: int = 3,
    assistant_text: str | None = None,
    tags: list[str] | None = None,
) -> dict:
    messages = [{"role": "system", "content": system}]
    for index in range(exchanges):
        messages.append(
            {
                "role": "user",
                "content": f"User turn {index} with enough detail to be meaningful.",
            }
        )
        messages.append(
            {
                "role": "assistant",
                "content": assistant_text
                if assistant_text is not None
                else (
                    "This assistant response is descriptive, specific, and long enough "
                    "to provide a useful supervised fine tuning signal for the model."
                ),
            }
        )
    return {"messages": messages, "tags": tags if tags is not None else ["dialogue"]}


def _snapshot() -> TagRegistrySnapshot:
    return TagRegistrySnapshot(
        active_registry={
            "Style": ["dialogue", "narration"],
            "Scene": ["medical"],
        },
        active_categories=[
            {"slug": "style", "name": "Style"},
            {"slug": "scene", "name": "Scene"},
        ],
        active_tag_slugs=["dialogue", "narration", "medical"],
        active_tag_slug_set={"dialogue", "narration", "medical"},
        tag_label_map={
            "dialogue": "Style / dialogue",
            "narration": "Style / narration",
            "medical": "Scene / medical",
        },
        tag_label_map_with_untagged={},
        tag_category_map={
            "dialogue": "Style",
            "narration": "Style",
            "medical": "Scene",
        },
        visible_archived_tags=[],
        default_category_slugs=set(),
        max_active_categories=8,
    )


def test_response_quality_flags_short_empty_and_placeholder_responses():
    entries = [
        _entry(assistant_text="test", exchanges=1),
        _entry(assistant_text="", exchanges=1),
    ]

    report = analyze_dataset_quality(entries)

    assert report.response_quality.short_response_count == 2
    assert report.response_quality.empty_response_count == 1
    assert report.response_quality.placeholder_count == 1
    assert report.response_quality.score < 10
    assert report.response_quality.flagged_entry_uuids == ("entry_index:0", "entry_index:1")


def test_diversity_detects_near_duplicate_entries_and_tag_metrics():
    entry_a = _entry(system="Unique system prompt A that is comfortably over fifty chars.", tags=["dialogue"])
    entry_b = deepcopy(entry_a)
    entry_c = _entry(
        system="Unique system prompt C that is comfortably over fifty chars.",
        assistant_text=(
            "A completely different medical assessment unfolds with clinical pacing, "
            "triage details, and grounded bedside reassurance."
        ),
        tags=["medical"],
    )

    report = analyze_dataset_quality([entry_a, entry_b, entry_c], tag_snapshot=_snapshot())

    assert report.diversity.unique_system_prompts == 2
    assert report.diversity.tag_coverage_percent == 100
    assert report.diversity.category_coverage_count == 2
    assert report.diversity.near_duplicate_count == 1
    assert report.diversity.near_duplicate_pairs == (("entry_index:0", "entry_index:1"),)


def test_structure_scores_validation_and_exchange_distribution():
    good = _entry(exchanges=4)
    short_system = _entry(system="Too short.", exchanges=1)
    invalid = {"messages": [{"role": "user", "content": "No system."}], "tags": []}

    report = analyze_dataset_quality([good, short_system, invalid])

    assert report.structure.invalid_entry_count == 1
    assert report.structure.exchange_count_distribution == {"1": 2, "2": 0, "3-7": 1, "8+": 0}
    assert report.structure.in_optimal_range_percent == 33.33
    assert report.structure.short_system_prompt_count == 1
    assert report.structure.missing_system_prompt_count == 1


def test_metadata_integrity_uses_native_tags_character_mappings_and_sidecar(tmp_path):
    stamped = stamp_entries(
        [
            _entry(tags=["dialogue"]),
            _entry(tags=[]),
        ],
        dataset_uuid="dataset-uuid",
    )
    sidecar = build_sidecar_registry(
        categories=[{"slug": "style", "name": "Style"}],
        tags=[{"slug": "dialogue", "name": "Dialogue", "category_slug": "style"}],
        aliases=[],
        dataset_uuid="dataset-uuid",
        dataset_filename="sample.jsonl",
        entry_count=2,
        tag_usage_counts={"dialogue": 1},
        characters=[{"slug": "emma", "display_name": "Emma"}],
        entry_character_mappings=[
            {
                "entry_uuid": get_entry_uuid(stamped[0]),
                "turns": [
                    {
                        "turn_index": 1,
                        "character_slug": "emma",
                        "training_role": "user",
                        "source_role_label": "Emma",
                    }
                ],
            }
        ],
    )
    sidecar_path = tmp_path / "sample.registry.json"
    write_sidecar(sidecar, sidecar_path)

    report = analyze_dataset_quality(
        stamped,
        sidecar_path=sidecar_path,
        tag_snapshot=_snapshot(),
    )

    assert report.metadata_integrity.native_stamp_percent == 100
    assert report.metadata_integrity.tagged_entry_percent == 50
    assert report.metadata_integrity.character_mapping_percent == 50
    assert report.metadata_integrity.sidecar_present is True
    assert report.metadata_integrity.sidecar_current is True
    assert get_entry_uuid(stamped[1]) in report.metadata_integrity.flagged_entry_uuids


def test_composite_score_is_sum_of_four_subscores():
    report = analyze_dataset_quality([_entry(exchanges=4)])
    expected = round(
        report.response_quality.score
        + report.diversity.score
        + report.structure.score
        + report.metadata_integrity.score,
        2,
    )

    assert report.composite_score == expected


def test_narrative_spectrum_detects_dialogue_heavy_content():
    dialogue_entry = _entry(
        assistant_text='"Hello there, friend, how are you feeling today?"',
        exchanges=1,
    )
    narrative_entry = _entry(
        assistant_text="Emma walked through the dim room and studied every quiet detail.",
        exchanges=1,
    )

    dialogue_report = analyze_dataset_quality([dialogue_entry])
    narrative_report = analyze_dataset_quality([narrative_entry])

    assert dialogue_report.narrative_insight.spectrum_label == "Heavy Dialogue"
    assert dialogue_report.narrative_insight.dialogue_ratio > 0.8
    assert narrative_report.narrative_insight.spectrum_label == "Heavy Narrative"
    assert narrative_report.narrative_insight.dialogue_ratio == 0


def test_empty_dataset_returns_safe_zero_report():
    report = analyze_dataset_quality([])

    assert report.total_entries == 0
    assert report.total_messages == 0
    assert report.composite_score == 0
    assert report.grade == "Significant Issues"
    assert report.response_quality.flagged_entry_uuids == ()


def test_single_entry_and_identical_entries_edge_cases():
    single = analyze_dataset_quality([_entry()])
    identical = analyze_dataset_quality([_entry(), _entry()])

    assert single.total_entries == 1
    assert single.diversity.near_duplicate_count == 0
    assert identical.total_entries == 2
    assert identical.diversity.near_duplicate_count == 1


def test_analysis_does_not_mutate_entries():
    entries = [_entry(tags=["dialogue", "medical"])]
    before = deepcopy(entries)

    analyze_dataset_quality(entries, tag_snapshot=_snapshot())

    assert entries == before
