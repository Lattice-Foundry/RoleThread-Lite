from pathlib import Path

from ui.theme import (
    SCORE_COLOR_ATTENTION,
    SCORE_COLOR_CRITICAL,
    SCORE_COLOR_EXCELLENT,
    SCORE_COLOR_FAIR,
    SCORE_COLOR_GOOD,
    score_color,
)


def _app_source() -> str:
    return (Path(__file__).resolve().parents[3] / "app.py").read_text(encoding="utf-8")


def test_score_color_composite_ranges():
    assert score_color(95, 100) == SCORE_COLOR_EXCELLENT
    assert score_color(75, 100) == SCORE_COLOR_GOOD
    assert score_color(55, 100) == SCORE_COLOR_FAIR
    assert score_color(35, 100) == SCORE_COLOR_ATTENTION
    assert score_color(20, 100) == SCORE_COLOR_CRITICAL


def test_score_color_subscore_ranges():
    assert score_color(23, 25) == SCORE_COLOR_EXCELLENT
    assert score_color(18, 25) == SCORE_COLOR_GOOD
    assert score_color(13, 25) == SCORE_COLOR_FAIR
    assert score_color(7, 25) == SCORE_COLOR_ATTENTION
    assert score_color(6.2, 25) == SCORE_COLOR_CRITICAL


def test_score_color_clamps_out_of_range_scores():
    assert score_color(200, 100) == SCORE_COLOR_EXCELLENT
    assert score_color(-10, 100) == SCORE_COLOR_CRITICAL
    assert score_color(10, 0) == SCORE_COLOR_CRITICAL


def test_recent_dataset_button_css_is_left_aligned_and_compact():
    source = _app_source()

    assert "div.st-key-recent_dataset_list" in source
    assert "justify-content: flex-start !important;" in source
    assert "min-height: 1.65rem !important;" in source
    assert "text-align: left !important;" in source
