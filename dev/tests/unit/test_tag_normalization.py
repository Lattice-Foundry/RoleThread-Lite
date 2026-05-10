from core.tag_normalization import normalize_tag
from core.tag_registry import prettify_tag_name, slugify_tag_name


def test_normalize_tag_canonicalizes_spacing_case_and_dashes():
    cases = [
        ("sLow burn", "slow_burn", "Slow Burn"),
        ("slow-burn", "slow_burn", "Slow Burn"),
        ("slow burn", "slow_burn", "Slow Burn"),
    ]

    for raw, slug, display_name in cases:
        normalized = normalize_tag(raw)
        assert normalized.slug == slug
        assert normalized.display_name == display_name
        assert normalized.changed is True


def test_normalize_tag_collapses_duplicate_punctuation_and_spacing():
    normalized = normalize_tag("  slow --- burn!!!  ")

    assert normalized.slug == "slow_burn"
    assert normalized.display_name == "Slow Burn"


def test_normalize_tag_preserves_known_uppercase_words_in_display_name():
    assert normalize_tag("ai generated").display_name == "AI Generated"
    assert normalize_tag("rp style").display_name == "RP Style"
    assert normalize_tag("llm judge").display_name == "LLM Judge"


def test_normalize_tag_handles_empty_or_invalid_values_safely():
    assert normalize_tag("").slug == ""
    assert normalize_tag("!!!").slug == ""
    assert normalize_tag(None).slug == ""


def test_slugify_and_prettify_wrappers_use_canonical_normalization():
    assert slugify_tag_name("sLow burn") == "slow_burn"
    assert slugify_tag_name("slow-burn") == "slow_burn"
    assert prettify_tag_name("slow-burn") == "Slow Burn"
    assert prettify_tag_name("ai_generated") == "AI Generated"
