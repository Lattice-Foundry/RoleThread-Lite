"""Shared UI color constants for RoleThread Lite."""
from math import ceil, floor

COLOR_PRIMARY = "#3EB489"
COLOR_PRIMARY_HOVER = "#31966F"
COLOR_PRIMARY_ACTIVE = "#257A59"
COLOR_PRIMARY_HOVER_BACKGROUND = "rgba(62, 180, 137, 0.10)"
COLOR_SIDEBAR_BACKGROUND = "#202326"
COLOR_SIDEBAR_BUTTON_BORDER = "rgba(232, 232, 232, 0.28)"
COLOR_SIDEBAR_BUTTON_TEXT = "#E8E8E8"

COLOR_USER = "#1A73E8"
COLOR_ASSISTANT = "#2ECC71"
COLOR_SUBTITLE = COLOR_USER
COLOR_CUSTOM_BADGE = COLOR_USER
COLOR_BUILT_IN_BADGE = "#888888"
COLOR_SECONDARY_TEXT = "#777777"

SCORE_COLOR_EXCELLENT = "#2ECC71"
SCORE_COLOR_GOOD = "#A8D86E"
SCORE_COLOR_FAIR = "#F1C40F"
SCORE_COLOR_ATTENTION = "#E67E22"
SCORE_COLOR_CRITICAL = "#E74C3C"

COLOR_WARNING_ACCENT = "#F4F15A"
COLOR_WARNING_BACKGROUND = "rgba(244, 241, 90, 0.13)"
COLOR_WARNING_TEXT = "#E8E8E8"

ENTRY_ROW_PRIMARY_MARKDOWN = "green"
ENTRY_ROW_USER_MARKDOWN = "blue"
ENTRY_ROW_WARNING_MARKDOWN = "yellow"
ENTRY_ROW_ATTENTION_MARKDOWN = "orange"


def score_color(score: float, max_score: float = 100.0) -> str:
    """Return the qualitative score color for a 0-max score."""

    if max_score <= 0:
        return SCORE_COLOR_CRITICAL
    bounded_score = max(0.0, min(float(score), max_score))
    if bounded_score >= ceil(max_score * 0.9):
        return SCORE_COLOR_EXCELLENT
    if bounded_score >= ceil(max_score * 0.7):
        return SCORE_COLOR_GOOD
    if bounded_score >= ceil(max_score * 0.5):
        return SCORE_COLOR_FAIR
    if bounded_score >= floor(max_score * 0.3):
        return SCORE_COLOR_ATTENTION
    return SCORE_COLOR_CRITICAL

