"""AlarmBarWidget — footer strip showing last 10 alarms."""
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

if TYPE_CHECKING:
    from smart_pid_hmi.themes.base import ThemeBase

_MAX_ALARMS = 5
_BAR_HEIGHT = 110


def _theme_attr(theme: ThemeBase, attr: str, fallback: str) -> str:
    """Return theme attribute if non-empty, else fallback."""
    val = getattr(theme, attr, "")
    return val if val else fallback


class AlarmBarWidget(QFrame):
    """Fixed-height footer showing recent alarms with semantic coloring."""

    ack_all_requested = Signal()

    def __init__(
        self, theme: ThemeBase, parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._theme = theme
        self._alarms: list[dict] = []
        self._counts: dict[str, int] = {
            "CRITICAL": 0, "WARNING": 0, "ADVISORY": 0,
        }

        self.setFixedHeight(_BAR_HEIGHT)
        self._apply_bar_style(theme)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(4)

        # Left column: title + alarm entries (vertical)
        left = QVBoxLayout()
        left.setSpacing(2)

        self._counter_label = QLabel("[ LOG ALARMES ]")
        self._counter_label.setStyleSheet(
            f"color: {theme.fg_primary}; background: transparent; "
            f"font-size: {theme.font_size_label}px; "
            f"font-weight: bold; padding: 0;"
        )
        left.addWidget(self._counter_label)

        # Alarm entries container (vertical list)
        self._container = QWidget()
        self._container_layout = QVBoxLayout(self._container)
        self._container_layout.setContentsMargins(0, 0, 0, 0)
        self._container_layout.setSpacing(1)
        self._container_layout.addStretch()
        left.addWidget(self._container, stretch=1)

        layout.addLayout(left, stretch=1)

        # Right: ACK ALL button
        self._ack_btn = QPushButton("ACK ALL")
        self._ack_btn.setFixedHeight(28)
        self._ack_btn.setFixedWidth(70)
        self._ack_btn.clicked.connect(self.ack_all_requested.emit)
        self._apply_ack_style(theme)
        layout.addWidget(self._ack_btn, alignment=Qt.AlignmentFlag.AlignTop)

    def _apply_bar_style(self, theme: ThemeBase) -> None:
        bg = _theme_attr(theme, "bg_toolbar", theme.bg_secondary)
        self.setStyleSheet(
            f"AlarmBarWidget {{ background-color: {bg}; "
            f"border-top: 1px solid {theme.border}; }}"
        )

    def _apply_ack_style(self, theme: ThemeBase) -> None:
        accent = _theme_attr(theme, "accent", theme.fg_secondary)
        br = _theme_attr(theme, "border_radius", "0px")
        self._ack_btn.setStyleSheet(
            f"QPushButton {{ "
            f"background-color: {theme.bg_secondary}; "
            f"color: {accent}; "
            f"border: 1px solid {accent}; "
            f"border-radius: {br}; "
            f"padding: 2px 12px; "
            f"font-size: {theme.font_size_label}px; "
            f"font-weight: bold; }} "
            f"QPushButton:hover {{ "
            f"background-color: {accent}; "
            f"color: {theme.fg_primary}; }}"
        )

    def apply_theme(self, theme: ThemeBase) -> None:
        """Update cached theme reference for dynamic theme switching."""
        self._theme = theme
        self._apply_bar_style(theme)
        self._apply_ack_style(theme)
        self._counter_label.setStyleSheet(
            f"color: {theme.fg_primary}; background: transparent; "
            f"font-size: {theme.font_size_label}px; "
            f"font-weight: bold; padding: 0 4px;"
        )
        self._rebuild()

    @property
    def alarm_count(self) -> int:
        return len(self._alarms)

    def on_alarm(self, controller_id: int, alarm: dict) -> None:
        priority = alarm.get("priority", "")
        transition = alarm.get("transition", "")
        if transition == "TRIGGERED" and priority in self._counts:
            self._counts[priority] += 1
        elif transition == "CLEARED" and priority in self._counts:
            self._counts[priority] = max(
                0, self._counts[priority] - 1
            )
        self._alarms.insert(0, alarm)
        if len(self._alarms) > _MAX_ALARMS:
            self._alarms = self._alarms[:_MAX_ALARMS]
        self._rebuild()

    def _rebuild(self) -> None:
        theme = self._theme

        # Update counter label with counts
        total = sum(self._counts.values())
        if total > 0:
            parts = []
            for name, count in self._counts.items():
                if count > 0:
                    parts.append(f"{name}: {count}")
            counter_text = (
                f"[ ALARMES ] {' | '.join(parts)}"
            )
        else:
            counter_text = "[ LOG ALARMES ]"
        self._counter_label.setText(counter_text)

        # Clear existing labels
        while self._container_layout.count() > 1:
            item = self._container_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        br = _theme_attr(theme, "border_radius", "0px")

        for alarm in self._alarms:
            priority = alarm.get("priority", "")

            # Choose pill background and icon
            if priority == "CRITICAL":
                bg = _theme_attr(
                    theme, "alarm_critical_bg", theme.alarm_critical,
                )
                icon = "\u25cf"  # filled circle
                text_color = theme.alarm_text
            elif priority == "WARNING":
                bg = _theme_attr(
                    theme, "alarm_warning_bg", theme.alarm_warning,
                )
                icon = "\u25b2"  # triangle
                text_color = theme.fg_primary
            else:
                bg = _theme_attr(
                    theme, "bg_hover", theme.bg_widget,
                )
                icon = "\u25cb"  # empty circle
                text_color = theme.fg_primary

            tag = alarm.get("controller_name", "?")
            atype = alarm.get("alarm_type", "?")
            ts = alarm.get("timestamp", "")
            # Show only HH:MM time part if ISO format
            if "T" in str(ts):
                ts = str(ts).split("T")[1][:5]

            pill_text = f" {icon} {ts} {atype} {tag} "
            label = QLabel(pill_text)
            label.setStyleSheet(
                f"background-color: {bg}; color: {text_color}; "
                f"font-size: {theme.font_size_label}px; "
                f"padding: 3px 8px; border: none; "
                f"border-radius: {br}; font-weight: bold;"
            )
            self._container_layout.insertWidget(
                self._container_layout.count() - 1, label,
            )
