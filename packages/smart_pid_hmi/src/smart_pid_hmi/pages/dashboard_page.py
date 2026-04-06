"""DashboardPage — cards grid + trend/faceplate + alarm bar."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QGridLayout,
    QLabel,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from smart_pid_hmi.widgets.alarm_bar import AlarmBarWidget
from smart_pid_hmi.widgets.controller_card import ControllerCardWidget
from smart_pid_hmi.widgets.faceplate import FaceplateWidget
from smart_pid_hmi.widgets.trend_chart import TrendChartWidget

if TYPE_CHECKING:
    from smart_pid_hmi.bus_bridge import BusBridge
    from smart_pid_hmi.themes.base import ThemeBase

_GRID_COLS = 4


class DashboardPage(QWidget):
    """Main operational dashboard with cards, trend, faceplate, alarm bar."""

    setpoint_requested = Signal(int, float)
    mode_requested = Signal(int, str)
    output_requested = Signal(int, float)
    settings_requested = Signal(int)

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

        # Top: cards in horizontal layout (no scroll, fixed height)
        self._cards_container = QWidget()
        self._cards_layout = QGridLayout(self._cards_container)
        self._cards_layout.setSpacing(8)
        self._cards_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._cards_container)

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

        # Middle: trend + faceplate (70/30 split)
        splitter = QSplitter()
        self._trend = TrendChartWidget(theme=theme)
        self._faceplate = FaceplateWidget(theme=theme)
        splitter.addWidget(self._trend)
        splitter.addWidget(self._faceplate)
        splitter.setStretchFactor(0, 7)
        splitter.setStretchFactor(1, 3)
        layout.addWidget(splitter, stretch=1)

        # Bottom: alarm bar
        self._alarm_bar = AlarmBarWidget(theme=theme)
        layout.addWidget(self._alarm_bar)

        # Wire faceplate command signals
        self._faceplate.setpoint_requested.connect(self.setpoint_requested)
        self._faceplate.mode_requested.connect(self.mode_requested)
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

        for idx, ctrl in enumerate(controllers):
            cid = ctrl["id"]
            name = ctrl["name"]
            lo = ctrl.get("sp_lo_lim", 0.0)
            hi = ctrl.get("sp_hi_lim", 100.0)
            desc = ctrl.get("description", "")
            self._controller_meta[cid] = {
                "name": name, "lo": lo, "hi": hi,
                "description": desc,
            }

            card = ControllerCardWidget(
                controller_id=cid, tag_name=name,
                min_val=lo, max_val=hi, theme=self._theme,
            )
            card.controller_selected.connect(self._on_card_selected)
            card.settings_requested.connect(self.settings_requested)
            row = idx // _GRID_COLS
            col = idx % _GRID_COLS
            self._cards_layout.addWidget(card, row, col)
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
        )
        self._trend.on_controller_selected(controller_id)

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
        self._alarm_bar.on_alarm(controller_id, alarm)

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
