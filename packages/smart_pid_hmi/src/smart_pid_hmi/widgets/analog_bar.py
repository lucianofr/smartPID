"""AnalogBarWidget — horizontal continuous bar with ISA-101 coloring."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import QWidget

if TYPE_CHECKING:
    from smart_pid_hmi.themes.base import ThemeBase

_BAR_HEIGHT = 20
_WIDGET_HEIGHT = 36


class AnalogBarWidget(QWidget):
    """Horizontal continuous bar with label, value, SP marker, and alarm coloring."""

    def __init__(
        self,
        label: str,
        unit: str,
        min_val: float,
        max_val: float,
        theme: ThemeBase,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._label = label
        self._unit = unit
        self._min = min_val
        self._max = max_val
        self._theme = theme
        self._value: float = 0.0
        self._sp_marker: float | None = None
        self._alarm_state: str | None = None
        self.setMinimumHeight(_WIDGET_HEIGHT)
        self.setMaximumHeight(_WIDGET_HEIGHT)

    @property
    def label(self) -> str:
        return self._label

    @property
    def value(self) -> float:
        return self._value

    @property
    def sp_marker(self) -> float | None:
        return self._sp_marker

    @property
    def alarm_state(self) -> str | None:
        return self._alarm_state

    def set_value(self, val: float) -> None:
        self._value = max(self._min, min(self._max, val))
        self.update()

    def set_sp_marker(self, val: float) -> None:
        self._sp_marker = val
        self.update()

    def set_alarm_state(self, state: str | None) -> None:
        self._alarm_state = state
        self.update()

    def _fill_color(self) -> QColor:
        if self._alarm_state == "CRITICAL":
            return QColor(self._theme.alarm_critical)
        if self._alarm_state == "WARNING":
            return QColor(self._theme.alarm_warning)
        return QColor(self._theme.bar_pv)

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)  # flat ISA-101
        w = self.width()

        # Label text (left)
        label_font = QFont(self._theme.font_family, self._theme.font_size_label)
        p.setFont(label_font)
        p.setPen(QColor(self._theme.fg_secondary))
        label_rect = QRectF(0, 0, 30, _WIDGET_HEIGHT)
        p.drawText(label_rect, Qt.AlignmentFlag.AlignVCenter, self._label)

        # Value text (right)
        value_font = QFont(self._theme.font_family, self._theme.font_size_value)
        p.setFont(value_font)
        p.setPen(QColor(self._theme.fg_primary))
        value_text = f"{self._value:.1f} {self._unit}"
        value_rect = QRectF(w - 80, 0, 80, _WIDGET_HEIGHT)
        p.drawText(
            value_rect,
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
            value_text,
        )

        # Bar area
        bar_x = 34
        bar_w = w - 120
        bar_y = (_WIDGET_HEIGHT - _BAR_HEIGHT) / 2

        if bar_w <= 0:
            p.end()
            return

        # Bar background
        p.fillRect(
            QRectF(bar_x, bar_y, bar_w, _BAR_HEIGHT), QColor(self._theme.bg_widget)
        )

        # Bar fill
        span = self._max - self._min
        if span > 0:
            frac = (self._value - self._min) / span
            fill_w = bar_w * frac
            p.fillRect(QRectF(bar_x, bar_y, fill_w, _BAR_HEIGHT), self._fill_color())

        # SP marker (thin vertical line)
        if self._sp_marker is not None and span > 0:
            sp_frac = (self._sp_marker - self._min) / span
            sp_x = bar_x + bar_w * sp_frac
            p.setPen(QColor(self._theme.bar_sp))
            p.drawLine(int(sp_x), int(bar_y), int(sp_x), int(bar_y + _BAR_HEIGHT))

        # Border
        p.setPen(QColor(self._theme.border))
        p.drawRect(QRectF(bar_x, bar_y, bar_w, _BAR_HEIGHT))

        p.end()
