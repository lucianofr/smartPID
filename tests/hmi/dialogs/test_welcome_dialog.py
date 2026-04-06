"""Tests for redesigned WelcomeDialog."""
import pytest
from PySide6.QtWidgets import QListWidget, QPushButton

from smart_pid_hmi.dialogs.welcome_dialog import WelcomeDialog


@pytest.fixture
def projects():
    return [
        {"name": "alpha", "controller_count": 3, "size_bytes": 1024},
        {"name": "beta", "controller_count": 0, "size_bytes": 512},
    ]


def test_creation(qtbot, projects):
    dlg = WelcomeDialog(projects=projects)
    qtbot.addWidget(dlg)
    assert dlg.windowTitle() == "Smart PID Edge Optimizer"


def test_project_list_populated(qtbot, projects):
    dlg = WelcomeDialog(projects=projects)
    qtbot.addWidget(dlg)
    list_widget = dlg.findChild(QListWidget, "project_list")
    assert list_widget is not None
    assert list_widget.count() == 2


def test_new_button_exists(qtbot, projects):
    dlg = WelcomeDialog(projects=projects)
    qtbot.addWidget(dlg)
    btn = dlg.findChild(QPushButton, "welcome_new_btn")
    assert btn is not None


def test_import_button_exists(qtbot, projects):
    dlg = WelcomeDialog(projects=projects)
    qtbot.addWidget(dlg)
    btn = dlg.findChild(QPushButton, "welcome_import_btn")
    assert btn is not None


def test_delete_button_exists(qtbot, projects):
    dlg = WelcomeDialog(projects=projects)
    qtbot.addWidget(dlg)
    btn = dlg.findChild(QPushButton, "welcome_delete_btn")
    assert btn is not None


def test_no_open_file_button(qtbot, projects):
    """Old 'Open Project' (QFileDialog) button should not exist."""
    dlg = WelcomeDialog(projects=projects)
    qtbot.addWidget(dlg)
    btn = dlg.findChild(QPushButton, "welcome_open_btn")
    assert btn is None


def test_empty_project_list(qtbot):
    dlg = WelcomeDialog(projects=[])
    qtbot.addWidget(dlg)
    list_widget = dlg.findChild(QListWidget, "project_list")
    assert list_widget.count() == 0
