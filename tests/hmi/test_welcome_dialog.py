"""Tests for WelcomeDialog — first-run project selection."""
from __future__ import annotations

import pytest
from PySide6.QtWidgets import QListWidget, QPushButton

from smart_pid_hmi.dialogs.welcome_dialog import WelcomeDialog


@pytest.fixture
def dialog():
    return WelcomeDialog(recent_projects=[
        {"name": "Project A", "path": "/a.spid", "controller_count": 3},
        {"name": "Project B", "path": "/b.spid", "controller_count": 1},
    ])


class TestWelcomeDialog:
    def test_new_button_exists(self, dialog) -> None:
        btn = dialog.findChild(QPushButton, "welcome_new_btn")
        assert btn is not None

    def test_open_button_exists(self, dialog) -> None:
        btn = dialog.findChild(QPushButton, "welcome_open_btn")
        assert btn is not None

    def test_recent_list_populated(self, dialog) -> None:
        lst = dialog.findChild(QListWidget, "recent_list")
        assert lst is not None
        assert lst.count() == 2

    def test_empty_recent_list(self) -> None:
        d = WelcomeDialog(recent_projects=[])
        lst = d.findChild(QListWidget, "recent_list")
        assert lst.count() == 0

    def test_result_defaults_none(self, dialog) -> None:
        assert dialog.result_action is None
        assert dialog.result_path is None
        assert dialog.result_name is None
