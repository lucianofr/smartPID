"""AlarmPanel — alarm management page with active alarms table and ACK."""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from PySide6.QtCore import QDateTime, Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QComboBox,
    QDateTimeEdit,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from smart_pid_hmi.services.ports import APIClientPort
    from smart_pid_hmi.themes.base import ThemeBase

_ACTIVE_COLUMNS = [
    "Controller", "Type", "Priority", "Value",
    "Limit", "Triggered", "Status",
]
_PRIORITY_CHOICES = ["All", "CRITICAL", "HIGH", "MEDIUM", "LOW"]
_TYPE_CHOICES = ["All", "HI_HI", "HI", "LO", "LO_LO", "RATE"]

_AI_LOG_MAX_LINES = 500


def _priority_colors(theme: ThemeBase) -> dict[str, str]:
    """Build priority-to-color map from the current theme."""
    return {
        "CRITICAL": theme.alarm_critical,
        "WARNING": theme.alarm_warning,
        "ADVISORY": theme.accent or "#1976D2",
        "LOG": theme.fg_muted or "#757575",
        "HIGH": theme.alarm_critical,
        "MEDIUM": theme.alarm_warning,
        "LOW": theme.accent or "#1976D2",
    }


class AlarmPanel(QWidget):
    """Page for alarm management: active alarms + ACK controls."""

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

        layout = QVBoxLayout(self)

        # --- Filter toolbar ---
        filter_layout = QHBoxLayout()

        filter_layout.addWidget(QLabel("Priority:"))
        self._priority_filter = QComboBox()
        self._priority_filter.addItems(_PRIORITY_CHOICES)
        filter_layout.addWidget(self._priority_filter)

        filter_layout.addWidget(QLabel("Type:"))
        self._type_filter = QComboBox()
        self._type_filter.addItems(_TYPE_CHOICES)
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

        # --- Splitter: table + AI log ---
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Active alarms table
        self.active_table = QTableWidget(0, len(_ACTIVE_COLUMNS))
        self.active_table.setHorizontalHeaderLabels(_ACTIVE_COLUMNS)
        self.active_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.active_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        splitter.addWidget(self.active_table)

        # AI Log Box (terminal-style)
        self._ai_log = QPlainTextEdit()
        self._ai_log.setReadOnly(True)
        self._ai_log.setMaximumBlockCount(_AI_LOG_MAX_LINES)
        ai_font = QFont("Fira Code", 11)
        ai_font.setStyleHint(QFont.StyleHint.Monospace)
        self._ai_log.setFont(ai_font)
        self._apply_ai_log_style(theme)
        self._ai_log.setPlaceholderText("AI tuning log...")
        splitter.addWidget(self._ai_log)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter)

    def _apply_ai_log_style(self, theme: ThemeBase) -> None:
        """Apply theme-aware style to the AI log box."""
        bg = theme.bg_card or theme.bg_secondary
        fg = theme.accent or theme.fg_primary
        bdr = theme.border
        self._ai_log.setStyleSheet(
            "QPlainTextEdit {"
            f"  background-color: {bg};"
            f"  color: {fg};"
            f"  border: 1px solid {bdr};"
            "  padding: 4px;"
            "}"
        )

    # --- Public API ---

    def append_ai_log(self, message: str) -> None:
        """Append a message to the AI log box with auto-scroll."""
        self._ai_log.appendPlainText(message)

    @property
    def ai_log_widget(self) -> QPlainTextEdit:
        """Expose AI log widget for testing."""
        return self._ai_log

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

    def get_filtered_alarms(self) -> list[dict]:
        """Return the active alarms filtered by current UI criteria."""
        priority = self._priority_filter.currentText()
        atype = self._type_filter.currentText()
        dt_from = self._dt_from.dateTime().toPython()
        dt_to = self._dt_to.dateTime().toPython()

        result: list[dict] = []
        for alarm in self._active_alarms.values():
            if priority != "All" and alarm.get("priority", "") != priority:
                continue
            if atype != "All" and alarm.get("alarm_type", "") != atype:
                continue
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
            alarms = list(self._active_alarms.values())

        colors = _priority_colors(self._theme)

        self.active_table.setRowCount(0)
        for alarm in alarms:
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
            color = colors.get(priority, self._theme.fg_muted or "#757575")
            alarm_id = alarm.get("alarm_id")
            for col, text in enumerate(items):
                item = QTableWidgetItem(text)
                item.setForeground(Qt.GlobalColor.white)
                item.setBackground(Qt.GlobalColor.transparent)
                if col == 2:  # Priority column
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
        self._apply_ai_log_style(theme)
        self._rebuild_table()
