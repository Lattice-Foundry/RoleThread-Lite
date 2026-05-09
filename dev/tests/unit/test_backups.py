import inspect
from datetime import datetime as RealDateTime
from pathlib import Path

import core.backups as backups


def _prefs(tmp_path, **overrides):
    prefs = {
        "backup_directory": str(tmp_path / "backups"),
        "backups_per_dataset": 25,
    }
    prefs.update(overrides)
    return prefs


def _use_prefs(monkeypatch, prefs):
    monkeypatch.setattr(backups, "load_preferences", lambda: prefs)


def _write_dataset(path: Path, content: bytes = b'{"messages": [], "tags": []}\n'):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def _fixed_datetime(value: RealDateTime):
    class FixedDateTime:
        min = RealDateTime.min

        @classmethod
        def now(cls):
            return value

        @staticmethod
        def strptime(date_string, fmt):
            return RealDateTime.strptime(date_string, fmt)

    return FixedDateTime


def _sequence_datetime(values: list[RealDateTime]):
    class SequenceDateTime:
        min = RealDateTime.min
        _values = list(values)

        @classmethod
        def now(cls):
            if len(cls._values) > 1:
                return cls._values.pop(0)
            return cls._values[0]

        @staticmethod
        def strptime(date_string, fmt):
            return RealDateTime.strptime(date_string, fmt)

    return SequenceDateTime


def test_backups_module_has_no_streamlit_import_or_session_state_usage():
    source = inspect.getsource(backups)

    assert "import streamlit" not in source
    assert "from streamlit" not in source
    assert "st.session_state" not in source


def test_safe_name_preserves_normal_names():
    assert backups._safe_name("dataset_01.jsonl") == "dataset_01.jsonl"


def test_safe_name_replaces_spaces_and_unsafe_characters():
    assert backups._safe_name("My Dataset! #1") == "My_Dataset_1"


def test_safe_name_strips_leading_and_trailing_dots_or_underscores():
    assert backups._safe_name("..__Dataset__..") == "Dataset"


def test_safe_name_falls_back_for_empty_or_fully_unsafe_names():
    assert backups._safe_name("") == "dataset"
    assert backups._safe_name("!!!") == "dataset"


def test_auto_backups_enabled_defaults_true_and_respects_explicit_false():
    assert backups.auto_backups_enabled({}) is True
    assert backups.auto_backups_enabled({"auto_backups_enabled": False}) is False


def test_get_backups_per_dataset_returns_valid_values_and_fallbacks():
    assert backups.get_backups_per_dataset({"backups_per_dataset": 7}) == 7
    assert backups.get_backups_per_dataset({"backups_per_dataset": "not-a-number"}) == 25


def test_get_backups_per_dataset_clamps_to_minimum_and_maximum():
    assert backups.get_backups_per_dataset({"backups_per_dataset": 0}) == 1
    assert backups.get_backups_per_dataset({"backups_per_dataset": 999}) == 500


def test_create_dataset_backup_copies_existing_dataset_to_configured_root(tmp_path, monkeypatch):
    _use_prefs(monkeypatch, _prefs(tmp_path))
    monkeypatch.setattr(
        backups,
        "datetime",
        _fixed_datetime(RealDateTime(2026, 1, 1, 12, 0, 0)),
    )
    source = _write_dataset(tmp_path / "My Dataset.jsonl", b"alpha\nbeta\n")

    backup_path = backups.create_dataset_backup(source, "before edit!?")

    assert backup_path is not None
    assert backup_path.exists()
    assert backup_path.read_bytes() == source.read_bytes()
    assert backup_path.parent == (tmp_path / "backups" / "My_Dataset").resolve()
    assert backup_path.name == "2026-01-01_120000_before_edit.jsonl"


def test_create_dataset_backup_returns_none_for_missing_or_non_file_paths(tmp_path, monkeypatch):
    _use_prefs(monkeypatch, _prefs(tmp_path))
    directory = tmp_path / "dataset_dir"
    directory.mkdir()

    assert backups.create_dataset_backup(tmp_path / "missing.jsonl", "reason") is None
    assert backups.create_dataset_backup(directory, "reason") is None


def test_create_dataset_backup_uses_suffix_when_timestamp_collides(tmp_path, monkeypatch):
    _use_prefs(monkeypatch, _prefs(tmp_path))
    monkeypatch.setattr(
        backups,
        "datetime",
        _fixed_datetime(RealDateTime(2026, 1, 1, 12, 0, 0)),
    )
    source = _write_dataset(tmp_path / "dataset.jsonl", b"same contents\n")

    first = backups.create_dataset_backup(source, "before edit")
    second = backups.create_dataset_backup(source, "before edit")

    assert first is not None
    assert second is not None
    assert first.exists()
    assert second.exists()
    assert first.name == "2026-01-01_120000_before_edit.jsonl"
    assert second.name == "2026-01-01_120000_before_edit_001.jsonl"
    assert first.read_bytes() == b"same contents\n"
    assert second.read_bytes() == b"same contents\n"


def test_prune_dataset_backups_keeps_newest_jsonl_and_ignores_other_files(tmp_path):
    backup_dir = tmp_path / "backups" / "dataset"
    backup_dir.mkdir(parents=True)
    old = _write_dataset(backup_dir / "2026-01-01_120000_before_edit.jsonl", b"old")
    middle = _write_dataset(backup_dir / "2026-01-01_120001_before_edit.jsonl", b"middle")
    newest = _write_dataset(backup_dir / "2026-01-01_120002_before_edit.jsonl", b"new")
    note = backup_dir / "notes.txt"
    note.write_text("keep me", encoding="utf-8")

    backups.prune_dataset_backups(backup_dir, keep_count=2)

    assert not old.exists()
    assert middle.exists()
    assert newest.exists()
    assert note.exists()


def test_prune_dataset_backups_treats_keep_count_below_one_as_one(tmp_path):
    backup_dir = tmp_path / "backups" / "dataset"
    backup_dir.mkdir(parents=True)
    old = _write_dataset(backup_dir / "2026-01-01_120000_before_edit.jsonl", b"old")
    newest = _write_dataset(backup_dir / "2026-01-01_120001_before_edit.jsonl", b"new")

    backups.prune_dataset_backups(backup_dir, keep_count=0)

    assert not old.exists()
    assert newest.exists()


def test_prune_dataset_backups_continues_after_one_unlink_failure(
    tmp_path,
    monkeypatch,
    capsys,
):
    backup_dir = tmp_path / "backups" / "dataset"
    backup_dir.mkdir(parents=True)
    locked = _write_dataset(backup_dir / "2026-01-01_120000_before_edit.jsonl", b"locked")
    deletable = _write_dataset(backup_dir / "2026-01-01_120001_before_edit.jsonl", b"delete")
    newest = _write_dataset(backup_dir / "2026-01-01_120002_before_edit.jsonl", b"keep")
    real_unlink = Path.unlink
    attempted: list[str] = []

    def flaky_unlink(self, *args, **kwargs):
        attempted.append(self.name)
        if self == locked:
            raise OSError("file is locked")
        return real_unlink(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", flaky_unlink)

    backups.prune_dataset_backups(backup_dir, keep_count=1)

    assert locked.exists()
    assert not deletable.exists()
    assert newest.exists()
    assert locked.name in attempted
    assert deletable.name in attempted
    assert "could not prune backup" in capsys.readouterr().out


def test_create_dataset_backup_prunes_to_configured_retention(tmp_path, monkeypatch):
    _use_prefs(monkeypatch, _prefs(tmp_path, backups_per_dataset=2))
    monkeypatch.setattr(
        backups,
        "datetime",
        _sequence_datetime(
            [
                RealDateTime(2026, 1, 1, 12, 0, 0),
                RealDateTime(2026, 1, 1, 12, 0, 1),
                RealDateTime(2026, 1, 1, 12, 0, 2),
            ]
        ),
    )
    source = _write_dataset(tmp_path / "dataset.jsonl", b"contents\n")

    backups.create_dataset_backup(source, "first")
    backups.create_dataset_backup(source, "second")
    backups.create_dataset_backup(source, "third")

    backup_dir = tmp_path / "backups" / "dataset"
    backup_names = sorted(path.name for path in backup_dir.glob("*.jsonl"))
    assert backup_names == [
        "2026-01-01_120001_second.jsonl",
        "2026-01-01_120002_third.jsonl",
    ]
