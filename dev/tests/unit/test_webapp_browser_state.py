import json
import sqlite3

from core.webapp_browser_state import (
    get_default_edge_profile_path,
    reset_rolethread_webapp_browser_state,
)


def test_default_edge_profile_path_uses_local_app_data(monkeypatch):
    monkeypatch.setattr("core.webapp_browser_state.os.name", "nt")

    path = get_default_edge_profile_path(
        env={"LOCALAPPDATA": "C:/Users/Scott/AppData/Local"}
    )

    assert str(path).replace("\\", "/").endswith(
        "Microsoft/Edge/User Data/Default"
    )


def test_reset_skips_when_edge_is_running(tmp_path):
    profile = tmp_path / "Default"
    profile.mkdir()

    result = reset_rolethread_webapp_browser_state(
        profile_path=profile,
        running_process_names=["msedge.exe"],
    )

    assert result.success is False
    assert result.items_cleared == []
    assert any("Edge appears to be running" in item for item in result.items_skipped)


def test_reset_removes_only_localhost_app_window_placement(tmp_path):
    profile = tmp_path / "Default"
    profile.mkdir()
    preferences = profile / "Preferences"
    preferences.write_text(
        json.dumps({
            "browser": {
                "app_window_placement": {
                    "localhost_/": {"left": 1},
                    "example.com_/": {"left": 2},
                }
            }
        }),
        encoding="utf-8",
    )

    result = reset_rolethread_webapp_browser_state(
        profile_path=profile,
        running_process_names=[],
    )

    data = json.loads(preferences.read_text(encoding="utf-8"))
    placement = data["browser"]["app_window_placement"]
    assert result.success is True
    assert "localhost_/" not in placement
    assert placement["example.com_/"] == {"left": 2}


def test_reset_removes_rolethread_localhost_history_without_other_history(tmp_path):
    profile = tmp_path / "Default"
    profile.mkdir()
    history = profile / "History"
    with sqlite3.connect(history) as connection:
        connection.execute("CREATE TABLE urls (id INTEGER PRIMARY KEY, url TEXT, title TEXT)")
        connection.execute("CREATE TABLE visits (id INTEGER PRIMARY KEY, url INTEGER)")
        connection.execute("CREATE TABLE keyword_search_terms (url_id INTEGER)")
        connection.execute(
            "INSERT INTO urls (id, url, title) VALUES (1, ?, ?)",
            ("http://localhost:8501/settings", "RoleThread Lite"),
        )
        connection.execute(
            "INSERT INTO urls (id, url, title) VALUES (2, ?, ?)",
            ("http://localhost:3000/", "Other Local App"),
        )
        connection.execute("INSERT INTO visits (id, url) VALUES (1, 1)")
        connection.execute("INSERT INTO visits (id, url) VALUES (2, 2)")
        connection.execute("INSERT INTO keyword_search_terms (url_id) VALUES (1)")

    result = reset_rolethread_webapp_browser_state(
        profile_path=profile,
        running_process_names=[],
    )

    with sqlite3.connect(history) as connection:
        urls = connection.execute("SELECT id, url FROM urls ORDER BY id").fetchall()
        visits = connection.execute("SELECT id, url FROM visits ORDER BY id").fetchall()
        search_terms = connection.execute("SELECT url_id FROM keyword_search_terms").fetchall()
    assert result.success is True
    assert urls == [(2, "http://localhost:3000/")]
    assert visits == [(2, 2)]
    assert search_terms == []


def test_reset_removes_only_cache_files_referencing_rolethread_localhost(tmp_path):
    profile = tmp_path / "Default"
    cache = profile / "Code Cache" / "js"
    cache.mkdir(parents=True)
    target = cache / "target"
    target.write_bytes(b"cached from http://localhost:8501/static/js/app.js")
    other = cache / "other"
    other.write_bytes(b"cached from http://localhost:3000/static/js/app.js")

    result = reset_rolethread_webapp_browser_state(
        profile_path=profile,
        running_process_names=[],
    )

    assert result.success is True
    assert not target.exists()
    assert other.exists()


def test_reset_reports_missing_profile_gracefully(tmp_path):
    result = reset_rolethread_webapp_browser_state(
        profile_path=tmp_path / "missing",
        running_process_names=[],
    )

    assert result.success is False
    assert result.items_cleared == []
    assert any("not found" in item for item in result.items_skipped)
