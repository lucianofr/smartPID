"""Tests for WelcomeDialog — project selection after login."""
from __future__ import annotations

import pytest
from PySide6.QtWidgets import QListWidget, QPushButton

from smart_pid_hmi.dialogs.welcome_dialog import WelcomeDialog


@pytest.fixture
def dialog(qtbot):
    dlg = WelcomeDialog(projects=[
        {"name": "Project A", "controller_count": 3, "size_bytes": 2048},
        {"name": "Project B", "controller_count": 1, "size_bytes": 512},
    ])
    qtbot.addWidget(dlg)
    return dlg


class TestWelcomeDialog:
    def test_new_button_exists(self, dialog) -> None:
        btn = dialog.findChild(QPushButton, "welcome_new_btn")
        assert btn is not None

    def test_import_button_exists(self, dialog) -> None:
        btn = dialog.findChild(QPushButton, "welcome_import_btn")
        assert btn is not None

    def test_delete_button_exists(self, dialog) -> None:
        btn = dialog.findChild(QPushButton, "welcome_delete_btn")
        assert btn is not None

    def test_no_open_file_button(self, dialog) -> None:
        """Old 'Open Project' (QFileDialog) button should not exist."""
        btn = dialog.findChild(QPushButton, "welcome_open_btn")
        assert btn is None

    def test_project_list_populated(self, dialog) -> None:
        lst = dialog.findChild(QListWidget, "project_list")
        assert lst is not None
        assert lst.count() == 2

    def test_empty_project_list(self, qtbot) -> None:
        d = WelcomeDialog(projects=[])
        qtbot.addWidget(d)
        lst = d.findChild(QListWidget, "project_list")
        assert lst.count() == 0

    def test_result_defaults_none(self, dialog) -> None:
        assert dialog.result_action is None
        assert dialog.result_path is None
        assert dialog.result_name is None
