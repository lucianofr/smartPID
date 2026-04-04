"""FaceplateWidget — detailed operation panel for selected controller."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from smart_pid_hmi.widgets.analog_bar import AnalogBarWidget

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget

    from smart_pid_hmi.themes.base import ThemeBase


class FaceplateWidget(QFrame):
    """Detailed control panel for a single controller."""

    setpoint_requested = Signal(int, float)    # (controller_id, value)
    mode_requested = Signal(int, str)          # (controller_id, mode)
    output_requested = Signal(int, float)      # (controller_id, value)

    def __init__(self, theme: ThemeBase, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._theme = theme
        self._controller_id: int | None = None

        self.setFrameShape(QFrame.Shape.Box)
        self.setStyleSheet(
            f"FaceplateWidget {{ background-color: {theme.bg_secondary}; "
            f"border: 1px solid {theme.border}; }}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        # Header
        self._tag_label = QLabel("\u2014")
        self._tag_label.setStyleSheet(
            f"font-size: {theme.font_size_title}px; font-weight: bold; "
            f"color: {theme.fg_primary}; background: transparent;"
        )
        self._mode_label = QLabel("\u2014")
        self._mode_label.setStyleSheet(
            f"font-size: {theme.font_size_label}px; color: {theme.fg_secondary}; "
            f"background: transparent; padding: 2px 6px; border: 1px solid {theme.border};"
        )
        header = QHBoxLayout()
        header.addWidget(self._tag_label)
        header.addStretch()
        header.addWidget(self._mode_label)
        layout.addLayout(header)

        # Bars (created with defaults, replaced on controller select)
        self._bar_pv = AnalogBarWidget("PV", "", 0.0, 100.0, theme)
        self._bar_sp = AnalogBarWidget("SP", "", 0.0, 100.0, theme)
        self._bar_co = AnalogBarWidget("CO", "%", 0.0, 100.0, theme)
        layout.addWidget(self._bar_pv)
        layout.addWidget(self._bar_sp)
        layout.addWidget(self._bar_co)

        # SP input
        sp_row = QHBoxLayout()
        sp_row.addWidget(QLabel("SP:"))
        self._sp_input = QLineEdit()
        self._sp_input.setPlaceholderText("Enter SP")
        self._sp_input.returnPressed.connect(self._on_sp_enter)
        sp_row.addWidget(self._sp_input)
        layout.addLayout(sp_row)

        # CO input
        co_row = QHBoxLayout()
        co_row.addWidget(QLabel("CO:"))
        self._co_input = QLineEdit()
        self._co_input.setPlaceholderText("Enter CO (MAN)")
        self._co_input.returnPressed.connect(self._on_co_enter)
        co_row.addWidget(self._co_input)
        layout.addLayout(co_row)

        # Mode buttons
        mode_row = QHBoxLayout()
        self._btn_auto = QPushButton("Auto")
        self._btn_man = QPushButton("Man")
        self._btn_auto.clicked.connect(lambda: self._on_mode("AUTO"))
        self._btn_man.clicked.connect(lambda: self._on_mode("MAN"))
        mode_row.addWidget(self._btn_auto)
        mode_row.addWidget(self._btn_man)
        layout.addLayout(mode_row)

        # Stats placeholder
        stats_label = QLabel("IAE: \u2014 | 2\u03c3/Range: \u2014")
        stats_label.setStyleSheet(
            f"font-size: {theme.font_size_label}px; color: {theme.fg_secondary}; "
            f"background: transparent;"
        )
        layout.addWidget(stats_label)
        layout.addStretch()

    def apply_theme(self, theme: ThemeBase) -> None:
        """Update cached theme reference for dynamic theme switching."""
        self._theme = theme
        self.setStyleSheet(
            f"FaceplateWidget {{ background-color: {theme.bg_secondary}; "
            f"border: 1px solid {theme.border}; }}"
        )
        self.update()

    def on_controller_selected(
        self, controller_id: int, tag_name: str, min_val: float, max_val: float
    ) -> None:
        self._controller_id = controller_id
        self._tag_label.setText(tag_name)
        self._mode_label.setText("\u2014")
        # Reset bars with new range
        for bar in [self._bar_pv, self._bar_sp]:
            bar._min = min_val
            bar._max = max_val
            bar.set_value(0.0)
        self._bar_co.set_value(0.0)

    def on_telemetry(self, controller_id: int, frame: dict) -> None:
        if self._controller_id is None or controller_id != self._controller_id:
            return
        self._bar_pv.set_value(frame.get("pv", 0.0))
        self._bar_pv.set_sp_marker(frame.get("sp"))
        self._bar_sp.set_value(frame.get("sp", 0.0))
        self._bar_co.set_value(frame.get("co", 0.0))
        mode = frame.get("mode")
        if mode:
            self._mode_label.setText(str(mode))

    def _on_sp_enter(self) -> None:
        if self._controller_id is None:
            return
        try:
            val = float(self._sp_input.text())
            self.setpoint_requested.emit(self._controller_id, val)
        except ValueError:
            pass

    def _on_co_enter(self) -> None:
        if self._controller_id is None:
            return
        try:
            val = float(self._co_input.text())
            self.output_requested.emit(self._controller_id, val)
        except ValueError:
            pass

    def _on_mode(self, mode: str) -> None:
        if self._controller_id is not None:
            self.mode_requested.emit(self._controller_id, mode)
