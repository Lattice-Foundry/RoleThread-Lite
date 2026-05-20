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

    assert len(registry) == 59
    assert get_default_help_article_id() == "installing-rolethread-lite"
    assert registry["installing-rolethread-lite"].file_name == (
        "00_installing_rolethread_lite.md"
    )
    assert registry["installing-rolethread-lite"].category == "Getting Started"
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
    assert registry["what-rolethread-is-actually-for"].file_name == (
        "41_what_rolethread_is_actually_for.md"
    )
    assert (
        registry["what-rolethread-is-actually-for"].category
        == "AI Training Fundamentals"
    )
    assert registry["what-fine-tuning-actually-is"].file_name == (
        "42_what_fine_tuning_actually_is.md"
    )
    assert registry["lora-vs-prompting-vs-fine-tuning"].file_name == (
        "43_lora_vs_prompting_vs_fine_tuning.md"
    )
    assert registry["why-dataset-quality-matters"].file_name == (
        "44_why_dataset_quality_matters.md"
    )
    assert registry["privacy-and-local-first-creative-workflows"].file_name == (
        "45_privacy_and_local_first_creative_workflows.md"
    )
    assert registry["what-makes-a-good-roleplay-dataset"].file_name == (
        "46_what_makes_a_good_roleplay_dataset.md"
    )
    assert registry["common-dataset-mistakes"].file_name == (
        "47_common_dataset_mistakes.md"
    )
    assert registry["dialogue-vs-narration-balance"].file_name == (
        "48_dialogue_vs_narration_balance.md"
    )
    assert registry["character-consistency-and-drift"].file_name == (
        "49_character_consistency_and_drift.md"
    )
    assert registry["ai-assisted-dataset-creation-workflow"].file_name == (
        "50_ai_assisted_dataset_creation_workflow.md"
    )
    assert registry["why-validation-matters"].file_name == (
        "51_why_validation_matters.md"
    )
    assert registry["preparing-datasets-for-lora-and-fine-tuning"].file_name == (
        "52_preparing_datasets_for_lora_and_fine_tuning.md"
    )
    assert registry["synthetic-data-vs-human-written-data"].file_name == (
        "53_synthetic_data_vs_human_written_data.md"
    )
    assert registry["dataset-scaling-and-maintenance"].file_name == (
        "54_dataset_scaling_and_maintenance.md"
    )
    assert registry["roleplay-archetypes-and-behavioral-bias"].file_name == (
        "55_roleplay_archetypes_and_behavioral_bias.md"
    )
    assert registry["realistic-expectations-for-fine-tuning"].file_name == (
        "56_realistic_expectations_for_fine_tuning.md"
    )
    assert (
        registry["creator-ownership-and-long-term-workflow-philosophy"].file_name
        == "57_creator_ownership_and_long_term_workflow_philosophy.md"
    )
    assert registry["planned-for-version-2"].file_name == (
        "58_planned_for_version_2.md"
    )
    assert registry["planned-for-version-2"].category == "Reference"
    assert registry["data-generation-beta"].file_name == "40_data_generation_beta.md"
    assert registry["data-generation-beta"].category == "Data Generation"
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
    assert document.article.category == "For Developers"
    assert "python -m litlaunch.cli run --profile rolethread-webapp" in document.content
    assert "python -m litlaunch.cli inspect --profile rolethread-webapp" in document.content
    assert "streamlit run app.py" in document.content
    assert "`dev`" in document.content
    assert "Launch Flags Detected" in document.content
    assert "Diagnostics are gated behind `dev`" not in document.content
    assert "custom `webapp` argument" in document.content


def test_public_help_docs_do_not_reference_removed_webapp_flows():
    obsolete_terms = (
        "streamlit run app.py -- webapp",
        "edge-debug",
        "webapp-debug",
        "Reset Webapp Browser State",
        "Use Windows Edge webapp mode by default",
        "app-owned",
    )

    for article in get_help_article_registry().values():
        if article.category == "For Developers":
            continue
        document = load_help_document(article.article_id)
        for term in obsolete_terms:
            assert term not in document.content, article.article_id


def test_installing_rolethread_lite_help_article_documents_install_and_uninstall():
    document = load_help_document("installing-rolethread-lite")

    assert document.article.title == "Installing RoleThread Lite"
    assert "Windows setup executable is a beta convenience path" in document.content
    assert "python -m litlaunch.cli run --profile rolethread-webapp" in document.content
    assert "Users do not choose a runtime mode during setup" in document.content
    assert "Use Windows Edge webapp mode" not in document.content
    assert "Linux uses the source/manual workflow" in document.content
    assert "macOS is beta/manual for V1" in document.content
    assert "Start Menu > RoleThread Lite > **RoleThread Uninstaller**" in (
        document.content
    )
    assert "default Windows uninstall path removes installed app/runtime files" not in (
        document.content
    )
    assert "Cloud backup copies and external sync folders" in document.content
    assert "minimize other windows or\ncheck the taskbar" in document.content


def test_os_compatibility_help_article_documents_v1_policy():
    document = load_help_document("os-compatibility-and-storage-policy")

    assert "Windows is a primary V1 support platform" in document.content
    assert "Linux is a primary V1 support platform" in document.content
    assert "macOS is beta-supported for V1" in document.content
    assert "Python 3.14.5" in document.content
    assert "%LOCALAPPDATA%\\RoleThread" in document.content
    assert "~/.local/share/rolethread" in document.content
    assert "~/Library/Application Support/RoleThread" in document.content
    assert "managed Microsoft Edge app window" in document.content
    assert "python -m litlaunch.cli inspect --profile rolethread-webapp" in document.content
    assert "streamlit run app.py -- webapp" not in document.content
    assert "For setup commands and uninstall instructions" in document.content
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


def test_planned_for_version_2_documents_roadmap_direction_without_promises():
    document = load_help_document("planned-for-version-2")

    assert document.article.category == "Reference"
    assert "not a release commitment, feature\nguarantee, or date promise" in (
        document.content
    )
    assert "additional browser adapters" in document.content
    assert "Edge to Chrome to Chromium fallback behavior" in document.content
    assert "improved Linux compatibility" in document.content
    assert "macOS beta refinement" in document.content
    assert "additional generation templates" in document.content
    assert "model-tailored generation guidance" in document.content
    assert "pacing and repetition heuristics" in document.content
    assert "in-app backup browsing" in document.content
    assert "dataset restore workflows" in document.content
    assert "optional cloud-backup recovery" in document.content
    assert "full\nGit-like version control" in document.content
    assert "Validation should remain guidance-oriented" in document.content
    assert "loopback-only managed runtime posture" in document.content
    assert "future launcher-managed update workflow is possible" in document.content
    assert "LatticeFoundry infrastructure" in document.content
    assert "hosted inference" in document.content
    assert "mandatory cloud workflow" in document.content
    assert "telemetry-heavy product" in document.content
    assert "Electron rewrite" in document.content
    assert "cloud-dependent AI operating system" in document.content


def test_data_generation_beta_help_article_documents_public_positioning():
    document = load_help_document("data-generation-beta")

    assert document.article.title == "Data Generation (Beta)"
    assert document.article.category == "Data Generation"
    assert "RoleThread Lite does not call an AI provider" in document.content
    assert "deterministic prompt compiler" in document.content
    assert "DB-backed prompt chunks" in document.content
    assert "conditional style, tone, system prompt, and output-delivery instructions" in (
        document.content
    )
    assert "ChatML JSONL" in document.content
    assert "provider-agnostic" in document.content
    assert "The beta label reflects" in document.content
    assert "not mean the application architecture is unstable" in document.content
    assert "Future RoleThread Studio work" in document.content


def test_ai_training_fundamentals_articles_document_rolethread_purpose():
    purpose = load_help_document("what-rolethread-is-actually-for")
    fine_tuning = load_help_document("what-fine-tuning-actually-is")
    comparison = load_help_document("lora-vs-prompting-vs-fine-tuning")
    quality = load_help_document("why-dataset-quality-matters")
    privacy = load_help_document("privacy-and-local-first-creative-workflows")

    assert purpose.article.category == "AI Training Fundamentals"
    assert "Use powerful AI models to scaffold the first 80%" in purpose.content
    assert "RoleThread Lite is dataset infrastructure" in purpose.content
    assert "not a hosted AI platform" in purpose.content
    assert "external LoRA or fine-tuning workflows" in purpose.content

    assert fine_tuning.article.category == "AI Training Fundamentals"
    assert "base model" in fine_tuning.content
    assert "not about making a model memorize exact scripts" in fine_tuning.content
    assert "shape tendencies" in fine_tuning.content
    assert "conversational structure" in fine_tuning.content

    assert comparison.article.category == "AI Training Fundamentals"
    assert "Prompting is temporary runtime guidance" in comparison.content
    assert "Character cards are structured runtime steering" in comparison.content
    assert "RAG means retrieval-augmented generation" in comparison.content
    assert "LoRA stands for low-rank adaptation" in comparison.content
    assert "Fine-tuning is deeper model adaptation" in comparison.content

    assert quality.article.category == "AI Training Fundamentals"
    assert "Training data is instruction by example" in quality.content
    assert "malformed JSONL" in quality.content
    assert "duplicated entries" in quality.content
    assert "Roleplay and narrative datasets" in quality.content
    assert "Validation is not there to scold the dataset" in quality.content

    assert privacy.article.category == "AI Training Fundamentals"
    assert "Creative AI workflows are often deeply personal" in privacy.content
    assert "adult fictional themes" in privacy.content
    assert "some work belongs on the creator's machine" in privacy.content
    assert "There is no hosted inference requirement" in privacy.content
    assert "privacy, autonomy, and local control" in privacy.content
    assert "direct file ownership" in privacy.content


def test_ai_training_fundamentals_articles_document_roleplay_dataset_craft():
    roleplay = load_help_document("what-makes-a-good-roleplay-dataset")
    mistakes = load_help_document("common-dataset-mistakes")
    balance = load_help_document("dialogue-vs-narration-balance")
    consistency = load_help_document("character-consistency-and-drift")
    workflow = load_help_document("ai-assisted-dataset-creation-workflow")
    validation = load_help_document("why-validation-matters")

    assert roleplay.article.category == "AI Training Fundamentals"
    assert "Repetition Becomes Behavior" in roleplay.content
    assert "Conversational rhythm matters" in roleplay.content
    assert "Weak assistant responses reduce output quality" in roleplay.content
    assert "high-quality datasets are curated intentionally" in roleplay.content
    assert "It is shaped" in roleplay.content

    assert mistakes.article.category == "AI Training Fundamentals"
    assert "More data does not automatically mean better data" in mistakes.content
    assert "malformed role order" in mistakes.content
    assert "Excessive Greeting Data" in mistakes.content
    assert "AI-generated examples can be useful scaffolding" in mistakes.content

    assert balance.article.category == "AI Training Fundamentals"
    assert "There is no single correct style" in balance.content
    assert "Dialogue-heavy datasets" in balance.content
    assert "Prose-heavy datasets" in balance.content
    assert "Emotionally dense conversational roleplay" in balance.content

    assert consistency.article.category == "AI Training Fundamentals"
    assert "dataset behavior shaping" in consistency.content
    assert "Models reinforce repeated behavioral patterns" in consistency.content
    assert "Tone drift is common in generated data" in consistency.content
    assert "Quirks are easy to overtrain" in consistency.content

    assert workflow.article.category == "AI Training Fundamentals"
    assert "Generate baseline examples with powerful AI models" in workflow.content
    assert "Remove repetitive or weak generations" in workflow.content
    assert "RoleThread is refinement infrastructure" in workflow.content
    assert "human judgment" in workflow.content
    assert "Generated data can look polished while still teaching poor habits" in (
        workflow.content
    )

    assert validation.article.category == "AI Training Fundamentals"
    assert "Validation protects conversational structure" in validation.content
    assert "malformed exchanges" in validation.content
    assert "Conversational integrity" in validation.content
    assert "Editing raw JSONL by hand is possible" in validation.content


def test_ai_training_fundamentals_articles_document_training_readiness():
    preparation = load_help_document("preparing-datasets-for-lora-and-fine-tuning")
    synthetic = load_help_document("synthetic-data-vs-human-written-data")
    scaling = load_help_document("dataset-scaling-and-maintenance")
    bias = load_help_document("roleplay-archetypes-and-behavioral-bias")
    expectations = load_help_document("realistic-expectations-for-fine-tuning")
    ownership = load_help_document(
        "creator-ownership-and-long-term-workflow-philosophy"
    )

    assert preparation.article.category == "AI Training Fundamentals"
    assert "Training readiness is a workflow" in preparation.content
    assert "Balance Examples" in preparation.content
    assert "iterative dataset engineering" in preparation.content
    assert "Avoid Garbage Amplification" in preparation.content

    assert synthetic.article.category == "AI Training Fundamentals"
    assert "It is a force multiplier, not a replacement for curation" in (
        synthetic.content
    )
    assert "flattened emotional nuance" in synthetic.content
    assert "synthetic flaws" in synthetic.content
    assert "Human editing is often where conversational quality emerges" in (
        synthetic.content
    )

    assert scaling.article.category == "AI Training Fundamentals"
    assert "iterative dataset engineering" in scaling.content
    assert "style drift" in scaling.content
    assert "Merge validation matters" in scaling.content
    assert "Range is intentional variation" in scaling.content

    assert bias.article.category == "AI Training Fundamentals"
    assert "Models inherit dataset blind spots" in bias.content
    assert "excessive verbosity" in bias.content
    assert "weak conversational initiative" in bias.content
    assert "Datasets reinforce behavioral tendencies" in bias.content

    assert expectations.article.category == "AI Training Fundamentals"
    assert "Fine-tuning is powerful, but it is not magic" in expectations.content
    assert "LoRAs are lightweight adaptation layers" in expectations.content
    assert "Tuning rarely succeeds perfectly on the first attempt" in (
        expectations.content
    )
    assert "Behavior shaping is usually gradual" in expectations.content

    assert ownership.article.category == "AI Training Fundamentals"
    assert "creators should control their own datasets" in ownership.content
    assert "Local-first infrastructure exists because ownership and privacy" in (
        ownership.content
    )
    assert "Portability keeps the creator in control" in ownership.content
    assert "Creator autonomy is not an extra feature" in ownership.content


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
    assert "bundled Python runtime" in packaging.content
    assert "bundled Streamlit runtime" in packaging.content
    assert "Inno Setup" in packaging.content
    assert "Inno Setup installer prototype" in packaging.content
    assert "There is no installer runtime-mode selector" in packaging.content
    assert "check the taskbar for the RoleThread Lite installer" in packaging.content
    assert "through Settings" not in packaging.content
    assert "Normal uninstall preserves RoleThread user data by default" in (
        packaging.content
    )
    assert "Start Menu **RoleThread\nUninstaller** shortcut" in packaging.content
    assert "Rerunning the setup executable" in packaging.content
    assert "rebuilds the PyInstaller bundle by default" in packaging.content
    assert "refuses to build the setup executable" in packaging.content
    assert "they differ" in packaging.content
    assert "running old app code" in packaging.content
    assert "Cloud backup copies outside those local RoleThread folders are preserved" in (
        packaging.content
    )
    assert "GitHub Releases" in packaging.content
    assert "requirements-dev.txt" in packaging.content
    assert "Generated artifacts do not belong in Git" in packaging.content
    assert "build_installer.ps1" in packaging.content
    assert "build_bundle.ps1" in packaging.content
    assert "do not edit installer or launcher" in packaging.content

    assert launcher.article.category == "For Developers"
    assert "packaged adapter" in launcher.content
    assert "LitLaunch owns the desktop/webapp lifecycle" in launcher.content
    assert "The installer no longer offers a runtime-mode selector" in launcher.content
    assert "Use Windows Edge webapp mode by default (recommended)" not in launcher.content
    assert "`enable_webapp_launch_mode`" not in launcher.content
    assert "DB-backed setting" not in launcher.content
    assert "Default uninstall" in launcher.content
    assert "installed app files and shortcuts" in launcher.content
    assert "Start Menu **RoleThread\nUninstaller** shortcut" in launcher.content
    assert "not expected to show the uninstall data-removal" in launcher.content
    assert "prompts" in launcher.content
    assert "rebuild the PyInstaller bundle by default" in launcher.content
    assert "prevents a setup executable from accidentally shipping stale" in launcher.content
    assert "Developer clean uninstall" not in launcher.content
    assert "Cloud backup copies outside the local RoleThread folders are preserved" in (
        launcher.content
    )
    assert "`RoleThreadLauncher.exe` is still running" in launcher.content
    assert "windowed/no-console" in launcher.content
    assert "`/_stcore/health`" in launcher.content
    assert "launcher-managed environment marker" not in launcher.content
    assert "Edge process IDs are not a reliable app-window abstraction" in launcher.content
    assert "Health means the backend is ready to accept traffic" in launcher.content
    assert "Successful relaunch is also a practical validation signal" in launcher.content
    assert "Settings > Experimental Features" not in launcher.content


def test_developer_docs_do_not_reference_removed_launcher_flows():
    contribution = load_help_document("contribution-guidelines")
    boundaries = load_help_document("lite-vs-studio-boundaries")
    obsolete_terms = (
        "streamlit run app.py -- webapp",
        "edge-debug",
        "webapp-debug",
        "Reset Webapp Browser State",
        "Use Windows Edge webapp mode by default",
        "`enable_webapp_launch_mode`",
        "app-owned browser",
        "duplicate browser cleanup",
        "installer option during setup",
    )

    for article in get_help_article_registry().values():
        if article.category != "For Developers":
            continue
        document = load_help_document(article.article_id)
        for term in obsolete_terms:
            assert term not in document.content, article.article_id

    assert contribution.article.category == "For Developers"
    assert "small, testable" in contribution.content
    assert "Keep durable business logic out of the UI layer" in contribution.content
    assert "`core/` and `services/` should remain framework-independent" in (
        contribution.content
    )
    assert "Changes that affect behavior should usually include tests" in (
        contribution.content
    )
    assert "Most contributors should not need to edit installer or launcher internals" in (
        contribution.content
    )
    assert "build_installer.ps1" in contribution.content
    assert "casual edits can break installed-app lifecycle" in contribution.content

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

    assert ordered_ids[0] == "installing-rolethread-lite"
    assert ordered_ids[1] == "getting-started"
    assert ordered_ids[-1] == "lite-vs-studio-boundaries"
    assert ordered_ids.index("creating-a-new-dataset") < ordered_ids.index(
        "what-rolethread-is-actually-for"
    )
    assert ordered_ids.index("privacy-and-local-first-creative-workflows") < (
        ordered_ids.index("what-makes-a-good-roleplay-dataset")
    )
    assert ordered_ids.index("creator-ownership-and-long-term-workflow-philosophy") < (
        ordered_ids.index("understanding-the-main-workspaces")
    )
    assert ordered_ids.index("creating-entries") < ordered_ids.index("editing-entries")
    assert ordered_ids.index("splitting-and-joining-entries") < ordered_ids.index(
        "data-generation-beta"
    )
    assert ordered_ids.index("data-generation-beta") < ordered_ids.index(
        "tags-categories-and-tag-lifecycle"
    )
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
        "installing-rolethread-lite",
        "getting-started",
        "what-rolethread-lite-does",
        "dataset-formats",
        "loading-datasets-and-working-copies",
        "creating-a-new-dataset",
    ]
    assert [
        article.article_id
        for article in grouped["AI Training Fundamentals"]
    ] == [
        "what-rolethread-is-actually-for",
        "what-fine-tuning-actually-is",
        "lora-vs-prompting-vs-fine-tuning",
        "why-dataset-quality-matters",
        "privacy-and-local-first-creative-workflows",
        "what-makes-a-good-roleplay-dataset",
        "common-dataset-mistakes",
        "dialogue-vs-narration-balance",
        "character-consistency-and-drift",
        "ai-assisted-dataset-creation-workflow",
        "why-validation-matters",
        "preparing-datasets-for-lora-and-fine-tuning",
        "synthetic-data-vs-human-written-data",
        "dataset-scaling-and-maintenance",
        "roleplay-archetypes-and-behavioral-bias",
        "realistic-expectations-for-fine-tuning",
        "creator-ownership-and-long-term-workflow-philosophy",
    ]
    assert [article.article_id for article in grouped["Data Generation"]] == [
        "data-generation-beta",
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
        "planned-for-version-2",
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
    assert resolve_help_article_id(None) == "installing-rolethread-lite"
    assert resolve_help_article_id("missing") == "installing-rolethread-lite"
    assert get_help_article("missing").article_id == "installing-rolethread-lite"
    assert get_help_article("exporting-datasets").title == "Exporting Datasets"


def test_active_help_article_uses_session_state_and_repairs_invalid_state(monkeypatch):
    fake = FakeHelpStreamlit()
    fake.session_state[ui_help.HELP_ACTIVE_ARTICLE_KEY] = "exporting-datasets"
    monkeypatch.setattr(ui_help, "st", fake)

    assert ui_help.get_active_help_article_id() == "exporting-datasets"
    assert fake.session_state[ui_help.HELP_ACTIVE_ARTICLE_KEY] == "exporting-datasets"

    fake.session_state[ui_help.HELP_ACTIVE_ARTICLE_KEY] = "unknown-article"
    assert ui_help.get_active_help_article_id() == "installing-rolethread-lite"
    assert fake.session_state[ui_help.HELP_ACTIVE_ARTICLE_KEY] == (
        "installing-rolethread-lite"
    )


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

    assert ui_help.select_help_article("unknown-article", rerun=False) == (
        "installing-rolethread-lite"
    )
    assert fake.session_state[ui_help.HELP_ACTIVE_ARTICLE_KEY] == (
        "installing-rolethread-lite"
    )


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
    assert get_adjacent_help_articles("installing-rolethread-lite")[0] is None
    previous_article, next_article = get_adjacent_help_articles("getting-started")
    assert previous_article.article_id == "installing-rolethread-lite"
    assert next_article.article_id == "what-rolethread-lite-does"
    previous_article, next_article = get_adjacent_help_articles(
        "v1-limitations-and-future-boundaries"
    )
    assert previous_article.article_id == "os-compatibility-and-storage-policy"
    assert next_article.article_id == "planned-for-version-2"
    previous_article, next_article = get_adjacent_help_articles(
        "planned-for-version-2"
    )
    assert previous_article.article_id == "v1-limitations-and-future-boundaries"
    assert next_article.article_id == "developer-launch-flags"
    previous_article, next_article = get_adjacent_help_articles("developer-launch-flags")
    assert previous_article.article_id == "planned-for-version-2"
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
        "what-rolethread-lite-does",
        "dataset-formats",
        "loading-datasets-and-working-copies",
        "understanding-the-main-workspaces",
    ]


def test_public_help_articles_do_not_keep_temporary_related_sections():
    for article in get_help_article_registry().values():
        document = load_help_document(article.article_id)
        if article.category == "For Developers":
            continue

        assert "## Related Articles" not in document.content


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

    app.button(key="_help_related_getting-started").click().run()
    assert app.session_state[ui_help.HELP_ACTIVE_ARTICLE_KEY] == "getting-started"
    assert any(
        value.startswith("# Getting Started")
        for value in _markdown_values(app)
    )

    app.button(key="_help_related_loading-datasets-and-working-copies").click().run()
    assert app.session_state[ui_help.HELP_ACTIVE_ARTICLE_KEY] == (
        "loading-datasets-and-working-copies"
    )
    assert any(
        value.startswith("# Loading Datasets and Working Copies")
        for value in _markdown_values(app)
    )

    app.button(key="_help_previous_dataset-formats").click().run()
    assert app.session_state[ui_help.HELP_ACTIVE_ARTICLE_KEY] == (
        "dataset-formats"
    )
    assert any(
        value.startswith("# Dataset Formats")
        for value in _markdown_values(app)
    )

    app.button(key="_help_next_loading-datasets-and-working-copies").click().run()
    assert app.session_state[ui_help.HELP_ACTIVE_ARTICLE_KEY] == (
        "loading-datasets-and-working-copies"
    )
    assert any(
        value.startswith("# Loading Datasets and Working Copies")
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
            category="Tags and Validation",
            source_prefix="Tags and metadata",
            related_help_ids=("tags-categories-and-tag-lifecycle",),
        ),
    )
    assert entries[0].display_question == "What is this?"


def test_faq_category_derivation_maps_legacy_prefixes_to_browser_categories():
    assert derive_faq_category("Getting started: What is Lite?") == "Getting Started"
    assert derive_faq_category("Dataset craftsmanship: Why split?") == (
        "AI Training Fundamentals"
    )
    assert derive_faq_category("Group Chat and characters: Why mappings?") == (
        "Tags and Validation"
    )
    assert derive_faq_category("Export and training: What is clean export?") == (
        "Import, Export, and Training Files"
    )
    assert derive_faq_category("Lite boundaries: Why local-first?") == (
        "Privacy and Local Workflows"
    )
    assert derive_faq_category("Installation and launching: How do I launch?") == (
        "Installation and Launching"
    )


def test_faq_entries_group_into_clean_sidebar_categories():
    entries = load_faq_entries()
    grouped = get_faq_entries_by_category(entries)

    assert tuple(grouped) == get_faq_category_order()
    assert sum(len(group) for group in grouped.values()) == len(entries)
    assert all(entry.category in get_faq_category_order() for entry in entries)
    assert all(grouped[category] for category in get_faq_category_order())
    assert max(len(group) for group in grouped.values()) < len(entries) * 0.25
    assert any(
        entry.display_question == "How do I launch RoleThread Lite from source?"
        and "python -m litlaunch.cli run --profile rolethread-webapp" in entry.answer
        and "installing-rolethread-lite" in entry.related_help_ids
        for entry in entries
    )
    assert any(
        entry.display_question == "Is RoleThread Lite exposed to my network?"
        and "`127.0.0.1`" in entry.answer
        and "os-compatibility-and-storage-policy" in entry.related_help_ids
        for entry in entries
    )
    assert any(
        entry.display_question == "How do I run launcher diagnostics?"
        and "litlaunch.cli inspect --profile rolethread-webapp" in entry.answer
        for entry in entries
    )
    assert any(
        "native-style webapp launcher with a compiled installer" in entry.question
        and "science reasons" in entry.answer
        for entry in entries
    )
    assert any(
        entry.display_question == "Does RoleThread generate AI responses directly?"
        and "data-generation-beta" in entry.related_help_ids
        for entry in entries
    )
    assert any(
        entry.display_question == "Why is Data Generation marked beta?"
        and "prompt refinement" in entry.answer
        for entry in entries
    )
    assert any(
        entry.display_question == "What is the 80/20 workflow?"
        and "first 80%" in entry.answer
        and "what-rolethread-is-actually-for" in entry.related_help_ids
        for entry in entries
    )
    assert any(
        entry.display_question == "Why keep creative training datasets local?"
        and "privacy-and-local-first-creative-workflows" in entry.related_help_ids
        for entry in entries
    )
    assert any(
        entry.display_question == "What makes a good roleplay dataset?"
        and "what-makes-a-good-roleplay-dataset" in entry.related_help_ids
        for entry in entries
    )
    assert any(
        entry.display_question == "Why not keep every synthetic generation?"
        and "ai-assisted-dataset-creation-workflow" in entry.related_help_ids
        for entry in entries
    )
    assert any(
        entry.display_question == "Why do characters drift during roleplay?"
        and "character-consistency-and-drift" in entry.related_help_ids
        for entry in entries
    )
    assert any(
        entry.display_question == "How do I prepare a dataset for LoRA or fine-tuning?"
        and "preparing-datasets-for-lora-and-fine-tuning" in entry.related_help_ids
        for entry in entries
    )
    assert any(
        entry.display_question == "Is synthetic data worse than human-written data?"
        and "force multiplier" in entry.answer
        for entry in entries
    )
    assert any(
        entry.display_question == "What are behavioral blind spots?"
        and "roleplay-archetypes-and-behavioral-bias" in entry.related_help_ids
        for entry in entries
    )
    assert any(
        entry.display_question == "Why does creator ownership matter long term?"
        and "creator-ownership-and-long-term-workflow-philosophy"
        in entry.related_help_ids
        for entry in entries
    )


def test_faq_category_descriptions_are_available_for_reader_polish():
    for category in get_faq_category_order():
        assert get_faq_category_description(category)


def test_faq_related_help_ids_are_known_and_lightweight():
    entries = load_faq_entries()
    help_article_ids = set(get_help_article_registry())
    raw_entries = json.loads(ui_faq.FAQ_JSON.read_text(encoding="utf-8"))

    assert all(set(entry.related_help_ids) <= help_article_ids for entry in entries)
    assert all(
        set(raw_entry.get("related_help_ids", ())) <= help_article_ids
        for raw_entry in raw_entries
    )
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


def test_faq_removes_stale_launcher_and_browser_state_references():
    entries = load_faq_entries()
    stale_terms = (
        "streamlit run app.py -- webapp",
        "edge-debug",
        "webapp-debug",
        "Use Webapp Mode",
        "Reset Webapp Browser State",
        "Clear Webapp Browser State",
        "browser-state reset",
        "app-owned browser",
        "duplicate browser cleanup",
    )
    faq_text = "\n".join(
        f"{entry.question}\n{entry.answer}"
        for entry in entries
    )

    for stale_term in stale_terms:
        assert stale_term not in faq_text


def test_filter_faq_entries_matches_question_and_answer():
    entries = (
        FAQEntry(question="What is Lite?", answer="A local-first app."),
        FAQEntry(
            question="How do I export?",
            answer="Use the Export page.",
            category="Import, Export, and Training Files",
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
        "Tags and Validation",
        rerun=False,
    )

    assert category == "Tags and Validation"
    assert fake.session_state[ui_faq.FAQ_ACTIVE_CATEGORY_KEY] == (
        "Tags and Validation"
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

    app.button(key="_faq_category_Tags and Validation").click().run()

    assert app.session_state[ui_faq.FAQ_ACTIVE_CATEGORY_KEY] == (
        "Tags and Validation"
    )
    assert any(value == "### Tags and Validation" for value in _markdown_values(app))

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


