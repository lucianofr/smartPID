"""Tests for edit controller wiring in MainWindow."""
from __future__ import annotations

from PySide6.QtWidgets import QApplication

from smart_pid_hmi.config import HMISettings
from smart_pid_hmi.main import MainWindow
from smart_pid_hmi.services.mock_service import MockAPIClient, MockTelemetrySource
from smart_pid_hmi.services.session import Session

app = QApplication.instance() or QApplication([])


def _make_window() -> MainWindow:
    from smart_pid_hmi.bus_bridge import BusBridge

    settings = HMISettings(mock_mode=True)
    session = Session()
    api_client = MockAPIClient()
    telemetry_source = MockTelemetrySource()
    bus_bridge = BusBridge(queue=telemetry_source.queue, refresh_ms=100)
    return MainWindow(
        settings=settings,
        session=session,
        api_client=api_client,
        telemetry_source=telemetry_source,
        bus_bridge=bus_bridge,
    )


class TestHidePIDTab:
    def test_pid_nav_not_visible(self):
        window = _make_window()
        nav_texts = [btn.text() for btn in window._nav_buttons if btn.isVisible()]
        assert "P&ID" not in nav_texts


class TestDashboardSettingsSignal:
    def test_dashboard_has_settings_requested_signal(self):
        window = _make_window()
        assert hasattr(window._dashboard_page, "settings_requested")

    def test_main_window_has_edit_method(self):
        window = _make_window()
        assert hasattr(window, "_on_edit_controller")
        assert callable(window._on_edit_controller)

    def test_main_window_has_open_edit_dialog(self):
        window = _make_window()
        assert hasattr(window, "_open_edit_dialog")
        assert callable(window._open_edit_dialog)
