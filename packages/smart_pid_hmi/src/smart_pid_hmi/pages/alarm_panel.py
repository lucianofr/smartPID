"""AlarmPanel — alarm management page with active alarms table and ACK controls."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from smart_pid_hmi.themes.base import ThemeBase

_ACTIVE_COLUMNS = ["Controller", "Type", "Priority", "Value", "Limit", "Triggered", "Status"]
_PRIORITY_COLORS = {
    "CRITICAL": "#D32F2F",
    "WARNING": "#FFA000",
    "ADVISORY": "#1976D2",
    "LOG": "#757575",
}


class AlarmPanel(QWidget):
    """Page for alarm management: active alarms + ACK controls."""

    ack_requested = Signal(int)  # alarm_id
    ack_all_requested = Signal()

    def __init__(self, theme: ThemeBase, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._theme = theme
        # (controller_id, alarm_type) -> row data dict
        self._active_alarms: dict[tuple[int, str], dict] = {}

        layout = QVBoxLayout(self)

        # Buttons
        btn_layout = QHBoxLayout()
        self._ack_btn = QPushButton("ACK Selected")
        self._ack_all_btn = QPushButton("ACK All")
        btn_layout.addWidget(self._ack_btn)
        btn_layout.addWidget(self._ack_all_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self._ack_btn.clicked.connect(self._on_ack_selected)
        self._ack_all_btn.clicked.connect(self.ack_all_requested.emit)

        # Active alarms table
        self.active_table = QTableWidget(0, len(_ACTIVE_COLUMNS))
        self.active_table.setHorizontalHeaderLabels(_ACTIVE_COLUMNS)
        self.active_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.active_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.active_table)

    def on_alarm(self, controller_id: int, alarm: dict) -> None:
        """Handle an alarm transition from BusBridge."""
        atype = alarm.get("alarm_type", "")
        transition = alarm.get("transition", "")
        key = (controller_id, atype)

        if transition == "TRIGGERED":
            self._active_alarms[key] = {
                **alarm,
                "status": "UNACKNOWLEDGED",
            }
        elif transition == "CLEARED":
            if key in self._active_alarms:
                self._active_alarms[key]["status"] = "CLEARED_UNACK"
                self._active_alarms[key]["transition"] = "CLEARED"

        self._rebuild_table()

    def _rebuild_table(self) -> None:
        self.active_table.setRowCount(0)
        for (_cid, _atype), alarm in self._active_alarms.items():
            row = self.active_table.rowCount()
            self.active_table.insertRow(row)
            items = [
                str(alarm.get("controller_id", "")),
                alarm.get("alarm_type", ""),
                alarm.get("priority", ""),
                f"{alarm.get('value', 0.0):.1f}",
                f"{alarm.get('limit', 0.0):.1f}",
                alarm.get("timestamp", ""),
                alarm.get("status", ""),
            ]
            priority = alarm.get("priority", "")
            color = _PRIORITY_COLORS.get(priority, "#757575")
            for col, text in enumerate(items):
                item = QTableWidgetItem(text)
                item.setForeground(Qt.GlobalColor.white)
                item.setBackground(Qt.GlobalColor.transparent)
                if col == 2:  # Priority column
                    item.setBackground(QColor(color))
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.active_table.setItem(row, col, item)

    def _on_ack_selected(self) -> None:
        selected = self.active_table.selectedItems()
        if selected:
            row = selected[0].row()
            alarm_id_text = self.active_table.item(row, 0)
            if alarm_id_text:
                self.ack_requested.emit(row)
