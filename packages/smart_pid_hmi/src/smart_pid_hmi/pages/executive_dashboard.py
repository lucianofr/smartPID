"""ExecutiveDashboardPage — KPI cards and performance table."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from smart_pid_hmi.themes.base import ThemeBase

_PERF_COLUMNS = ["Loop", "Mode", "PV", "SP", "Error%", "IAE", "Status"]


class _KPICard(QFrame):
    """Internal KPI display card with title and value labels."""

    def __init__(
        self,
        title: str,
        theme: ThemeBase | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._theme = theme
        self.setFrameShape(QFrame.Shape.StyledPanel)

        bg = theme.bg_card if theme else ""
        bdr = theme.border if theme else ""
        radius = theme.border_radius if theme else "0px"
        if bg:
            self.setStyleSheet(
                f"_KPICard {{ background-color: {bg};"
                f" border: 1px solid {bdr};"
                f" border-radius: {radius}; }}"
            )

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        fg2 = theme.fg_secondary if theme else ""
        self._title_label = QLabel(title)
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title_label.setStyleSheet(
            f"font-weight: bold; font-size: 12px;"
            f" color: {fg2}; background: transparent;"
            if fg2 else "font-weight: bold; font-size: 12px;"
        )
        layout.addWidget(self._title_label)

        accent = theme.accent if theme else ""
        self._value_label = QLabel("0")
        self._value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._value_label.setStyleSheet(
            f"font-size: 24px; font-weight: bold;"
            f" color: {accent}; background: transparent;"
            if accent else "font-size: 24px; font-weight: bold;"
        )
        layout.addWidget(self._value_label)

    @property
    def value_label(self) -> QLabel:
        return self._value_label

    @property
    def title_label(self) -> QLabel:
        return self._title_label

    def set_value(self, value: str) -> None:
        self._value_label.setText(value)

    def apply_theme(self, theme: ThemeBase) -> None:
        """Re-apply theme to card."""
        self._theme = theme
        self.setStyleSheet(
            f"_KPICard {{ background-color: {theme.bg_card};"
            f" border: 1px solid {theme.border};"
            f" border-radius: {theme.border_radius}; }}"
        )
        self._title_label.setStyleSheet(
            f"font-weight: bold; font-size: 12px;"
            f" color: {theme.fg_secondary}; background: transparent;"
        )
        self._value_label.setStyleSheet(
            f"font-size: 24px; font-weight: bold;"
            f" color: {theme.accent}; background: transparent;"
        )


class ExecutiveDashboardPage(QWidget):
    """Executive dashboard with KPI cards row and performance table."""

    def __init__(
        self,
        theme: ThemeBase | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._theme = theme

        layout = QVBoxLayout(self)

        # Title
        title = QLabel("Executive Dashboard")
        title.setObjectName("title_label")
        fg = theme.fg_primary if theme else ""
        title.setStyleSheet(
            f"font-size: 20px; font-weight: bold; color: {fg};"
            " background: transparent;"
            if fg else "font-size: 20px; font-weight: bold;"
        )
        layout.addWidget(title)

        # KPI cards row
        kpi_row = QHBoxLayout()
        self._card_total = _KPICard("Total Loops", theme=theme)
        self._card_auto = _KPICard("In AUTO", theme=theme)
        self._card_alarms = _KPICard("Active Alarms", theme=theme)
        self._card_ai = _KPICard("AI Tuning Active", theme=theme)

        self._kpi_total = self._card_total.value_label
        self._kpi_auto = self._card_auto.value_label
        self._kpi_alarms = self._card_alarms.value_label
        self._kpi_ai = self._card_ai.value_label

        for card in (
            self._card_total, self._card_auto,
            self._card_alarms, self._card_ai,
        ):
            kpi_row.addWidget(card)
        layout.addLayout(kpi_row)

        # Performance table
        self._table = QTableWidget(0, len(_PERF_COLUMNS))
        self._table.setObjectName("performance_table")
        self._table.setHorizontalHeaderLabels(_PERF_COLUMNS)
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self._table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows,
        )
        self._table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers,
        )
        layout.addWidget(self._table, stretch=1)

    def update_kpis(
        self,
        total: int,
        in_auto: int,
        active_alarms: int,
        ai_active: int,
    ) -> None:
        """Update KPI card values."""
        self._kpi_total.setText(str(total))
        self._kpi_auto.setText(str(in_auto))
        self._kpi_alarms.setText(str(active_alarms))
        self._kpi_ai.setText(str(ai_active))

    def update_performance_table(self, rows: list[dict]) -> None:
        """Populate the performance table from a list of row dicts.

        Expected keys: loop, mode, pv, sp, error_pct, iae, status.
        """
        self._table.setRowCount(0)
        for row_data in rows:
            row_idx = self._table.rowCount()
            self._table.insertRow(row_idx)
            values = [
                str(row_data.get("loop", "")),
                str(row_data.get("mode", "")),
                f"{row_data.get('pv', 0.0):.1f}",
                f"{row_data.get('sp', 0.0):.1f}",
                f"{row_data.get('error_pct', 0.0):.1f}",
                f"{row_data.get('iae', 0.0):.1f}",
                str(row_data.get("status", "")),
            ]
            for col, val in enumerate(values):
                item = QTableWidgetItem(val)
                item.setFlags(
                    item.flags() & ~Qt.ItemFlag.ItemIsEditable,
                )
                self._table.setItem(row_idx, col, item)

    def apply_theme(self, theme: ThemeBase) -> None:
        """Re-apply theme colors to KPI cards and labels."""
        self._theme = theme
        for card in (
            self._card_total, self._card_auto,
            self._card_alarms, self._card_ai,
        ):
            card.apply_theme(theme)
