"""DashboardPage — cards grid + trend/faceplate + alarm bar."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QScrollArea,
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

        # Left side: trend chart + AI log stacked
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(4)

        self._trend = TrendChartWidget(theme=theme)
        left_layout.addWidget(self._trend, stretch=1)

        self._ai_log = QPlainTextEdit()
        self._ai_log.setReadOnly(True)
        self._ai_log.setMaximumHeight(80)
        self._ai_log.setPlaceholderText("AI Log — reasoning and tuning actions")
        self._ai_log.setStyleSheet(
            "QPlainTextEdit {"
            " background-color: #0A0A0A;"
            " color: #33FF33;"
            " border: 1px solid #333333;"
            " font-size: 13px;"
            " padding: 6px;"
            " selection-background-color: #004400;"
            "}"
        )
        from PySide6.QtGui import QFont
        ai_font = QFont("Fira Code", 11)
        ai_font.setStyleHint(QFont.StyleHint.Monospace)
        self._ai_log.setFont(ai_font)
        left_layout.addWidget(self._ai_log)

        splitter.addWidget(left_panel)

        # Right side: faceplate (stretches to alarm bar)
        self._faceplate = FaceplateWidget(theme=theme)
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

    def append_ai_log(self, message: str) -> None:
        """Append a message to the AI log box (terminal-style)."""
        self._ai_log.appendPlainText(message)
        # Keep max 200 lines
        doc = self._ai_log.document()
        if doc.blockCount() > 200:
            cursor = self._ai_log.textCursor()
            cursor.movePosition(cursor.MoveOperation.Start)
            cursor.movePosition(
                cursor.MoveOperation.Down, cursor.MoveMode.KeepAnchor, doc.blockCount() - 200,
            )
            cursor.removeSelectedText()
            cursor.deleteChar()  # remove trailing newline

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
