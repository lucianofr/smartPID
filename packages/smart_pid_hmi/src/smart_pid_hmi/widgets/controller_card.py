"""ControllerCardWidget — compact summary card per controller loop."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

from smart_pid_hmi.widgets.analog_bar import AnalogBarWidget

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget

    from smart_pid_hmi.themes.base import ThemeBase

_CARD_WIDTH = 260
_CARD_MIN_HEIGHT = 160


class ControllerCardWidget(QFrame):
    """Summary card showing tag, mode, and 3 analog bars (PV, SP, CO)."""

    controller_selected = Signal(int)

    def __init__(
        self,
        controller_id: int,
        tag_name: str,
        min_val: float,
        max_val: float,
        theme: ThemeBase,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._controller_id = controller_id
        self._tag_name = tag_name
        self._theme = theme

        self.setFixedWidth(_CARD_WIDTH)
        self.setMinimumHeight(_CARD_MIN_HEIGHT)
        self.setFrameShape(QFrame.Shape.Box)
        self.setLineWidth(1)
        self.setStyleSheet(
            f"ControllerCardWidget {{ background-color: {theme.bg_widget}; "
            f"border: 1px solid {theme.border}; }}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)

        # Header: tag name + mode badge
        header = QHBoxLayout()
        tag_label = QLabel(tag_name)
        tag_label.setStyleSheet(
            f"font-size: {theme.font_size_title}px; font-weight: bold; "
            f"color: {theme.fg_primary}; background: transparent;"
        )
        self._mode_label = QLabel("\u2014")
        self._mode_label.setStyleSheet(
            f"font-size: {theme.font_size_label}px; color: {theme.fg_secondary}; "
            f"background: transparent; padding: 2px 6px; "
            f"border: 1px solid {theme.border};"
        )
        header.addWidget(tag_label)
        header.addStretch()
        header.addWidget(self._mode_label)
        layout.addLayout(header)

        # Bars
        self._bar_pv = AnalogBarWidget("PV", "", min_val, max_val, theme)
        self._bar_sp = AnalogBarWidget("SP", "", min_val, max_val, theme)
        self._bar_co = AnalogBarWidget("CO", "%", 0.0, 100.0, theme)
        layout.addWidget(self._bar_pv)
        layout.addWidget(self._bar_sp)
        layout.addWidget(self._bar_co)
        layout.addStretch()

    @property
    def controller_id(self) -> int:
        return self._controller_id

    @property
    def tag_name(self) -> str:
        return self._tag_name

    def on_telemetry(self, controller_id: int, frame: dict) -> None:
        if controller_id != self._controller_id:
            return
        self._bar_pv.set_value(frame.get("pv", 0.0))
        self._bar_pv.set_sp_marker(frame.get("sp"))
        self._bar_sp.set_value(frame.get("sp", 0.0))
        self._bar_co.set_value(frame.get("co", 0.0))
        mode = frame.get("mode")
        if mode:
            self._mode_label.setText(str(mode))

    def on_alarm(self, controller_id: int, alarm: dict) -> None:
        if controller_id != self._controller_id:
            return
        priority = alarm.get("priority", "")
        if priority == "CRITICAL":
            self.setStyleSheet(
                f"ControllerCardWidget {{ background-color: {self._theme.bg_widget}; "
                f"border: 2px solid {self._theme.alarm_critical}; }}"
            )
            self._bar_pv.set_alarm_state("CRITICAL")
        elif priority == "WARNING":
            self.setStyleSheet(
                f"ControllerCardWidget {{ background-color: {self._theme.bg_widget}; "
                f"border: 2px solid {self._theme.alarm_warning}; }}"
            )
            self._bar_pv.set_alarm_state("WARNING")
        else:
            self.setStyleSheet(
                f"ControllerCardWidget {{ background-color: {self._theme.bg_widget}; "
                f"border: 1px solid {self._theme.border}; }}"
            )
            self._bar_pv.set_alarm_state(None)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        self.controller_selected.emit(self._controller_id)
        super().mousePressEvent(event)
