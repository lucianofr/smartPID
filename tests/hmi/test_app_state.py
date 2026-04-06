"""Tests for simplified AppStateManager."""
import json

from smart_pid_hmi.services.app_state import AppStateManager


def test_default_state(tmp_path):
    mgr = AppStateManager(tmp_path / "state.json")
    assert mgr.last_project_name is None
    assert mgr.last_theme is None


def test_set_and_save(tmp_path):
    path = tmp_path / "state.json"
    mgr = AppStateManager(path)
    mgr.set_last_project_name("elkem")
    mgr.set_last_theme("dark_room")
    mgr.save()

    data = json.loads(path.read_text())
    assert data["last_project_name"] == "elkem"
    assert data["last_theme"] == "dark_room"
    assert "recent_projects" not in data
    assert "last_project" not in data


def test_load_existing(tmp_path):
    path = tmp_path / "state.json"
    path.write_text(json.dumps({
        "last_project_name": "test",
        "last_theme": "ocean",
    }))
    mgr = AppStateManager(path)
    assert mgr.last_project_name == "test"
    assert mgr.last_theme == "ocean"


def test_load_migrates_old_format(tmp_path):
    """Old format with last_project (path) should be ignored gracefully."""
    path = tmp_path / "state.json"
    path.write_text(json.dumps({
        "last_project": "/old/path/project.spid",
        "recent_projects": [{"name": "x", "path": "/x", "controller_count": 0}],
        "last_theme": "isa101",
    }))
    mgr = AppStateManager(path)
    assert mgr.last_project_name is None  # old path-based field ignored
    assert mgr.last_theme == "isa101"
