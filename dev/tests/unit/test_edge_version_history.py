from dataclasses import dataclass

from sqlalchemy import create_engine, inspect as sa_inspect
from sqlalchemy.orm import sessionmaker

import core.edge_version_history as edge_history
from core.models import Base, EdgeVersionHistory


@dataclass
class _CompletedProcess:
    returncode: int
    stdout: str = ""
    stderr: str = ""


def _edge_history_db(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'edge_history.db'}",
        connect_args={"check_same_thread": False},
    )
    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    monkeypatch.setattr(edge_history, "SessionLocal", session_factory)
    monkeypatch.setattr(
        edge_history,
        "init_db",
        lambda: Base.metadata.create_all(bind=engine),
    )
    Base.metadata.create_all(engine)
    return engine, session_factory


def test_edge_version_history_table_registers_in_metadata(tmp_path, monkeypatch):
    engine, _session_factory = _edge_history_db(tmp_path, monkeypatch)
    inspector = sa_inspect(engine)

    assert "edge_version_history" in Base.metadata.tables
    assert "edge_version_history" in inspector.get_table_names()
    indexes = {
        index["name"]
        for index in inspector.get_indexes("edge_version_history")
    }
    assert "ix_edge_version_history_browser_name" in indexes
    assert "ix_edge_version_history_version" in indexes


def test_record_edge_version_inserts_new_row(tmp_path, monkeypatch):
    _engine, session_factory = _edge_history_db(tmp_path, monkeypatch)

    record = edge_history.record_edge_version(
        "123.0.1.2",
        source="launcher",
    )

    session = session_factory()
    try:
        row = session.query(EdgeVersionHistory).one()
    finally:
        session.close()
    assert record.version == "123.0.1.2"
    assert row.browser_name == "Microsoft Edge"
    assert row.version == "123.0.1.2"
    assert row.encounter_count == 1
    assert row.source == "launcher"
    assert row.first_seen is not None
    assert row.last_seen is not None


def test_record_edge_version_upserts_existing_version(tmp_path, monkeypatch):
    _engine, session_factory = _edge_history_db(tmp_path, monkeypatch)

    edge_history.record_edge_version("123.0.1.2", source="launcher")
    record = edge_history.record_edge_version("123.0.1.2", source="webapp_diag")

    session = session_factory()
    try:
        rows = session.query(EdgeVersionHistory).all()
    finally:
        session.close()
    assert len(rows) == 1
    assert record.encounter_count == 2
    assert record.source == "webapp_diag"


def test_record_edge_version_tracks_new_versions_separately(tmp_path, monkeypatch):
    _edge_history_db(tmp_path, monkeypatch)

    edge_history.record_edge_version("123.0.1.2", source="launcher")
    edge_history.record_edge_version("124.0.1.2", source="webapp_diag")
    records = edge_history.get_edge_version_history()

    assert {record.version for record in records} == {"123.0.1.2", "124.0.1.2"}


def test_record_edge_version_ignores_blank_versions(tmp_path, monkeypatch):
    _edge_history_db(tmp_path, monkeypatch)

    record = edge_history.record_edge_version("", source="launcher")

    assert record is None
    assert edge_history.get_edge_version_history() == ()


def test_read_edge_version_uses_local_file_version(tmp_path):
    edge_path = tmp_path / "msedge.exe"
    edge_path.write_text("placeholder", encoding="utf-8")

    def fake_run(command, **kwargs):
        assert "powershell" in command[0]
        assert str(edge_path) in command[-1]
        return _CompletedProcess(returncode=0, stdout="Microsoft Edge 123.0.1.2\n")

    version = edge_history.read_edge_version(edge_path, run_fn=fake_run)

    assert version == "123.0.1.2"


def test_read_edge_version_prefers_install_directory_version(tmp_path):
    app_dir = tmp_path / "Application"
    edge_path = app_dir / "msedge.exe"
    edge_path.parent.mkdir()
    edge_path.write_text("placeholder", encoding="utf-8")
    (app_dir / "123.0.1.2").mkdir()
    (app_dir / "124.0.1.2").mkdir()

    def fail_run(command, **kwargs):
        raise AssertionError("PowerShell fallback should not run")

    version = edge_history.read_edge_version(edge_path, run_fn=fail_run)

    assert version == "124.0.1.2"


def test_record_installed_edge_version_reads_and_upserts(tmp_path, monkeypatch):
    _edge_history_db(tmp_path, monkeypatch)

    record = edge_history.record_installed_edge_version(
        "C:/Edge/msedge.exe",
        source="launcher",
        version_reader=lambda path: "125.0.0.1",
    )

    assert record.version == "125.0.0.1"
    assert record.source == "launcher"
