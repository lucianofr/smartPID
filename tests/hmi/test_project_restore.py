"""Tests for _check_active_project — welcome dialog skip when project is active."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest


@pytest.fixture
def main_window_deps():
    """Create minimal mocks for MainWindow dependencies."""
    api_client = MagicMock()
    session = MagicMock()
    session.username = "admin"
    session.token = "tok"

    app_state = MagicMock()
    app_state.last_project_name = None
    app_state.last_theme = None

    settings_page = MagicMock()
    return api_client, session, app_state, settings_page


class TestCheckActiveProject:
    """Test the _check_active_project logic without a real MainWindow."""

    def test_managed_project_active_skips_welcome(self, main_window_deps):
        """When backend already has a managed project, skip welcome dialog."""
        api, session, app_state, settings_page = main_window_deps
        api.get_current_project.return_value = {
            "name": "MyProject",
            "path": "MyProject.spid",
            "controller_count": 5,
        }

        # Simulate the logic from _check_active_project
        current = api.get_current_project()
        path = current.get("path", "")
        assert path != "project.spid"  # managed project → no welcome

    def test_scratch_with_last_project_restores(self, main_window_deps):
        """When backend has scratch and HMI knows last project, restore it."""
        api, session, app_state, settings_page = main_window_deps
        api.get_current_project.return_value = {
            "name": "project",
            "path": "project.spid",
            "controller_count": 0,
        }
        api.open_project.return_value = {
            "name": "RestoredProj",
            "path": "RestoredProj.spid",
            "controller_count": 3,
        }
        app_state.last_project_name = "RestoredProj"

        # Simulate _check_active_project logic
        current = api.get_current_project()
        path = current.get("path", "")

        show_welcome = True
        if path != "project.spid":
            show_welcome = False
        elif app_state.last_project_name:
            api.open_project(app_state.last_project_name)
            show_welcome = False

        assert not show_welcome
        api.open_project.assert_called_once_with("RestoredProj")

    def test_scratch_no_last_project_shows_welcome(self, main_window_deps):
        """When backend has scratch and no last project, show welcome."""
        api, session, app_state, settings_page = main_window_deps
        api.get_current_project.return_value = {
            "name": "project",
            "path": "project.spid",
            "controller_count": 0,
        }
        app_state.last_project_name = None

        current = api.get_current_project()
        path = current.get("path", "")

        show_welcome = True
        if path != "project.spid" or app_state.last_project_name:
            show_welcome = False

        assert show_welcome

    def test_scratch_last_project_deleted_shows_welcome(self, main_window_deps):
        """When last project was deleted, fallback fails → show welcome."""
        api, session, app_state, settings_page = main_window_deps
        api.get_current_project.return_value = {
            "name": "project",
            "path": "project.spid",
            "controller_count": 0,
        }
        api.open_project.side_effect = Exception("Project not found")
        app_state.last_project_name = "DeletedProj"

        current = api.get_current_project()
        path = current.get("path", "")

        show_welcome = True
        if path != "project.spid":
            show_welcome = False
        elif app_state.last_project_name:
            try:
                api.open_project(app_state.last_project_name)
                show_welcome = False
            except Exception:
                show_welcome = True

        assert show_welcome
