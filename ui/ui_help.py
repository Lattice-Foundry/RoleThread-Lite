"""Help documentation browser for RoleThread Lite."""

import streamlit as st
import streamlit.components.v1 as components

from ui.help_docs import (
    HelpSearchResult,
    build_help_search_results,
    extract_markdown_sections,
    format_section_outline,
    get_adjacent_help_articles,
    get_help_breadcrumb,
    get_help_articles_by_category,
    get_related_help_articles,
    load_help_document,
    resolve_help_article_id,
)
from ui.navigation import render_sidebar_branding
from ui.search_controls import (
    clear_document_search,
    render_document_search_controls,
    show_document_search_results,
)


HELP_ACTIVE_ARTICLE_KEY = "help_active_article_id"
HELP_LAST_RENDERED_ARTICLE_KEY = "_help_last_rendered_article_id"
HELP_SCROLL_COUNTER_KEY = "_help_scroll_counter"
HELP_SEARCH_QUERY_KEY = "help_search_query"
HELP_SEARCH_RESULTS_VISIBLE_KEY = "help_search_results_visible"
CLICKABLE_ARTICLE_OUTLINE = False


def get_active_help_article_id() -> str:
    """Return the active Help article ID, repairing invalid state."""

    article_id = resolve_help_article_id(st.session_state.get(HELP_ACTIVE_ARTICLE_KEY))
    st.session_state[HELP_ACTIVE_ARTICLE_KEY] = article_id
    return article_id


def select_help_article(
    article_id: str,
    *,
    clear_search: bool = False,
    hide_search_results: bool = False,
    rerun: bool = True,
) -> str:
    """Select a Help article using session state as the source of truth."""

    resolved_article_id = resolve_help_article_id(article_id)
    st.session_state[HELP_ACTIVE_ARTICLE_KEY] = resolved_article_id
    if clear_search:
        st.session_state[HELP_SEARCH_QUERY_KEY] = ""
        st.session_state[HELP_SEARCH_RESULTS_VISIBLE_KEY] = False
    elif hide_search_results:
        st.session_state[HELP_SEARCH_RESULTS_VISIBLE_KEY] = False
    if rerun:
        st.rerun()
    return resolved_article_id


def set_active_help_article(article_id: str) -> str:
    """Set the active Help article ID after safe fallback resolution."""

    return select_help_article(article_id, rerun=False)


def _render_article_selection_button(
    label: str,
    article_id: str,
    *,
    key: str,
    button_type: str = "secondary",
    hide_search_results: bool = False,
    icon: str | None = None,
) -> None:
    """Render a Help navigation button that uses the shared selection path."""

    button_kwargs = {
        "key": key,
        "type": button_type,
        "width": "stretch",
    }
    if icon is not None:
        button_kwargs["icon"] = icon
    if st.button(label, **button_kwargs):
        select_help_article(
            article_id,
            hide_search_results=hide_search_results,
        )


def _show_help_search_results() -> None:
    show_document_search_results(
        HELP_SEARCH_QUERY_KEY,
        HELP_SEARCH_RESULTS_VISIBLE_KEY,
    )


def _clear_help_search() -> None:
    clear_document_search(
        HELP_SEARCH_QUERY_KEY,
        HELP_SEARCH_RESULTS_VISIBLE_KEY,
    )


def _scroll_to_top_on_article_change(article_id: str) -> None:
    previous_article_id = st.session_state.get(HELP_LAST_RENDERED_ARTICLE_KEY)
    st.session_state[HELP_LAST_RENDERED_ARTICLE_KEY] = article_id
    if previous_article_id in (None, article_id):
        return

    scroll_counter = int(st.session_state.get(HELP_SCROLL_COUNTER_KEY, 0)) + 1
    st.session_state[HELP_SCROLL_COUNTER_KEY] = scroll_counter
    scroll_token = f"{article_id}:{scroll_counter}"

    # Streamlit does not expose a reliable native imperative scroll-to-top API.
    # Keep this helper isolated to Help article transitions only.
    components.html(
        f"""
        <script>
        (() => {{
          const token = "{scroll_token}";
          const targetWindow = window.parent || window;
          targetWindow.__rolethreadHelpScrollToken = token;

          function getTargets() {{
            const doc = targetWindow.document || document;
            return [
              doc.querySelector('[data-testid="stAppViewContainer"]'),
              doc.querySelector('[data-testid="stMain"]'),
              doc.querySelector('section.main'),
              doc.querySelector('.main'),
              doc.querySelector('[data-testid="stMainBlockContainer"]'),
              doc.scrollingElement,
              doc.documentElement,
              doc.body,
              targetWindow,
            ].filter(Boolean);
          }}

          function scrollTopNow() {{
            if (targetWindow.__rolethreadHelpScrollToken !== token) return;
            for (const target of getTargets()) {{
              try {{
                if (typeof target.scrollTo === "function") {{
                  target.scrollTo({{ top: 0, left: 0, behavior: "auto" }});
                }} else if ("scrollTop" in target) {{
                  target.scrollTop = 0;
                }}
              }} catch (error) {{}}
            }}
          }}

          scrollTopNow();
          requestAnimationFrame(scrollTopNow);
          setTimeout(scrollTopNow, 50);
          setTimeout(scrollTopNow, 120);
          setTimeout(scrollTopNow, 250);
          setTimeout(scrollTopNow, 400);
        }})();
        </script>
        """,
        height=1,
    )


def _render_help_sidebar(active_article_id: str) -> None:
    render_sidebar_branding()
    st.sidebar.markdown("**Help Documentation**")
    for category, articles in get_help_articles_by_category().items():
        expanded = any(
            article.article_id == active_article_id
            for article in articles
        )
        with st.sidebar.expander(category, expanded=expanded):
            for article in articles:
                _render_article_selection_button(
                    article.title,
                    article.article_id,
                    key=f"_help_article_{article.article_id}",
                    button_type=(
                        "primary"
                        if article.article_id == active_article_id
                        else "secondary"
                    ),
                )


def _render_search_results(
    query: str,
    matches: tuple[HelpSearchResult, ...],
) -> None:
    if not query.strip():
        return

    result_count = len(matches)
    st.markdown(f"**Search Results ({result_count})**")
    if not matches:
        st.info("No Help articles matched your search. Try a workflow, page, or concept name.")
        st.divider()
        return

    for result in matches:
        article = result.article
        button_col, text_col = st.columns([0.16, 0.84])
        with button_col:
            _render_article_selection_button(
                "Open",
                article.article_id,
                key=f"_help_search_{article.article_id}",
                hide_search_results=True,
            )
        with text_col:
            st.markdown(f"**{article.title}**")
            st.caption(f"{article.category} - {result.snippet}")
    st.divider()


def _render_search_controls() -> None:
    search_state = render_document_search_controls(
        form_key="help_search_form",
        input_label="Search help articles...",
        query_key=HELP_SEARCH_QUERY_KEY,
        results_visible_key=HELP_SEARCH_RESULTS_VISIBLE_KEY,
        search_button_key="_help_search_submit",
        clear_button_key="_help_search_clear",
    )
    if search_state.results_visible:
        matches = build_help_search_results(search_state.query)
        _render_search_results(search_state.query, matches)
    elif search_state.query.strip():
        st.caption("Search query preserved. Click Search to show results again.")


def _render_related_articles(article_id: str) -> None:
    related_articles = get_related_help_articles(article_id)
    if not related_articles:
        return

    st.divider()
    st.markdown("**Related Articles**")
    columns = st.columns(2)
    for index, article in enumerate(related_articles):
        with columns[index % 2]:
            _render_article_selection_button(
                article.title,
                article.article_id,
                key=f"_help_related_{article.article_id}",
            )
            st.caption(article.summary)


def _render_article_navigation(article_id: str) -> None:
    previous_article, next_article = get_adjacent_help_articles(article_id)
    if previous_article is None and next_article is None:
        return

    st.divider()
    previous_col, next_col = st.columns(2)
    with previous_col:
        if previous_article is not None:
            _render_article_selection_button(
                previous_article.title,
                previous_article.article_id,
                key=f"_help_previous_{previous_article.article_id}",
                icon=":material/arrow_back:",
            )
    with next_col:
        if next_article is not None:
            _render_article_selection_button(
                next_article.title,
                next_article.article_id,
                key=f"_help_next_{next_article.article_id}",
                icon=":material/arrow_forward:",
            )


def _render_active_article(article_id: str) -> None:
    _scroll_to_top_on_article_change(article_id)
    document = load_help_document(article_id)
    article = document.article
    st.caption(" / ".join(get_help_breadcrumb(article.article_id)))
    if document.content:
        _render_article_outline(document.content)
        st.markdown(document.content)
    else:
        st.warning(f"Help article not found: `{article.file_name}`")
    _render_related_articles(article.article_id)
    _render_article_navigation(article.article_id)


def _render_article_outline(content: str) -> None:
    sections = extract_markdown_sections(content)
    if len(sections) < 2:
        return

    st.markdown("**On this page**")
    # Keep section links informational until Streamlit heading anchors can be
    # verified in a live browser reliably; the generated anchors are ready.
    st.markdown(
        "\n".join(
            format_section_outline(sections, clickable=CLICKABLE_ARTICLE_OUTLINE)
        )
    )
    st.divider()


def render_help_page() -> None:
    """Render the Help documentation browser."""

    active_article_id = get_active_help_article_id()
    _render_help_sidebar(active_article_id)

    st.subheader("Help")
    _render_search_controls()
    active_article_id = get_active_help_article_id()
    _render_active_article(active_article_id)

