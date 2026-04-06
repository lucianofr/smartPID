"""Test projects_dir setting."""
from pathlib import Path

from smart_pid_core.config import CoreSettings


def test_projects_dir_default():
    settings = CoreSettings(jwt_secret="test-secret-key-minimum-32-bytes!")
    assert settings.projects_dir == Path.home() / ".smart-pid" / "projects"


def test_projects_dir_override(monkeypatch):
    monkeypatch.setenv("SPID_PROJECTS_DIR", "/tmp/custom-projects")
    settings = CoreSettings(jwt_secret="test-secret-key-minimum-32-bytes!")
    assert settings.projects_dir == Path("/tmp/custom-projects")
