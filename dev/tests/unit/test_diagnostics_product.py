from core.product_diagnostics import (
    CloudBackupDiagnostics,
    DataHealthDiagnostics,
    ProductDiagnostics,
    ProductOverviewDiagnostics,
    ProductPathDiagnostics,
    SupportArtifactDiagnostics,
)
from ui import diagnostics_product


class _FakeContext:
    def __init__(self, parent):
        self.parent = parent

    def __enter__(self):
        return self.parent

    def __exit__(self, exc_type, exc, traceback):
        return False


class _FakeStreamlit:
    def __init__(self):
        self.calls = []

    def subheader(self, value):
        self.calls.append(("subheader", value))

    def markdown(self, value, **kwargs):
        self.calls.append(("markdown", value, kwargs))

    def caption(self, value):
        self.calls.append(("caption", value))

    def warning(self, value):
        self.calls.append(("warning", value))

    def columns(self, count):
        return [_FakeContext(self) for _ in range(count)]

    def expander(self, label, expanded=False):
        self.calls.append(("expander", label, expanded))
        return _FakeContext(self)

    def text(self):
        return "\n".join(str(call) for call in self.calls)


def _sample_diagnostics(secret_value="do-not-render") -> ProductDiagnostics:
    return ProductDiagnostics(
        overview=ProductOverviewDiagnostics(
            rolethread_version="1.4.45",
            python_version="3.14.5",
            python_status="Supported",
            python_message="Runtime is supported.",
            platform="Windows",
            platform_support="primary",
            runtime_context="source",
            streamlit_version="1.57.0",
            litlaunch_version="1.0.0rc6",
        ),
        paths=(
            ProductPathDiagnostics(
                "App data",
                r"C:\Users\tester\AppData\Local\RoleThread",
                True,
                "directory",
            ),
            ProductPathDiagnostics(
                "Workspace",
                r"C:\Users\tester\RoleThread",
                True,
                "directory",
            ),
            ProductPathDiagnostics(
                "Training data",
                r"C:\Users\tester\RoleThread\training_data",
                False,
                "directory",
                source="user_override",
                platform_default=r"C:\Users\tester\RoleThread\training_data",
            ),
            ProductPathDiagnostics(
                "Imports",
                r"C:\Users\tester\RoleThread\imports",
                False,
                "directory",
            ),
        ),
        cloud_backup=CloudBackupDiagnostics(
            status="configured",
            provider="OneDrive",
            destination_path=r"C:\Users\tester\OneDrive\RoleThread Lite\backups",
            destination_exists=True,
            last_sync_at="2026-05-24T12:00:00",
            config_path=r"C:\Users\tester\AppData\Local\RoleThread\backup_config.json",
            config_exists=True,
        ),
        support_artifacts=SupportArtifactDiagnostics(
            product_log_path=r"C:\Users\tester\AppData\Local\RoleThread\logs\launcher.log",
            product_log_env_var="ROLETHREAD_LAUNCHER_LOG_PATH",
            runtime_event_log_path=r"X:\rolethread\.litlaunch\runtime-events.log",
            reports_dir=r"X:\rolethread\.litlaunch\reports",
            reports_dir_exists=True,
        ),
        data_health=DataHealthDiagnostics(
            database_path=r"C:\Users\tester\AppData\Local\RoleThread\rolethread.db",
            database_exists=True,
            database_readable=True,
            preferences_path=r"C:\Users\tester\AppData\Local\RoleThread\preferences.json",
            preferences_exists=False,
            preferences_readable=False,
        ),
        privacy_notes=(
            "Product diagnostics include local filesystem paths for support.",
            f"Secret fixture value {secret_value} should not be used by tests.",
        ),
    )


def test_render_product_diagnostics_outputs_expected_sections(monkeypatch):
    fake_st = _FakeStreamlit()
    monkeypatch.setattr(diagnostics_product, "st", fake_st)

    diagnostics_product.render_product_diagnostics(_sample_diagnostics())

    text = fake_st.text()
    assert "RoleThread Overview" in text
    assert "Storage &amp; Data" in text
    assert "Cloud Backup" in text
    assert "Support &amp; Data Health" in text
    assert "v1.4.45" in text
    assert "1.0.0rc6" in text
    assert "Local-only" not in text
    assert "OneDrive" in text
    assert "Additional paths" in text


def test_render_product_diagnostics_escapes_values(monkeypatch):
    fake_st = _FakeStreamlit()
    monkeypatch.setattr(diagnostics_product, "st", fake_st)
    diagnostics = _sample_diagnostics()
    diagnostics = ProductDiagnostics(
        overview=ProductOverviewDiagnostics(
            **{
                **diagnostics.overview.__dict__,
                "platform": "<script>alert(1)</script>",
            }
        ),
        paths=diagnostics.paths,
        cloud_backup=diagnostics.cloud_backup,
        support_artifacts=diagnostics.support_artifacts,
        data_health=diagnostics.data_health,
        privacy_notes=diagnostics.privacy_notes,
    )

    diagnostics_product.render_product_diagnostics(diagnostics)

    text = fake_st.text()
    assert "<script>alert(1)</script>" not in text
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in text


def test_render_product_diagnostics_does_not_render_raw_secret_fixture(monkeypatch):
    fake_st = _FakeStreamlit()
    monkeypatch.setattr(diagnostics_product, "st", fake_st)
    diagnostics = _sample_diagnostics(secret_value="token-secret")
    diagnostics = ProductDiagnostics(
        overview=diagnostics.overview,
        paths=diagnostics.paths,
        cloud_backup=diagnostics.cloud_backup,
        support_artifacts=diagnostics.support_artifacts,
        data_health=diagnostics.data_health,
        privacy_notes=("Raw environment variables, tokens, and cloud credentials are not collected.",),
    )

    diagnostics_product.render_product_diagnostics(diagnostics)

    assert "token-secret" not in fake_st.text()


def test_cloud_backup_local_only_wording_is_friendly():
    cloud_backup = CloudBackupDiagnostics(status="local_only", provider="Local only")

    assert diagnostics_product._cloud_status(cloud_backup) == ("Local-only", "ok")


def test_availability_labels_are_compact():
    assert diagnostics_product._availability_label(True, True) == "readable"
    assert diagnostics_product._availability_label(True, False) == "exists, unreadable"
    assert diagnostics_product._availability_label(False, False) == "not found"
