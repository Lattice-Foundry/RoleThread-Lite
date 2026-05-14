from ui.theme import (
    SCORE_COLOR_ATTENTION,
    SCORE_COLOR_CRITICAL,
    SCORE_COLOR_EXCELLENT,
    SCORE_COLOR_FAIR,
    SCORE_COLOR_GOOD,
    score_color,
)


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
