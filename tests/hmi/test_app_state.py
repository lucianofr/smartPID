"""Tests for AppStateManager — app.json read/write."""
from __future__ import annotations

from smart_pid_hmi.services.app_state import AppStateManager


class TestAppStateManager:
    def test_load_nonexistent_returns_defaults(self, tmp_path) -> None:
        path = tmp_path / "app.json"
        mgr = AppStateManager(path)
        assert mgr.last_project is None
        assert mgr.recent_projects == []

    def test_save_and_reload(self, tmp_path) -> None:
        path = tmp_path / "app.json"
        mgr = AppStateManager(path)
        mgr.set_last_project("/path/to/project.spid", "My Project", 3)
        mgr.save()
        mgr2 = AppStateManager(path)
        assert mgr2.last_project == "/path/to/project.spid"
        assert len(mgr2.recent_projects) == 1
        assert mgr2.recent_projects[0]["name"] == "My Project"
        assert mgr2.recent_projects[0]["controller_count"] == 3

    def test_recent_projects_fifo_limit_5(self, tmp_path) -> None:
        path = tmp_path / "app.json"
        mgr = AppStateManager(path)
        for i in range(7):
            mgr.set_last_project(f"/path/{i}.spid", f"Project {i}", i)
        mgr.save()
        mgr2 = AppStateManager(path)
        assert len(mgr2.recent_projects) == 5
        assert mgr2.recent_projects[0]["name"] == "Project 6"
        assert mgr2.recent_projects[4]["name"] == "Project 2"

    def test_duplicate_path_moves_to_front(self, tmp_path) -> None:
        path = tmp_path / "app.json"
        mgr = AppStateManager(path)
        mgr.set_last_project("/a.spid", "A", 1)
        mgr.set_last_project("/b.spid", "B", 2)
        mgr.set_last_project("/a.spid", "A Updated", 5)
        mgr.save()
        mgr2 = AppStateManager(path)
        assert len(mgr2.recent_projects) == 2
        assert mgr2.recent_projects[0]["path"] == "/a.spid"
        assert mgr2.recent_projects[0]["name"] == "A Updated"

    def test_prune_removes_nonexistent(self, tmp_path) -> None:
        path = tmp_path / "app.json"
        existing = tmp_path / "exists.spid"
        existing.touch()
        mgr = AppStateManager(path)
        mgr.set_last_project(str(existing), "Exists", 1)
        mgr.set_last_project("/nonexistent.spid", "Gone", 0)
        mgr.save()
        mgr2 = AppStateManager(path)
        mgr2.prune()
        assert len(mgr2.recent_projects) == 1
        assert mgr2.recent_projects[0]["name"] == "Exists"

    def test_creates_parent_dirs(self, tmp_path) -> None:
        path = tmp_path / "subdir" / "deep" / "app.json"
        mgr = AppStateManager(path)
        mgr.set_last_project("/a.spid", "A", 1)
        mgr.save()
        assert path.exists()
