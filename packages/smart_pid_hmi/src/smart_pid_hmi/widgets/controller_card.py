"""ControllerCardWidget — compact summary card per controller loop.

Visual reference: rounded card with alarm strip at top, tag + config button
header, three analog bars (PV, SP, CO) with values.  Alarm state turns the
top strip and card border to the priority color with an icon.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
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
    from PySide6.QtGui import QMouseEvent

    from smart_pid_hmi.themes.base import ThemeBase

_CARD_WIDTH = 280
_CARD_MIN_HEIGHT = 175
_ALARM_STRIP_HEIGHT = 5


def _theme_attr(theme: ThemeBase, attr: str, fallback: str) -> str:
    val = getattr(theme, attr, "")
    return val if val else fallback


class ControllerCardWidget(QFrame):
    """Summary card: tag, alarm strip, PV/SP/CO bars, config button."""

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

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 6)
        root.setSpacing(2)

        # ── Alarm strip (colored bar at very top of card) ──
        self._alarm_strip = QFrame()
        self._alarm_strip.setFixedHeight(_ALARM_STRIP_HEIGHT)
        self._alarm_strip.setStyleSheet("background: transparent;")
        root.addWidget(self._alarm_strip)

        # ── Content area with padding ──
        content = QVBoxLayout()
        content.setContentsMargins(10, 2, 10, 0)
        content.setSpacing(4)

        # ── Header row: alarm icon + tag(description) + config button ──
        header = QHBoxLayout()
        header.setSpacing(4)

        # Alarm icon (hidden by default, shown on alarm)
        self._alarm_icon = QLabel("")
        self._alarm_icon.setFixedWidth(20)
        self._alarm_icon.setStyleSheet(
            "background: transparent; font-size: 16px;"
        )
        self._alarm_icon.hide()
        header.addWidget(self._alarm_icon)

        # Tag + description
        display_text = f"<b>{tag_name}</b>"
        if description:
            display_text += f" ({description})"
        self._tag_label = QLabel(display_text)
        self._tag_label.setStyleSheet(
            f"font-size: {theme.font_size_title}px;"
            f" color: {theme.fg_primary}; background: transparent;"
        )
        self._tag_label.setWordWrap(True)
        header.addWidget(self._tag_label, stretch=1)

        # Settings button — gear icon with symbol font
        self._settings_btn = QPushButton("\u2699")
        self._settings_btn.setObjectName("settings_btn")
        self._settings_btn.setFixedSize(28, 28)
        from PySide6.QtGui import QFont
        btn_font = QFont("Symbola, Noto Sans Symbols2, Segoe UI Symbol", 16)
        self._settings_btn.setFont(btn_font)
        self._apply_settings_btn_style(theme)
        self._settings_btn.setToolTip("Controller settings")
        self._settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._settings_btn.clicked.connect(self._on_settings_clicked)
        header.addWidget(self._settings_btn)

        content.addLayout(header)

        # ── Mode badge ──
        self._mode_label = QLabel("\u2014")
        self._mode_label.setFixedHeight(18)
        self._apply_mode_style(theme)
        content.addWidget(self._mode_label)

        # ── Analog bars (PV, SP, CO) ──
        self._bar_pv = AnalogBarWidget("PV", "", min_val, max_val, theme)
        self._bar_sp = AnalogBarWidget("SP", "", min_val, max_val, theme)
        self._bar_co = AnalogBarWidget("CO", "%", 0.0, 100.0, theme)
        content.addWidget(self._bar_pv)
        content.addWidget(self._bar_sp)
        content.addWidget(self._bar_co)

        root.addLayout(content)

    # ── Styling ──────────────────────────────────────────────────

    def _apply_card_style(
        self, theme: ThemeBase, alarm: str | None = None,
    ) -> None:
        bg = _theme_attr(theme, "bg_card", theme.bg_widget)
        br = _theme_attr(theme, "border_radius", "6px")
        if alarm == "CRITICAL":
            border_css = f"border: 2px solid {theme.alarm_critical};"
        elif alarm == "WARNING":
            border_css = f"border: 2px solid {theme.alarm_warning};"
        else:
            border_css = f"border: 1px solid {theme.border};"
        self.setStyleSheet(
            f"ControllerCardWidget {{"
            f" background-color: {bg}; {border_css}"
            f" border-radius: {br}; }}"
        )

    def _apply_mode_style(self, theme: ThemeBase) -> None:
        self._mode_label.setStyleSheet(
            f"font-size: {theme.font_size_label}px;"
            f" font-weight: bold;"
            f" color: {theme.fg_secondary};"
            f" background: transparent;"
            f" padding: 0 2px;"
        )

    def _apply_settings_btn_style(self, theme: ThemeBase) -> None:
        self._settings_btn.setStyleSheet(
            f"QPushButton {{ background: {theme.bg_widget};"
            f" border: 1px solid {theme.border};"
            f" border-radius: 3px;"
            f" color: {theme.fg_primary};"
            f" font-size: 9px; font-weight: bold;"
            f" padding: 2px 4px; }}"
            f"QPushButton:hover {{ background: {theme.accent};"
            f" color: {theme.bg_widget}; }}"
        )

    # ── Properties ───────────────────────────────────────────────

    @property
    def controller_id(self) -> int:
        return self._controller_id

    @property
    def tag_name(self) -> str:
        return self._tag_name

    # ── Theme switching ──────────────────────────────────────────

    def apply_theme(self, theme: ThemeBase) -> None:
        self._theme = theme
        self._apply_card_style(theme, self._alarm_priority)
        self._tag_label.setStyleSheet(
            f"font-size: {theme.font_size_title}px;"
            f" color: {theme.fg_primary}; background: transparent;"
        )
        self._apply_mode_style(theme)
        self._apply_settings_btn_style(theme)
        self._bar_pv.apply_theme(theme)
        self._bar_sp.apply_theme(theme)
        self._bar_co.apply_theme(theme)
        self.update()

    # ── Data updates ─────────────────────────────────────────────

    def on_telemetry(self, controller_id: int, frame: dict) -> None:
        if controller_id != self._controller_id:
            return
        self._bar_pv.set_value(frame.get("pv", 0.0))
        self._bar_pv.set_sp_marker(frame.get("sp"))
        self._bar_sp.set_value(frame.get("sp", 0.0))
        self._bar_co.set_value(frame.get("co", 0.0))
        mode = frame.get("mode")
        if mode:
            self._mode_label.setText(f"Mode: {mode}")

    def on_alarm(self, controller_id: int, alarm: dict) -> None:
        if controller_id != self._controller_id:
            return
        priority = alarm.get("priority", "")
        transition = alarm.get("transition", "")

        if transition == "CLEARED":
            self._set_alarm_visual(None)
            return

        if priority in ("CRITICAL", "WARNING"):
            self._set_alarm_visual(priority)
        else:
            self._set_alarm_visual(None)

    def _set_alarm_visual(self, priority: str | None) -> None:
        """Update strip, icon, border for alarm state."""
        t = self._theme
        self._alarm_priority = priority

        if priority == "CRITICAL":
            self._alarm_strip.setStyleSheet(
                f"background: {t.alarm_critical};"
            )
            self._alarm_icon.setText("\u26d4")  # no-entry (octagon)
            self._alarm_icon.setStyleSheet(
                f"color: {t.alarm_critical};"
                " background: transparent; font-size: 16px;"
            )
            self._alarm_icon.show()
            self._apply_card_style(t, "CRITICAL")
            self._bar_pv.set_alarm_state("CRITICAL")
        elif priority == "WARNING":
            self._alarm_strip.setStyleSheet(
                f"background: {t.alarm_warning};"
            )
            self._alarm_icon.setText("\u26a0")  # warning triangle
            self._alarm_icon.setStyleSheet(
                f"color: {t.alarm_warning};"
                " background: transparent; font-size: 16px;"
            )
            self._alarm_icon.show()
            self._apply_card_style(t, "WARNING")
            self._bar_pv.set_alarm_state("WARNING")
        else:
            self._alarm_strip.setStyleSheet("background: transparent;")
            self._alarm_icon.hide()
            self._apply_card_style(t)
            self._bar_pv.set_alarm_state(None)

    # ── Interaction ──────────────────────────────────────────────

    def _on_settings_clicked(self) -> None:
        self.settings_requested.emit(self._controller_id)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        child = self.childAt(event.position().toPoint())
        if child is self._settings_btn:
            return
        self.controller_selected.emit(self._controller_id)
        super().mousePressEvent(event)
