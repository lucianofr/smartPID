"""AlarmBarWidget — footer strip showing last 10 alarms."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QScrollArea, QWidget

if TYPE_CHECKING:
    from smart_pid_hmi.themes.base import ThemeBase

_MAX_ALARMS = 10
_BAR_HEIGHT = 40


class AlarmBarWidget(QFrame):
    """Fixed-height footer showing recent alarms with semantic coloring."""

    def __init__(self, theme: ThemeBase, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._theme = theme
        self._alarms: list[dict] = []

        self.setFixedHeight(_BAR_HEIGHT)
        self.setStyleSheet(
            f"AlarmBarWidget {{ background-color: {theme.bg_secondary}; "
            f"border-top: 1px solid {theme.border}; }}"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(0)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet("border: none; background: transparent;")

        self._container = QWidget()
        self._container_layout = QHBoxLayout(self._container)
        self._container_layout.setContentsMargins(0, 0, 0, 0)
        self._container_layout.setSpacing(8)
        self._container_layout.addStretch()

        self._scroll.setWidget(self._container)
        layout.addWidget(self._scroll)

    @property
    def alarm_count(self) -> int:
        return len(self._alarms)

    def on_alarm(self, controller_id: int, alarm: dict) -> None:
        self._alarms.insert(0, alarm)
        if len(self._alarms) > _MAX_ALARMS:
            self._alarms = self._alarms[:_MAX_ALARMS]
        self._rebuild()

    def _rebuild(self) -> None:
        # Clear existing labels
        while self._container_layout.count() > 1:
            item = self._container_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for alarm in self._alarms:
            priority = alarm.get("priority", "")
            if priority == "CRITICAL":
                bg = self._theme.alarm_critical
            elif priority == "WARNING":
                bg = self._theme.alarm_warning
            else:
                bg = self._theme.bg_widget

            text_color = (
                self._theme.alarm_text
                if priority == "CRITICAL"
                else self._theme.fg_primary
            )
            tag = alarm.get("controller_name", "?")
            atype = alarm.get("alarm_type", "?")
            val = alarm.get("value", 0.0)
            ts = alarm.get("timestamp", "")
            # Show only time part if ISO format
            if "T" in str(ts):
                ts = str(ts).split("T")[1][:8]

            label = QLabel(f" {ts} | {tag} | {atype} | {val:.1f} ")
            label.setStyleSheet(
                f"background-color: {bg}; color: {text_color}; "
                f"font-size: {self._theme.font_size_label}px; "
                f"padding: 2px 6px; border: none;"
            )
            self._container_layout.insertWidget(
                self._container_layout.count() - 1, label
            )
