"""Tests for SettingsPage."""
from PySide6.QtWidgets import QComboBox, QSpinBox

from smart_pid_hmi.pages.settings_page import SettingsPage
from smart_pid_hmi.themes.dark_room import DarkRoomTheme
from smart_pid_hmi.themes.isa101 import ISA101Theme
from smart_pid_hmi.themes.manager import ThemeManager


def _make_manager():
    mgr = ThemeManager()
    mgr.register(ISA101Theme())
    mgr.register(DarkRoomTheme())
    mgr.set_theme("isa101")
    return mgr


def test_creation(qtbot):
    mgr = _make_manager()
    page = SettingsPage(theme_manager=mgr)
    qtbot.addWidget(page)
    assert page is not None


def test_theme_combo_populated(qtbot):
    mgr = _make_manager()
    page = SettingsPage(theme_manager=mgr)
    qtbot.addWidget(page)
    combo = page.findChild(QComboBox, "theme_combo")
    assert combo is not None
    items = [combo.itemText(i) for i in range(combo.count())]
    assert "dark_room" in items
    assert "isa101" in items


def test_theme_changed_signal(qtbot):
    mgr = _make_manager()
    page = SettingsPage(theme_manager=mgr)
    qtbot.addWidget(page)

    signals: list[str] = []
    page.theme_changed.connect(signals.append)

    combo = page.findChild(QComboBox, "theme_combo")
    # Find dark_room index and select it
    idx = combo.findText("dark_room")
    combo.setCurrentIndex(idx)

    assert "dark_room" in signals


def test_refresh_spinbox_exists(qtbot):
    mgr = _make_manager()
    page = SettingsPage(theme_manager=mgr)
    qtbot.addWidget(page)
    spinbox = page.findChild(QSpinBox, "refresh_spinbox")
    assert spinbox is not None
    assert spinbox.value() > 0


def test_refresh_rate_changed_signal(qtbot):
    mgr = _make_manager()
    page = SettingsPage(theme_manager=mgr)
    qtbot.addWidget(page)

    values: list[int] = []
    page.refresh_rate_changed.connect(values.append)

    spinbox = page.findChild(QSpinBox, "refresh_spinbox")
    spinbox.setValue(500)

    assert 500 in values
