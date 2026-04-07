"""AlarmPanel — alarm & event management page with active alarms table and ACK."""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from PySide6.QtCore import QDateTime, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDateTimeEdit,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from smart_pid_hmi.widgets.checkable_combo import CheckableComboBox

if TYPE_CHECKING:
    from smart_pid_hmi.services.ports import APIClientPort
    from smart_pid_hmi.themes.base import ThemeBase

_ACTIVE_COLUMNS = [
    "Controller", "Category", "Type", "Priority", "Value",
    "Limit", "Triggered", "Status",
]

_PRIORITY_ITEMS = ["CRITICAL", "WARNING", "ADVISORY", "LOG"]
_TYPE_ITEMS = ["HIHI", "HI", "LO", "LOLO", "DV_HI", "DV_LO", "AI_LOG", "SYSTEM"]

# Categories
CATEGORY_ALARM = "Loop Alarm"
CATEGORY_AI = "AI Log"
CATEGORY_SYSTEM = "System Event"
_CATEGORY_ITEMS = [CATEGORY_ALARM, CATEGORY_AI, CATEGORY_SYSTEM]

# Map alarm_type -> category
_TYPE_TO_CATEGORY = {
    "HIHI": CATEGORY_ALARM,
    "HI": CATEGORY_ALARM,
    "LO": CATEGORY_ALARM,
    "LOLO": CATEGORY_ALARM,
    "DV_HI": CATEGORY_ALARM,
    "DV_LO": CATEGORY_ALARM,
    "AI_LOG": CATEGORY_AI,
    "SYSTEM": CATEGORY_SYSTEM,
}


def _priority_colors(theme: ThemeBase) -> dict[str, str]:
    """Build priority-to-color map from the current theme."""
    return {
        "CRITICAL": theme.alarm_critical,
        "WARNING": theme.alarm_warning,
        "ADVISORY": theme.accent or "#1976D2",
        "LOG": theme.fg_muted or "#757575",
    }


class AlarmPanel(QWidget):
    """Page for alarm & event management: active alarms + AI logs + system events."""

    ack_requested = Signal(int)  # alarm_id
    ack_all_requested = Signal()

    def __init__(
        self,
        theme: ThemeBase,
        parent: QWidget | None = None,
        api_client: APIClientPort | None = None,
    ) -> None:
        super().__init__(parent)
        self._theme = theme
        self._api_client = api_client
        # (controller_id, alarm_type) -> row data dict
        self._active_alarms: dict[tuple[int, str], dict] = {}
        # AI log events and system events (kept separately)
        self._ai_events: list[dict] = []
        self._system_events: list[dict] = []

        layout = QVBoxLayout(self)

        # --- Filter toolbar ---
        filter_layout = QHBoxLayout()

        filter_layout.addWidget(QLabel("Category:"))
        self._category_filter = CheckableComboBox()
        self._category_filter.add_items(_CATEGORY_ITEMS, check_all=True)
        self._category_filter.setMinimumWidth(140)
        filter_layout.addWidget(self._category_filter)

        filter_layout.addWidget(QLabel("Priority:"))
        self._priority_filter = CheckableComboBox()
        self._priority_filter.add_items(_PRIORITY_ITEMS, check_all=True)
        self._priority_filter.setMinimumWidth(140)
        filter_layout.addWidget(self._priority_filter)

        filter_layout.addWidget(QLabel("Type:"))
        self._type_filter = CheckableComboBox()
        self._type_filter.add_items(_TYPE_ITEMS, check_all=True)
        self._type_filter.setMinimumWidth(140)
        filter_layout.addWidget(self._type_filter)

        filter_layout.addWidget(QLabel("From:"))
        self._dt_from = QDateTimeEdit()
        self._dt_from.setCalendarPopup(True)
        self._dt_from.setDisplayFormat("yyyy-MM-dd HH:mm")
        now = QDateTime.currentDateTime()
        self._dt_from.setDateTime(now.addDays(-1))
        filter_layout.addWidget(self._dt_from)

        filter_layout.addWidget(QLabel("To:"))
        self._dt_to = QDateTimeEdit()
        self._dt_to.setCalendarPopup(True)
        self._dt_to.setDisplayFormat("yyyy-MM-dd HH:mm")
        self._dt_to.setDateTime(now)
        filter_layout.addWidget(self._dt_to)

        self._apply_btn = QPushButton("Apply")
        self._apply_btn.clicked.connect(self._apply_filters)
        filter_layout.addWidget(self._apply_btn)

        self._load_history_btn = QPushButton("Load History")
        self._load_history_btn.clicked.connect(self._load_history)
        filter_layout.addWidget(self._load_history_btn)

        filter_layout.addStretch()
        layout.addLayout(filter_layout)

        # --- Action buttons ---
        btn_layout = QHBoxLayout()
        self._ack_btn = QPushButton("ACK Selected")
        self._ack_all_btn = QPushButton("ACK All")
        btn_layout.addWidget(self._ack_btn)
        btn_layout.addWidget(self._ack_all_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self._ack_btn.clicked.connect(self._on_ack_selected)
        self._ack_all_btn.clicked.connect(self.ack_all_requested.emit)

        # Active alarms / events table (full height)
        self.active_table = QTableWidget(0, len(_ACTIVE_COLUMNS))
        self.active_table.setHorizontalHeaderLabels(_ACTIVE_COLUMNS)
        self.active_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.active_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        layout.addWidget(self.active_table)

    # --- Public API ---

    def on_ai_event(self, controller_id: int, message: str) -> None:
        """Add an AI tuning action as event row (type/priority not applicable)."""
        ts = datetime.now().isoformat()[:19]
        event = {
            "controller_id": controller_id,
            "alarm_type": "AI_LOG",
            "priority": "\u2014",
            "value": 0.0,
            "limit": 0.0,
            "timestamp": ts,
            "status": message,
            "transition": "INFO",
        }
        self._ai_events.append(event)
        if len(self._ai_events) > 500:
            self._ai_events = self._ai_events[-500:]
        self._rebuild_table()

    def on_system_event(self, message: str, priority: str = "LOG") -> None:
        """Add a system event (e.g. login, config change). Type not applicable."""
        ts = datetime.now().isoformat()[:19]
        event = {
            "controller_id": "",
            "alarm_type": "SYSTEM",
            "priority": priority,
            "value": 0.0,
            "limit": 0.0,
            "timestamp": ts,
            "status": message,
            "transition": "INFO",
        }
        self._system_events.append(event)
        if len(self._system_events) > 500:
            self._system_events = self._system_events[-500:]
        self._rebuild_table()

    def load_active_alarms(self) -> None:
        """Fetch currently active alarms from backend and populate table."""
        if self._api_client is None:
            return
        try:
            alarms = self._api_client.get_active_alarms()
        except Exception:  # noqa: BLE001
            return
        self._active_alarms.clear()
        for alarm in alarms:
            key = (alarm.get("controller_id", 0), alarm.get("alarm_type", ""))
            self._active_alarms[key] = {
                **alarm,
                "status": alarm.get("status", "UNACKNOWLEDGED"),
            }
        self._rebuild_table()

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
        elif transition == "CLEARED" and key in self._active_alarms:
            self._active_alarms[key]["status"] = "CLEARED_UNACK"
            self._active_alarms[key]["transition"] = "CLEARED"

        self._rebuild_table()

    # --- Filtering ---

    def _get_all_events(self) -> list[dict]:
        """Merge active alarms, AI events, and system events into one list."""
        return (
            list(self._active_alarms.values())
            + list(self._ai_events)
            + list(self._system_events)
        )

    def get_filtered_alarms(self) -> list[dict]:
        """Return events filtered by current UI criteria."""
        categories = (
            set(_CATEGORY_ITEMS)
            if self._category_filter.all_checked()
            else set(self._category_filter.checked_items())
        )
        priority_all = self._priority_filter.all_checked()
        priorities = set(self._priority_filter.checked_items())
        type_all = self._type_filter.all_checked()
        types = set(self._type_filter.checked_items())
        dt_from = self._dt_from.dateTime().toPython()
        dt_to = self._dt_to.dateTime().toPython()

        result: list[dict] = []
        for alarm in self._get_all_events():
            atype = alarm.get("alarm_type", "")
            category = _TYPE_TO_CATEGORY.get(atype, CATEGORY_SYSTEM)
            if category not in categories:
                continue
            # AI_LOG: priority/type not applicable — skip those filters
            # SYSTEM: type not applicable — skip type filter
            pri = alarm.get("priority", "")
            if category == CATEGORY_ALARM:
                if not priority_all and pri not in priorities:
                    continue
                if not type_all and atype not in types:
                    continue
            elif category == CATEGORY_SYSTEM:
                if not priority_all and pri not in priorities:
                    continue
                # Type filter does not apply to system events
            # AI Log: neither priority nor type filter applies

            ts_str = alarm.get("timestamp", "")
            if ts_str:
                try:
                    ts = datetime.fromisoformat(ts_str)
                    if ts < dt_from or ts > dt_to:
                        continue
                except (ValueError, TypeError):
                    pass
            result.append(alarm)
        return result

    def _apply_filters(self) -> None:
        """Rebuild table using current filter criteria."""
        filtered = self.get_filtered_alarms()
        self._rebuild_table(alarms=filtered)

    def _load_history(self) -> None:
        """Fetch historical alarms from backend and populate table."""
        if self._api_client is None:
            return
        dt_from = self._dt_from.dateTime().toPython()
        dt_to = self._dt_to.dateTime().toPython()
        try:
            history = self._api_client.get_alarm_history(
                start=dt_from, end=dt_to,
            )
        except Exception:  # noqa: BLE001
            return
        self._rebuild_table(alarms=history)

    # --- Table rendering ---

    def _rebuild_table(
        self, alarms: list[dict] | None = None,
    ) -> None:
        if alarms is None:
            alarms = self._get_all_events()

        colors = _priority_colors(self._theme)

        self.active_table.setRowCount(0)
        for alarm in alarms:
            row = self.active_table.rowCount()
            self.active_table.insertRow(row)
            atype = alarm.get("alarm_type", "")
            category = _TYPE_TO_CATEGORY.get(atype, CATEGORY_SYSTEM)
            pri = alarm.get("priority", "")
            # AI Log: type and priority shown as "—"
            # System Event: type shown as "—"
            display_type = "\u2014" if category in (CATEGORY_AI, CATEGORY_SYSTEM) else atype
            display_pri = "\u2014" if category == CATEGORY_AI else pri
            items = [
                str(alarm.get("controller_id", "")),
                category,
                display_type,
                display_pri,
                f"{alarm.get('value', 0.0):.1f}",
                f"{alarm.get('limit', 0.0):.1f}",
                alarm.get("timestamp", ""),
                alarm.get("status", ""),
            ]
            priority = alarm.get("priority", "")
            color = colors.get(priority, self._theme.fg_muted or "#757575")
            alarm_id = alarm.get("alarm_id")
            for col, text in enumerate(items):
                item = QTableWidgetItem(text)
                item.setForeground(Qt.GlobalColor.white)
                item.setBackground(Qt.GlobalColor.transparent)
                if col == 3:  # Priority column
                    item.setBackground(QColor(color))
                item.setFlags(
                    item.flags() & ~Qt.ItemFlag.ItemIsEditable
                )
                if col == 0 and alarm_id is not None:
                    item.setData(
                        Qt.ItemDataRole.UserRole, alarm_id,
                    )
                self.active_table.setItem(row, col, item)

    def _on_ack_selected(self) -> None:
        selected = self.active_table.selectedItems()
        if selected:
            row = selected[0].row()
            first_item = self.active_table.item(row, 0)
            if first_item is not None:
                alarm_id = first_item.data(Qt.ItemDataRole.UserRole)
                if alarm_id is not None:
                    self.ack_requested.emit(int(alarm_id))

    def apply_theme(self, theme: ThemeBase) -> None:
        """Re-apply theme colors to dynamic elements."""
        self._theme = theme
        self._rebuild_table()
