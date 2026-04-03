"""Application bootstrap — QApplication, MainWindow, service wiring."""
from __future__ import annotations

import sys
import threading

from PySide6.QtCore import QMetaObject, Qt, Slot
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QMainWindow,
    QStackedWidget,
    QToolBar,
    QWidget,
)

from smart_pid_hmi.bus_bridge import BusBridge
from smart_pid_hmi.config import HMISettings
from smart_pid_hmi.pages.connection_page import ConnectionPage
from smart_pid_hmi.pages.dashboard_page import DashboardPage
from smart_pid_hmi.pages.simulator_page import SimulatorPage
from smart_pid_hmi.services.session import Session
from smart_pid_hmi.themes.isa101 import ISA101Theme


class MainWindow(QMainWindow):
    """Top-level window with page stack and toolbar."""

    def __init__(
        self,
        settings: HMISettings,
        session: Session,
        api_client: object,
        telemetry_source: object,
        bus_bridge: BusBridge,
    ) -> None:
        super().__init__()
        self._settings = settings
        self._session = session
        self._api_client = api_client
        self._telemetry_source = telemetry_source
        self._bus_bridge = bus_bridge
        self._login_error: str = ""
        self._pending_controllers: list[dict] = []

        self.setWindowTitle("Smart PID HMI")
        self.setMinimumSize(1024, 700)

        # Theme
        theme = ISA101Theme()
        theme.apply(QApplication.instance())

        # Toolbar
        toolbar = QToolBar("Main")
        toolbar.setMovable(False)
        app_label = QLabel("  Smart PID  ")
        app_label.setStyleSheet(
            f"font-weight: bold; font-size: {theme.font_size_title}px; "
            f"color: {theme.fg_primary}; background: transparent;"
        )
        toolbar.addWidget(app_label)
        toolbar.addSeparator()

        self._conn_indicator = QLabel(" \u25cf ")
        self._conn_indicator.setStyleSheet("color: red; background: transparent;")
        toolbar.addWidget(self._conn_indicator)

        self._user_label = QLabel("")
        self._user_label.setStyleSheet(
            f"color: {theme.fg_secondary}; background: transparent; padding-left: 8px;"
        )
        toolbar.addWidget(self._user_label)

        toolbar.addSeparator()
        self._dashboard_btn = toolbar.addAction("Dashboard")
        self._dashboard_btn.triggered.connect(
            lambda: self._stack.setCurrentWidget(self._dashboard_page)
        )
        self._simulator_btn = toolbar.addAction("Simulator")
        self._simulator_btn.triggered.connect(
            lambda: self._stack.setCurrentWidget(self._simulator_page)
        )
        self._simulator_btn.setEnabled(False)  # enabled after login if backend has simulator

        spacer = QWidget()
        toolbar.addWidget(spacer)
        self.addToolBar(toolbar)

        # Pages
        self._stack = QStackedWidget()
        self.setCentralWidget(self._stack)

        self._connection_page = ConnectionPage(theme=theme, default_url=settings.server_url)
        self._dashboard_page = DashboardPage(theme=theme, bus_bridge=bus_bridge)
        self._stack.addWidget(self._connection_page)
        self._stack.addWidget(self._dashboard_page)
        self._simulator_page = SimulatorPage(theme=theme)
        self._stack.addWidget(self._simulator_page)

        # Wire signals
        self._connection_page.login_requested.connect(self._on_login)
        self._dashboard_page.setpoint_requested.connect(self._send_setpoint)
        self._dashboard_page.mode_requested.connect(self._send_mode)
        self._dashboard_page.output_requested.connect(self._send_output)
        bus_bridge.connection_lost.connect(
            lambda: self._conn_indicator.setStyleSheet("color: red; background: transparent;")
        )
        bus_bridge.connection_restored.connect(
            lambda: self._conn_indicator.setStyleSheet("color: green; background: transparent;")
        )
        self._simulator_page.preset_changed.connect(self._send_sim_preset)
        self._simulator_page.parameters_changed.connect(self._send_sim_parameters)
        self._simulator_page.step_requested.connect(self._send_sim_step)
        self._simulator_page.noise_requested.connect(self._send_sim_noise)
        self._simulator_page.clear_disturbance_requested.connect(self._send_sim_clear)

    def _on_login(self, server_url: str, username: str, password: str) -> None:
        """Handle login in background thread."""
        def do_login():
            try:
                resp = self._api_client.login(username, password)
                self._session.store_token(resp.access_token)
                QMetaObject.invokeMethod(
                    self, "_login_success", Qt.ConnectionType.QueuedConnection,
                )
            except Exception as e:
                self._login_error = str(e)
                QMetaObject.invokeMethod(
                    self, "_login_failed", Qt.ConnectionType.QueuedConnection,
                )

        threading.Thread(target=do_login, daemon=True).start()

    @Slot()
    def _login_success(self) -> None:
        self._conn_indicator.setStyleSheet("color: green; background: transparent;")
        self._user_label.setText(self._session.username or "")
        self._telemetry_source.start()
        self._bus_bridge.start()
        self._load_dashboard()
        self._stack.setCurrentWidget(self._dashboard_page)
        self._check_simulator_available()

    @Slot()
    def _login_failed(self) -> None:
        self._connection_page.show_error(self._login_error or "Login failed")

    def _load_dashboard(self) -> None:
        """Load controllers from API and populate dashboard."""
        def do_load():
            try:
                controllers = self._api_client.list_controllers()
                self._pending_controllers = [c.model_dump() for c in controllers]
                QMetaObject.invokeMethod(
                    self, "_populate_dashboard", Qt.ConnectionType.QueuedConnection,
                )
            except Exception:
                pass  # Dashboard stays empty; user can retry

        threading.Thread(target=do_load, daemon=True).start()

    @Slot()
    def _populate_dashboard(self) -> None:
        self._dashboard_page.populate_controllers(self._pending_controllers)
        self._simulator_page.populate_controllers(self._pending_controllers)

    def _send_setpoint(self, controller_id: int, value: float) -> None:
        threading.Thread(
            target=lambda: self._api_client.set_setpoint(controller_id, value),
            daemon=True,
        ).start()

    def _send_mode(self, controller_id: int, mode: str) -> None:
        threading.Thread(
            target=lambda: self._api_client.set_mode(controller_id, mode),
            daemon=True,
        ).start()

    def _send_output(self, controller_id: int, value: float) -> None:
        threading.Thread(
            target=lambda: self._api_client.set_output(controller_id, value),
            daemon=True,
        ).start()

    def _check_simulator_available(self) -> None:
        """Check if backend has simulator and enable button if so."""
        def do_check():
            try:
                status = self._api_client.get_simulator_status()
                if status.enabled:
                    QMetaObject.invokeMethod(
                        self, "_enable_simulator", Qt.ConnectionType.QueuedConnection,
                    )
            except Exception:
                pass  # Not available — button stays disabled

        threading.Thread(target=do_check, daemon=True).start()

    @Slot()
    def _enable_simulator(self) -> None:
        self._simulator_btn.setEnabled(True)

    def _send_sim_preset(self, preset: str) -> None:
        cid = self._simulator_page.current_controller_id
        if cid is None:
            return
        threading.Thread(
            target=lambda: self._api_client.set_simulator_preset(cid, preset),
            daemon=True,
        ).start()

    def _send_sim_parameters(self, gain: float, tau1: float, tau2: float, dead_time: float) -> None:
        cid = self._simulator_page.current_controller_id
        if cid is None:
            return
        tau2_val = tau2 if tau2 > 0 else None
        threading.Thread(
            target=lambda: self._api_client.set_simulator_parameters(
                cid, gain, tau1, tau2_val, dead_time,
            ),
            daemon=True,
        ).start()

    def _send_sim_step(self, amplitude: float) -> None:
        cid = self._simulator_page.current_controller_id
        if cid is None:
            return
        threading.Thread(
            target=lambda: self._api_client.inject_simulator_disturbance(cid, "step", amplitude),
            daemon=True,
        ).start()

    def _send_sim_noise(self, amplitude: float) -> None:
        cid = self._simulator_page.current_controller_id
        if cid is None:
            return
        threading.Thread(
            target=lambda: self._api_client.inject_simulator_disturbance(cid, "noise", amplitude),
            daemon=True,
        ).start()

    def _send_sim_clear(self) -> None:
        cid = self._simulator_page.current_controller_id
        if cid is None:
            return
        threading.Thread(
            target=lambda: self._api_client.clear_simulator_disturbance(cid),
            daemon=True,
        ).start()

    def closeEvent(self, event) -> None:  # noqa: N802
        self._bus_bridge.stop()
        self._telemetry_source.stop()
        super().closeEvent(event)


def main() -> None:
    """Entry point for the HMI application."""
    settings = HMISettings()
    session = Session()

    if settings.mock_mode:
        from smart_pid_hmi.services.mock_service import MockAPIClient, MockTelemetrySource

        api_client = MockAPIClient()
        telemetry_source = MockTelemetrySource()
    else:
        from smart_pid_hmi.services.api_client import APIClient
        from smart_pid_hmi.services.telemetry_sub import TelemetrySub

        api_client = APIClient(base_url=settings.server_url, session=session)
        telemetry_source = TelemetrySub(zmq_url=settings.zmq_url)

    bus_bridge = BusBridge(queue=telemetry_source.queue, refresh_ms=settings.refresh_ms)

    app = QApplication(sys.argv)
    window = MainWindow(
        settings=settings,
        session=session,
        api_client=api_client,
        telemetry_source=telemetry_source,
        bus_bridge=bus_bridge,
    )
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
