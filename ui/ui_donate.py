"""Support RoleThread page backed by LatticeFoundry donation infrastructure."""

from __future__ import annotations

import streamlit as st
import streamlit.components.v1 as components


DONATION_EMBED_URL = (
    "https://latticefoundry.dev/donate/embed?"
    "source=rolethread-lite&interest=rolethread"
)
DONATION_FALLBACK_URL = (
    "https://latticefoundry.dev/donate?"
    "source=rolethread-lite&interest=rolethread"
)
DONATION_IFRAME_HEIGHT = 1000


def render_support_rolethread_page() -> None:
    """Render the in-app donation entry point without owning payments."""

    st.subheader("Support RoleThread")
    st.markdown(
        """
RoleThread Lite is developed by LatticeFoundry, a Sierra Cognitive Group company.

If RoleThread has been useful to you and you would like to support future
development, you can contribute through LatticeFoundry below.

Donations are processed securely through Stripe on LatticeFoundry infrastructure.
RoleThread Lite does not process, store, or retain payment information.
        """.strip()
    )
    st.info(
        "This page requires an internet connection. The rest of RoleThread Lite "
        "remains a local application."
    )
    st.link_button(
        "Open full donation page",
        DONATION_FALLBACK_URL,
        icon=":material/open_in_new:",
    )
    components.iframe(
        src=DONATION_EMBED_URL,
        height=DONATION_IFRAME_HEIGHT,
        scrolling=True,
    )

