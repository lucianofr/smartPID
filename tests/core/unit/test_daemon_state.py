"""Tests for DaemonState — daemon-level persistence of active project."""
from __future__ import annotations

import json

from smart_pid_core.application.daemon_state import DaemonState


def test_fresh_state_has_no_project(tmp_path):
    state = DaemonState(tmp_path / "state.json")
    assert state.active_project is None


def test_set_and_persist(tmp_path):
    path = tmp_path / "state.json"
    state = DaemonState(path)
    state.set_active_project("myproj")
    assert state.active_project == "myproj"

    # Reload from disk
    state2 = DaemonState(path)
    assert state2.active_project == "myproj"


def test_clear_project(tmp_path):
    path = tmp_path / "state.json"
    state = DaemonState(path)
    state.set_active_project("proj1")
    state.set_active_project(None)
    assert state.active_project is None

    state2 = DaemonState(path)
    assert state2.active_project is None


def test_corrupted_file_ignored(tmp_path):
    path = tmp_path / "state.json"
    path.write_text("not-json!!!", encoding="utf-8")
    state = DaemonState(path)
    assert state.active_project is None


def test_creates_parent_dirs(tmp_path):
    path = tmp_path / "nested" / "deep" / "state.json"
    state = DaemonState(path)
    state.set_active_project("test")
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["active_project"] == "test"
