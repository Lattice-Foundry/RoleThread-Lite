import inspect
from pathlib import Path

import core.storage as storage


def test_storage_module_has_no_streamlit_import_or_session_state_usage():
    source = inspect.getsource(storage)

    assert "import streamlit" not in source
    assert "from streamlit" not in source
    assert "st.session_state" not in source


def test_app_root_resolves_to_project_like_parent_path():
    assert isinstance(storage.APP_ROOT, Path)
    assert storage.APP_ROOT.exists()
    assert (storage.APP_ROOT / "core" / "storage.py").exists()


def test_storage_directory_constants_are_paths():
    assert isinstance(storage.APP_DATA_DIR, Path)
    assert isinstance(storage.BACKUPS_DIR, Path)
    assert isinstance(storage.TEMP_DIR, Path)
    assert isinstance(storage.TRAINING_DATA_DIR, Path)


def test_storage_getters_return_configured_paths():
    assert storage.get_default_training_data_dir() == storage.TRAINING_DATA_DIR
    assert storage.get_backups_dir() == storage.BACKUPS_DIR
    assert storage.get_temp_dir() == storage.TEMP_DIR


def test_ensure_app_directories_creates_expected_directories(tmp_path, monkeypatch):
    app_data = tmp_path / "app_data"
    backups = app_data / "backups"
    temp = app_data / "temp"
    training_data = tmp_path / "training_data"
    monkeypatch.setattr(storage, "APP_DATA_DIR", app_data)
    monkeypatch.setattr(storage, "BACKUPS_DIR", backups)
    monkeypatch.setattr(storage, "TEMP_DIR", temp)
    monkeypatch.setattr(storage, "TRAINING_DATA_DIR", training_data)

    storage.ensure_app_directories()

    assert app_data.is_dir()
    assert backups.is_dir()
    assert temp.is_dir()
    assert training_data.is_dir()
