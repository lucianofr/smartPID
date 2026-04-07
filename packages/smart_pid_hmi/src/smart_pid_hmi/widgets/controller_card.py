"""ControllerCardWidget — compact summary card per controller loop.

Visual reference: rounded card with alarm strip at top, tag + config button
header, three analog bars (PV, SP, CO) with values.  Alarm state turns the
top strip and card border to the priority color with an icon.
Status badges show controller mode, optimizer state, and AI engine.
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
_CARD_MIN_HEIGHT = 200
_ALARM_STRIP_HEIGHT = 5

# Badge color schemes: (background, text_color)
_MODE_COLORS: dict[str, tuple[str, str]] = {
    "AUTO": ("#1B5E20", "#A5D6A7"),   # green
    "CAS": ("#1B5E20", "#A5D6A7"),    # green
    "RCAS": ("#1B5E20", "#A5D6A7"),   # green
    "MAN": ("#E65100", "#FFCC80"),     # orange
    "ROUT": ("#E65100", "#FFCC80"),    # orange
    "OOS": ("#424242", "#9E9E9E"),     # gray
    "LO": ("#424242", "#9E9E9E"),      # gray
    "IMAN": ("#424242", "#9E9E9E"),    # gray
    "BYPASS": ("#424242", "#9E9E9E"),  # gray
}
_MODE_DEFAULT = ("#424242", "#9E9E9E")

_OPT_STATE_COLORS: dict[str, tuple[str, str]] = {
    "RUN": ("#0D47A1", "#90CAF9"),      # blue
    "RUNNING": ("#0D47A1", "#90CAF9"),  # alias
    "PAUSE": ("#F57F17", "#FFF176"),    # yellow
    "STOP": ("#424242", "#9E9E9E"),     # gray
    "STOPPED": ("#424242", "#9E9E9E"),  # alias
}
_OPT_STATE_DEFAULT = ("#424242", "#9E9E9E")

_AI_ENGINE_COLORS: dict[str, tuple[str, str]] = {
    "FUZZY": ("#4A148C", "#CE93D8"),  # purple
    "RL": ("#006064", "#80DEEA"),     # teal
    "NONE": ("#424242", "#9E9E9E"),   # gray
}
_AI_ENGINE_DEFAULT = ("#424242", "#9E9E9E")


def _theme_attr(theme: ThemeBase, attr: str, fallback: str) -> str:
    val = getattr(theme, attr, "")
    return val if val else fallback


def _badge_stylesheet(bg: str, fg: str) -> str:
    """Return QLabel stylesheet for a status badge."""
    return (
        f"background-color: {bg}; color: {fg};"
        " font-size: 10px; font-weight: bold;"
        " border-radius: 3px; padding: 1px 5px;"
        " border: none;"
    )


class ControllerCardWidget(QFrame):
    """Summary card: tag, alarm strip, PV/SP/CO bars, status badges."""

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
        ai_engine: str = "NONE",
        optimizer_state: str = "STOP",
    ) -> None:
        super().__init__(parent)
        self._controller_id = controller_id
        self._tag_name = tag_name
        self._description = description
        self._theme = theme
        self._alarm_priority: str | None = None
        self._current_mode = "\u2014"
        self._current_ai_engine = ai_engine.upper()
        self._current_opt_state = optimizer_state.upper()

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

        # ── Analog bars (PV, SP, CO) ──
        self._bar_pv = AnalogBarWidget("PV", "", min_val, max_val, theme)
        self._bar_sp = AnalogBarWidget("SP", "", min_val, max_val, theme)
        self._bar_co = AnalogBarWidget("CO", "%", 0.0, 100.0, theme)
        content.addWidget(self._bar_pv)
        content.addWidget(self._bar_sp)
        content.addWidget(self._bar_co)

        # ── Status badges row (mode | optimizer state | AI engine) ──
        badges_row = QHBoxLayout()
        badges_row.setSpacing(4)
        badges_row.setContentsMargins(0, 2, 0, 0)

        self._badge_mode = QLabel(self._current_mode)
        self._badge_mode.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._badge_mode.setFixedHeight(18)
        self._update_mode_badge()
        badges_row.addWidget(self._badge_mode)

        self._badge_opt_state = QLabel(self._current_opt_state)
        self._badge_opt_state.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._badge_opt_state.setFixedHeight(18)
        self._update_opt_state_badge()
        badges_row.addWidget(self._badge_opt_state)

        self._badge_ai_engine = QLabel(self._current_ai_engine)
        self._badge_ai_engine.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._badge_ai_engine.setFixedHeight(18)
        self._update_ai_engine_badge()
        badges_row.addWidget(self._badge_ai_engine)

        badges_row.addStretch()
        content.addLayout(badges_row)

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

    def _update_mode_badge(self) -> None:
        mode = self._current_mode.upper()
        bg, fg = _MODE_COLORS.get(mode, _MODE_DEFAULT)
        self._badge_mode.setText(mode)
        self._badge_mode.setStyleSheet(_badge_stylesheet(bg, fg))

    def _update_opt_state_badge(self) -> None:
        state = self._current_opt_state.upper()
        bg, fg = _OPT_STATE_COLORS.get(state, _OPT_STATE_DEFAULT)
        self._badge_opt_state.setText(state)
        self._badge_opt_state.setStyleSheet(_badge_stylesheet(bg, fg))

    def _update_ai_engine_badge(self) -> None:
        engine = self._current_ai_engine.upper()
        label = "AI RL" if engine == "RL" else engine
        bg, fg = _AI_ENGINE_COLORS.get(engine, _AI_ENGINE_DEFAULT)
        self._badge_ai_engine.setText(label)
        self._badge_ai_engine.setStyleSheet(_badge_stylesheet(bg, fg))

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
        self._apply_settings_btn_style(theme)
        self._update_mode_badge()
        self._update_opt_state_badge()
        self._update_ai_engine_badge()
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
        if mode and str(mode).upper() not in ("UNKNOWN", ""):
            self._current_mode = str(mode).upper()
            self._update_mode_badge()

    def on_ai_status(
        self, controller_id: int, ai_engine: str, optimizer_state: str,
    ) -> None:
        """Update AI engine and optimizer state badges."""
        if controller_id != self._controller_id:
            return
        self._current_ai_engine = ai_engine.upper()
        self._current_opt_state = optimizer_state.upper()
        self._update_ai_engine_badge()
        self._update_opt_state_badge()

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
