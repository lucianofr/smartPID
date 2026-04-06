"""Tests for audit gaps #37-41, #44: MainWindow signal wiring fixes."""
from __future__ import annotations

from queue import SimpleQueue
from unittest.mock import MagicMock, patch

import pytest

from smart_pid_hmi.bus_bridge import BusBridge
from smart_pid_hmi.config import HMISettings
from smart_pid_hmi.main import MainWindow
from smart_pid_hmi.services.session import Session


@pytest.fixture
def settings() -> HMISettings:
    return HMISettings(mock_mode=True)  # type: ignore[call-arg]


@pytest.fixture
def session() -> Session:
    return Session()


@pytest.fixture
def bus_bridge() -> BusBridge:
    return BusBridge(queue=SimpleQueue(), refresh_ms=100)


@pytest.fixture
def api_client() -> MagicMock:
    client = MagicMock()
    client.get_active_alarms.return_value = []
    client.get_all_stats.return_value = []
    return client


@pytest.fixture
def main_window(qtbot, settings, session, bus_bridge, api_client):
    telemetry_source = MagicMock()
    telemetry_source.queue = SimpleQueue()
    window = MainWindow(
        settings=settings,
        session=session,
        api_client=api_client,
        telemetry_source=telemetry_source,
        bus_bridge=bus_bridge,
    )
    qtbot.addWidget(window)
    return window


# --- Gap #37: Multi-trend wired to data ---

class TestMultiTrendWiring:
    def test_controllers_loaded_sets_available_loops(self, main_window):
        """After controllers load, multi-trend combos should be populated."""
        controllers = [
            {"id": 1, "name": "FIC-101", "mode": "AUTO", "pv": 50.0, "sp": 50.0},
            {"id": 2, "name": "LIC-201", "mode": "AUTO", "pv": 65.0, "sp": 65.0},
        ]
        main_window._on_controllers_received(controllers)
        combo = main_window._multi_trend_page._loop_combos[0]
        assert combo.count() == 2
        assert combo.itemText(0) == "FIC-101"
        assert combo.itemText(1) == "LIC-201"

    def test_telemetry_updates_matching_trend_plot(self, main_window):
        """Telemetry for a controller selected in a trend combo updates plot."""
        controllers = [
            {"id": 1, "name": "FIC-101", "mode": "AUTO", "pv": 50.0, "sp": 50.0},
        ]
        main_window._on_controllers_received(controllers)
        # Combo 0 should have FIC-101 selected by default
        assert main_window._multi_trend_page._loop_combos[0].currentText() == "FIC-101"

        frame = {"pv": 51.0, "sp": 50.0, "co": 45.0}
        main_window._on_telemetry_for_trends(1, frame)

        # Check that buffer was created
        assert hasattr(main_window, "_trend_buffers")
        assert 0 in main_window._trend_buffers
        buf = main_window._trend_buffers[0]
        assert buf["pvs"] == [51.0]
        assert buf["sps"] == [50.0]
        assert buf["cos"] == [45.0]

    def test_telemetry_ignores_non_dict_frame(self, main_window):
        """Non-dict frames should be silently ignored."""
        main_window._on_telemetry_for_trends(1, "not a dict")
        assert not hasattr(main_window, "_trend_buffers")


# --- Gaps #38-41: Executive dashboard KPIs ---

class TestExecutiveDashboardWiring:
    def test_controllers_loaded_populates_controller_cards(self, main_window):
        """After controllers load, exec dashboard should have cards."""
        controllers = [
            {
                "id": 1, "name": "FIC-101", "mode": "AUTO",
                "execution_mode": "DDC",
                "pv": 50.0, "sp": 50.0,
                "sp_hi_lim": 100.0, "sp_lo_lim": 0.0,
            },
            {
                "id": 2, "name": "LIC-201", "mode": "OOS",
                "execution_mode": "DDC",
                "pv": 65.0, "sp": 65.0,
                "sp_hi_lim": 100.0, "sp_lo_lim": 0.0,
            },
        ]
        main_window._on_controllers_received(controllers)
        cards = main_window._executive_page._controller_cards
        assert len(cards) == 2
        assert "FIC-101" in cards

    def test_controllers_loaded_updates_kpis(self, main_window):
        """Initial KPIs computed from controller list."""
        controllers = [
            {"id": 1, "name": "FIC-101", "mode": "AUTO", "pv": 50.0, "sp": 50.0},
            {"id": 2, "name": "LIC-201", "mode": "AUTO", "pv": 65.0, "sp": 65.0},
            {"id": 3, "name": "TIC-301", "mode": "MAN", "pv": 180.0, "sp": 180.0},
        ]
        main_window._on_controllers_received(controllers)
        assert main_window._executive_page._kpi_total.text() == "3"
        assert main_window._executive_page._kpi_auto.text() == "2"

    def test_kpi_timer_created(self, main_window):
        """KPI timer should exist but not be active before login."""
        assert main_window._kpi_timer is not None
        assert not main_window._kpi_timer.isActive()

    def test_kpi_data_signal_updates_dashboard(self, main_window):
        """_on_kpi_data_received should update executive dashboard KPIs."""
        main_window._cached_controllers = [
            {"id": 1, "name": "FIC-101", "mode": "AUTO", "pv": 50.0, "sp": 50.0},
        ]
        main_window._on_kpi_data_received({
            "active_alarms": 5,
            "stats": [],
        })
        assert main_window._executive_page._kpi_total.text() == "1"
        assert main_window._executive_page._kpi_auto.text() == "1"
        assert main_window._executive_page._kpi_alarms.text() == "5"


# --- Gap #44: ACK individual alarm ---

class TestAlarmAckWiring:
    def test_ack_single_connected(self, main_window, api_client):
        """ack_requested signal should call ack_alarm API."""
        with patch.object(main_window, "_safe_api_call") as mock_call:
            main_window._alarm_panel.ack_requested.emit(42)
            mock_call.assert_called_once_with(api_client.ack_alarm, 42)

    def test_send_ack_single(self, main_window, api_client):
        """_send_ack_single calls API with alarm_id."""
        with patch.object(main_window, "_safe_api_call") as mock_call:
            main_window._send_ack_single(99)
            mock_call.assert_called_once_with(api_client.ack_alarm, 99)


# --- SettingsPage refresh_rate_changed wiring ---

class TestRefreshRateWiring:
    def test_refresh_rate_changed_updates_bus_bridge(self, main_window, bus_bridge):
        """refresh_rate_changed signal should update BusBridge interval."""
        main_window._settings_page.refresh_rate_changed.emit(500)
        assert bus_bridge._refresh_ms == 500

    def test_bus_bridge_set_refresh_ms(self, bus_bridge):
        """BusBridge.set_refresh_ms updates the interval."""
        bus_bridge.set_refresh_ms(200)
        assert bus_bridge._refresh_ms == 200

    def test_bus_bridge_set_refresh_ms_while_running(self, bus_bridge):
        """set_refresh_ms updates a running timer's interval."""
        bus_bridge.start()
        try:
            bus_bridge.set_refresh_ms(250)
            assert bus_bridge._timer.interval() == 250
        finally:
            bus_bridge.stop()
