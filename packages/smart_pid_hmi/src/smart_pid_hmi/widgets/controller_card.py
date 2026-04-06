"""ControllerCardWidget — compact summary card per controller loop."""
from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from smart_pid_hmi.widgets.analog_bar import AnalogBarWidget

if TYPE_CHECKING:
    from PySide6.QtGui import QMouseEvent, QPaintEvent

    from smart_pid_hmi.themes.base import ThemeBase

_CARD_WIDTH = 260
_CARD_MIN_HEIGHT = 180
_ALARM_STRIP_HEIGHT = 4


class SparklineWidget(QWidget):
    """Mini trend showing last N PV values as a line chart."""

    def __init__(
        self,
        theme: ThemeBase | None = None,
        buffer_size: int = 30,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._buffer_size = buffer_size
        self._data: deque[float] = deque(maxlen=buffer_size)
        self._theme = theme
        self.setMaximumHeight(32)
        self.setMinimumHeight(24)

    @property
    def data(self) -> deque[float]:
        return self._data

    def add_value(self, value: float) -> None:
        self._data.append(value)
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        if len(self._data) < 2:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = self._theme.accent if self._theme else "#00e5cc"
        pen = QPen()
        pen.setColor(Qt.GlobalColor.cyan if not self._theme else pen.color())
        from PySide6.QtGui import QColor
        pen.setColor(QColor(color))
        pen.setWidthF(1.5)
        painter.setPen(pen)
        w, h = self.width(), self.height()
        vals = list(self._data)
        lo, hi = min(vals), max(vals)
        span = hi - lo if hi != lo else 1.0
        path = QPainterPath()
        for i, v in enumerate(vals):
            x = i * w / (len(vals) - 1)
            y = h - (v - lo) / span * h
            if i == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)
        painter.drawPath(path)
        painter.end()


def _theme_attr(theme: ThemeBase, attr: str, fallback: str) -> str:
    """Return theme attribute if non-empty, else fallback."""
    val = getattr(theme, attr, "")
    return val if val else fallback


class ControllerCardWidget(QFrame):
    """Summary card showing tag, description, mode, alarm state,
    and 3 analog bars (PV, SP, CO)."""

    controller_selected = Signal(int)
    settings_requested = Signal(int)

    def __init__(
        self,
        controller_id: int,
        tag_name: str,
        min_val: float,
        max_val: float,
        theme: ThemeBase,
        parent: QWidget | None = None,
        description: str = "",
    ) -> None:
        super().__init__(parent)
        self._controller_id = controller_id
        self._tag_name = tag_name
        self._description = description
        self._theme = theme
        self._alarm_priority: str | None = None

        self.setFixedWidth(_CARD_WIDTH)
        self.setMinimumHeight(_CARD_MIN_HEIGHT)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._apply_card_style(theme)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 8)
        layout.setSpacing(4)

        # Alarm strip (colored bar at top of card)
        self._alarm_strip = QFrame()
        self._alarm_strip.setFixedHeight(_ALARM_STRIP_HEIGHT)
        self._alarm_strip.setStyleSheet("background: transparent;")
        layout.addWidget(self._alarm_strip)

        # Header: tag name + description + alarm icon + mode badge
        header = QHBoxLayout()
        header.setSpacing(4)

        # Alarm icon (hidden by default)
        self._alarm_icon = QLabel("")
        self._alarm_icon.setStyleSheet(
            "background: transparent; font-size: 14px;"
        )
        self._alarm_icon.setFixedWidth(18)
        self._alarm_icon.hide()
        header.addWidget(self._alarm_icon)

        # Tag + description label
        display_text = tag_name
        if description:
            display_text += f" ({description})"
        self._tag_label = QLabel(display_text)
        self._tag_label.setStyleSheet(
            f"font-size: {theme.font_size_title}px; font-weight: bold; "
            f"color: {theme.fg_primary}; background: transparent;"
        )
        self._tag_label.setWordWrap(True)

        self._mode_label = QLabel("\u2014")
        self._mode_label.setStyleSheet(
            f"font-size: {theme.font_size_label}px; "
            f"color: {theme.fg_secondary}; "
            f"background: transparent; padding: 2px 6px; "
            f"border: 1px solid {theme.border};"
        )
        header.addWidget(self._tag_label)
        header.addStretch()
        header.addWidget(self._mode_label)

        # Gear button for settings
        self._settings_btn = QPushButton("\u2699")
        self._settings_btn.setObjectName("settings_btn")
        self._settings_btn.setFixedSize(28, 28)
        self._settings_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; border: none; "
            f"color: {theme.fg_secondary}; font-size: 16px; }}"
            f"QPushButton:hover {{ border: 1px solid {theme.border}; }}"
        )
        self._settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._settings_btn.clicked.connect(self._on_settings_clicked)
        header.addWidget(self._settings_btn)

        layout.addLayout(header)

        # Bars
        self._bar_pv = AnalogBarWidget(
            "PV", "", min_val, max_val, theme
        )
        self._bar_sp = AnalogBarWidget(
            "SP", "", min_val, max_val, theme
        )
        self._bar_co = AnalogBarWidget(
            "CO", "%", 0.0, 100.0, theme
        )
        layout.addWidget(self._bar_pv)
        layout.addWidget(self._bar_sp)
        layout.addWidget(self._bar_co)

        # Sparkline (mini PV trend)
        self._sparkline = SparklineWidget(theme=theme)
        layout.addWidget(self._sparkline)

        layout.addStretch()

    def _apply_card_style(
        self, theme: ThemeBase, alarm: str | None = None,
    ) -> None:
        bg = _theme_attr(theme, "bg_card", theme.bg_widget)
        br = _theme_attr(theme, "border_radius", "0px")
        if alarm == "CRITICAL":
            border_css = (
                f"border: 2px solid {theme.alarm_critical}; "
                f"outline: 1px solid {theme.alarm_critical};"
            )
        elif alarm == "WARNING":
            border_css = (
                f"border: 2px solid {theme.alarm_warning}; "
                f"outline: 1px solid {theme.alarm_warning};"
            )
        else:
            border_css = f"border: 1px solid {theme.border};"
        self.setStyleSheet(
            f"ControllerCardWidget {{ "
            f"background-color: {bg}; {border_css} "
            f"border-radius: {br}; }}"
        )

    @property
    def controller_id(self) -> int:
        return self._controller_id

    @property
    def tag_name(self) -> str:
        return self._tag_name

    def apply_theme(self, theme: ThemeBase) -> None:
        """Update cached theme reference for dynamic theme switching."""
        self._theme = theme
        self._apply_card_style(theme, self._alarm_priority)
        self._tag_label.setStyleSheet(
            f"font-size: {theme.font_size_title}px; font-weight: bold; "
            f"color: {theme.fg_primary}; background: transparent;"
        )
        self._mode_label.setStyleSheet(
            f"font-size: {theme.font_size_label}px; "
            f"color: {theme.fg_secondary}; "
            f"background: transparent; padding: 2px 6px; "
            f"border: 1px solid {theme.border};"
        )
        self._settings_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; border: none; "
            f"color: {theme.fg_secondary}; font-size: 16px; }}"
            f"QPushButton:hover {{ border: 1px solid {theme.border}; }}"
        )
        self._bar_pv.apply_theme(theme)
        self._bar_sp.apply_theme(theme)
        self._bar_co.apply_theme(theme)
        self.update()

    def on_telemetry(self, controller_id: int, frame: dict) -> None:
        if controller_id != self._controller_id:
            return
        pv = frame.get("pv", 0.0)
        self._bar_pv.set_value(pv)
        self._bar_pv.set_sp_marker(frame.get("sp"))
        self._bar_sp.set_value(frame.get("sp", 0.0))
        self._bar_co.set_value(frame.get("co", 0.0))
        self._sparkline.add_value(pv)
        mode = frame.get("mode")
        if mode:
            self._mode_label.setText(str(mode))

    def on_alarm(self, controller_id: int, alarm: dict) -> None:
        if controller_id != self._controller_id:
            return
        priority = alarm.get("priority", "")
        transition = alarm.get("transition", "")
        if transition == "CLEARED":
            self._alarm_priority = None
            self._alarm_icon.hide()
            self._alarm_strip.setStyleSheet(
                "background: transparent;"
            )
            self._apply_card_style(self._theme)
            self._bar_pv.set_alarm_state(None)
            return

        if priority == "CRITICAL":
            self._alarm_priority = "CRITICAL"
            self._alarm_icon.setText("\u25cf")  # filled circle
            self._alarm_icon.setStyleSheet(
                f"color: {self._theme.alarm_critical}; "
                f"background: transparent; font-size: 14px;"
            )
            self._alarm_icon.show()
            self._alarm_strip.setStyleSheet(
                f"background: {self._theme.alarm_critical};"
            )
            self._apply_card_style(self._theme, "CRITICAL")
            self._bar_pv.set_alarm_state("CRITICAL")
        elif priority == "WARNING":
            self._alarm_priority = "WARNING"
            self._alarm_icon.setText("\u26a0")  # warning triangle
            self._alarm_icon.setStyleSheet(
                f"color: {self._theme.alarm_warning}; "
                f"background: transparent; font-size: 14px;"
            )
            self._alarm_icon.show()
            self._alarm_strip.setStyleSheet(
                f"background: {self._theme.alarm_warning};"
            )
            self._apply_card_style(self._theme, "WARNING")
            self._bar_pv.set_alarm_state("WARNING")
        else:
            self._alarm_priority = None
            self._alarm_icon.hide()
            self._alarm_strip.setStyleSheet(
                "background: transparent;"
            )
            self._apply_card_style(self._theme)
            self._bar_pv.set_alarm_state(None)

    def _on_settings_clicked(self) -> None:
        self.settings_requested.emit(self._controller_id)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        # Don't emit controller_selected if the gear button was clicked
        child = self.childAt(event.position().toPoint())
        if child is self._settings_btn:
            return
        self.controller_selected.emit(self._controller_id)
        super().mousePressEvent(event)
