"""Application bootstrap — QApplication, MainWindow, service wiring."""
from __future__ import annotations

import logging
import sys
import threading
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QMetaObject, Qt, QTimer, Signal, Slot
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
from smart_pid_hmi.config import HMISettings
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


class MainWindow(QMainWindow):
    """Top-level window with page stack and toolbar."""

    # Thread-safe signals for cross-thread communication
    _login_error_signal = Signal(str)
    _controllers_loaded_signal = Signal(list)
    _api_error_signal = Signal(str)
    _users_loaded_signal = Signal(list)
    _kpi_data_signal = Signal(dict)  # KPI + performance data from background
    _edit_dialog_signal = Signal(int, object)
    _project_loaded_signal = Signal(dict)

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
        self._app_state.prune()

        # Pending project to open after login
        self._pending_project_action: str | None = None
        self._pending_project_path: str | None = None
        self._pending_project_name: str | None = None

        # Connect thread-safe signals
        self._login_error_signal.connect(self._on_login_error_received)
        self._controllers_loaded_signal.connect(self._on_controllers_received)
        self._api_error_signal.connect(self._on_api_error)
        self._users_loaded_signal.connect(self._on_users_loaded)
        self._kpi_data_signal.connect(self._on_kpi_data_received)
        self._edit_dialog_signal.connect(self._open_edit_dialog)

        # Cached controller list for KPI computation
        self._cached_controllers: list[dict] = []

        # KPI refresh timer (started after login)
        self._kpi_timer = QTimer(self)
        self._kpi_timer.timeout.connect(self._refresh_kpis)

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
            f" border-bottom: 1px solid {theme.border};"
            " }}"
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
        self._settings_page.theme_changed.connect(self._on_theme_switch)
        self._settings_page.refresh_rate_changed.connect(self._on_refresh_rate_changed)
        self._settings_page.project_new_requested.connect(self._on_project_new)
        self._settings_page.project_open_requested.connect(self._on_project_open)
        self._settings_page.project_save_as_requested.connect(self._on_project_save_as)
        self._project_loaded_signal.connect(self._on_project_loaded)
        bus_bridge.telemetry_received.connect(self._on_telemetry_for_trends)
        self._user_mgmt_page.user_create_requested.connect(self._create_user)
        self._user_mgmt_page.user_update_requested.connect(self._update_user)
        self._user_mgmt_page.user_deactivate_requested.connect(self._deactivate_user)
        self._user_mgmt_page.user_reactivate_requested.connect(self._reactivate_user)

        # Optimizer signals from faceplate
        faceplate = self._dashboard_page._faceplate  # noqa: SLF001
        faceplate.optimizer_run_requested.connect(self._send_optimizer_start)
        faceplate.optimizer_pause_requested.connect(
            self._send_optimizer_pause,
        )
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
        self._load_dashboard()
        self._stack.setCurrentWidget(self._dashboard_page)
        self._check_simulator_available()
        self._show_admin_controls()
        # Load currently active alarms so alarm panel is populated
        self._alarm_panel.load_active_alarms()
        # Start periodic KPI refresh (every 30 seconds)
        self._kpi_timer.start(30_000)

        # Open pending project after login
        if self._pending_project_path:
            if self._pending_project_action == "new" and self._pending_project_name:
                self._do_new_project(self._pending_project_name, self._pending_project_path)
            else:
                self._do_open_project(self._pending_project_path)
            self._pending_project_action = None
            self._pending_project_path = None
            self._pending_project_name = None
        else:
            # No pending action — fetch current project state from backend
            self._refresh_project_info()

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

        def do_update():
            try:
                self._api_client.update_controller(controller_id, updated)
                self._load_dashboard()
            except Exception as e:
                logger.error("Failed to update controller %d: %s", controller_id, e)
                self._api_error_signal.emit(str(e))

        threading.Thread(target=do_update, daemon=True).start()

    @Slot(list)
    def _on_controllers_received(self, controllers: list[dict]) -> None:
        """Handle controllers loaded via thread-safe signal."""
        self._cached_controllers = controllers
        self._dashboard_page.populate_controllers(controllers)
        self._simulator_page.populate_controllers(controllers)

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

    def _send_optimizer_start(self, controller_id: int) -> None:
        self._safe_api_call(
            self._api_client.start_optimizer, controller_id,
        )

    def _send_optimizer_pause(self, controller_id: int) -> None:
        self._safe_api_call(
            self._api_client.pause_optimizer, controller_id,
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

    def _on_refresh_rate_changed(self, ms: int) -> None:
        """Update BusBridge refresh interval when user changes setting."""
        self._bus_bridge.set_refresh_ms(ms)

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
            if combo.currentText() == name:
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
                self._kpi_data_signal.emit({
                    "active_alarms": len(alarms),
                    "stats": stats,
                })
            except Exception as e:
                logger.debug("KPI refresh failed: %s", e)

        threading.Thread(target=do_fetch, daemon=True).start()

    @Slot(dict)
    def _on_kpi_data_received(self, data: dict) -> None:
        """Update executive dashboard with KPI data from background fetch."""
        active_alarms = data.get("active_alarms", 0)
        total = len(self._cached_controllers)
        in_auto = sum(
            1 for c in self._cached_controllers if c.get("mode") == "AUTO"
        )
        ai_active = sum(
            1 for c in self._cached_controllers
            if c.get("ai_mode") and c.get("ai_mode") != "NONE"
        )
        self._executive_page.update_kpis(
            total=total,
            in_auto=in_auto,
            active_alarms=active_alarms,
            ai_active=ai_active,
        )

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
                " padding: 4px 14px; }}"
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
            f" border-bottom: 1px solid {theme.border};"
            " }}"
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

    def _on_project_new(self, name: str, path: str) -> None:
        from PySide6.QtWidgets import QMessageBox

        reply = QMessageBox.question(
            self, "New Project",
            "This will stop all running loops. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._do_new_project(name, path)

    def _do_new_project(self, name: str, path: str) -> None:
        def do_new():
            try:
                result = self._api_client.new_project(name, path)
                self._app_state.set_last_project(
                    result["path"], result["name"], result["controller_count"],
                )
                self._app_state.save()
                self._project_loaded_signal.emit(result)
                self._load_dashboard()
            except Exception as e:
                self._api_error_signal.emit(str(e))

        threading.Thread(target=do_new, daemon=True).start()
        # Fallback: refresh project info after a short delay to ensure
        # Settings page is updated even if the signal is missed
        QTimer.singleShot(1500, self._refresh_project_info)

    def _on_project_open(self, path: str) -> None:
        from PySide6.QtWidgets import QMessageBox

        reply = QMessageBox.question(
            self, "Open Project",
            "This will stop all running loops. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._do_open_project(path)

    def _do_open_project(self, path: str) -> None:
        def do_open():
            try:
                result = self._api_client.open_project(path)
                self._app_state.set_last_project(
                    result["path"], result["name"], result["controller_count"],
                )
                self._app_state.save()
                self._project_loaded_signal.emit(result)
                self._load_dashboard()
            except Exception as e:
                self._api_error_signal.emit(str(e))

        threading.Thread(target=do_open, daemon=True).start()
        QTimer.singleShot(1500, self._refresh_project_info)

    def _on_project_save_as(self, path: str) -> None:
        def do_save():
            try:
                result = self._api_client.save_as_project(path)
                self._app_state.set_last_project(
                    result["path"], result["name"], result["controller_count"],
                )
                self._app_state.save()
                self._project_loaded_signal.emit(result)
            except Exception as e:
                self._api_error_signal.emit(str(e))

        threading.Thread(target=do_save, daemon=True).start()
        QTimer.singleShot(1500, self._refresh_project_info)

    @Slot(dict)
    def _on_project_loaded(self, result: dict) -> None:
        self._settings_page.update_project_info(
            result.get("name", ""), result.get("path", ""),
            result.get("controller_count", 0),
        )

    def _refresh_project_info(self) -> None:
        """Fetch current project state from backend and update Settings page."""
        def do_fetch():
            try:
                result = self._api_client.get_current_project()
                self._project_loaded_signal.emit(result)
            except Exception:
                logger.debug("Could not fetch current project info")

        threading.Thread(target=do_fetch, daemon=True).start()

    def closeEvent(self, event) -> None:  # noqa: N802
        self._kpi_timer.stop()
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

    # Project management: open last project or show welcome dialog
    app_state = window._app_state
    if app_state.last_project and Path(app_state.last_project).exists():
        window._pending_project_path = app_state.last_project
    else:
        from smart_pid_hmi.dialogs.welcome_dialog import WelcomeDialog

        dialog = WelcomeDialog(recent_projects=app_state.recent_projects)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            if dialog.result_action == "new":
                window._pending_project_action = "new"
                window._pending_project_name = dialog.result_name
                window._pending_project_path = dialog.result_path
            elif dialog.result_action == "open":
                window._pending_project_action = "open"
                window._pending_project_path = dialog.result_path
        else:
            sys.exit(0)

    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
