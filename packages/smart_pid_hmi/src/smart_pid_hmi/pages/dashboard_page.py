"""DashboardPage — cards grid + trend/faceplate + alarm bar."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from smart_pid_hmi.widgets.ai_log_widget import AILogWidget
from smart_pid_hmi.widgets.alarm_bar import AlarmBarWidget
from smart_pid_hmi.widgets.controller_card import ControllerCardWidget
from smart_pid_hmi.widgets.faceplate import FaceplateWidget
from smart_pid_hmi.widgets.trend_chart import TrendChartWidget

if TYPE_CHECKING:
    from smart_pid_hmi.bus_bridge import BusBridge
    from smart_pid_hmi.themes.base import ThemeBase

class DashboardPage(QWidget):
    """Main operational dashboard with cards, trend, faceplate, alarm bar."""

    setpoint_requested = Signal(int, float)
    mode_requested = Signal(int, str)
    output_requested = Signal(int, float)
    gains_changed = Signal(int, dict)
    settings_requested = Signal(int)
    alarm_ack_requested = Signal(int)    # alarm_id
    alarm_ack_all_requested = Signal()

    def __init__(
        self,
        theme: ThemeBase,
        bus_bridge: BusBridge,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._theme = theme
        self._bridge = bus_bridge
        self._cards: list[ControllerCardWidget] = []
        self._controller_meta: dict[int, dict] = {}
        self._selected_id: int | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 0)
        layout.setSpacing(6)

        # Section title: overview
        self._overview_label = QLabel(
            "VISAO GERAL DOS CONTROLADORES \u2014 Nivel 1"
        )
        self._overview_label.setStyleSheet(
            f"color: {theme.fg_muted}; font-size: {theme.font_size_label}px;"
            " font-weight: bold; text-transform: uppercase;"
            " background: transparent; padding: 2px 0px;"
        )
        layout.addWidget(self._overview_label)

        # Top: cards in horizontal row, left-justified, scrollable
        self._cards_scroll = QScrollArea()
        self._cards_scroll.setWidgetResizable(True)
        self._cards_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff,
        )
        self._cards_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded,
        )
        self._cards_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._cards_scroll.setFixedHeight(220)
        self._cards_container = QWidget()
        self._cards_layout = QHBoxLayout(self._cards_container)
        self._cards_layout.setSpacing(6)
        self._cards_layout.setContentsMargins(0, 0, 0, 0)
        self._cards_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self._cards_scroll.setWidget(self._cards_container)
        layout.addWidget(self._cards_scroll)

        # Section title: detail
        self._detail_label = QLabel(
            "DETALHE DA MALHA \u2014 Nivel 3"
        )
        self._detail_label.setStyleSheet(
            f"color: {theme.fg_muted}; font-size: {theme.font_size_label}px;"
            " font-weight: bold; text-transform: uppercase;"
            " background: transparent; padding: 2px 0px;"
        )
        layout.addWidget(self._detail_label)

        # Middle: (trend + AI log) | faceplate — splitter 70/30
        splitter = QSplitter()

        # Left side: trend chart + AI log (vertical split)
        left_splitter = QSplitter(Qt.Orientation.Vertical)
        self._trend = TrendChartWidget(theme=theme)
        left_splitter.addWidget(self._trend)
        self._ai_log = AILogWidget(theme=theme)
        left_splitter.addWidget(self._ai_log)
        left_splitter.setStretchFactor(0, 4)
        left_splitter.setStretchFactor(1, 1)
        splitter.addWidget(left_splitter)

        # Right side: faceplate (stretches to alarm bar)
        self._faceplate = FaceplateWidget(theme=theme)
        splitter.addWidget(self._faceplate)

        splitter.setStretchFactor(0, 7)
        splitter.setStretchFactor(1, 3)
        layout.addWidget(splitter, stretch=1)

        # Bottom: alarm bar
        self._alarm_bar = AlarmBarWidget(theme=theme)
        self._alarm_bar.ack_requested.connect(self.alarm_ack_requested)
        self._alarm_bar.ack_all_requested.connect(self.alarm_ack_all_requested)
        layout.addWidget(self._alarm_bar)

        # Wire faceplate command signals
        self._faceplate.setpoint_requested.connect(self.setpoint_requested)
        self._faceplate.mode_requested.connect(self.mode_requested)
        self._faceplate.gains_changed.connect(self.gains_changed)
        self._faceplate.output_requested.connect(self.output_requested)

        # Wire bus bridge
        bus_bridge.telemetry_received.connect(self._on_telemetry)
        bus_bridge.alarm_received.connect(self._on_alarm)

    def populate_controllers(self, controllers: list[dict]) -> None:
        """Create cards from controller list (from API response dicts)."""
        # Clear existing
        for card in self._cards:
            card.deleteLater()
        self._cards.clear()
        self._controller_meta.clear()

        for _idx, ctrl in enumerate(controllers):
            cid = ctrl["id"]
            name = ctrl["name"]
            lo = ctrl.get("sp_lo_lim", 0.0)
            hi = ctrl.get("sp_hi_lim", 100.0)
            desc = ctrl.get("description", "")
            pid_params = ctrl.get("pid_params", {})
            integral_type = ctrl.get("integral_type", "TIME_TI")
            ai_cfg = ctrl.get("ai_config", {})
            self._controller_meta[cid] = {
                "name": name, "lo": lo, "hi": hi,
                "description": desc,
                "scan_rate_s": ctrl.get("scan_rate_s", 1.0),
                "pid_gains": {
                    "gain": pid_params.get("gain", 1.0),
                    "reset": pid_params.get("reset", 10.0),
                    "rate": pid_params.get("rate", 0.0),
                    "integral_type": integral_type,
                },
                "ai_engine": ai_cfg.get("engine", "NONE"),
            }
            ai_engine = ai_cfg.get("engine", "NONE")

            card = ControllerCardWidget(
                controller_id=cid, tag_name=name,
                min_val=lo, max_val=hi, theme=self._theme,
                ai_engine=ai_engine,
            )
            card.controller_selected.connect(self._on_card_selected)
            card.settings_requested.connect(self.settings_requested)
            self._cards_layout.addWidget(card)
            self._cards.append(card)

        # Auto-select first
        if controllers:
            first = controllers[0]
            self._select_controller(first["id"])

    def _select_controller(self, controller_id: int) -> None:
        meta = self._controller_meta.get(controller_id)
        if meta is None:
            return
        self._selected_id = controller_id
        tag = meta["name"]
        desc = meta.get("description", "")
        suffix = f" ({desc})" if desc else ""
        self._detail_label.setText(
            f"DETALHE DA MALHA: {tag}{suffix} \u2014 Nivel 3"
        )
        self._faceplate.on_controller_selected(
            controller_id, meta["name"], meta["lo"], meta["hi"],
            pid_gains=meta.get("pid_gains"),
            ai_engine=meta.get("ai_engine", "NONE"),
        )
        self._trend.on_controller_selected(
            controller_id,
            scan_rate_s=meta.get("scan_rate_s", 1.0),
        )
        self._ai_log.on_controller_selected(controller_id)

    def update_single_controller(self, controller_id: int, ctrl: dict) -> None:
        """Update metadata for one controller without recreating cards or resetting the chart."""
        pid_params = ctrl.get("pid_params", {})
        integral_type = ctrl.get("integral_type", "TIME_TI")
        ai_cfg = ctrl.get("ai_config", {})
        name = ctrl.get("name", "")
        lo = ctrl.get("sp_lo_lim", 0.0)
        hi = ctrl.get("sp_hi_lim", 100.0)
        desc = ctrl.get("description", "")

        self._controller_meta[controller_id] = {
            "name": name, "lo": lo, "hi": hi,
            "description": desc,
            "scan_rate_s": ctrl.get("scan_rate_s", 1.0),
            "pid_gains": {
                "gain": pid_params.get("gain", 1.0),
                "reset": pid_params.get("reset", 10.0),
                "rate": pid_params.get("rate", 0.0),
                "integral_type": integral_type,
            },
            "ai_engine": ai_cfg.get("engine", "NONE"),
        }

        # Update the faceplate if this is the currently selected controller
        if self._selected_id == controller_id:
            meta = self._controller_meta[controller_id]
            suffix = f" ({desc})" if desc else ""
            self._detail_label.setText(
                f"DETALHE DA MALHA: {name}{suffix} \u2014 Nivel 3"
            )
            self._faceplate.on_controller_selected(
                controller_id, meta["name"], meta["lo"], meta["hi"],
                pid_gains=meta.get("pid_gains"),
                ai_engine=meta.get("ai_engine", "NONE"),
            )
            # NOTE: intentionally NOT calling self._trend.on_controller_selected()
            # to preserve the running chart data

    def _on_card_selected(self, controller_id: int) -> None:
        self._select_controller(controller_id)

    def _on_telemetry(self, controller_id: int, frame: dict) -> None:
        for card in self._cards:
            card.on_telemetry(controller_id, frame)
        self._faceplate.on_telemetry(controller_id, frame)
        self._trend.on_telemetry(controller_id, frame)

    def _on_alarm(self, controller_id: int, alarm: dict) -> None:
        for card in self._cards:
            card.on_alarm(controller_id, alarm)
        self._alarm_bar.on_alarm(alarm)

    def on_ai_action(self, controller_id: int, action: dict) -> None:
        """Forward AI tuning decision to the AI log widget."""
        self._ai_log.on_ai_action(controller_id, action)

    def on_alarm_ack(self, controller_id: int, alarm_type: str | None = None) -> None:
        """Propagate ACK to cards and alarm bar."""
        for card in self._cards:
            card.on_alarm_ack(controller_id, alarm_type)
        if alarm_type is not None:
            self._alarm_bar.on_alarm_acked(controller_id, alarm_type)

    def on_all_alarms_acked(self) -> None:
        """Propagate ACK All to alarm bar."""
        self._alarm_bar.on_all_alarms_acked()

    def apply_theme(self, theme: ThemeBase) -> None:
        """Re-apply theme colors to dynamic elements."""
        self._theme = theme
        self._overview_label.setStyleSheet(
            f"color: {theme.fg_muted};"
            f" font-size: {theme.font_size_label}px;"
            " font-weight: bold; text-transform: uppercase;"
            " background: transparent; padding: 2px 0px;"
        )
        self._detail_label.setStyleSheet(
            f"color: {theme.fg_muted};"
            f" font-size: {theme.font_size_label}px;"
            " font-weight: bold; text-transform: uppercase;"
            " background: transparent; padding: 2px 0px;"
        )
        self._ai_log.apply_theme(theme)
