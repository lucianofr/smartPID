"""Application bootstrap — QApplication, MainWindow, service wiring."""
from __future__ import annotations

import logging
import sys
import threading
from typing import TYPE_CHECKING

from PySide6.QtCore import Q_ARG, QMetaObject, Qt, QTimer, Signal, Slot
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QToolBar,
    QWidget,
)

from smart_pid_hmi.bus_bridge import BusBridge
from smart_pid_hmi.config import HMISettings, ensure_config_file
from smart_pid_hmi.pages.alarm_panel import AlarmPanel
from smart_pid_hmi.pages.connection_page import ConnectionPage
from smart_pid_hmi.pages.dashboard_page import DashboardPage
from smart_pid_hmi.pages.executive_dashboard import ExecutiveDashboardPage
from smart_pid_hmi.pages.multi_trend_page import MultiTrendPage
from smart_pid_hmi.pages.settings_page import SettingsPage
from smart_pid_hmi.pages.simulator_page import SimulatorPage
from smart_pid_hmi.pages.user_management_page import UserManagementPage
from smart_pid_hmi.services.app_state import AppStateManager
from smart_pid_hmi.services.session import Session
from smart_pid_hmi.themes import (
    DarkRoomTheme,
    HPCLightTheme,
    ISA101Theme,
    MD3DarkTheme,
    MD3LightTheme,
    OceanTheme,
    ThemeManager,
)

if TYPE_CHECKING:
    from smart_pid_hmi.services.ports import APIClientPort, TelemetrySourcePort

logger = logging.getLogger(__name__)

# Maps between dialog flat keys and AlarmType enum values
_ALARM_KEY_TO_TYPE = {
    "hihi": "HIHI",
    "hi": "HI",
    "lo": "LO",
    "lolo": "LOLO",
    "dv_hi": "DV_HI",
    "dv_lo": "DV_LO",
}
_ALARM_TYPE_TO_KEY = {v: k for k, v in _ALARM_KEY_TO_TYPE.items()}


def _flat_alarm_to_thresholds(flat: dict) -> list[dict]:
    """Convert flat alarm dict from dialog to list of AlarmThreshold dicts."""
    deadband = flat.get("deadband_percent", 1.0)
    thresholds: list[dict] = []
    for key, alarm_type in _ALARM_KEY_TO_TYPE.items():
        thresholds.append({
            "alarm_type": alarm_type,
            "enabled": flat.get(f"{key}_enabled", False),
            "limit": flat.get(f"{key}_value", 0.0),
            "priority": flat.get(f"{key}_priority", "WARNING"),
            "deadband": deadband,
            "delay_on_s": flat.get(f"{key}_delay_on_s", 0.0),
            "delay_off_s": flat.get(f"{key}_delay_off_s", 0.0),
        })
    return thresholds


def _alarm_thresholds_to_flat(thresholds: list[dict]) -> dict:
    """Convert list of AlarmThreshold dicts to flat alarm dict for dialog."""
    flat: dict[str, object] = {}
    deadband = 1.0
    for t in thresholds:
        key = _ALARM_TYPE_TO_KEY.get(t.get("alarm_type", ""), "")
        if not key:
            continue
        flat[f"{key}_enabled"] = t.get("enabled", False)
        flat[f"{key}_value"] = t.get("limit", 0.0)
        flat[f"{key}_priority"] = t.get("priority", "WARNING")
        flat[f"{key}_delay_on_s"] = t.get("delay_on_s", 0.0)
        flat[f"{key}_delay_off_s"] = t.get("delay_off_s", 0.0)
        deadband = t.get("deadband", deadband)
    flat["deadband_percent"] = deadband
    return flat


class MainWindow(QMainWindow):
    """Top-level window with page stack and toolbar."""

    # Thread-safe signals for cross-thread communication
    _login_error_signal = Signal(str)
    _controllers_loaded_signal = Signal(list)
    _api_error_signal = Signal(str)
    _users_loaded_signal = Signal(list)
    _kpi_data_signal = Signal(dict)  # KPI + performance data from background
    _edit_dialog_signal = Signal(int, object)
    _project_info_signal = Signal(str, str, int)  # (name, path, controller_count)
    _sim_controllers_signal = Signal(list)  # populate simulator combo from sim status
    _opcua_status_signal = Signal(bool)  # OPC-UA connection status from watchdog
    _stats_signal = Signal(int, dict)  # (controller_id, stats_dict)
    _exec_cards_signal = Signal(list)  # enriched controller dicts for executive cards
    _sim_live_signal = Signal(dict)  # simulator live values from poll
    _ai_status_signal = Signal(int, str, bool)  # (controller_id, engine, running)
    _controller_updated_signal = Signal(int, object)  # (controller_id, controller_dict)

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
        self._app_state = AppStateManager(settings.app_state_path)

        # Connect thread-safe signals
        self._login_error_signal.connect(self._on_login_error_received)
        self._controllers_loaded_signal.connect(self._on_controllers_received)
        self._api_error_signal.connect(self._on_api_error)
        self._users_loaded_signal.connect(self._on_users_loaded)
        self._kpi_data_signal.connect(self._on_kpi_data_received)
        self._edit_dialog_signal.connect(self._open_edit_dialog)
        self._controller_updated_signal.connect(self._on_controller_updated)
        self._project_info_signal.connect(self._on_project_info_received)
        self._opcua_status_signal.connect(self._on_opcua_status_received)
        # Cached controller list for KPI computation
        self._cached_controllers: list[dict] = []

        # KPI refresh timer (started after login)
        self._kpi_timer = QTimer(self)
        self._kpi_timer.timeout.connect(self._refresh_kpis)

        # Executive cards polling timer (2s interval)
        self._exec_cards_timer = QTimer(self)
        self._exec_cards_timer.timeout.connect(self._refresh_exec_cards)
        self._exec_cards_signal.connect(self._on_exec_cards_received)

        # Simulator live values polling timer (2s interval)
        self._sim_poll_timer = QTimer(self)
        self._sim_poll_timer.timeout.connect(self._poll_sim_status)

        # OPC-UA connection watchdog (5s interval, started after first connect)
        self._opcua_watchdog = QTimer(self)
        self._opcua_watchdog.timeout.connect(self._poll_opcua_status)
        self._opcua_connected = False

        # Performance stats polling timer (2s interval, started after login)
        self._stats_timer = QTimer(self)
        self._stats_timer.timeout.connect(self._poll_stats)
        self._stats_signal.connect(self._on_stats_received)
        self._sim_live_signal.connect(self._on_sim_live_received)
        self._ai_status_signal.connect(self._on_ai_status_received)

        self.setWindowTitle("Smart PID HMI")
        self.setMinimumSize(1024, 700)

        # Theme manager
        self._theme_manager = ThemeManager()
        isa_theme = ISA101Theme()
        self._theme_manager.register(isa_theme)
        self._theme_manager.register(DarkRoomTheme())
        self._theme_manager.register(MD3DarkTheme())
        self._theme_manager.register(MD3LightTheme())
        self._theme_manager.register(HPCLightTheme())
        self._theme_manager.register(OceanTheme())
        initial_theme = self._app_state.last_theme or "isa101"
        self._theme_manager.set_theme(initial_theme)
        theme = self._theme_manager.current
        theme.apply(QApplication.instance())

        # Toolbar — polished header bar
        self._toolbar = QToolBar("Main")
        self._toolbar.setMovable(False)
        self._toolbar.setFixedHeight(48)
        self._toolbar.setStyleSheet(
            f"QToolBar {{ background-color: {theme.bg_toolbar};"
            f" border-bottom: 1px solid {theme.border}; }}"
        )

        # --- Left: app title ---
        app_label = QLabel(
            "\u2699 Smart PID Edge Optimizer"
        )
        app_label.setStyleSheet(
            f"font-weight: bold;"
            f" font-size: {theme.font_size_title + 2}px;"
            f" color: {theme.fg_primary};"
            " background: transparent;"
            " padding: 0 12px;"
        )
        self._toolbar.addWidget(app_label)
        self._app_label = app_label

        # --- Connection indicator (larger dot) ---
        self._conn_indicator = QLabel(" \u25cf ")
        self._conn_indicator.setStyleSheet(
            "color: red; background: transparent;"
            " font-size: 18px; padding: 0 4px;"
        )
        self._toolbar.addWidget(self._conn_indicator)

        # --- Center: navigation buttons ---
        nav_container = QWidget()
        nav_container.setStyleSheet("background: transparent;")
        nav_layout = QHBoxLayout(nav_container)
        nav_layout.setContentsMargins(8, 0, 8, 0)
        nav_layout.setSpacing(2)

        self._nav_buttons: list[QPushButton] = []
        self._active_nav_btn: QPushButton | None = None

        def _make_nav_btn(label: str) -> QPushButton:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setStyleSheet(self._nav_btn_style(theme, False))
            btn.setFixedHeight(34)
            btn.setMinimumWidth(80)
            self._nav_buttons.append(btn)
            nav_layout.addWidget(btn)
            return btn

        self._dashboard_nav = _make_nav_btn("Dashboard")
        self._simulator_nav = _make_nav_btn("Simulator")
        self._alarms_nav = _make_nav_btn("Alarms")
        self._executive_nav = _make_nav_btn("Executive")
        self._trends_nav = _make_nav_btn("Multi-Trend")
        self._settings_nav = _make_nav_btn("Settings")
        self._users_nav = _make_nav_btn("Admin")
        self._users_nav.setVisible(False)

        self._toolbar.addWidget(nav_container)

        # --- Right side spacer + user label + add loop ---
        right_spacer = QWidget()
        right_spacer.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred,
        )
        right_spacer.setStyleSheet("background: transparent;")
        self._toolbar.addWidget(right_spacer)

        self._add_ctrl_btn = self._toolbar.addAction("+ Add Loop")
        self._add_ctrl_btn.triggered.connect(self._on_add_controller)
        self._add_ctrl_btn.setEnabled(False)

        self._user_label = QLabel("")
        self._user_label.setStyleSheet(
            f"color: {theme.fg_secondary};"
            " background: transparent; padding: 0 12px;"
        )
        self._toolbar.addWidget(self._user_label)

        self.addToolBar(self._toolbar)

        # Backward-compat references used by tests
        self._simulator_btn = self._simulator_nav
        self._users_btn = self._users_nav
        self._dashboard_btn = self._dashboard_nav
        self._alarms_btn = self._alarms_nav
        self._executive_btn = self._executive_nav
        self._trends_btn = self._trends_nav
        self._settings_btn = self._settings_nav

        # Pages
        self._stack = QStackedWidget()
        self.setCentralWidget(self._stack)

        self._connection_page = ConnectionPage(
            theme=theme, default_url=settings.server_url,
        )
        self._dashboard_page = DashboardPage(
            theme=theme, bus_bridge=bus_bridge,
        )
        self._stack.addWidget(self._connection_page)
        self._stack.addWidget(self._dashboard_page)
        self._simulator_page = SimulatorPage(theme=theme)
        self._stack.addWidget(self._simulator_page)
        self._alarm_panel = AlarmPanel(theme=theme)
        self._stack.addWidget(self._alarm_panel)
        self._executive_page = ExecutiveDashboardPage(theme=theme)
        self._stack.addWidget(self._executive_page)
        self._multi_trend_page = MultiTrendPage(theme=theme)
        self._stack.addWidget(self._multi_trend_page)
        self._settings_page = SettingsPage(
            theme_manager=self._theme_manager,
            server_url=settings.server_url,
            zmq_url=settings.zmq_url,
        )
        self._stack.addWidget(self._settings_page)
        self._user_mgmt_page = UserManagementPage(theme=theme)
        self._stack.addWidget(self._user_mgmt_page)

        # Nav button -> page mapping and wiring
        self._nav_page_map: dict[QPushButton, QWidget] = {
            self._dashboard_nav: self._dashboard_page,
            self._simulator_nav: self._simulator_page,
            self._alarms_nav: self._alarm_panel,
            self._executive_nav: self._executive_page,
            self._trends_nav: self._multi_trend_page,
            self._settings_nav: self._settings_page,
            self._users_nav: self._user_mgmt_page,
        }
        for btn, page in self._nav_page_map.items():
            if btn is self._users_nav:
                btn.clicked.connect(
                    lambda _=False, b=btn: (
                        self._set_active_nav(b),
                        self._show_users_page(),
                    )
                )
            else:
                btn.clicked.connect(
                    lambda _=False, p=page, b=btn: (
                        self._set_active_nav(b),
                        self._stack.setCurrentWidget(p),
                    )
                )

        # Wire signals
        self._connection_page.login_requested.connect(self._on_login)
        self._dashboard_page.setpoint_requested.connect(self._send_setpoint)
        self._dashboard_page.mode_requested.connect(self._send_mode)
        self._dashboard_page.gains_changed.connect(self._send_tuning)
        self._dashboard_page.output_requested.connect(self._send_output)
        self._dashboard_page.settings_requested.connect(self._on_edit_controller)
        bus_bridge.connection_lost.connect(
            lambda: self._conn_indicator.setStyleSheet(
                "color: red; background: transparent;"
                " font-size: 18px; padding: 0 4px;"
            )
        )
        bus_bridge.connection_restored.connect(
            lambda: self._conn_indicator.setStyleSheet(
                "color: #00C853; background: transparent;"
                " font-size: 18px; padding: 0 4px;"
            )
        )
        bus_bridge.alarm_received.connect(self._alarm_panel.on_alarm)
        bus_bridge.ai_action_received.connect(self._on_ai_action)
        self._alarm_panel.ack_all_requested.connect(self._send_ack_all)
        self._alarm_panel.ack_requested.connect(self._send_ack_single)
        self._simulator_page.preset_changed.connect(self._send_sim_preset)
        self._simulator_page.parameters_changed.connect(self._send_sim_parameters)
        self._simulator_page.step_requested.connect(self._send_sim_step)
        self._simulator_page.noise_requested.connect(self._send_sim_noise)
        self._simulator_page.clear_disturbance_requested.connect(self._send_sim_clear)
        self._simulator_page.pid_enabled_changed.connect(self._send_sim_pid_enable)
        self._simulator_page.pid_params_changed.connect(self._send_sim_pid_params)
        self._simulator_page.pid_mode_changed.connect(self._send_sim_pid_mode)
        self._simulator_page.auto_sp_changed.connect(self._send_sim_auto_sp)
        self._simulator_page.auto_disturbance_changed.connect(self._send_sim_auto_dist)
        self._simulator_page.sim_start_requested.connect(self._send_sim_start)
        self._simulator_page.sim_stop_requested.connect(self._send_sim_stop)
        self._simulator_page.opcua_start_requested.connect(self._send_opcua_start)
        self._simulator_page.opcua_stop_requested.connect(self._send_opcua_stop)
        self._simulator_page.pid_sp_changed.connect(self._send_sim_pid_sp)
        self._simulator_page.pid_co_changed.connect(self._send_sim_pid_co)
        self._sim_controllers_signal.connect(self._simulator_page.populate_controllers)
        self._settings_page.theme_changed.connect(self._on_theme_switch)
        self._settings_page.refresh_rate_changed.connect(self._on_refresh_rate_changed)
        self._settings_page.opcua_connect_requested.connect(self._on_opcua_connect)
        self._settings_page.opcua_disconnect_requested.connect(self._on_opcua_disconnect)
        self._settings_page.opcua_endpoint_save_requested.connect(
            self._on_opcua_endpoint_save,
        )
        self._settings_page.project_new_requested.connect(self._show_project_dialog)
        self._settings_page.project_open_requested.connect(self._show_project_dialog)
        self._settings_page.project_download_requested.connect(self._on_project_download)
        self._settings_page.project_import_requested.connect(self._show_project_dialog)

        bus_bridge.telemetry_received.connect(self._on_telemetry_for_trends)
        self._user_mgmt_page.user_create_requested.connect(self._create_user)
        self._user_mgmt_page.user_update_requested.connect(self._update_user)
        self._user_mgmt_page.user_deactivate_requested.connect(self._deactivate_user)
        self._user_mgmt_page.user_reactivate_requested.connect(self._reactivate_user)

        # Optimizer signals from faceplate
        faceplate = self._dashboard_page._faceplate  # noqa: SLF001
        faceplate.optimizer_run_requested.connect(self._send_optimizer_start)
        faceplate.optimizer_stop_requested.connect(
            self._send_optimizer_stop,
        )

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
        self._conn_indicator.setStyleSheet(
            "color: #00C853; background: transparent;"
            " font-size: 18px; padding: 0 4px;"
        )
        self._set_active_nav(self._dashboard_nav)
        self._user_label.setText(self._session.username or "")
        self._telemetry_source.start()
        self._bus_bridge.start()
        self._stack.setCurrentWidget(self._dashboard_page)
        self._load_dashboard()
        self._check_simulator_available()
        self._show_admin_controls()
        self._alarm_panel.load_active_alarms()
        self._kpi_timer.start(30_000)
        self._stats_timer.start(2000)
        self._exec_cards_timer.start(2000)

        # Check if backend has a managed project active
        QTimer.singleShot(500, self._check_active_project)

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

    def _on_edit_controller(self, controller_id: int) -> None:
        """Fetch controller data in background, then open edit dialog via signal."""

        def do_fetch():
            try:
                ctrl = self._api_client.get_controller(controller_id)
                data = ctrl.model_dump()
                # Fetch alarm config and convert to flat format for dialog
                try:
                    alarm_resp = self._api_client.get_alarm_config(controller_id)
                    logger.debug(
                        "Loaded alarm config for controller %d: %s",
                        controller_id, alarm_resp,
                    )
                    data["alarm_config"] = _alarm_thresholds_to_flat(
                        alarm_resp.get("thresholds", []),
                    )
                except Exception:
                    logger.debug(
                        "No alarm config for controller %d",
                        controller_id, exc_info=True,
                    )
                self._edit_dialog_signal.emit(controller_id, data)
            except Exception as e:
                logger.error("Failed to fetch controller %d: %s", controller_id, e)
                self._api_error_signal.emit(str(e))

        threading.Thread(target=do_fetch, daemon=True).start()

    @Slot(int, object)
    def _open_edit_dialog(self, controller_id: int, data: dict) -> None:
        """Open the edit dialog on the GUI thread with pre-fetched data."""
        from smart_pid_hmi.widgets.controller_dialog import ControllerDialog

        dialog = ControllerDialog(edit_data=data, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        updated = dialog.get_controller_data()
        alarm_data = updated.pop("alarm_config", None)

        def do_update():
            try:
                self._api_client.update_controller(controller_id, updated)
                if alarm_data is not None:
                    thresholds = _flat_alarm_to_thresholds(alarm_data)
                    logger.debug(
                        "Saving alarm config for controller %d: %s",
                        controller_id, thresholds,
                    )
                    self._api_client.update_alarm_config(
                        controller_id, {"thresholds": thresholds},
                    )
                ctrl = self._api_client.get_controller(controller_id)
                self._controller_updated_signal.emit(
                    controller_id, ctrl.model_dump(),
                )
            except Exception as e:
                logger.error("Failed to update controller %d: %s", controller_id, e)
                self._api_error_signal.emit(str(e))

        threading.Thread(target=do_update, daemon=True).start()

    @Slot(list)
    def _on_controllers_received(self, controllers: list[dict]) -> None:
        """Handle controllers loaded via thread-safe signal."""
        self._cached_controllers = controllers
        self._dashboard_page.populate_controllers(controllers)
        # Simulator combo populated separately from simulator status

        # Feed multi-trend page with available loop names
        loop_names = [c.get("name", f"Loop-{c.get('id', '?')}") for c in controllers]
        self._multi_trend_page.set_available_loops(loop_names)

        # Feed executive dashboard controller cards
        self._executive_page.update_controller_cards(controllers)

        # Also compute initial KPIs from controller data
        total = len(controllers)
        in_auto = sum(1 for c in controllers if c.get("mode") == "AUTO")
        self._executive_page.update_kpis(
            total=total,
            in_auto=in_auto,
            active_alarms=0,
            ai_active=0,
        )

    @Slot(int, object)
    def _on_controller_updated(self, controller_id: int, ctrl: dict) -> None:
        """Refresh a single controller's metadata without resetting the chart."""
        # Update cached list
        for i, c in enumerate(self._cached_controllers):
            if c.get("id") == controller_id:
                self._cached_controllers[i] = ctrl
                break

        self._dashboard_page.update_single_controller(controller_id, ctrl)
        self._executive_page.update_controller_cards(self._cached_controllers)

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

    def _send_ack_single(self, alarm_id: int) -> None:
        """ACK a single alarm by id."""
        self._safe_api_call(self._api_client.ack_alarm, alarm_id)

    def _send_ack_all(self) -> None:
        self._safe_api_call(self._api_client.ack_all_alarms)

    def _send_tuning(self, controller_id: int, gains: dict) -> None:
        self._safe_api_call(
            self._api_client.write_tuning, controller_id,
            gains.get("gain", 0.0), gains.get("reset", 0.0),
            gains.get("rate", 0.0),
        )

    def _send_optimizer_start(self, controller_id: int) -> None:
        self._safe_api_call(
            self._api_client.start_optimizer, controller_id,
        )

    def _send_optimizer_stop(self, controller_id: int) -> None:
        self._safe_api_call(
            self._api_client.stop_optimizer, controller_id,
        )

    def _check_simulator_available(self) -> None:
        """Check if backend has simulator and enable button if so."""
        def do_check():
            try:
                status = self._api_client.get_simulator_status()
                if status.enabled:
                    QMetaObject.invokeMethod(
                        self, "_enable_simulator", Qt.ConnectionType.QueuedConnection,
                    )
                if status.running:
                    QMetaObject.invokeMethod(
                        self._simulator_page, "set_sim_running",
                        Qt.ConnectionType.QueuedConnection,
                        Q_ARG(bool, True),
                    )
                    self._refresh_sim_controllers()
                    QMetaObject.invokeMethod(
                        self._sim_poll_timer, "start",
                        Qt.ConnectionType.QueuedConnection,
                        Q_ARG(int, 2000),
                    )
                opcua_status = self._api_client.get_opcua_status()
                if opcua_status.get("running"):
                    QMetaObject.invokeMethod(
                        self._simulator_page, "set_opcua_running",
                        Qt.ConnectionType.QueuedConnection,
                        Q_ARG(bool, True),
                    )
            except Exception:
                pass  # Not available — button stays disabled

        threading.Thread(target=do_check, daemon=True).start()

    def _refresh_sim_controllers(self) -> None:
        """Fetch simulator status and populate the simulator combo box."""
        try:
            status = self._api_client.get_simulator_status()
            sim_ctrls = [
                {"name": f"Sim Loop {cid}", "id": cid}
                for cid in status.controllers
            ]
            self._sim_controllers_signal.emit(sim_ctrls)
        except Exception:
            pass

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

    def _send_sim_pid_enable(self, enabled: bool) -> None:
        cid = self._simulator_page.current_controller_id
        if cid is None:
            return
        self._safe_api_call(self._api_client.enable_simulator_pid, cid, enabled)

    def _send_sim_pid_params(self, kp: float, ti: float, td: float) -> None:
        cid = self._simulator_page.current_controller_id
        if cid is None:
            return
        self._safe_api_call(self._api_client.set_simulator_pid_params, cid, kp, ti, td)

    def _send_sim_pid_mode(self, mode: str) -> None:
        cid = self._simulator_page.current_controller_id
        if cid is None:
            return
        self._safe_api_call(self._api_client.set_simulator_pid_mode, cid, mode)

    def _send_sim_auto_sp(self, enabled: bool, sp_min_pct: float, sp_max_pct: float) -> None:
        cid = self._simulator_page.current_controller_id
        if cid is None:
            return
        self._safe_api_call(
            self._api_client.set_simulator_auto_sp, cid, enabled, sp_min_pct, sp_max_pct,
        )

    def _send_sim_auto_dist(self, enabled: bool, max_amplitude_pct: float) -> None:
        cid = self._simulator_page.current_controller_id
        if cid is None:
            return
        self._safe_api_call(
            self._api_client.set_simulator_auto_disturbance, cid, enabled, max_amplitude_pct,
        )

    def _send_sim_start(self) -> None:
        def do_start():
            try:
                self._api_client.start_simulator()
                QMetaObject.invokeMethod(
                    self._simulator_page, "set_sim_running",
                    Qt.ConnectionType.QueuedConnection,
                    Q_ARG(bool, True),
                )
                # Populate simulator combo from actual simulator controllers
                self._refresh_sim_controllers()
                # Start polling live values
                QMetaObject.invokeMethod(
                    self._sim_poll_timer, "start",
                    Qt.ConnectionType.QueuedConnection,
                    Q_ARG(int, 2000),
                )
            except Exception as e:
                self._api_error_signal.emit(str(e))
        threading.Thread(target=do_start, daemon=True).start()

    def _send_sim_stop(self) -> None:
        def do_stop():
            try:
                self._api_client.stop_simulator()
                QMetaObject.invokeMethod(
                    self._simulator_page, "set_sim_running",
                    Qt.ConnectionType.QueuedConnection,
                    Q_ARG(bool, False),
                )
                QMetaObject.invokeMethod(
                    self._sim_poll_timer, "stop",
                    Qt.ConnectionType.QueuedConnection,
                )
            except Exception as e:
                self._api_error_signal.emit(str(e))
        threading.Thread(target=do_stop, daemon=True).start()

    def _send_opcua_start(self) -> None:
        def do_start():
            try:
                self._api_client.start_opcua_server()
                QMetaObject.invokeMethod(
                    self._simulator_page, "set_opcua_running",
                    Qt.ConnectionType.QueuedConnection,
                    Q_ARG(bool, True),
                )
            except Exception as e:
                self._api_error_signal.emit(str(e))
        threading.Thread(target=do_start, daemon=True).start()

    def _send_opcua_stop(self) -> None:
        def do_stop():
            try:
                self._api_client.stop_opcua_server()
                QMetaObject.invokeMethod(
                    self._simulator_page, "set_opcua_running",
                    Qt.ConnectionType.QueuedConnection,
                    Q_ARG(bool, False),
                )
            except Exception as e:
                self._api_error_signal.emit(str(e))
        threading.Thread(target=do_stop, daemon=True).start()

    def _send_sim_pid_sp(self, sp: float) -> None:
        cid = self._simulator_page.current_controller_id
        if cid is None:
            return
        self._safe_api_call(self._api_client.set_simulator_pid_sp, cid, sp)

    def _send_sim_pid_co(self, co: float) -> None:
        cid = self._simulator_page.current_controller_id
        if cid is None:
            return
        self._safe_api_call(self._api_client.set_simulator_co, cid, co)

    def _poll_sim_status(self) -> None:
        """Poll simulator status and update live values on the simulator page."""
        cid = self._simulator_page.current_controller_id
        if cid is None:
            logger.debug("sim poll: no controller selected, skipping")
            return

        def do_poll():
            try:
                status = self._api_client.get_simulator_status()
                if not status.controllers:
                    logger.debug(
                        "sim poll: backend has 0 controllers registered in simulator"
                    )
                    return
                ctrl_status = status.controllers.get(cid)
                if ctrl_status is None:
                    logger.debug(
                        "sim poll: controller %d not in simulator (available: %s)",
                        cid, list(status.controllers.keys()),
                    )
                    return
                data: dict = {
                    "pv": ctrl_status.pv,
                    "co": ctrl_status.co,
                    "error": ctrl_status.error,
                    "pid_cv": ctrl_status.pid_cv,
                    "process_in": ctrl_status.process_input,
                    "process_out": ctrl_status.process_output,
                    "disturbance_out": ctrl_status.disturbance_output,
                    "sp": ctrl_status.sp,
                    "kp": ctrl_status.pid_kp,
                    "ti": ctrl_status.pid_ti,
                    "td": ctrl_status.pid_td,
                    "mode": ctrl_status.pid_mode,
                    "pid_enabled": ctrl_status.pid_enabled,
                }
                if ctrl_status.auto_sp is not None:
                    data["auto_sp_enabled"] = ctrl_status.auto_sp.enabled
                    data["auto_sp_min"] = ctrl_status.auto_sp.sp_min_pct
                    data["auto_sp_max"] = ctrl_status.auto_sp.sp_max_pct
                if ctrl_status.auto_disturbance is not None:
                    data["auto_dist_enabled"] = ctrl_status.auto_disturbance.enabled
                    data["auto_dist_amp"] = ctrl_status.auto_disturbance.max_amplitude_pct
                self._sim_live_signal.emit(data)
            except Exception as e:
                logger.debug("sim poll error: %s", e)
        threading.Thread(target=do_poll, daemon=True).start()

    @Slot(dict)
    def _on_sim_live_received(self, vals: dict) -> None:
        self._simulator_page.update_live_values(
            pv=vals["pv"], co=vals["co"], error=vals["error"],
            pid_cv=vals["pid_cv"], process_in=vals["process_in"],
            process_out=vals["process_out"],
            disturbance_out=vals["disturbance_out"], sp=vals["sp"],
            kp=vals.get("kp"), ti=vals.get("ti"), td=vals.get("td"),
            mode=vals.get("mode"),
            pid_enabled=vals.get("pid_enabled"),
            auto_sp_enabled=vals.get("auto_sp_enabled"),
            auto_sp_min=vals.get("auto_sp_min"),
            auto_sp_max=vals.get("auto_sp_max"),
            auto_dist_enabled=vals.get("auto_dist_enabled"),
            auto_dist_amp=vals.get("auto_dist_amp"),
        )

    def _on_refresh_rate_changed(self, ms: int) -> None:
        """Update BusBridge refresh interval when user changes setting."""
        self._bus_bridge.set_refresh_ms(ms)

    def _on_opcua_connect(self, endpoint_url: str) -> None:
        """Connect to OPC-UA server via backend, passing the current field endpoint."""
        def do_connect():
            try:
                result = self._api_client.opcua_client_connect(endpoint=endpoint_url)
                state = result.get("state", "")
                connected = state.upper() == "ONLINE"
                self._opcua_status_signal.emit(connected)
            except Exception as e:
                logger.error("OPC-UA connect failed: %s", e)
                self._opcua_status_signal.emit(False)

        threading.Thread(target=do_connect, daemon=True).start()

    def _on_opcua_disconnect(self) -> None:
        """Disconnect from OPC-UA server via backend."""
        self._opcua_watchdog.stop()

        def do_disconnect():
            try:
                self._api_client.opcua_client_disconnect()
            except Exception as e:
                logger.error("OPC-UA disconnect failed: %s", e)
            self._opcua_status_signal.emit(False)

        threading.Thread(target=do_disconnect, daemon=True).start()

    @Slot(bool)
    def _on_opcua_status_received(self, connected: bool) -> None:
        """Handle OPC-UA status update on the main thread."""
        self._opcua_connected = connected
        self._settings_page.set_opcua_status(connected)
        if connected:
            # Start watchdog to monitor connection every 5s
            if not self._opcua_watchdog.isActive():
                self._opcua_watchdog.start(5000)
        else:
            # If watchdog is running, it will attempt auto-reconnect on next tick
            pass

    def _poll_opcua_status(self) -> None:
        """Periodically check OPC-UA connection; auto-reconnect if dropped."""
        def do_poll():
            try:
                result = self._api_client.opcua_client_status()
                state = result.get("state", "")
                connected = state.upper() == "ONLINE"
                if not connected:
                    logger.info("OPC-UA connection lost, attempting reconnect...")
                    result = self._api_client.opcua_client_connect()
                    state = result.get("state", "")
                    connected = state.upper() == "ONLINE"
                self._opcua_status_signal.emit(connected)
            except Exception as e:
                logger.error("OPC-UA status poll failed: %s", e)
                self._opcua_status_signal.emit(False)

        threading.Thread(target=do_poll, daemon=True).start()

    def _on_opcua_endpoint_save(self, url: str) -> None:
        """Persist OPC-UA endpoint to project metadata via backend."""
        def do_save():
            try:
                self._api_client.save_opcua_endpoint(url)
                logger.info("OPC-UA endpoint saved: %s", url)
            except Exception as e:
                logger.error("Failed to save OPC-UA endpoint: %s", e)
                self._api_error_signal.emit(f"Failed to save endpoint: {e}")

        threading.Thread(target=do_save, daemon=True).start()

    def _sync_opcua_status(self) -> None:
        """Query backend OPC-UA status and sync settings page."""
        def do_sync():
            try:
                result = self._api_client.opcua_client_status()
                state = result.get("state", "")
                endpoint = result.get("endpoint", "")
                connected = state.upper() == "ONLINE"
                QMetaObject.invokeMethod(
                    self,
                    "_apply_opcua_sync",
                    Qt.ConnectionType.QueuedConnection,
                    Q_ARG(str, endpoint),
                    Q_ARG(bool, connected),
                )
            except Exception as e:
                logger.error("OPC-UA status sync failed: %s", e)

        threading.Thread(target=do_sync, daemon=True).start()

    @Slot(str, bool)
    def _apply_opcua_sync(self, endpoint: str, connected: bool) -> None:
        """Apply OPC-UA sync results on the main thread."""
        self._settings_page.set_opcua_endpoint_and_status(endpoint, connected)
        self._opcua_connected = connected
        if connected and not self._opcua_watchdog.isActive():
            self._opcua_watchdog.start(5000)

    def _poll_stats(self) -> None:
        """Poll performance stats and AI optimizer status."""
        def do_poll():
            try:
                stats_list = self._api_client.get_all_stats()
                for stats in stats_list:
                    cid = stats.get("controller_id", 0)
                    self._stats_signal.emit(cid, stats)
            except Exception:
                pass  # Stats are non-critical

            # Poll AI optimizer status for selected controller
            cid = self._dashboard_page._selected_id  # noqa: SLF001
            if cid is not None:
                try:
                    ai = self._api_client.get_ai_status(cid)
                    self._ai_status_signal.emit(
                        cid, ai.get("engine", "NONE"), ai.get("enabled", False),
                    )
                except Exception:
                    self._ai_status_signal.emit(cid, "NONE", False)

        threading.Thread(target=do_poll, daemon=True).start()

    @Slot(int, dict)
    def _on_stats_received(self, controller_id: int, stats: dict) -> None:
        """Update faceplate with performance stats."""
        self._dashboard_page._faceplate.update_stats(stats)  # noqa: SLF001

    @Slot(int, str, bool)
    def _on_ai_status_received(
        self, controller_id: int, engine: str, running: bool,
    ) -> None:
        """Update faceplate and cards with AI optimizer status."""
        self._dashboard_page._faceplate.set_ai_running(running)  # noqa: SLF001
        self._dashboard_page._faceplate.set_ai_engine(engine)  # noqa: SLF001
        opt_state = "RUN" if running else "STOP"
        for card in self._dashboard_page._cards:  # noqa: SLF001
            card.on_ai_status(controller_id, engine, opt_state)

    def _on_ai_action(self, controller_id: int, action: dict) -> None:
        """Handle AI optimizer action: log to alarm panel and write Ki to OPC-UA."""
        engine = action.get("engine", "?")
        gamma = action.get("gamma", 0.0)
        new_ki = action.get("new_ki", 0.0)
        reasoning = action.get("reasoning", "")
        ts = action.get("timestamp", "")[:19]
        msg = f"[{ts}] {engine} \u03b3={gamma:+.4f} Ki={new_ki:.4f} \u2014 {reasoning}"
        self._alarm_panel.on_ai_event(controller_id, msg)

        # Write new Ki (Ti) to OPC-UA so the DCS uses the updated value
        self._safe_api_call(
            self._api_client.write_tuning, controller_id,
            None, new_ki, None,
        )

    def _on_telemetry_for_trends(self, controller_id: int, frame: object) -> None:
        """Forward telemetry to multi-trend page for matching plots."""
        if not isinstance(frame, dict):
            return
        # Find which plot panels are showing this controller
        name = ""
        for c in self._cached_controllers:
            if c.get("id") == controller_id:
                name = c.get("name", "")
                break
        if not name:
            return
        for i, combo in enumerate(self._multi_trend_page._loop_combos):
            selected = combo.currentText()
            if selected == "\u2014":  # em-dash = no loop
                continue
            if selected == name:
                # Append to internal buffer and update plot
                if not hasattr(self, "_trend_buffers"):
                    self._trend_buffers: dict[int, dict] = {}
                buf = self._trend_buffers.setdefault(i, {
                    "ts": [], "pvs": [], "sps": [], "cos": [],
                })
                buf["ts"].append(len(buf["ts"]))
                buf["pvs"].append(frame.get("pv", 0.0))
                buf["sps"].append(frame.get("sp", 0.0))
                buf["cos"].append(frame.get("co", 0.0))
                # Keep max 3600 points
                max_pts = 3600
                if len(buf["ts"]) > max_pts:
                    for k in buf:
                        buf[k] = buf[k][-max_pts:]
                self._multi_trend_page.update_plot(
                    i, buf["ts"], buf["pvs"], buf["sps"], buf["cos"],
                )

    def _refresh_kpis(self) -> None:
        """Fetch KPI data from API in a background thread."""
        def do_fetch():
            try:
                alarms = self._api_client.get_active_alarms()
                stats = self._api_client.get_all_stats()
                controllers = self._api_client.list_controllers()
                controller_dicts = [c.model_dump() for c in controllers]
                self._kpi_data_signal.emit({
                    "active_alarms": len(alarms),
                    "stats": stats,
                    "controllers": controller_dicts,
                })
            except Exception as e:
                logger.debug("KPI refresh failed: %s", e)

        threading.Thread(target=do_fetch, daemon=True).start()

    @Slot(dict)
    def _on_kpi_data_received(self, data: dict) -> None:
        """Update executive dashboard with KPI data from background fetch."""
        active_alarms = data.get("active_alarms", 0)

        # Refresh cached controllers from latest API data
        controllers = data.get("controllers")
        if controllers:
            self._cached_controllers = controllers

        total = len(self._cached_controllers)
        in_auto = sum(
            1 for c in self._cached_controllers if c.get("mode") == "AUTO"
        )
        ai_active = sum(
            1 for c in self._cached_controllers
            if c.get("ai_config", {}).get("engine", "NONE") != "NONE"
        )
        self._executive_page.update_kpis(
            total=total,
            in_auto=in_auto,
            active_alarms=active_alarms,
            ai_active=ai_active,
        )

        # Merge stats into controller dicts and refresh executive cards
        stats_list = data.get("stats", [])
        stats_by_id: dict[int, dict] = {}
        for s in stats_list:
            cid = s.get("controller_id")
            if cid is not None:
                stats_by_id[cid] = s

        enriched = []
        for ctrl in self._cached_controllers:
            merged = dict(ctrl)
            st = stats_by_id.get(ctrl.get("id"))
            if st:
                merged.update(st)
            enriched.append(merged)

        self._executive_page.update_controller_cards(enriched)

    def _refresh_exec_cards(self) -> None:
        """Fetch controller + stats + AI status and emit enriched dicts."""
        def do_fetch():
            try:
                controllers = self._api_client.list_controllers()
                ctrl_dicts = [c.model_dump() for c in controllers]
                stats = self._api_client.get_all_stats()

                stats_by_id: dict[int, dict] = {}
                for s in stats:
                    cid = s.get("controller_id")
                    if cid is not None:
                        stats_by_id[cid] = s

                enriched = []
                for ctrl in ctrl_dicts:
                    merged = dict(ctrl)
                    cid = ctrl.get("id")
                    # Merge performance stats
                    st = stats_by_id.get(cid)
                    if st:
                        merged.update(st)
                    # Fetch AI status for this controller
                    try:
                        ai = self._api_client.get_ai_status(cid)
                        merged["ai_state"] = "RUN" if ai.get("enabled") else "STOP"
                        merged["ai_gamma"] = ai.get("last_gamma")
                        merged["ai_optimizer_state"] = (
                            "RUN" if ai.get("enabled") else "STOP"
                        )
                    except Exception:
                        pass
                    enriched.append(merged)

                self._exec_cards_signal.emit(enriched)
            except Exception as e:
                logger.debug("Executive cards refresh failed: %s", e)

        threading.Thread(target=do_fetch, daemon=True).start()

    @Slot(list)
    def _on_exec_cards_received(self, enriched: list) -> None:
        """Update executive dashboard cards with enriched data."""
        self._cached_controllers = enriched
        self._executive_page.update_controller_cards(enriched)

    @staticmethod
    def _nav_btn_style(theme, active: bool) -> str:
        """Return stylesheet for a navigation button."""
        if active:
            return (
                f"QPushButton {{ background-color: {theme.accent};"
                f" color: {theme.bg_primary};"
                f" border: 1px solid {theme.accent};"
                f" border-radius: {theme.border_radius};"
                " font-weight: bold;"
                f" font-size: {theme.font_size_normal}px;"
                f" padding: 4px 14px; }}"
            )
        return (
            f"QPushButton {{ background-color: transparent;"
            f" color: {theme.fg_secondary};"
            f" border: 1px solid transparent;"
            f" border-radius: {theme.border_radius};"
            f" font-size: {theme.font_size_normal}px;"
            " padding: 4px 14px; }\n"
            f"QPushButton:hover {{ background-color:"
            f" {theme.bg_hover};"
            f" color: {theme.fg_primary};"
            f" border-color: {theme.border}; }}\n"
            f"QPushButton:disabled {{ color:"
            f" {theme.fg_muted}; }}"
        )

    def _set_active_nav(self, btn: QPushButton) -> None:
        """Highlight the active nav button and reset others."""
        theme = self._theme_manager.current
        for b in self._nav_buttons:
            is_active = b is btn
            b.setChecked(is_active)
            b.setStyleSheet(self._nav_btn_style(theme, is_active))
        self._active_nav_btn = btn

    def _on_theme_switch(self, name: str) -> None:
        """Apply the selected theme globally and propagate to child widgets."""
        self._theme_manager.set_theme(name)
        self._app_state.set_last_theme(name)
        self._app_state.save()
        theme = self._theme_manager.current
        theme.apply(QApplication.instance())
        # Update toolbar styling
        self._toolbar.setStyleSheet(
            f"QToolBar {{ background-color: {theme.bg_toolbar};"
            f" border-bottom: 1px solid {theme.border}; }}"
        )
        self._app_label.setStyleSheet(
            f"font-weight: bold;"
            f" font-size: {theme.font_size_title + 2}px;"
            f" color: {theme.fg_primary};"
            " background: transparent; padding: 0 12px;"
        )
        self._user_label.setStyleSheet(
            f"color: {theme.fg_secondary};"
            " background: transparent; padding: 0 12px;"
        )
        # Re-highlight active nav button
        if self._active_nav_btn is not None:
            self._set_active_nav(self._active_nav_btn)
        else:
            for b in self._nav_buttons:
                b.setStyleSheet(
                    self._nav_btn_style(theme, False),
                )
        # Propagate theme to widgets that cache theme references
        for widget in self.findChildren(QWidget):
            if hasattr(widget, "apply_theme"):
                widget.apply_theme(theme)

    def _show_admin_controls(self) -> None:
        """Show/hide and enable/disable UI elements based on session role.

        Role hierarchy:
        - OPERATOR: view, change SP/CO/mode
        - SUPERVISOR: + apply tuning, manage alarms, settings
        - ADMIN: + user management
        """
        role = (self._session.role or "").upper()
        is_admin = role == "ADMIN"
        is_supervisor = role in ("SUPERVISOR", "ADMIN")

        # Admin-only: user management tab
        self._users_btn.setVisible(is_admin)

        # Supervisor+: add controller button requires supervisor
        self._add_ctrl_btn.setEnabled(is_supervisor)

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

    # ------------------------------------------------------------------
    # Project management
    # ------------------------------------------------------------------

    @Slot()
    def _check_active_project(self) -> None:
        """After login, check if backend has a project active in projects_dir."""
        try:
            current = self._api_client.get_current_project()
            path = current.get("path", "")
            name = current.get("name", "")
            count = current.get("controller_count", 0)
            self._settings_page.update_project_info(name, path, count)

            # If the project is managed (not the scratch default), proceed
            if path != "project.spid":
                self._app_state.set_last_project_name(name)
                self._app_state.save()
                self._load_dashboard()
                self._sync_opcua_status()
                return
        except Exception as e:
            print(f"[PROJECT CHECK] Error: {e}")  # noqa: T201

        # Fallback: try to re-open last known project from HMI state
        last = self._app_state.last_project_name
        if last:
            try:
                result = self._api_client.open_project(last)
                rname = result.get("name", last)
                rpath = result.get("path", "")
                rcount = result.get("controller_count", 0)
                self._settings_page.update_project_info(rname, rpath, rcount)
                self._load_dashboard()
                self._sync_opcua_status()
                return
            except Exception as e:
                print(f"[PROJECT RESTORE] Could not re-open '{last}': {e}")  # noqa: T201

        # No managed project and no restorable project — show Welcome Dialog
        self._show_project_dialog()

    def _show_project_dialog(self) -> None:
        """Show the Welcome Dialog with projects from backend."""
        from smart_pid_hmi.dialogs.welcome_dialog import WelcomeDialog

        try:
            projects = self._api_client.list_projects()
        except Exception:
            projects = []

        dialog = WelcomeDialog(projects=projects, parent=self)
        while True:
            result = dialog.exec()
            if result != QDialog.DialogCode.Accepted:
                if dialog.result_action == "delete" and dialog.result_name:
                    self._handle_project_delete(dialog)
                    continue
                break

            action = dialog.result_action
            if action == "new" and dialog.result_name:
                self._handle_project_new(dialog.result_name)
                break
            elif action == "open" and dialog.result_name:
                self._handle_project_open(dialog.result_name)
                break
            elif action == "import" and dialog.result_path:
                name = dialog.result_name or ""
                self._handle_project_import(name, dialog.result_path)
                break

    def _handle_project_new(self, name: str) -> None:
        """Create a new project on the backend."""
        def do_new():
            try:
                result = self._api_client.new_project(name)
                self._app_state.set_last_project_name(result["name"])
                self._app_state.save()
                self._project_info_signal.emit(
                    result["name"], result["path"],
                    int(result.get("controller_count", 0)),
                )
                self._load_dashboard()
            except Exception as e:
                self._api_error_signal.emit(str(e))

        threading.Thread(target=do_new, daemon=True).start()

    def _handle_project_open(self, name: str) -> None:
        """Open an existing project on the backend."""
        def do_open():
            try:
                result = self._api_client.open_project(name)
                self._app_state.set_last_project_name(result["name"])
                self._app_state.save()
                self._project_info_signal.emit(
                    result["name"], result["path"],
                    int(result.get("controller_count", 0)),
                )
                self._load_dashboard()
            except Exception as e:
                self._api_error_signal.emit(str(e))

        threading.Thread(target=do_open, daemon=True).start()

    def _handle_project_import(self, name: str, file_path: str) -> None:
        """Upload a .spid file to the backend."""
        def do_import():
            try:
                result = self._api_client.import_project(name, file_path)
                self._app_state.set_last_project_name(result["name"])
                self._app_state.save()
                self._project_info_signal.emit(
                    result["name"], result["path"],
                    int(result.get("controller_count", 0)),
                )
                self._load_dashboard()
            except Exception as e:
                self._api_error_signal.emit(str(e))

        threading.Thread(target=do_import, daemon=True).start()

    def _handle_project_delete(self, dialog) -> None:
        """Delete a project and refresh the dialog list."""
        name = dialog.result_name
        try:
            self._api_client.delete_project(name)
            projects = self._api_client.list_projects()
            dialog.set_projects(projects)
            dialog.result_action = None
            dialog.result_name = None
        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(dialog, "Error", str(e))

    def _on_project_download(self) -> None:
        """Download the active project to a local file."""
        from PySide6.QtWidgets import QFileDialog

        path, _ = QFileDialog.getSaveFileName(
            self, "Download Project", "", "Smart PID Project (*.spid)",
        )
        if not path:
            return
        if not path.endswith(".spid"):
            path += ".spid"

        def do_download():
            try:
                self._api_client.download_project(path)
            except Exception as e:
                self._api_error_signal.emit(str(e))

        threading.Thread(target=do_download, daemon=True).start()

    @Slot(str, str, int)
    def _on_project_info_received(self, name: str, path: str, count: int) -> None:
        """Handle project info from background threads."""
        self._settings_page.update_project_info(name, path, count)

    def closeEvent(self, event) -> None:  # noqa: N802
        self._kpi_timer.stop()
        self._sim_poll_timer.stop()
        self._stats_timer.stop()
        self._exec_cards_timer.stop()
        self._bus_bridge.stop()
        self._telemetry_source.stop()
        if hasattr(self._api_client, "close"):
            self._api_client.close()
        super().closeEvent(event)


def main() -> None:
    """Entry point for the HMI application."""
    ensure_config_file()
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
