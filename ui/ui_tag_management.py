"""Compatibility wrapper for the Tag Management page package."""

from ui.tag_management.formatting import (
    active_tag_detail_html as _active_tag_detail_html,
    archived_tag_label_html as _archived_tag_label_html,
)
from ui.tag_management.page import render_tag_management_page

__all__ = [
    "render_tag_management_page",
    "_active_tag_detail_html",
    "_archived_tag_label_html",
]

