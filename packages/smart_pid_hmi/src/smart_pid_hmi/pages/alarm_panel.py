"""AlarmPanel — alarm & event management page with active alarms table and ACK."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from PySide6.QtCore import QDateTime, Qt, QTimer, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
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
    "Controller", "Category", "Level", "Priority", "Value",
    "Limit", "Triggered", "Status",
]

_PRIORITY_ITEMS = ["CRITICAL", "WARNING", "ADVISORY", "LOG"]
_LEVEL_ITEMS = ["HIHI", "HI", "LO", "LOLO", "DV_HI", "DV_LO"]

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
        api_client: APIClientPort,
        parent: QWidget | None = None,
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

        filter_layout.addWidget(QLabel("Level:"))
        self._level_filter = CheckableComboBox()
        self._level_filter.add_items(_LEVEL_ITEMS, check_all=True)
        self._level_filter.setMinimumWidth(140)
        filter_layout.addWidget(self._level_filter)

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

        self._live_checkbox = QCheckBox("Live")
        self._live_checkbox.toggled.connect(self._on_live_toggled)
        filter_layout.addWidget(self._live_checkbox)

        # Live timer (5s refresh)
        self._live_timer = QTimer(self)
        self._live_timer.setInterval(5000)
        self._live_timer.timeout.connect(self._live_refresh)

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
        """Add an AI tuning action as event row (level/priority not applicable)."""
        ts = datetime.now().isoformat()[:19]
        event = {
            "controller_id": controller_id,
            "alarm_type": "",
            "_category": CATEGORY_AI,
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
        """Add a system event (e.g. login, config change). Level not applicable."""
        ts = datetime.now().isoformat()[:19]
        event = {
            "controller_id": "",
            "alarm_type": "",
            "_category": CATEGORY_SYSTEM,
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

    def on_all_acked(self) -> None:
        """Mark all active alarms as ACKNOWLEDGED (called after ACK All response)."""
        for key in self._active_alarms:
            self._active_alarms[key]["status"] = "ACKNOWLEDGED"
        self._rebuild_table()

    def on_alarm_acked(self, alarm_id: int) -> None:
        """Mark a specific alarm as ACKNOWLEDGED (called after single ACK response)."""
        for _key, alarm in self._active_alarms.items():
            if alarm.get("id") == alarm_id:
                alarm["status"] = "ACKNOWLEDGED"
                break
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
        level_all = self._level_filter.all_checked()
        levels = set(self._level_filter.checked_items())
        dt_from = self._dt_from.dateTime().toPython()
        dt_to = self._dt_to.dateTime().toPython()

        result: list[dict] = []
        for alarm in self._get_all_events():
            atype = alarm.get("alarm_type", "")
            category = alarm.get("_category") or _TYPE_TO_CATEGORY.get(
                atype, CATEGORY_ALARM
            )
            if category not in categories:
                continue
            pri = alarm.get("priority", "")
            if category == CATEGORY_ALARM:
                if not priority_all and pri not in priorities:
                    continue
                if not level_all and atype not in levels:
                    continue
            elif category == CATEGORY_SYSTEM:
                if not priority_all and pri not in priorities:
                    continue
                # Level filter does not apply to system events
            # AI Log: neither priority nor level filter applies

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
            category = alarm.get("_category") or _TYPE_TO_CATEGORY.get(
                atype, CATEGORY_ALARM
            )
            pri = alarm.get("priority", "")
            # AI Log: level and priority shown as "—"
            # System Event: level shown as "—"
            display_level = "\u2014" if category in (CATEGORY_AI, CATEGORY_SYSTEM) else atype
            display_pri = "\u2014" if category == CATEGORY_AI else pri
            ctrl_display = alarm.get("controller_name") or str(alarm.get("controller_id", ""))
            items = [
                ctrl_display,
                category,
                display_level,
                display_pri,
                f"{alarm.get('value', 0.0):.1f}",
                f"{alarm.get('limit', 0.0):.1f}",
                alarm.get("timestamp", ""),
                alarm.get("status", ""),
            ]
            priority = alarm.get("priority", "")
            color = colors.get(priority, self._theme.fg_muted or "#757575")
            alarm_id = alarm.get("id")
            text_color = QColor(self._theme.fg_primary or "#1A1A1A")
            for col, text in enumerate(items):
                item = QTableWidgetItem(text)
                item.setForeground(text_color)
                item.setBackground(Qt.GlobalColor.transparent)
                if col == 3:  # Priority column
                    item.setBackground(QColor(color))
                    item.setForeground(QColor("#FFFFFF"))
                item.setFlags(
                    item.flags() & ~Qt.ItemFlag.ItemIsEditable
                )
                if col == 0 and alarm_id is not None:
                    item.setData(
                        Qt.ItemDataRole.UserRole, alarm_id,
                    )
                self.active_table.setItem(row, col, item)

    def _on_live_toggled(self, checked: bool) -> None:
        """Toggle live mode."""
        self._dt_from.setEnabled(not checked)
        self._dt_to.setEnabled(not checked)
        self._load_history_btn.setEnabled(not checked)
        if checked:
            self._live_refresh()
            self._live_timer.start()
        else:
            self._live_timer.stop()

    def _live_refresh(self) -> None:
        """Fetch active alarms + recent system events for live view."""
        if self._api_client is None:
            return
        try:
            alarms = self._api_client.get_active_alarms()
        except Exception:  # noqa: BLE001
            alarms = []
        self._active_alarms.clear()
        for alarm in alarms:
            key = (alarm.get("controller_id", 0), alarm.get("alarm_type", ""))
            self._active_alarms[key] = {
                **alarm,
                "status": "ACKNOWLEDGED" if alarm.get("acknowledged") else "UNACKNOWLEDGED",
            }
        # Also fetch recent system events (last 5 min)
        from datetime import timedelta

        now = datetime.now(tz=UTC)
        try:
            sys_events = self._api_client.get_system_events(
                start=now - timedelta(minutes=5),
                end=now,
            )
            self._system_events = [
                {
                    "controller_id": "",
                    "alarm_type": "",
                    "_category": CATEGORY_SYSTEM,
                    "priority": e.get("severity", "INFO"),
                    "value": 0.0,
                    "limit": 0.0,
                    "timestamp": e.get("timestamp", ""),
                    "status": e.get("message", ""),
                    "transition": "INFO",
                }
                for e in sys_events
            ]
        except Exception:  # noqa: BLE001
            pass
        self._rebuild_table()

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
