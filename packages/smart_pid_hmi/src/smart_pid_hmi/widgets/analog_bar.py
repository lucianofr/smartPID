"""AnalogBarWidget — horizontal continuous bar with ISA-101 coloring."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import QWidget

if TYPE_CHECKING:
    from smart_pid_hmi.themes.base import ThemeBase

_BAR_HEIGHT = 22
_WIDGET_HEIGHT = 32
_LABEL_WIDTH = 32
_VALUE_WIDTH = 70


def _theme_attr(theme: ThemeBase, attr: str, fallback: str) -> str:
    """Return theme attribute if non-empty, else fallback."""
    val = getattr(theme, attr, "")
    return val if val else fallback


class AnalogBarWidget(QWidget):
    """Horizontal continuous bar with label, value, SP marker,
    and alarm coloring."""

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

    def set_sp_marker(self, val: float | None) -> None:
        self._sp_marker = val
        self.update()

    def apply_theme(self, theme: ThemeBase) -> None:
        """Update cached theme reference for dynamic theme switching."""
        self._theme = theme
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

    def _border_radius(self) -> int:
        """Parse border_radius from theme (e.g. '12px' -> 12)."""
        raw = _theme_attr(self._theme, "border_radius", "0px")
        try:
            return int(raw.replace("px", ""))
        except (ValueError, AttributeError):
            return 0

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        br = self._border_radius()
        use_aa = br > 0
        p.setRenderHint(QPainter.RenderHint.Antialiasing, use_aa)
        w = self.width()
        t = self._theme

        # -- Label text (left, fixed width) --
        label_font = QFont(t.font_family, t.font_size_label)
        label_font.setBold(True)
        p.setFont(label_font)
        p.setPen(QColor(t.fg_secondary))
        label_rect = QRectF(0, 0, _LABEL_WIDTH, _WIDGET_HEIGHT)
        p.drawText(label_rect, Qt.AlignmentFlag.AlignVCenter, self._label)

        # -- Value text (right, monospaced, fixed width) --
        value_font = QFont("Fira Code", t.font_size_value - 2)
        value_font.setStyleHint(QFont.StyleHint.Monospace)
        p.setFont(value_font)
        p.setPen(QColor(t.fg_primary))
        value_text = f"{self._value:.1f}"
        if self._unit:
            value_text += f" {self._unit}"
        value_rect = QRectF(
            w - _VALUE_WIDTH, 0, _VALUE_WIDTH, _WIDGET_HEIGHT
        )
        p.drawText(
            value_rect,
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
            value_text,
        )

        # -- Bar area --
        bar_x = _LABEL_WIDTH + 4
        bar_w = w - _LABEL_WIDTH - _VALUE_WIDTH - 12
        bar_y = (_WIDGET_HEIGHT - _BAR_HEIGHT) / 2.0

        if bar_w <= 0:
            p.end()
            return

        bar_rect = QRectF(bar_x, bar_y, bar_w, _BAR_HEIGHT)
        bar_radius = min(br, _BAR_HEIGHT // 2) if br > 0 else 0

        # Bar background (use bg_input for subtle contrast)
        bg_input = _theme_attr(t, "bg_input", t.bg_widget)
        if bar_radius > 0:
            p.setBrush(QColor(bg_input))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(bar_rect, bar_radius, bar_radius)
        else:
            p.fillRect(bar_rect, QColor(bg_input))

        # Bar fill
        span = self._max - self._min
        if span > 0:
            frac = (self._value - self._min) / span
            fill_w = bar_w * frac
            fill_rect = QRectF(bar_x, bar_y, fill_w, _BAR_HEIGHT)
            if bar_radius > 0:
                # Clip to bar shape
                clip_path = QPainterPath()
                clip_path.addRoundedRect(bar_rect, bar_radius, bar_radius)
                p.setClipPath(clip_path)
                p.fillRect(fill_rect, self._fill_color())
                p.setClipping(False)
            else:
                p.fillRect(fill_rect, self._fill_color())

        # SP marker (2px line + triangular notch at top)
        if self._sp_marker is not None and span > 0:
            sp_frac = (self._sp_marker - self._min) / span
            sp_frac = max(0.0, min(1.0, sp_frac))
            sp_x = bar_x + bar_w * sp_frac
            pen = QPen(QColor(t.bar_sp), 2.0)
            p.setPen(pen)
            p.drawLine(
                QPointF(sp_x, bar_y),
                QPointF(sp_x, bar_y + _BAR_HEIGHT),
            )
            # Small triangular notch at top
            notch_size = 4.0
            notch = QPolygonF([
                QPointF(sp_x - notch_size, bar_y - 1),
                QPointF(sp_x + notch_size, bar_y - 1),
                QPointF(sp_x, bar_y + notch_size),
            ])
            p.setBrush(QColor(t.bar_sp))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawPolygon(notch)

        # Border
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QColor(t.border))
        if bar_radius > 0:
            p.drawRoundedRect(bar_rect, bar_radius, bar_radius)
        else:
            p.drawRect(bar_rect)

        p.end()
