"""AlarmBarWidget — QTableWidget grid showing active alarms (spec section 8.1)."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from smart_pid_hmi.themes.base import ThemeBase

_BAR_HEIGHT = 130
_COLUMNS = ["Priority", "Level", "Loop", "Description", "Date/Time", "ACK"]

_PRIORITY_RANK = {"CRITICAL": 0, "WARNING": 1, "ADVISORY": 2}
def _utc_to_local(ts_str: str) -> str:
    """Convert ISO UTC timestamp to local time string."""
    try:
        dt = datetime.fromisoformat(ts_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.astimezone().strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return ts_str[:19].replace("T", " ") if ts_str else ""


_PRIORITY_COLORS = {
    "CRITICAL": "#D32F2F",
    "WARNING": "#FBC02D",
    "ADVISORY": "#1976D2",
}
_PRIORITY_TEXT = {
    "CRITICAL": "#FFFFFF",
    "WARNING": "#000000",
    "ADVISORY": "#FFFFFF",
}


def _theme_attr(theme: ThemeBase, attr: str, fallback: str) -> str:
    """Return theme attribute if non-empty, else fallback."""
    val = getattr(theme, attr, "")
    return val if val else fallback


class AlarmBarWidget(QFrame):
    """Fixed-height footer grid showing active alarms with per-row ACK."""

    ack_requested = Signal(int)       # alarm_id for single ACK
    ack_all_requested = Signal()

    def __init__(
        self, theme: ThemeBase, parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._theme = theme
        self._active: dict[tuple[int, str], dict] = {}

        self.setFixedHeight(_BAR_HEIGHT)
        bg = _theme_attr(theme, "bg_toolbar", theme.bg_secondary)
        self.setStyleSheet(
            f"AlarmBarWidget {{ background-color: {bg}; "
            f"border-top: 1px solid {theme.border}; }}"
        )

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(8, 4, 8, 4)
        main_layout.setSpacing(4)

        left = QVBoxLayout()
        left.setSpacing(2)

        self._counter_label = QLabel("[ ACTIVE ALARMS ]")
        self._counter_label.setStyleSheet(
            f"color: {theme.fg_primary}; background: transparent; "
            f"font-size: {theme.font_size_label}px; font-weight: bold; padding: 0;"
        )
        left.addWidget(self._counter_label)

        self._table = QTableWidget(0, len(_COLUMNS))
        self._table.setHorizontalHeaderLabels(_COLUMNS)
        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        hdr.resizeSection(4, 150)  # Date/Time — enough for "YYYY-MM-DD HH:MM:SS"
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        left.addWidget(self._table, stretch=1)

        main_layout.addLayout(left, stretch=1)

        right = QVBoxLayout()
        self._ack_btn = QPushButton("ACK\nALL")
        self._ack_btn.setFixedWidth(60)
        self._ack_btn.clicked.connect(self.ack_all_requested.emit)
        right.addWidget(self._ack_btn)
        right.addStretch()
        main_layout.addLayout(right)

        self._blink_timer = QTimer(self)
        self._blink_timer.setInterval(500)
        self._blink_timer.timeout.connect(self._on_blink)
        self._blink_visible = True

    @property
    def alarm_count(self) -> int:
        """Return number of active alarms."""
        return len(self._active)

    def load_active_alarms(self, alarms: list[dict]) -> None:
        """Seed the bar with active alarms from backend REST API."""
        self._active.clear()
        for alarm in alarms:
            cid = alarm.get("controller_id", 0)
            atype = alarm.get("alarm_type", "")
            priority = alarm.get("priority", "")
            if priority == "LOG" or not atype:
                continue
            key = (cid, atype)
            # Skip already-cleared alarms (returned by API for ISA-18.2 but not
            # actively alarming — the alarm panel handles those separately)
            if alarm.get("cleared_at") is not None:
                continue
            acked = bool(alarm.get("acknowledged", False))
            self._active[key] = {**alarm, "acked": acked, "transition": "TRIGGERED"}
        self._rebuild()

    def on_alarm(self, alarm: dict) -> None:
        """Handle alarm event — add on TRIGGERED, remove on CLEARED."""
        cid = alarm.get("controller_id", 0)
        atype = alarm.get("alarm_type", "")
        priority = alarm.get("priority", "")
        transition = alarm.get("transition", "")

        if priority == "LOG":
            return

        key = (cid, atype)

        if transition == "TRIGGERED":
            self._active[key] = {**alarm, "acked": False}
        elif transition == "CLEARED":
            self._active.pop(key, None)

        self._rebuild()

    def on_alarm_acked(self, controller_id: int, alarm_type: str) -> None:
        """Mark specific alarm as acknowledged."""
        key = (controller_id, alarm_type)
        if key in self._active:
            self._active[key]["acked"] = True
        self._rebuild()

    def on_all_alarms_acked(self) -> None:
        """Mark all active alarms as acknowledged."""
        for info in self._active.values():
            info["acked"] = True
        self._rebuild()

    def _rebuild(self) -> None:
        """Sort alarms, rebuild table rows, update counters and blink timer."""
        # Sort: group by priority (CRITICAL first), within each group newest first
        groups: dict[str, list[dict]] = {}
        for alarm in self._active.values():
            pri = alarm.get("priority", "")
            groups.setdefault(pri, []).append(alarm)
        sorted_alarms: list[dict] = []
        for pri in ["CRITICAL", "WARNING", "ADVISORY"]:
            grp = groups.get(pri, [])
            grp.sort(key=lambda a: a.get("timestamp", ""), reverse=True)
            sorted_alarms.extend(grp)

        self._table.setRowCount(0)
        has_unacked = False

        for alarm in sorted_alarms:
            row = self._table.rowCount()
            self._table.insertRow(row)
            priority = alarm.get("priority", "")
            acked = alarm.get("acked", False)
            if not acked:
                has_unacked = True

            items = [
                priority,
                alarm.get("alarm_type", ""),
                alarm.get("controller_name", "?"),
                alarm.get("controller_description", ""),
                _utc_to_local(alarm.get("timestamp", "")),
                "\u2713" if acked else "ACK",
            ]
            color = _PRIORITY_COLORS.get(priority, "#757575")
            text_color = _PRIORITY_TEXT.get(priority, "#FFFFFF")

            for col, text in enumerate(items):
                item = QTableWidgetItem(text)
                item.setForeground(QColor(text_color))
                item.setBackground(QColor(color))
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self._table.setItem(row, col, item)

        # Update counters
        unacked_counts: dict[str, int] = {"CRITICAL": 0, "WARNING": 0, "ADVISORY": 0}
        for alarm in self._active.values():
            if not alarm.get("acked", False):
                pri = alarm.get("priority", "")
                if pri in unacked_counts:
                    unacked_counts[pri] += 1

        parts = [f"{k}: {v}" for k, v in unacked_counts.items() if v > 0]
        if parts:
            self._counter_label.setText(f"[ ACTIVE ALARMS ] {' | '.join(parts)}")
        else:
            self._counter_label.setText("[ ACTIVE ALARMS ]")

        if has_unacked and not self._blink_timer.isActive():
            self._blink_visible = True
            self._blink_timer.start()
        elif not has_unacked and self._blink_timer.isActive():
            self._blink_timer.stop()
            # Restore solid colors on all rows after blink stops
            self._restore_solid_colors()

    def _restore_solid_colors(self) -> None:
        """Ensure all rows show their solid priority color (after blink stops)."""
        for row in range(self._table.rowCount()):
            pri_item = self._table.item(row, 0)
            if pri_item:
                priority = pri_item.text()
                color = _PRIORITY_COLORS.get(priority, "#757575")
                for col in range(self._table.columnCount()):
                    item = self._table.item(row, col)
                    if item:
                        item.setBackground(QColor(color))

    def _on_blink(self) -> None:
        """Toggle background color for unacked alarm rows."""
        self._blink_visible = not self._blink_visible
        for row in range(self._table.rowCount()):
            ack_item = self._table.item(row, 5)
            if ack_item and ack_item.text() != "\u2713":
                pri_item = self._table.item(row, 0)
                if pri_item:
                    priority = pri_item.text()
                    color = _PRIORITY_COLORS.get(priority, "#757575")
                    for col in range(self._table.columnCount()):
                        item = self._table.item(row, col)
                        if item:
                            if self._blink_visible:
                                item.setBackground(QColor(color))
                            else:
                                item.setBackground(QColor("transparent"))

    def apply_theme(self, theme: ThemeBase) -> None:
        """Update cached theme reference for dynamic theme switching."""
        self._theme = theme
        bg = _theme_attr(theme, "bg_toolbar", theme.bg_secondary)
        self.setStyleSheet(
            f"AlarmBarWidget {{ background-color: {bg}; "
            f"border-top: 1px solid {theme.border}; }}"
        )
        self._counter_label.setStyleSheet(
            f"color: {theme.fg_primary}; background: transparent; "
            f"font-size: {theme.font_size_label}px; font-weight: bold; padding: 0;"
        )
        self._rebuild()
