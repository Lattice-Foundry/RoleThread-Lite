import json
from pathlib import Path

from streamlit.testing.v1 import AppTest

import ui.ui_help as ui_help
import ui.ui_faq as ui_faq
from ui.ui_faq import (
    FAQEntry,
    derive_faq_category,
    derive_related_help_ids,
    filter_faq_entries,
    get_faq_category_description,
    get_faq_category_order,
    get_faq_entries_by_category,
    load_faq_entries,
)
from ui.ui_help import HelpTopic, clean_help_topic_title, filter_help_topics, load_help_topics
from ui.help_docs import (
    HELP_DIR,
    build_help_search_results,
    extract_markdown_sections,
    format_section_outline,
    get_adjacent_help_articles,
    get_default_help_article_id,
    get_help_article,
    get_help_article_order,
    get_help_breadcrumb,
    get_help_article_registry,
    get_help_articles_by_category,
    get_help_category_order,
    get_related_help_articles,
    load_help_document,
    resolve_help_article_id,
    search_help_documents,
    slugify_heading,
    validate_help_article_registry,
)


class FakeHelpStreamlit:
    def __init__(self):
        self.session_state = {}
        self.rerun_count = 0
        self.iframe_calls = []

    def rerun(self):
        self.rerun_count += 1

    def iframe(self, body, *, height=None, width=None):
        self.iframe_calls.append({
            "body": body,
            "height": height,
            "width": width,
        })


class FakeFAQStreamlit:
    def __init__(self):
        self.session_state = {}
        self.rerun_count = 0

    def rerun(self):
        self.rerun_count += 1


def test_clean_help_topic_title_formats_filename():
    assert clean_help_topic_title(Path("getting_started.md")) == "Getting Started"


def test_load_help_topics_reads_markdown_files(tmp_path):
    help_dir = tmp_path / "help"
    help_dir.mkdir()
    (help_dir / "getting_started.md").write_text("# Welcome", encoding="utf-8")
    (help_dir / "ignore.txt").write_text("Nope", encoding="utf-8")

    topics = load_help_topics(help_dir)

    assert len(topics) == 1
    assert topics[0].title == "Getting Started"
    assert topics[0].content == "# Welcome"


def test_filter_help_topics_matches_title_and_content():
    topics = (
        HelpTopic(title="Getting Started", content="Welcome guide", path=Path("a.md")),
        HelpTopic(title="Export", content="Create JSONL files", path=Path("b.md")),
    )

    assert filter_help_topics(topics, "export") == (topics[1],)
    assert filter_help_topics(topics, "welcome") == (topics[0],)
    assert filter_help_topics(topics, "   ") == topics


def test_help_article_registry_has_expected_articles():
    registry = get_help_article_registry()

    assert len(registry) == 39
    assert get_default_help_article_id() == "getting-started"
    assert registry["getting-started"].file_name == "01_getting_started.md"
    assert registry["glossary"].category == "Reference"
    assert (
        registry["os-compatibility-and-storage-policy"].file_name
        == "25_os_compatibility_and_storage.md"
    )
    assert registry["understanding-default-tags"].file_name == "27_understanding_default_tags.md"
    assert registry["understanding-default-tags"].category == "Metadata and Organization"
    assert registry["developer-launch-flags"].file_name == "26_developer_launch_flags.md"
    assert registry["developer-launch-flags"].category == "For Developers"
    assert registry["rolethread-studio-vision"].file_name == "28_rolethread_studio_vision.md"
    assert registry["rolethread-studio-vision"].category == "For Developers"
    assert registry["codebase-architecture"].file_name == "29_codebase_architecture.md"
    assert registry["codebase-architecture"].category == "For Developers"
    assert registry["layer-boundaries-and-responsibilities"].file_name == (
        "30_layer_boundaries_and_responsibilities.md"
    )
    assert registry["layer-boundaries-and-responsibilities"].category == "For Developers"
    assert registry["platform-support-philosophy"].file_name == (
        "31_platform_support_philosophy.md"
    )
    assert registry["platform-support-philosophy"].category == "For Developers"
    assert registry["data-safety-philosophy"].file_name == "32_data_safety_philosophy.md"
    assert registry["data-safety-philosophy"].category == "For Developers"
    assert registry["testing-philosophy"].file_name == "33_testing_philosophy.md"
    assert registry["testing-philosophy"].category == "For Developers"
    assert registry["naming-and-terminology-guide"].file_name == (
        "34_naming_and_terminology_guide.md"
    )
    assert registry["naming-and-terminology-guide"].category == "For Developers"
    assert registry["ui-and-theme-style-guide"].file_name == (
        "35_ui_and_theme_style_guide.md"
    )
    assert registry["ui-and-theme-style-guide"].category == "For Developers"
    assert registry["build-and-packaging-overview"].file_name == (
        "36_build_and_packaging_overview.md"
    )
    assert registry["build-and-packaging-overview"].category == "For Developers"
    assert registry["windows-installer-and-launcher-architecture"].file_name == (
        "37_windows_installer_and_launcher_architecture.md"
    )
    assert (
        registry["windows-installer-and-launcher-architecture"].category
        == "For Developers"
    )
    assert registry["contribution-guidelines"].file_name == (
        "38_contribution_guidelines.md"
    )
    assert registry["contribution-guidelines"].category == "For Developers"
    assert registry["lite-vs-studio-boundaries"].file_name == (
        "39_lite_vs_studio_boundaries.md"
    )
    assert registry["lite-vs-studio-boundaries"].category == "For Developers"
    assert len(registry) == len(set(registry))


def test_help_article_registry_files_exist():
    for article in get_help_article_registry().values():
        assert (HELP_DIR / article.file_name).is_file()


def test_deep_edit_article_keeps_legacy_article_id_and_file_name():
    article = get_help_article_registry()["editing-entries"]

    assert article.title == "Deep Edit"
    assert article.file_name == "09_editing_entries.md"


def test_developer_launch_flags_help_article_documents_supported_flags():
    document = load_help_document("developer-launch-flags")

    assert document.article.title == "Developer Launch Flags"
    assert "`dev`" in document.content
    assert "`webapp`" in document.content
    assert "`edge-debug`" in document.content
    assert "`webapp-debug`" in document.content
    assert "streamlit run app.py -- webapp edge-debug" in document.content
    assert "Launch Flags Detected" in document.content
    assert "Edge Launch Debug Diagnostics" in document.content
    assert "official internal webapp launch mode" in document.content
    assert "Diagnostics are gated behind `dev`" in document.content


def test_os_compatibility_help_article_documents_v1_policy():
    document = load_help_document("os-compatibility-and-storage-policy")

    assert "Windows is a primary V1 support platform" in document.content
    assert "Linux is a primary V1 support platform" in document.content
    assert "macOS is beta-supported for V1" in document.content
    assert "Python 3.14.4" in document.content
    assert "%LOCALAPPDATA%\\RoleThread" in document.content
    assert "~/.local/share/rolethread" in document.content
    assert "~/Library/Application Support/RoleThread" in document.content
    assert "Edge web app" in document.content
    assert "Cloud sync folders are optional backup or sync targets" in document.content


def test_understanding_default_tags_documents_v1_taxonomy():
    document = load_help_document("understanding-default-tags")

    assert document.article.title == "Understanding Default Tags"
    assert "conversational dataset engineering" in document.content
    assert "`no_user_control`" in document.content
    assert "`grounded`" in document.content
    assert "`imported`" in document.content
    assert "`duplicate`" in document.content
    assert "Custom tags are expected" in document.content
    assert "Overtagging can become noisy" in document.content


def test_rolethread_studio_vision_documents_lite_and_studio_split():
    document = load_help_document("rolethread-studio-vision")

    assert document.article.title == "RoleThread Studio Vision"
    assert "separate product surfaces" in document.content
    assert "Lite owns deterministic dataset creation" in document.content
    assert "architectural boundary, not a public roadmap" in document.content
    assert "dataset crafting, validation, repair, organization, and export" in document.content


def test_developer_architecture_help_articles_document_layer_boundaries():
    architecture = load_help_document("codebase-architecture")
    boundaries = load_help_document("layer-boundaries-and-responsibilities")
    platform = load_help_document("platform-support-philosophy")

    assert architecture.article.category == "For Developers"
    assert "Streamlit presentation shell" in architecture.content
    assert "`ui/`" in architecture.content
    assert "`services/`" in architecture.content
    assert "`core/`" in architecture.content
    assert "important rules should not depend on one UI framework" in architecture.content

    assert boundaries.article.category == "For Developers"
    assert "durable business logic" in boundaries.content
    assert "Services may call core modules" in boundaries.content
    assert "Core modules should be usable from tests" in boundaries.content

    assert platform.article.category == "For Developers"
    assert "Windows is a primary supported platform" in platform.content
    assert "Linux is a primary supported platform" in platform.content
    assert "macOS is beta/manual support" in platform.content
    assert "Managed webapp mode is Windows/Microsoft Edge only" in platform.content


def test_developer_philosophy_help_articles_document_engineering_conventions():
    safety = load_help_document("data-safety-philosophy")
    testing = load_help_document("testing-philosophy")
    naming = load_help_document("naming-and-terminology-guide")
    style = load_help_document("ui-and-theme-style-guide")

    assert safety.article.category == "For Developers"
    assert "RoleThread Lite's mutation model" in (
        safety.content
    )
    assert "Backup Before Write" in safety.content
    assert "Atomic and Staged Writes" in safety.content
    assert "Rust-Inspired, Not Rust" in safety.content
    assert "Unknown or orphan tags are preserved" in safety.content

    assert testing.article.category == "For Developers"
    assert "pytest" in testing.content
    assert "`core/` and `services/`" in testing.content
    assert "dataset mutation services" in testing.content
    assert "Launcher and platform behavior" in testing.content

    assert naming.article.category == "For Developers"
    assert "Interaction, Not Scene" in naming.content
    assert "Working Copy" in naming.content
    assert "Sidecar" in naming.content
    assert "Python Naming and Style" in naming.content
    assert "PEP 8" in naming.content
    assert "`snake_case` for variables, functions, and modules" in naming.content
    assert "`PascalCase` for classes and dataclasses" in naming.content
    assert "`ALL_CAPS` for constants" in naming.content
    assert "lowercase `snake_case`" in naming.content
    assert "`save_dataset()`" in naming.content
    assert "`create_dataset_backup()`" in naming.content
    assert "`replace_tags_bulk_service()`" in naming.content
    assert "RoleThread Studio" in naming.content

    assert style.article.category == "For Developers"
    assert "#3EB489" in style.content
    assert "#101214" in style.content
    assert "#383A3C" in style.content
    assert "#E8E8E8" in style.content
    assert "#3D9F64" in style.content
    assert "noisy dashboard patterns" in style.content


def test_developer_packaging_help_articles_document_release_and_contribution_flows():
    packaging = load_help_document("build-and-packaging-overview")
    launcher = load_help_document("windows-installer-and-launcher-architecture")
    contribution = load_help_document("contribution-guidelines")
    boundaries = load_help_document("lite-vs-studio-boundaries")

    assert packaging.article.category == "For Developers"
    assert "PyInstaller one-folder bundle" in packaging.content
    assert "Inno Setup" in packaging.content
    assert "Inno Setup installer prototype" in packaging.content
    assert "managed Edge webapp launch mode" in packaging.content
    assert "Normal uninstall preserves RoleThread user data by default" in (
        packaging.content
    )
    assert "Start Menu **Uninstall\nRoleThread Lite** shortcut" in packaging.content
    assert "Rerunning the setup executable" in packaging.content
    assert "rebuilds the PyInstaller bundle by default" in packaging.content
    assert "refuses to build the setup executable" in packaging.content
    assert "they differ" in packaging.content
    assert "Cloud backup copies outside those local RoleThread folders are preserved" in (
        packaging.content
    )
    assert "GitHub Releases" in packaging.content
    assert "requirements-dev.txt" in packaging.content
    assert "Generated artifacts do not belong in Git" in packaging.content

    assert launcher.article.category == "For Developers"
    assert "startup orchestrator" in launcher.content
    assert "installer prototype installs bundled app files" in launcher.content
    assert "Launch RoleThread Lite as a Windows Edge webapp" in launcher.content
    assert "`enable_webapp_launch_mode`" in launcher.content
    assert "DB-backed setting" in launcher.content
    assert "Default uninstall removes installed app files and shortcuts" in (
        launcher.content
    )
    assert "Start Menu **RoleThread\nUninstaller** shortcut" in launcher.content
    assert "not expected to show the uninstall data-removal prompts" in launcher.content
    assert "rebuild the PyInstaller bundle by default" in launcher.content
    assert "prevents a setup executable from accidentally shipping stale" in launcher.content
    assert "Developer clean uninstall" in launcher.content
    assert "does not remove repositories" in launcher.content
    assert "Cloud backup copies outside the local RoleThread folders are preserved" in (
        launcher.content
    )
    assert "`RoleThreadLauncher.exe` is still running" in launcher.content
    assert "selected launch mode" in launcher.content
    assert "windowed/no-console" in launcher.content
    assert "local-only shutdown endpoint" in launcher.content
    assert "`/_stcore/health`" in launcher.content
    assert "`terminate()`" in launcher.content
    assert "`kill()` only as a last resort" in launcher.content
    assert "Managed webapp mode is Windows/Microsoft Edge only" in launcher.content
    assert "launcher-managed environment marker" in launcher.content

    assert contribution.article.category == "For Developers"
    assert "small, testable" in contribution.content
    assert "Keep durable business logic out of the UI layer" in contribution.content
    assert "`core/` and `services/` should remain framework-independent" in (
        contribution.content
    )
    assert "Changes that affect behavior should usually include tests" in (
        contribution.content
    )

    assert boundaries.article.category == "For Developers"
    assert "Lite is the stable dataset tooling surface" in boundaries.content
    assert "Studio is the planned surface" in boundaries.content
    assert "boundary statement, not a feature promise or release schedule" in (
        boundaries.content
    )
    assert "Does it directly improve dataset creation" in boundaries.content


def test_help_article_registry_has_unique_file_names_and_orders():
    articles = tuple(get_help_article_registry().values())
    file_names = [article.file_name for article in articles]
    orders = [article.order for article in articles]

    assert len(file_names) == len(set(file_names))
    assert len(orders) == len(set(orders))


def test_help_article_registry_validates_relationships():
    assert validate_help_article_registry() == ()


def test_help_article_order_is_global_reader_order():
    ordered_ids = [article.article_id for article in get_help_article_order()]

    assert ordered_ids[0] == "getting-started"
    assert ordered_ids[-1] == "lite-vs-studio-boundaries"
    assert ordered_ids.index("creating-entries") < ordered_ids.index("editing-entries")
    assert ordered_ids.index("developer-launch-flags") < ordered_ids.index(
        "codebase-architecture"
    )
    assert ordered_ids.index("platform-support-philosophy") < ordered_ids.index(
        "data-safety-philosophy"
    )
    assert ordered_ids.index("ui-and-theme-style-guide") < ordered_ids.index(
        "build-and-packaging-overview"
    )


def test_help_article_category_order_and_grouping():
    grouped = get_help_articles_by_category()

    assert tuple(grouped) == get_help_category_order()
    assert [article.article_id for article in grouped["Getting Started"]] == [
        "getting-started",
        "what-rolethread-lite-does",
        "dataset-formats",
        "loading-datasets-and-working-copies",
        "creating-a-new-dataset",
    ]
    assert [article.article_id for article in grouped["Metadata and Organization"]] == [
        "tags-categories-and-tag-lifecycle",
        "understanding-default-tags",
        "archived-and-imported-tags",
        "character-registry-and-character-mappings",
        "system-prompt-library",
        "sidecars-and-portable-metadata",
    ]
    assert [article.article_id for article in grouped["Reference"]] == [
        "glossary",
        "os-compatibility-and-storage-policy",
        "v1-limitations-and-future-boundaries",
    ]
    assert [article.article_id for article in grouped["For Developers"]] == [
        "developer-launch-flags",
        "codebase-architecture",
        "layer-boundaries-and-responsibilities",
        "platform-support-philosophy",
        "data-safety-philosophy",
        "testing-philosophy",
        "naming-and-terminology-guide",
        "ui-and-theme-style-guide",
        "build-and-packaging-overview",
        "windows-installer-and-launcher-architecture",
        "contribution-guidelines",
        "rolethread-studio-vision",
        "lite-vs-studio-boundaries",
    ]


def test_help_article_lookup_falls_back_to_default():
    assert resolve_help_article_id(None) == "getting-started"
    assert resolve_help_article_id("missing") == "getting-started"
    assert get_help_article("missing").article_id == "getting-started"
    assert get_help_article("exporting-datasets").title == "Exporting Datasets"


def test_active_help_article_uses_session_state_and_repairs_invalid_state(monkeypatch):
    fake = FakeHelpStreamlit()
    fake.session_state[ui_help.HELP_ACTIVE_ARTICLE_KEY] = "exporting-datasets"
    monkeypatch.setattr(ui_help, "st", fake)

    assert ui_help.get_active_help_article_id() == "exporting-datasets"
    assert fake.session_state[ui_help.HELP_ACTIVE_ARTICLE_KEY] == "exporting-datasets"

    fake.session_state[ui_help.HELP_ACTIVE_ARTICLE_KEY] = "unknown-article"
    assert ui_help.get_active_help_article_id() == "getting-started"
    assert fake.session_state[ui_help.HELP_ACTIVE_ARTICLE_KEY] == "getting-started"


def test_select_help_article_updates_state_and_reruns(monkeypatch):
    fake = FakeHelpStreamlit()
    monkeypatch.setattr(ui_help, "st", fake)

    assert ui_help.select_help_article("editing-entries") == "editing-entries"

    assert fake.session_state[ui_help.HELP_ACTIVE_ARTICLE_KEY] == "editing-entries"
    assert fake.rerun_count == 1


def test_set_active_help_article_updates_state_without_rerun(monkeypatch):
    fake = FakeHelpStreamlit()
    monkeypatch.setattr(ui_help, "st", fake)

    assert ui_help.set_active_help_article("editing-entries") == "editing-entries"

    assert fake.session_state[ui_help.HELP_ACTIVE_ARTICLE_KEY] == "editing-entries"
    assert fake.rerun_count == 0


def test_select_help_article_can_clear_search(monkeypatch):
    fake = FakeHelpStreamlit()
    fake.session_state[ui_help.HELP_SEARCH_QUERY_KEY] = "tags"
    fake.session_state[ui_help.HELP_SEARCH_RESULTS_VISIBLE_KEY] = True
    monkeypatch.setattr(ui_help, "st", fake)

    ui_help.select_help_article("validation-and-repair", clear_search=True, rerun=False)

    assert fake.session_state[ui_help.HELP_ACTIVE_ARTICLE_KEY] == "validation-and-repair"
    assert fake.session_state[ui_help.HELP_SEARCH_QUERY_KEY] == ""
    assert fake.session_state[ui_help.HELP_SEARCH_RESULTS_VISIBLE_KEY] is False


def test_select_help_article_can_hide_results_while_preserving_query(monkeypatch):
    fake = FakeHelpStreamlit()
    fake.session_state[ui_help.HELP_SEARCH_QUERY_KEY] = "tags"
    fake.session_state[ui_help.HELP_SEARCH_RESULTS_VISIBLE_KEY] = True
    monkeypatch.setattr(ui_help, "st", fake)

    ui_help.select_help_article(
        "validation-and-repair",
        hide_search_results=True,
        rerun=False,
    )

    assert fake.session_state[ui_help.HELP_ACTIVE_ARTICLE_KEY] == "validation-and-repair"
    assert fake.session_state[ui_help.HELP_SEARCH_QUERY_KEY] == "tags"
    assert fake.session_state[ui_help.HELP_SEARCH_RESULTS_VISIBLE_KEY] is False


def test_select_help_article_falls_back_for_unknown_article(monkeypatch):
    fake = FakeHelpStreamlit()
    monkeypatch.setattr(ui_help, "st", fake)

    assert ui_help.select_help_article("unknown-article", rerun=False) == "getting-started"
    assert fake.session_state[ui_help.HELP_ACTIVE_ARTICLE_KEY] == "getting-started"


def test_scroll_to_top_does_not_run_on_initial_article_render(monkeypatch):
    fake_st = FakeHelpStreamlit()
    monkeypatch.setattr(ui_help, "st", fake_st)

    ui_help._scroll_to_top_on_article_change("getting-started")

    assert fake_st.session_state[ui_help.HELP_LAST_RENDERED_ARTICLE_KEY] == "getting-started"
    assert fake_st.iframe_calls == []


def test_scroll_to_top_runs_only_when_article_changes(monkeypatch):
    fake_st = FakeHelpStreamlit()
    fake_st.session_state[ui_help.HELP_LAST_RENDERED_ARTICLE_KEY] = "getting-started"
    monkeypatch.setattr(ui_help, "st", fake_st)

    ui_help._scroll_to_top_on_article_change("getting-started")
    ui_help._scroll_to_top_on_article_change("exporting-datasets")

    assert len(fake_st.iframe_calls) == 1
    assert "scrollTo" in fake_st.iframe_calls[0]["body"]
    assert "requestAnimationFrame(scrollTopNow)" in fake_st.iframe_calls[0]["body"]
    assert "__rolethreadHelpScrollToken" in fake_st.iframe_calls[0]["body"]
    assert "exporting-datasets:1" in fake_st.iframe_calls[0]["body"]
    assert "stAppViewContainer" in fake_st.iframe_calls[0]["body"]
    assert "stMain" in fake_st.iframe_calls[0]["body"]
    assert "stMainBlockContainer" in fake_st.iframe_calls[0]["body"]
    assert "setTimeout(scrollTopNow, 400)" in fake_st.iframe_calls[0]["body"]
    assert 'behavior: "auto"' in fake_st.iframe_calls[0]["body"]
    assert fake_st.iframe_calls[0]["height"] == 1
    assert fake_st.iframe_calls[0]["width"] == 1
    assert fake_st.session_state[ui_help.HELP_SCROLL_COUNTER_KEY] == 1
    assert fake_st.session_state[ui_help.HELP_LAST_RENDERED_ARTICLE_KEY] == (
        "exporting-datasets"
    )


def test_scroll_to_top_token_changes_per_article_change(monkeypatch):
    fake_st = FakeHelpStreamlit()
    fake_st.session_state[ui_help.HELP_LAST_RENDERED_ARTICLE_KEY] = "getting-started"
    monkeypatch.setattr(ui_help, "st", fake_st)

    ui_help._scroll_to_top_on_article_change("exporting-datasets")
    ui_help._scroll_to_top_on_article_change("editing-entries")

    assert len(fake_st.iframe_calls) == 2
    assert "exporting-datasets:1" in fake_st.iframe_calls[0]["body"]
    assert "editing-entries:2" in fake_st.iframe_calls[1]["body"]
    assert fake_st.iframe_calls[0]["body"] != fake_st.iframe_calls[1]["body"]


def test_clickable_article_outline_remains_disabled_by_default():
    assert ui_help.CLICKABLE_ARTICLE_OUTLINE is False


def test_help_breadcrumb_uses_registry_metadata():
    assert get_help_breadcrumb("creating-entries") == (
        "Help",
        "Core Workflows",
        "Creating Entries",
    )


def test_adjacent_help_articles_follow_global_order():
    previous_article, next_article = get_adjacent_help_articles("creating-entries")

    assert previous_article.article_id == "understanding-the-main-workspaces"
    assert next_article.article_id == "default-mode-vs-group-chat"
    assert get_adjacent_help_articles("getting-started")[0] is None
    previous_article, next_article = get_adjacent_help_articles(
        "v1-limitations-and-future-boundaries"
    )
    assert previous_article.article_id == "os-compatibility-and-storage-policy"
    assert next_article.article_id == "developer-launch-flags"
    previous_article, next_article = get_adjacent_help_articles("developer-launch-flags")
    assert previous_article.article_id == "v1-limitations-and-future-boundaries"
    assert next_article.article_id == "codebase-architecture"
    previous_article, next_article = get_adjacent_help_articles(
        "platform-support-philosophy"
    )
    assert previous_article.article_id == "layer-boundaries-and-responsibilities"
    assert next_article.article_id == "data-safety-philosophy"
    previous_article, next_article = get_adjacent_help_articles("data-safety-philosophy")
    assert previous_article.article_id == "platform-support-philosophy"
    assert next_article.article_id == "testing-philosophy"
    previous_article, next_article = get_adjacent_help_articles("ui-and-theme-style-guide")
    assert previous_article.article_id == "naming-and-terminology-guide"
    assert next_article.article_id == "build-and-packaging-overview"
    previous_article, next_article = get_adjacent_help_articles(
        "build-and-packaging-overview"
    )
    assert previous_article.article_id == "ui-and-theme-style-guide"
    assert next_article.article_id == "windows-installer-and-launcher-architecture"
    previous_article, next_article = get_adjacent_help_articles("rolethread-studio-vision")
    assert previous_article.article_id == "contribution-guidelines"
    assert next_article.article_id == "lite-vs-studio-boundaries"
    assert get_adjacent_help_articles("lite-vs-studio-boundaries")[1] is None


def test_related_help_articles_follow_registry_metadata():
    related_articles = get_related_help_articles("getting-started")

    assert [article.article_id for article in related_articles] == [
        "understanding-the-main-workspaces",
        "loading-datasets-and-working-copies",
        "creating-entries",
    ]


def test_help_related_ids_are_known_unique_and_not_self_referential():
    registry = get_help_article_registry()

    for article in registry.values():
        assert len(article.related_ids) == len(set(article.related_ids))
        assert article.article_id not in article.related_ids
        assert set(article.related_ids) <= set(registry)


def test_load_help_document_reads_registered_markdown():
    document = load_help_document("getting-started")

    assert document.article.article_id == "getting-started"
    assert document.path.name == "01_getting_started.md"
    assert document.content.startswith("# Getting Started")


def test_search_help_documents_matches_title_summary_and_content(tmp_path):
    help_dir = tmp_path / "help"
    help_dir.mkdir()
    for article in get_help_article_registry().values():
        content = f"# {article.title}\n\nPlain article body."
        if article.article_id == "creating-entries":
            content += "\n\nNeedle content marker."
        (help_dir / article.file_name).write_text(content, encoding="utf-8")

    title_matches = search_help_documents("Exporting Datasets", help_dir)
    deep_edit_matches = search_help_documents("Deep Edit", help_dir)
    summary_matches = search_help_documents("first-session workflow", help_dir)
    content_matches = search_help_documents("needle content", help_dir)

    assert [doc.article.article_id for doc in title_matches] == ["exporting-datasets"]
    assert [doc.article.article_id for doc in deep_edit_matches] == ["editing-entries"]
    assert [doc.article.article_id for doc in summary_matches] == ["getting-started"]
    assert [doc.article.article_id for doc in content_matches] == ["creating-entries"]


def test_build_help_search_results_returns_compact_snippets(tmp_path):
    help_dir = tmp_path / "help"
    help_dir.mkdir()
    for article in get_help_article_registry().values():
        content = f"# {article.title}\n\nPlain article body."
        if article.article_id == "creating-entries":
            content += "\n\nThe hidden marker appears inside this article body."
        (help_dir / article.file_name).write_text(content, encoding="utf-8")

    summary_results = build_help_search_results("first-session workflow", help_dir)
    content_results = build_help_search_results("hidden marker", help_dir)

    assert summary_results[0].article.article_id == "getting-started"
    assert summary_results[0].snippet == "First-session workflow and the basic RoleThread rhythm."
    assert content_results[0].article.article_id == "creating-entries"
    assert "hidden marker" in content_results[0].snippet.lower()


def _markdown_values(app):
    return [markdown.value for markdown in app.markdown]


def _caption_values(app):
    return [caption.value for caption in app.caption]


def test_help_search_open_and_sidebar_clicks_render_selected_articles():
    app = AppTest.from_string(
        "from ui.ui_help import render_help_page\nrender_help_page()\n",
        default_timeout=10,
    ).run()

    app.text_input[0].input("tags").run()
    app.button(key="_help_search_submit").click().run()
    app.button(key="_help_search_tags-categories-and-tag-lifecycle").click().run()

    assert app.session_state[ui_help.HELP_ACTIVE_ARTICLE_KEY] == (
        "tags-categories-and-tag-lifecycle"
    )
    assert any(
        value.startswith("# Tags, Categories, and Tag Lifecycle")
        for value in _markdown_values(app)
    )
    assert any(
        caption.value == "Help / Metadata and Organization / Tags, Categories, and Tag Lifecycle"
        for caption in app.caption
    )

    app.button(key="_help_article_archived-and-imported-tags").click().run()
    assert app.session_state[ui_help.HELP_ACTIVE_ARTICLE_KEY] == "archived-and-imported-tags"
    assert any(
        value.startswith("# Archived and Imported Tags")
        for value in _markdown_values(app)
    )

    app.button(key="_help_article_tags-categories-and-tag-lifecycle").click().run()
    assert app.session_state[ui_help.HELP_ACTIVE_ARTICLE_KEY] == (
        "tags-categories-and-tag-lifecycle"
    )
    assert any(
        value.startswith("# Tags, Categories, and Tag Lifecycle")
        for value in _markdown_values(app)
    )


def test_help_search_open_hides_results_preserves_query_and_can_rerun_same_query():
    app = AppTest.from_string(
        "from ui.ui_help import render_help_page\nrender_help_page()\n",
        default_timeout=10,
    ).run()

    app.text_input[0].input("tag").run()
    app.button(key="_help_search_submit").click().run()
    assert any(
        value.startswith("**Search Results")
        for value in _markdown_values(app)
    )

    app.button(key="_help_search_tags-categories-and-tag-lifecycle").click().run()

    assert app.session_state[ui_help.HELP_ACTIVE_ARTICLE_KEY] == (
        "tags-categories-and-tag-lifecycle"
    )
    assert app.session_state[ui_help.HELP_SEARCH_QUERY_KEY] == "tag"
    assert app.session_state[ui_help.HELP_SEARCH_RESULTS_VISIBLE_KEY] is False
    assert app.text_input[0].value == "tag"
    assert not any(
        value.startswith("**Search Results")
        for value in _markdown_values(app)
    )
    assert any(
        value.startswith("# Tags, Categories, and Tag Lifecycle")
        for value in _markdown_values(app)
    )

    app.button(key="_help_search_submit").click().run()

    assert app.session_state[ui_help.HELP_SEARCH_RESULTS_VISIBLE_KEY] is True
    assert app.text_input[0].value == "tag"
    assert any(
        value.startswith("**Search Results")
        for value in _markdown_values(app)
    )


def test_help_search_clear_clears_query_and_hides_results():
    app = AppTest.from_string(
        "from ui.ui_help import render_help_page\nrender_help_page()\n",
        default_timeout=10,
    ).run()

    app.text_input[0].input("tag").run()
    app.button(key="_help_search_submit").click().run()
    assert any(
        value.startswith("**Search Results")
        for value in _markdown_values(app)
    )

    app.button(key="_help_search_clear").click().run()

    assert app.session_state[ui_help.HELP_SEARCH_QUERY_KEY] == ""
    assert app.session_state[ui_help.HELP_SEARCH_RESULTS_VISIBLE_KEY] is False
    assert app.text_input[0].value == ""
    assert not any(
        value.startswith("**Search Results")
        for value in _markdown_values(app)
    )


def test_help_sidebar_navigation_without_search_renders_selected_article():
    app = AppTest.from_string(
        "from ui.ui_help import render_help_page\nrender_help_page()\n",
        default_timeout=10,
    ).run()

    app.button(key="_help_article_exporting-datasets").click().run()

    assert app.session_state[ui_help.HELP_ACTIVE_ARTICLE_KEY] == "exporting-datasets"
    assert any(
        value.startswith("# Exporting Datasets")
        for value in _markdown_values(app)
    )
    assert any(
        caption == "Help / Output and Recovery / Exporting Datasets"
        for caption in _caption_values(app)
    )


def test_help_related_previous_and_next_buttons_render_selected_articles():
    app = AppTest.from_string(
        "from ui.ui_help import render_help_page\nrender_help_page()\n",
        default_timeout=10,
    ).run()

    app.button(key="_help_related_creating-entries").click().run()
    assert app.session_state[ui_help.HELP_ACTIVE_ARTICLE_KEY] == "creating-entries"
    assert any(
        value.startswith("# Creating Entries")
        for value in _markdown_values(app)
    )

    app.button(key="_help_previous_understanding-the-main-workspaces").click().run()
    assert app.session_state[ui_help.HELP_ACTIVE_ARTICLE_KEY] == (
        "understanding-the-main-workspaces"
    )
    assert any(
        value.startswith("# Understanding the Main Workspaces")
        for value in _markdown_values(app)
    )

    app.button(key="_help_next_creating-entries").click().run()
    assert app.session_state[ui_help.HELP_ACTIVE_ARTICLE_KEY] == "creating-entries"
    assert any(
        value.startswith("# Creating Entries")
        for value in _markdown_values(app)
    )


def test_slugify_heading_normalizes_punctuation_and_spacing():
    assert slugify_heading("Clean Export: JSONL & Sidecars!") == "clean-export-jsonl-sidecars"
    assert slugify_heading("  `System Prompt` Template  ") == "system-prompt-template"


def test_slugify_heading_matches_expected_streamlit_style_examples():
    assert slugify_heading("The Short Version") == "the-short-version"
    assert slugify_heading("Included Example Datasets") == "included-example-datasets"
    assert (
        slugify_heading("Writing Effective Narrative Training Data")
        == "writing-effective-narrative-training-data"
    )
    assert (
        slugify_heading("Narrative-Heavy vs Dialogue-Heavy")
        == "narrative-heavy-vs-dialogue-heavy"
    )


def test_extract_markdown_sections_reads_level_two_and_three_headings():
    sections = extract_markdown_sections(
        "# Article Title\n\n"
        "## First Section\n\n"
        "### Nested Section\n\n"
        "#### Too Deep\n\n"
        "## Second Section\n"
    )

    assert [(section.level, section.title, section.anchor) for section in sections] == [
        (2, "First Section", "first-section"),
        (3, "Nested Section", "nested-section"),
        (2, "Second Section", "second-section"),
    ]


def test_extract_markdown_sections_ignores_code_fence_headings():
    sections = extract_markdown_sections(
        "## Real Section\n\n"
        "```markdown\n"
        "## Not A Section\n"
        "```\n"
        "~~~\n"
        "### Also Ignored\n"
        "~~~\n"
        "### Real Subsection\n"
    )

    assert [section.title for section in sections] == [
        "Real Section",
        "Real Subsection",
    ]


def test_extract_markdown_sections_deduplicates_anchors():
    sections = extract_markdown_sections(
        "## Repeat\n"
        "### Repeat\n"
        "## Repeat!\n"
    )

    assert [section.anchor for section in sections] == [
        "repeat",
        "repeat-2",
        "repeat-3",
    ]


def test_extract_markdown_sections_returns_empty_for_no_sections():
    assert extract_markdown_sections("# Only Title\n\nPlain text.") == ()


def test_format_section_outline_supports_informational_and_clickable_lines():
    sections = extract_markdown_sections("## Parent\n### Child")

    assert format_section_outline(sections) == (
        "- Parent",
        "  - Child",
    )
    assert format_section_outline(sections, clickable=True) == (
        "- [Parent](#parent)",
        "  - [Child](#child)",
    )


def test_load_faq_entries_reads_json(tmp_path):
    (tmp_path / "faq.json").write_text(
        json.dumps([
            {"question": "Tags and metadata: What is this?", "answer": "A FAQ."},
            {"question": "", "answer": "Skipped."},
        ]),
        encoding="utf-8",
    )

    entries = load_faq_entries(tmp_path)

    assert entries == (
        FAQEntry(
            question="Tags and metadata: What is this?",
            answer="A FAQ.",
            category="Metadata and Characters",
            source_prefix="Tags and metadata",
            related_help_ids=("tags-categories-and-tag-lifecycle",),
        ),
    )
    assert entries[0].display_question == "What is this?"


def test_faq_category_derivation_maps_legacy_prefixes_to_browser_categories():
    assert derive_faq_category("Getting started: What is Lite?") == "Getting Started"
    assert derive_faq_category("Dataset craftsmanship: Why split?") == (
        "Workflow and Editing"
    )
    assert derive_faq_category("Group Chat and characters: Why mappings?") == (
        "Metadata and Characters"
    )
    assert derive_faq_category("Export and training: What is clean export?") == (
        "Validation, Export, and Training"
    )
    assert derive_faq_category("Lite boundaries: Why local-first?") == (
        "Safety, Backups, and Boundaries"
    )


def test_faq_entries_group_into_clean_sidebar_categories():
    entries = load_faq_entries()
    grouped = get_faq_entries_by_category(entries)

    assert tuple(grouped) == get_faq_category_order()
    assert sum(len(group) for group in grouped.values()) == len(entries)
    assert all(entry.category in get_faq_category_order() for entry in entries)
    assert all(grouped[category] for category in get_faq_category_order())


def test_faq_category_descriptions_are_available_for_reader_polish():
    for category in get_faq_category_order():
        assert get_faq_category_description(category)


def test_faq_related_help_ids_are_known_and_lightweight():
    entries = load_faq_entries()
    help_article_ids = set(get_help_article_registry())

    assert all(set(entry.related_help_ids) <= help_article_ids for entry in entries)
    assert all(len(entry.related_help_ids) <= 3 for entry in entries)
    assert derive_related_help_ids(
        "Working copies and sidecars: Why did RoleThread create a working copy?"
    ) == (
        "loading-datasets-and-working-copies",
        "sidecars-and-portable-metadata",
    )
    assert derive_related_help_ids(
        "Workflow philosophy: Why isn't Deep Edit the primary editing workspace?"
    ) == (
        "understanding-the-main-workspaces",
        "editing-entries",
    )
    assert derive_related_help_ids(
        "Lite boundaries: Why separate Lite and Studio ideas?"
    ) == (
        "v1-limitations-and-future-boundaries",
        "rolethread-studio-vision",
    )


def test_filter_faq_entries_matches_question_and_answer():
    entries = (
        FAQEntry(question="What is Lite?", answer="A local-first app."),
        FAQEntry(
            question="How do I export?",
            answer="Use the Export page.",
            category="Validation, Export, and Training",
        ),
    )

    assert filter_faq_entries(entries, "export") == (entries[1],)
    assert filter_faq_entries(entries, "local") == (entries[0],)
    assert filter_faq_entries(entries, "training") == (entries[1],)
    assert filter_faq_entries(entries, "") == entries


def test_active_faq_category_repairs_invalid_state(monkeypatch):
    fake = FakeFAQStreamlit()
    fake.session_state[ui_faq.FAQ_ACTIVE_CATEGORY_KEY] = "Missing"
    monkeypatch.setattr(ui_faq, "st", fake)

    assert ui_faq.get_active_faq_category() == "Getting Started"
    assert fake.session_state[ui_faq.FAQ_ACTIVE_CATEGORY_KEY] == "Getting Started"


def test_select_faq_category_hides_search_results_and_reruns(monkeypatch):
    fake = FakeFAQStreamlit()
    fake.session_state[ui_faq.FAQ_SEARCH_QUERY_KEY] = "tag"
    fake.session_state[ui_faq.FAQ_SEARCH_RESULTS_VISIBLE_KEY] = True
    monkeypatch.setattr(ui_faq, "st", fake)

    category = ui_faq.select_faq_category(
        "Metadata and Characters",
        rerun=False,
    )

    assert category == "Metadata and Characters"
    assert fake.session_state[ui_faq.FAQ_ACTIVE_CATEGORY_KEY] == (
        "Metadata and Characters"
    )
    assert fake.session_state[ui_faq.FAQ_SEARCH_QUERY_KEY] == "tag"
    assert fake.session_state[ui_faq.FAQ_SEARCH_RESULTS_VISIBLE_KEY] is False


def test_open_related_help_article_uses_help_selection_and_page_navigation(monkeypatch):
    selected_articles = []
    navigated_pages = []

    def fake_select_help_article(article_id, *, rerun=True):
        selected_articles.append((article_id, rerun))
        return article_id

    def fake_navigate_to_page(page_id, *, rerun=True):
        navigated_pages.append((page_id, rerun))
        return page_id

    monkeypatch.setattr(ui_faq, "select_help_article", fake_select_help_article)
    monkeypatch.setattr(ui_faq, "navigate_to_page", fake_navigate_to_page)

    selected_id = ui_faq.open_related_help_article("validation-and-repair")

    assert selected_id == "validation-and-repair"
    assert selected_articles == [("validation-and-repair", False)]
    assert navigated_pages == [("Help", True)]


def test_faq_sidebar_category_and_search_controls_render_browser_state():
    app = AppTest.from_string(
        "from ui.ui_faq import render_faq_page\nrender_faq_page()\n",
        default_timeout=10,
    ).run()

    assert app.session_state[ui_faq.FAQ_ACTIVE_CATEGORY_KEY] == "Getting Started"
    assert any(value == "### Getting Started" for value in _markdown_values(app))

    app.button(key="_faq_category_Metadata and Characters").click().run()

    assert app.session_state[ui_faq.FAQ_ACTIVE_CATEGORY_KEY] == (
        "Metadata and Characters"
    )
    assert any(value == "### Metadata and Characters" for value in _markdown_values(app))

    app.text_input[0].input("sidecar").run()
    app.button(key="_faq_search_submit").click().run()

    assert app.session_state[ui_faq.FAQ_SEARCH_QUERY_KEY] == "sidecar"
    assert app.session_state[ui_faq.FAQ_SEARCH_RESULTS_VISIBLE_KEY] is True
    assert any(
        value.startswith("**Search Results")
        for value in _markdown_values(app)
    )

    app.button(key="_faq_search_submit").click().run()
    assert app.session_state[ui_faq.FAQ_SEARCH_RESULTS_VISIBLE_KEY] is True

    app.button(key="_faq_search_clear").click().run()

    assert app.session_state[ui_faq.FAQ_SEARCH_QUERY_KEY] == ""
    assert app.session_state[ui_faq.FAQ_SEARCH_RESULTS_VISIBLE_KEY] is False


