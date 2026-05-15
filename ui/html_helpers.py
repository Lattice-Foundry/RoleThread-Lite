"""HTML escaping helpers for Streamlit unsafe-markdown fragments."""

from html import escape


def escape_html(value: object) -> str:
    """Return value escaped for interpolation into trusted HTML wrappers."""

    return escape(str(value if value is not None else ""), quote=True)


def escape_upper_html(value: object) -> str:
    """Return value uppercased and escaped for role/display labels."""

    return escape_html(str(value if value is not None else "").upper())
