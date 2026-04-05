"""Application bootstrap — QApplication, MainWindow, service wiring."""
from __future__ import annotations

import logging
import sys
import threading
from typing import TYPE_CHECKING

from PySide6.QtCore import QMetaObject, Qt, Signal, Slot
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QLabel,
    QMainWindow,
    QStackedWidget,
    QToolBar,
    QWidget,
)

from smart_pid_hmi.bus_bridge import BusBridge
from smart_pid_hmi.config import HMISettings
from smart_pid_hmi.pages.alarm_panel import AlarmPanel
from smart_pid_hmi.pages.connection_page import ConnectionPage
from smart_pid_hmi.pages.dashboard_page import DashboardPage
from smart_pid_hmi.pages.executive_dashboard import ExecutiveDashboardPage
from smart_pid_hmi.pages.multi_trend_page import MultiTrendPage
from smart_pid_hmi.pages.settings_page import SettingsPage
from smart_pid_hmi.pages.user_management_page import UserManagementPage
from smart_pid_hmi.pages.simulator_page import SimulatorPage
from smart_pid_hmi.services.session import Session
from smart_pid_hmi.themes import DarkRoomTheme, ISA101Theme, MD3DarkTheme, ThemeManager

if TYPE_CHECKING:
    from smart_pid_hmi.services.ports import APIClientPort, TelemetrySourcePort

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Top-level window with page stack and toolbar."""

    # Thread-safe signals for cross-thread communication
    _login_error_signal = Signal(str)
    _controllers_loaded_signal = Signal(list)
    _api_error_signal = Signal(str)
    _users_loaded_signal = Signal(list)

    def __init__(
        self,
        settings: HMISettings,
        session: Session,
        api_client: APIClientPort,
        telemetry_source: TelemetrySourcePort,
        bus_bridge: BusBridge,
    ) -> None:
        super().__init__()
        self._settings = settings
        self._session = session
        self._api_client = api_client
        self._telemetry_source = telemetry_source
        self._bus_bridge = bus_bridge

        # Connect thread-safe signals
        self._login_error_signal.connect(self._on_login_error_received)
        self._controllers_loaded_signal.connect(self._on_controllers_received)
        self._api_error_signal.connect(self._on_api_error)
        self._users_loaded_signal.connect(self._on_users_loaded)

        self.setWindowTitle("Smart PID HMI")
        self.setMinimumSize(1024, 700)

        # Theme manager
        self._theme_manager = ThemeManager()
        isa_theme = ISA101Theme()
        self._theme_manager.register(isa_theme)
        self._theme_manager.register(DarkRoomTheme())
        self._theme_manager.register(MD3DarkTheme())
        self._theme_manager.set_theme("isa101")
        theme = isa_theme
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
        self._add_ctrl_btn = toolbar.addAction("+ Add Loop")
        self._add_ctrl_btn.triggered.connect(self._on_add_controller)
        self._add_ctrl_btn.setEnabled(False)  # enabled after login
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
        self._alarms_btn = toolbar.addAction("Alarms")
        self._alarms_btn.triggered.connect(
            lambda: self._stack.setCurrentWidget(self._alarm_panel)
        )
        self._executive_btn = toolbar.addAction("Executive")
        self._executive_btn.triggered.connect(
            lambda: self._stack.setCurrentWidget(self._executive_page)
        )
        self._trends_btn = toolbar.addAction("Trends")
        self._trends_btn.triggered.connect(
            lambda: self._stack.setCurrentWidget(self._multi_trend_page)
        )
        self._settings_btn = toolbar.addAction("Settings")
        self._settings_btn.triggered.connect(
            lambda: self._stack.setCurrentWidget(self._settings_page)
        )
        self._users_btn = toolbar.addAction("Users")
        self._users_btn.triggered.connect(
            lambda: self._show_users_page()
        )
        self._users_btn.setVisible(False)

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
        self._alarm_panel = AlarmPanel(theme=theme)
        self._stack.addWidget(self._alarm_panel)
        self._executive_page = ExecutiveDashboardPage()
        self._stack.addWidget(self._executive_page)
        self._multi_trend_page = MultiTrendPage()
        self._stack.addWidget(self._multi_trend_page)
        self._settings_page = SettingsPage(
            theme_manager=self._theme_manager,
            server_url=settings.server_url,
            zmq_url=settings.zmq_url,
        )
        self._stack.addWidget(self._settings_page)
        self._user_mgmt_page = UserManagementPage(theme=theme)
        self._stack.addWidget(self._user_mgmt_page)

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
        bus_bridge.alarm_received.connect(self._alarm_panel.on_alarm)
        self._alarm_panel.ack_all_requested.connect(self._send_ack_all)
        self._simulator_page.preset_changed.connect(self._send_sim_preset)
        self._simulator_page.parameters_changed.connect(self._send_sim_parameters)
        self._simulator_page.step_requested.connect(self._send_sim_step)
        self._simulator_page.noise_requested.connect(self._send_sim_noise)
        self._simulator_page.clear_disturbance_requested.connect(self._send_sim_clear)
        self._settings_page.theme_changed.connect(self._on_theme_switch)
        self._user_mgmt_page.user_create_requested.connect(self._create_user)
        self._user_mgmt_page.user_update_requested.connect(self._update_user)
        self._user_mgmt_page.user_deactivate_requested.connect(self._deactivate_user)
        self._user_mgmt_page.user_reactivate_requested.connect(self._reactivate_user)

    def _on_login(self, server_url: str, username: str, password: str) -> None:
        """Handle login in background thread."""
        # Update API client base URL to match what the user typed
        if hasattr(self._api_client, "set_base_url"):
            self._api_client.set_base_url(server_url)

        def do_login():
            try:
                resp = self._api_client.login(username, password)
                self._session.store_token(resp.access_token)
                QMetaObject.invokeMethod(
                    self, "_login_success", Qt.ConnectionType.QueuedConnection,
                )
            except Exception as e:
                logger.error("Login failed: %s", e)
                self._login_error_signal.emit(str(e))

        threading.Thread(target=do_login, daemon=True).start()

    @Slot()
    def _login_success(self) -> None:
        self._conn_indicator.setStyleSheet("color: green; background: transparent;")
        self._user_label.setText(self._session.username or "")
        self._add_ctrl_btn.setEnabled(True)
        self._telemetry_source.start()
        self._bus_bridge.start()
        self._load_dashboard()
        self._stack.setCurrentWidget(self._dashboard_page)
        self._check_simulator_available()
        self._show_admin_controls()

    @Slot(str)
    def _on_login_error_received(self, error_msg: str) -> None:
        """Handle login error via thread-safe signal."""
        self._connection_page.show_error(error_msg or "Login failed")

    def _on_add_controller(self) -> None:
        """Open dialog to create a new controller, then refresh dashboard."""
        from smart_pid_hmi.widgets.add_controller_dialog import AddControllerDialog

        dialog = AddControllerDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        data = dialog.get_data()

        def do_create():
            try:
                self._api_client.create_controller(data)
                self._load_dashboard()
            except Exception as e:
                logger.error("Failed to create controller: %s", e)
                self._api_error_signal.emit(str(e))

        threading.Thread(target=do_create, daemon=True).start()

    @Slot(list)
    def _on_controllers_received(self, controllers: list[dict]) -> None:
        """Handle controllers loaded via thread-safe signal."""
        self._dashboard_page.populate_controllers(controllers)
        self._simulator_page.populate_controllers(controllers)

    @Slot(str)
    def _on_api_error(self, error_msg: str) -> None:
        """Log API errors from background threads."""
        logger.error("API call failed: %s", error_msg)

    def _load_dashboard(self) -> None:
        """Load controllers from API and populate dashboard."""
        def do_load():
            try:
                controllers = self._api_client.list_controllers()
                controller_dicts = [c.model_dump() for c in controllers]
                self._controllers_loaded_signal.emit(controller_dicts)
            except Exception as e:
                logger.error("Failed to load controllers: %s", e)

        threading.Thread(target=do_load, daemon=True).start()

    def _safe_api_call(self, func, *args) -> None:
        """Run an API call in a background thread with error logging."""
        def wrapper():
            try:
                func(*args)
            except Exception as e:
                self._api_error_signal.emit(str(e))

        threading.Thread(target=wrapper, daemon=True).start()

    def _send_setpoint(self, controller_id: int, value: float) -> None:
        self._safe_api_call(self._api_client.set_setpoint, controller_id, value)

    def _send_mode(self, controller_id: int, mode: str) -> None:
        self._safe_api_call(self._api_client.set_mode, controller_id, mode)

    def _send_output(self, controller_id: int, value: float) -> None:
        self._safe_api_call(self._api_client.set_output, controller_id, value)

    def _send_ack_all(self) -> None:
        self._safe_api_call(self._api_client.ack_all_alarms)

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
        self._safe_api_call(self._api_client.set_simulator_preset, cid, preset)

    def _send_sim_parameters(
        self, gain: float, tau1: float, tau2: float, dead_time: float,
    ) -> None:
        cid = self._simulator_page.current_controller_id
        if cid is None:
            return
        tau2_val = tau2 if tau2 > 0 else None
        self._safe_api_call(
            self._api_client.set_simulator_parameters, cid, gain, tau1, tau2_val, dead_time,
        )

    def _send_sim_step(self, amplitude: float) -> None:
        cid = self._simulator_page.current_controller_id
        if cid is None:
            return
        self._safe_api_call(
            self._api_client.inject_simulator_disturbance, cid, "step", amplitude,
        )

    def _send_sim_noise(self, amplitude: float) -> None:
        cid = self._simulator_page.current_controller_id
        if cid is None:
            return
        self._safe_api_call(
            self._api_client.inject_simulator_disturbance, cid, "noise", amplitude,
        )

    def _send_sim_clear(self) -> None:
        cid = self._simulator_page.current_controller_id
        if cid is None:
            return
        self._safe_api_call(self._api_client.clear_simulator_disturbance, cid)

    def _on_theme_switch(self, name: str) -> None:
        """Apply the selected theme globally and propagate to child widgets."""
        self._theme_manager.set_theme(name)
        theme = self._theme_manager.current
        theme.apply(QApplication.instance())
        # Propagate theme to widgets that cache theme references
        for widget in self.findChildren(QWidget):
            if hasattr(widget, "apply_theme"):
                widget.apply_theme(theme)

    def _show_admin_controls(self) -> None:
        """Show admin-only UI elements based on session role."""
        is_admin = self._session.role and self._session.role.upper() == "ADMIN"
        self._users_btn.setVisible(is_admin)

    def _show_users_page(self) -> None:
        """Switch to user management page and refresh user list."""
        self._stack.setCurrentWidget(self._user_mgmt_page)
        self._load_users()

    def _load_users(self) -> None:
        """Load users from API and populate user management page."""
        def do_load():
            try:
                users = self._api_client.list_users()
                user_dicts = [u.model_dump() for u in users]
                self._users_loaded_signal.emit(user_dicts)
            except Exception as e:
                logger.error("Failed to load users: %s", e)

        threading.Thread(target=do_load, daemon=True).start()

    @Slot(list)
    def _on_users_loaded(self, users: list[dict]) -> None:
        """Populate user management page with loaded data."""
        self._user_mgmt_page.populate_users(users)
        self._user_mgmt_page.set_status(f"Loaded {len(users)} users")

    def _create_user(self, username: str, password: str, role: str) -> None:
        def do_create():
            try:
                self._api_client.create_user(username, password, role)
                self._load_users()
            except Exception as e:
                self._api_error_signal.emit(str(e))
        threading.Thread(target=do_create, daemon=True).start()

    def _update_user(self, user_id: int, role: str, password: str, active: object) -> None:
        def do_update():
            try:
                pw = password if password else None
                active_val = active if isinstance(active, bool) else None
                self._api_client.update_user(user_id, role=role, password=pw, active=active_val)
                self._load_users()
            except Exception as e:
                self._api_error_signal.emit(str(e))
        threading.Thread(target=do_update, daemon=True).start()

    def _deactivate_user(self, user_id: int) -> None:
        def do_deactivate():
            try:
                self._api_client.deactivate_user(user_id)
                self._load_users()
            except Exception as e:
                self._api_error_signal.emit(str(e))
        threading.Thread(target=do_deactivate, daemon=True).start()

    def _reactivate_user(self, user_id: int) -> None:
        def do_reactivate():
            try:
                self._api_client.update_user(user_id, active=True)
                self._load_users()
            except Exception as e:
                self._api_error_signal.emit(str(e))
        threading.Thread(target=do_reactivate, daemon=True).start()

    def closeEvent(self, event) -> None:  # noqa: N802
        self._bus_bridge.stop()
        self._telemetry_source.stop()
        if hasattr(self._api_client, "close"):
            self._api_client.close()
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
