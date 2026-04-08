"""ControllerCardWidget — compact summary card per controller loop.

Visual reference: rounded card with alarm strip at top, tag + config button
header, three analog bars (PV, SP, CO) with values.  Alarm state turns the
top strip and card border to the priority color with an icon.
Status badges show controller mode, optimizer state, and AI engine.

Alarm visual behaviour (ISA-18.2 inspired):
- ACTIVE + UNACKNOWLEDGED → blinking strip (500 ms) in priority color + icon
- ACTIVE + ACKNOWLEDGED   → solid strip in priority color + icon (no blink)
- CLEARED / NORMAL        → no strip, no icon
When multiple alarms are active, the highest-priority one drives the visual.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QTimer, Signal
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
_ALARM_BANNER_HEIGHT = 24
_BLINK_INTERVAL_MS = 500

# Priority ordering: lower index = higher priority
_PRIORITY_RANK: dict[str, int] = {
    "CRITICAL": 0,
    "WARNING": 1,
    "ADVISORY": 2,
    "LOG": 3,
}

# Icons per priority (shown in upper-right corner)
_PRIORITY_ICON: dict[str, str] = {
    "CRITICAL": "\u26d4",   # no-entry (octagon)
    "WARNING": "\u26a0",    # warning triangle
    "ADVISORY": "\u2139",   # info circle
}

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


def _alarm_color(theme: ThemeBase, priority: str) -> str:
    """Return the theme color for a given alarm priority."""
    if priority == "CRITICAL":
        return theme.alarm_critical
    if priority == "WARNING":
        return theme.alarm_warning
    return getattr(theme, "accent", "") or "#1976D2"


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

        # Active alarms: {alarm_type: {"priority": str, "acked": bool}}
        self._active_alarms: dict[str, dict] = {}

        # Blink state
        self._blink_visible = True
        self._blink_timer = QTimer(self)
        self._blink_timer.setInterval(_BLINK_INTERVAL_MS)
        self._blink_timer.timeout.connect(self._on_blink_tick)

        self.setFixedWidth(_CARD_WIDTH)
        self.setMinimumHeight(_CARD_MIN_HEIGHT)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._apply_card_style(theme)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 6)
        root.setSpacing(0)

        # ── Alarm banner (colored band at top of card with priority icon) ──
        self._alarm_banner = QFrame()
        self._alarm_banner.setFixedHeight(_ALARM_BANNER_HEIGHT)
        banner_layout = QHBoxLayout(self._alarm_banner)
        banner_layout.setContentsMargins(8, 0, 8, 0)
        banner_layout.setSpacing(0)

        self._alarm_banner_label = QLabel("")
        self._alarm_banner_label.setStyleSheet(
            "color: #FFFFFF; font-size: 11px; font-weight: bold;"
            " background: transparent;"
        )
        banner_layout.addWidget(self._alarm_banner_label, stretch=1)

        self._alarm_icon = QLabel("")
        self._alarm_icon.setFixedWidth(22)
        self._alarm_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._alarm_icon.setStyleSheet(
            "color: #FFFFFF; background: transparent; font-size: 16px;"
        )
        banner_layout.addWidget(self._alarm_icon)

        self._alarm_banner.setStyleSheet("background: transparent;")
        self._alarm_banner.setVisible(False)
        root.addWidget(self._alarm_banner)

        # ── Content area with padding ──
        content = QVBoxLayout()
        content.setContentsMargins(10, 4, 10, 0)
        content.setSpacing(4)

        # ── Header row: tag(description) + config button ──
        header = QHBoxLayout()
        header.setSpacing(4)

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
        if alarm is not None:
            color = _alarm_color(theme, alarm)
            # Banner covers top — remove top border so banner sits flush
            border_css = (
                f"border-left: 1px solid {color};"
                f" border-right: 1px solid {color};"
                f" border-bottom: 1px solid {color};"
                " border-top: none;"
            )
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
        if self._alarm_priority:
            self._refresh_alarm_visual()
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
        """Handle alarm transition: TRIGGERED adds, CLEARED removes."""
        if controller_id != self._controller_id:
            return
        alarm_type = alarm.get("alarm_type", "")
        priority = alarm.get("priority", "")
        transition = alarm.get("transition", "")

        if transition == "TRIGGERED" and alarm_type:
            self._active_alarms[alarm_type] = {
                "priority": priority,
                "acked": False,
            }
        elif transition == "CLEARED" and alarm_type:
            self._active_alarms.pop(alarm_type, None)

        self._resolve_top_alarm()

    def on_alarm_ack(self, controller_id: int, alarm_type: str | None = None) -> None:
        """Mark alarm(s) as acknowledged. None = ack all."""
        if controller_id != self._controller_id:
            return
        if alarm_type is None:
            for entry in self._active_alarms.values():
                entry["acked"] = True
        elif alarm_type in self._active_alarms:
            self._active_alarms[alarm_type]["acked"] = True
        self._resolve_top_alarm()

    # ── Alarm visual logic ───────────────────────────────────────

    def _resolve_top_alarm(self) -> None:
        """Find the highest-priority active alarm and update the visual."""
        if not self._active_alarms:
            self._set_alarm_visual(None, acked=False)
            return

        # Find alarm with lowest rank (= highest priority)
        top_type = min(
            self._active_alarms,
            key=lambda k: _PRIORITY_RANK.get(
                self._active_alarms[k]["priority"], 99,
            ),
        )
        top = self._active_alarms[top_type]
        self._set_alarm_visual(top["priority"], acked=top["acked"])

    def _set_alarm_visual(self, priority: str | None, *, acked: bool) -> None:
        """Update banner, icon, border, and blink state for alarm."""
        self._alarm_priority = priority
        self._blink_timer.stop()

        if priority is None:
            # Normal — clear everything
            self._alarm_banner.setVisible(False)
            self._apply_card_style(self._theme)
            self._bar_pv.set_alarm_state(None)
            return

        self._refresh_alarm_visual()

        if not acked:
            # UNACKNOWLEDGED → start blinking
            self._blink_visible = True
            self._blink_timer.start()
        # else: solid banner, no blink — already rendered by _refresh_alarm_visual

    def _refresh_alarm_visual(self) -> None:
        """Render banner, icon, and border for the current alarm priority."""
        priority = self._alarm_priority
        if priority is None:
            return
        t = self._theme
        color = _alarm_color(t, priority)
        icon_char = _PRIORITY_ICON.get(priority, "")

        br = _theme_attr(t, "border_radius", "6px")
        self._alarm_banner.setStyleSheet(
            f"background: {color};"
            f" border-top-left-radius: {br};"
            f" border-top-right-radius: {br};"
        )
        self._alarm_banner_label.setText(priority)
        self._alarm_icon.setText(icon_char)
        self._alarm_banner.setVisible(True)

        if priority in ("CRITICAL", "WARNING"):
            self._apply_card_style(t, priority)
            self._bar_pv.set_alarm_state(priority)
        else:
            self._apply_card_style(t)
            self._bar_pv.set_alarm_state(None)

    def _on_blink_tick(self) -> None:
        """Toggle banner visibility for unacknowledged alarm blink."""
        self._blink_visible = not self._blink_visible
        if self._alarm_priority is None:
            self._blink_timer.stop()
            return

        if self._blink_visible:
            color = _alarm_color(self._theme, self._alarm_priority)
            br = _theme_attr(self._theme, "border_radius", "6px")
            self._alarm_banner.setStyleSheet(
                f"background: {color};"
                f" border-top-left-radius: {br};"
                f" border-top-right-radius: {br};"
            )
        else:
            self._alarm_banner.setStyleSheet("background: transparent;")

    # ── Interaction ──────────────────────────────────────────────

    def _on_settings_clicked(self) -> None:
        self.settings_requested.emit(self._controller_id)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        child = self.childAt(event.position().toPoint())
        if child is self._settings_btn:
            return
        self.controller_selected.emit(self._controller_id)
        super().mousePressEvent(event)
