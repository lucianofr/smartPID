"""Tests for SettingsPage Apply/Cancel pattern (Task 8)."""
from __future__ import annotations

import pytest

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


class TestButtonsExist:
    """Apply and Cancel buttons must exist with correct objectNames."""

    def test_apply_btn_exists(self, page):
        assert page._apply_btn is not None
        assert page._apply_btn.objectName() == "apply_btn"

    def test_cancel_btn_exists(self, page):
        assert page._cancel_btn is not None
        assert page._cancel_btn.objectName() == "cancel_btn"


class TestInitialState:
    """Both buttons disabled initially (no pending changes)."""

    def test_apply_btn_disabled_initially(self, page):
        assert not page._apply_btn.isEnabled()

    def test_cancel_btn_disabled_initially(self, page):
        assert not page._cancel_btn.isEnabled()

    def test_has_unsaved_changes_false_initially(self, page):
        assert page.has_unsaved_changes() is False


class TestEditEnablesButtons:
    """Editing any field enables both Apply and Cancel."""

    def test_editing_theme_enables_buttons(self, page):
        # Change theme combo to a different index
        original_idx = page._theme_combo.currentIndex()
        new_idx = 1 if original_idx == 0 else 0
        page._theme_combo.setCurrentIndex(new_idx)

        assert page._apply_btn.isEnabled()
        assert page._cancel_btn.isEnabled()
        assert page.has_unsaved_changes() is True

    def test_editing_refresh_enables_buttons(self, page):
        original = page._refresh_spin.value()
        page._refresh_spin.setValue(original + 100)

        assert page._apply_btn.isEnabled()
        assert page._cancel_btn.isEnabled()
        assert page.has_unsaved_changes() is True

    def test_editing_opcua_enables_buttons(self, page):
        page._opcua_endpoint.setText("opc.tcp://different:4840")

        assert page._apply_btn.isEnabled()
        assert page._cancel_btn.isEnabled()
        assert page.has_unsaved_changes() is True


class TestCancel:
    """Cancel reverts fields to committed state and disables buttons."""

    def test_cancel_reverts_theme(self, page):
        original_idx = page._theme_combo.currentIndex()
        new_idx = 1 if original_idx == 0 else 0
        page._theme_combo.setCurrentIndex(new_idx)

        page._cancel_btn.click()

        assert page._theme_combo.currentIndex() == original_idx
        assert not page._apply_btn.isEnabled()
        assert not page._cancel_btn.isEnabled()
        assert page.has_unsaved_changes() is False

    def test_cancel_reverts_refresh(self, page):
        original = page._refresh_spin.value()
        page._refresh_spin.setValue(original + 100)

        page._cancel_btn.click()

        assert page._refresh_spin.value() == original
        assert not page._apply_btn.isEnabled()
        assert not page._cancel_btn.isEnabled()

    def test_cancel_reverts_opcua(self, page):
        original = page._opcua_endpoint.text()
        page._opcua_endpoint.setText("opc.tcp://different:4840")

        page._cancel_btn.click()

        assert page._opcua_endpoint.text() == original
        assert not page._apply_btn.isEnabled()
        assert not page._cancel_btn.isEnabled()


class TestApply:
    """Apply emits signals for changed values, updates committed state, disables buttons."""

    def test_apply_emits_theme_changed(self, qtbot, page):
        # Change theme
        original_idx = page._theme_combo.currentIndex()
        new_idx = 1 if original_idx == 0 else 0
        page._theme_combo.setCurrentIndex(new_idx)

        with qtbot.waitSignal(page.theme_changed, timeout=1000):
            page._apply_btn.click()

        assert not page._apply_btn.isEnabled()
        assert not page._cancel_btn.isEnabled()
        assert page.has_unsaved_changes() is False

    def test_apply_emits_refresh_rate_changed(self, qtbot, page):
        original = page._refresh_spin.value()
        page._refresh_spin.setValue(original + 100)

        with qtbot.waitSignal(page.refresh_rate_changed, timeout=1000):
            page._apply_btn.click()

        assert not page._apply_btn.isEnabled()
        assert not page._cancel_btn.isEnabled()

    def test_apply_does_not_emit_unchanged_signals(self, qtbot, page):
        """If only theme changed, refresh_rate_changed should NOT be emitted."""
        original_idx = page._theme_combo.currentIndex()
        new_idx = 1 if original_idx == 0 else 0
        page._theme_combo.setCurrentIndex(new_idx)

        signals_emitted = []
        page.refresh_rate_changed.connect(lambda v: signals_emitted.append("refresh"))

        page._apply_btn.click()

        assert "refresh" not in signals_emitted

    def test_apply_updates_committed_state(self, page):
        """After apply, the new values become committed — no unsaved changes."""
        new_idx = 1 if page._theme_combo.currentIndex() == 0 else 0
        page._theme_combo.setCurrentIndex(new_idx)
        page._apply_btn.click()

        # Now committed state should match current
        assert page.has_unsaved_changes() is False

        # Changing back to original should show unsaved changes
        old_idx = 0 if new_idx == 1 else 1
        page._theme_combo.setCurrentIndex(old_idx)
        assert page.has_unsaved_changes() is True


class TestConnectDisconnectImmediate:
    """Connect/Disconnect buttons remain immediate actions, not buffered."""

    def test_connect_emits_immediately(self, qtbot, page):
        page._opcua_endpoint.setText("opc.tcp://test:4840")

        with qtbot.waitSignal(page.opcua_connect_requested, timeout=1000):
            page._opcua_connect_btn.click()

    def test_disconnect_emits_immediately(self, qtbot, page):
        # Enable disconnect button first (simulating connected state)
        page.set_opcua_status(True)

        with qtbot.waitSignal(page.opcua_disconnect_requested, timeout=1000):
            page._opcua_disconnect_btn.click()
