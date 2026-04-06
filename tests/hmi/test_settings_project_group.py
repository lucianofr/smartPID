"""Tests for SettingsPage Project group box (Task 9)."""
from __future__ import annotations

import pytest
from PySide6.QtWidgets import QGroupBox, QLabel, QPushButton

from smart_pid_hmi.pages.settings_page import SettingsPage
from smart_pid_hmi.themes.dark_room import DarkRoomTheme
from smart_pid_hmi.themes.isa101 import ISA101Theme
from smart_pid_hmi.themes.manager import ThemeManager


@pytest.fixture
def theme_manager() -> ThemeManager:
    tm = ThemeManager()
    tm.register(ISA101Theme())
    tm.register(DarkRoomTheme())
    tm.set_theme("isa101")
    return tm


@pytest.fixture
def page(qtbot, theme_manager) -> SettingsPage:
    p = SettingsPage(theme_manager=theme_manager)
    qtbot.addWidget(p)
    return p


class TestProjectGroupExists:
    """Project group box and its children must exist."""

    def test_project_group_exists(self, page):
        group = page.findChild(QGroupBox, "project_group")
        assert group is not None

    def test_project_name_label_exists(self, page):
        label = page.findChild(QLabel, "project_name")
        assert label is not None

    def test_project_path_label_exists(self, page):
        label = page.findChild(QLabel, "project_path")
        assert label is not None

    def test_project_count_label_exists(self, page):
        label = page.findChild(QLabel, "project_count")
        assert label is not None


class TestProjectButtons:
    """New, Open, Download, Import buttons must exist; Save As removed."""

    def test_new_button_exists(self, page):
        btn = page.findChild(QPushButton, "project_new_btn")
        assert btn is not None

    def test_open_button_exists(self, page):
        btn = page.findChild(QPushButton, "project_open_btn")
        assert btn is not None

    def test_download_button_exists(self, page):
        btn = page.findChild(QPushButton, "project_download_btn")
        assert btn is not None

    def test_import_button_exists(self, page):
        btn = page.findChild(QPushButton, "project_import_btn")
        assert btn is not None

    def test_save_as_button_removed(self, page):
        btn = page.findChild(QPushButton, "project_save_as_btn")
        assert btn is None


class TestProjectSignals:
    """Project-related signals must exist."""

    def test_project_changed_signal_exists(self, page):
        assert hasattr(page, "project_changed")

    def test_project_new_requested_signal_exists(self, page):
        assert hasattr(page, "project_new_requested")

    def test_project_open_requested_signal_exists(self, page):
        assert hasattr(page, "project_open_requested")

    def test_project_download_requested_signal_exists(self, page):
        assert hasattr(page, "project_download_requested")

    def test_project_import_requested_signal_exists(self, page):
        assert hasattr(page, "project_import_requested")


class TestUpdateProjectInfo:
    """update_project_info() should update the labels."""

    def test_update_project_info_sets_name(self, page):
        page.update_project_info("MyProject", "/tmp/my.spid", 5)
        label = page.findChild(QLabel, "project_name")
        assert label.text() == "MyProject"

    def test_update_project_info_sets_path(self, page):
        page.update_project_info("MyProject", "/tmp/my.spid", 5)
        label = page.findChild(QLabel, "project_path")
        assert label.text() == "/tmp/my.spid"

    def test_update_project_info_sets_count(self, page):
        page.update_project_info("MyProject", "/tmp/my.spid", 5)
        label = page.findChild(QLabel, "project_count")
        assert label.text() == "5"

    def test_update_project_info_zero_count(self, page):
        page.update_project_info("Empty", "/tmp/empty.spid", 0)
        label = page.findChild(QLabel, "project_count")
        assert label.text() == "0"


class TestProjectGroupPosition:
    """Project group should be ABOVE Appearance group in the layout."""

    def test_project_group_is_before_appearance(self, page):
        layout = page.layout()
        project_idx = None
        appearance_idx = None
        for i in range(layout.count()):
            item = layout.itemAt(i)
            widget = item.widget() if item else None
            if isinstance(widget, QGroupBox):
                if widget.objectName() == "project_group":
                    project_idx = i
                elif widget.title() == "Appearance":
                    appearance_idx = i
        assert project_idx is not None, "project_group not found"
        assert appearance_idx is not None, "Appearance group not found"
        assert project_idx < appearance_idx


class TestProjectButtonsNotAffectedByApplyCancel:
    """Project buttons are immediate actions — Apply/Cancel should not affect them."""

    def test_project_buttons_always_enabled(self, page):
        """Project buttons should be enabled even when Apply/Cancel are disabled."""
        assert not page._apply_btn.isEnabled()
        assert not page._cancel_btn.isEnabled()

        new_btn = page.findChild(QPushButton, "project_new_btn")
        open_btn = page.findChild(QPushButton, "project_open_btn")
        download_btn = page.findChild(QPushButton, "project_download_btn")
        import_btn = page.findChild(QPushButton, "project_import_btn")

        assert new_btn.isEnabled()
        assert open_btn.isEnabled()
        assert download_btn.isEnabled()
        assert import_btn.isEnabled()
