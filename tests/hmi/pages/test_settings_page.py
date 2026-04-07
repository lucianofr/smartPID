"""Tests for SettingsPage."""
from PySide6.QtWidgets import QComboBox, QLabel, QLineEdit, QPushButton, QSpinBox

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
    """With Apply/Cancel pattern, theme_changed emits on Apply, not on combo change."""
    mgr = _make_manager()
    page = SettingsPage(theme_manager=mgr)
    qtbot.addWidget(page)

    signals: list[str] = []
    page.theme_changed.connect(signals.append)

    combo = page.findChild(QComboBox, "theme_combo")
    # Find dark_room index and select it
    idx = combo.findText("dark_room")
    combo.setCurrentIndex(idx)

    # Not emitted yet — buffered until Apply
    assert "dark_room" not in signals

    # Click Apply to commit the change
    page._apply_btn.click()
    assert "dark_room" in signals


def test_refresh_spinbox_exists(qtbot):
    mgr = _make_manager()
    page = SettingsPage(theme_manager=mgr)
    qtbot.addWidget(page)
    spinbox = page.findChild(QSpinBox, "refresh_spinbox")
    assert spinbox is not None
    assert spinbox.value() > 0


def test_refresh_rate_changed_signal(qtbot):
    """With Apply/Cancel pattern, refresh_rate_changed emits on Apply."""
    mgr = _make_manager()
    page = SettingsPage(theme_manager=mgr)
    qtbot.addWidget(page)

    values: list[int] = []
    page.refresh_rate_changed.connect(values.append)

    spinbox = page.findChild(QSpinBox, "refresh_spinbox")
    spinbox.setValue(500)

    # Not emitted yet — buffered until Apply
    assert 500 not in values

    # Click Apply to commit the change
    page._apply_btn.click()
    assert 500 in values


# --- Gap #46: OPC-UA settings ---

def test_opcua_endpoint_field_exists(qtbot):
    mgr = _make_manager()
    page = SettingsPage(theme_manager=mgr)
    qtbot.addWidget(page)
    endpoint = page.findChild(QLineEdit, "opcua_endpoint")
    assert endpoint is not None
    assert "opc.tcp" in endpoint.text()


def test_opcua_status_label_exists(qtbot):
    mgr = _make_manager()
    page = SettingsPage(theme_manager=mgr)
    qtbot.addWidget(page)
    status = page.findChild(QLabel, "opcua_status")
    assert status is not None
    assert status.text() == "Disconnected"


def test_opcua_connect_disconnect_buttons_exist(qtbot):
    mgr = _make_manager()
    page = SettingsPage(theme_manager=mgr)
    qtbot.addWidget(page)
    connect_btn = page.findChild(QPushButton, "opcua_connect_btn")
    disconnect_btn = page.findChild(QPushButton, "opcua_disconnect_btn")
    assert connect_btn is not None
    assert disconnect_btn is not None
    # Initially: Connect enabled, Disconnect disabled
    assert connect_btn.isEnabled()
    assert not disconnect_btn.isEnabled()


def test_set_opcua_status_connected(qtbot):
    mgr = _make_manager()
    page = SettingsPage(theme_manager=mgr)
    qtbot.addWidget(page)
    page.set_opcua_status(True)
    assert page._opcua_status.text() == "Connected"
    assert not page._opcua_connect_btn.isEnabled()
    assert page._opcua_disconnect_btn.isEnabled()


def test_set_opcua_status_disconnected(qtbot):
    mgr = _make_manager()
    page = SettingsPage(theme_manager=mgr)
    qtbot.addWidget(page)
    page.set_opcua_status(False)
    assert page._opcua_status.text() == "Disconnected"
    assert page._opcua_connect_btn.isEnabled()
    assert not page._opcua_disconnect_btn.isEnabled()


def test_opcua_connect_signal(qtbot):
    mgr = _make_manager()
    page = SettingsPage(theme_manager=mgr)
    qtbot.addWidget(page)
    received = []
    page.opcua_connect_requested.connect(received.append)
    page._opcua_endpoint.setText("opc.tcp://myserver:4840")
    page._opcua_connect_btn.click()
    assert received == ["opc.tcp://myserver:4840"]


def test_opcua_disconnect_signal(qtbot):
    mgr = _make_manager()
    page = SettingsPage(theme_manager=mgr)
    qtbot.addWidget(page)
    page.set_opcua_status(True)  # Enable disconnect button
    received = []
    page.opcua_disconnect_requested.connect(lambda: received.append(True))
    page._opcua_disconnect_btn.click()
    assert received == [True]


def test_set_opcua_connecting(qtbot):
    mgr = _make_manager()
    page = SettingsPage(theme_manager=mgr)
    qtbot.addWidget(page)
    page.set_opcua_connecting()
    assert page._opcua_status.text() == "Connecting..."
    assert not page._opcua_connect_btn.isEnabled()
    assert not page._opcua_disconnect_btn.isEnabled()


# --- Task 8: Download/Import buttons replace Save As ---


def test_download_button_exists(qtbot):
    mgr = _make_manager()
    page = SettingsPage(theme_manager=mgr)
    qtbot.addWidget(page)
    btn = page.findChild(QPushButton, "project_download_btn")
    assert btn is not None


def test_import_button_exists(qtbot):
    mgr = _make_manager()
    page = SettingsPage(theme_manager=mgr)
    qtbot.addWidget(page)
    btn = page.findChild(QPushButton, "project_import_btn")
    assert btn is not None


def test_no_save_as_button(qtbot):
    mgr = _make_manager()
    page = SettingsPage(theme_manager=mgr)
    qtbot.addWidget(page)
    btn = page.findChild(QPushButton, "project_save_as_btn")
    assert btn is None


# --- OPC-UA endpoint persistence ---


def test_set_opcua_endpoint_and_status_connected(qtbot):
    mgr = _make_manager()
    page = SettingsPage(theme_manager=mgr)
    qtbot.addWidget(page)

    page.set_opcua_endpoint_and_status("opc.tcp://10.0.0.1:4840", connected=True)

    assert page._opcua_endpoint.text() == "opc.tcp://10.0.0.1:4840"
    assert page._opcua_status.text() == "Connected"
    assert page._committed_opcua_url == "opc.tcp://10.0.0.1:4840"
    assert not page.has_unsaved_changes()


def test_set_opcua_endpoint_and_status_disconnected(qtbot):
    mgr = _make_manager()
    page = SettingsPage(theme_manager=mgr)
    qtbot.addWidget(page)

    page.set_opcua_endpoint_and_status("opc.tcp://10.0.0.1:4840", connected=False)

    assert page._opcua_endpoint.text() == "opc.tcp://10.0.0.1:4840"
    assert page._opcua_status.text() == "Disconnected"
    assert page._committed_opcua_url == "opc.tcp://10.0.0.1:4840"
    assert not page.has_unsaved_changes()


def test_opcua_endpoint_save_signal_on_apply(qtbot):
    """Apply emits opcua_endpoint_save_requested when endpoint changed."""
    mgr = _make_manager()
    page = SettingsPage(theme_manager=mgr)
    qtbot.addWidget(page)

    saved = []
    page.opcua_endpoint_save_requested.connect(saved.append)

    page._opcua_endpoint.setText("opc.tcp://newhost:4840")
    page._apply_btn.click()

    assert saved == ["opc.tcp://newhost:4840"]


def test_no_save_signal_when_endpoint_unchanged(qtbot):
    """Apply does NOT emit opcua_endpoint_save_requested if endpoint same."""
    mgr = _make_manager()
    page = SettingsPage(theme_manager=mgr)
    qtbot.addWidget(page)

    saved = []
    page.opcua_endpoint_save_requested.connect(saved.append)

    # Change only the theme, not the endpoint
    idx = page._theme_combo.currentIndex()
    page._theme_combo.setCurrentIndex(1 if idx == 0 else 0)
    page._apply_btn.click()

    assert saved == []
