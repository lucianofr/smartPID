"""MultiTrendPage — 2x2 grid of pyqtgraph trend plots with loop selectors."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtGui import QPen
from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from smart_pid_hmi.themes.base import ThemeBase

_TIME_RANGES = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600}


class MultiTrendPage(QWidget):
    """2x2 grid of trend plots with time range and live mode controls."""

    def __init__(
        self,
        theme: ThemeBase | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._theme = theme

        # Resolve curve colors from theme or fallback
        pv_color = theme.chart_pv if theme else "#00BCD4"
        sp_color = theme.chart_sp if theme else "#FFC107"
        co_color = theme.chart_co if theme else "#4CAF50"
        grid_bg = theme.chart_bg if theme else "#1E1E1E"
        grid_color = theme.chart_grid if theme else "#333337"

        root = QVBoxLayout(self)

        # Controls row
        ctrl_row = QHBoxLayout()

        self._time_combo = QComboBox()
        self._time_combo.setObjectName("time_range_combo")
        self._time_combo.addItems(list(_TIME_RANGES.keys()))
        ctrl_row.addWidget(self._time_combo)

        self._live_btn = QPushButton("Live")
        self._live_btn.setObjectName("live_mode_btn")
        self._live_btn.setCheckable(True)
        self._live_btn.setChecked(True)
        ctrl_row.addWidget(self._live_btn)

        ctrl_row.addStretch()
        root.addLayout(ctrl_row)

        # 2x2 grid of plots
        grid = QGridLayout()
        self._plots: list[pg.PlotWidget] = []
        self._loop_combos: list[QComboBox] = []
        self._pv_curves: list[pg.PlotDataItem] = []
        self._sp_curves: list[pg.PlotDataItem] = []
        self._co_curves: list[pg.PlotDataItem] = []
        self._co_viewboxes: list[pg.ViewBox] = []
        self._mode_labels: list[QLabel] = []

        for i in range(4):
            container = QVBoxLayout()

            header_row = QHBoxLayout()
            loop_combo = QComboBox()
            loop_combo.setObjectName(f"loop_combo_{i}")
            header_row.addWidget(loop_combo, stretch=1)

            mode_label = QLabel("\u2014")
            mode_label.setObjectName(f"mode_label_{i}")
            mode_label.setFixedHeight(20)
            mode_label.setStyleSheet(
                "font-weight: bold; padding: 2px 6px; border-radius: 3px;"
            )
            header_row.addWidget(mode_label)
            self._mode_labels.append(mode_label)

            container.addLayout(header_row)
            self._loop_combos.append(loop_combo)

            pw = pg.PlotWidget()
            pw.setBackground(grid_bg)
            pw.showGrid(x=True, y=True, alpha=0.3)
            pw.getAxis("bottom").setPen(pg.mkPen(grid_color))
            pw.getAxis("left").setPen(pg.mkPen(grid_color))
            pw.setLabel("bottom", "Time", units="s")
            pw.setLabel("left", "PV / SP")
            container.addWidget(pw)

            # Primary curves: PV and SP
            pv_curve = pw.plot(
                pen=pg.mkPen(pv_color, width=2), name="PV",
            )
            sp_curve = pw.plot(
                pen=pg.mkPen(sp_color, width=2), name="SP",
            )

            # Secondary Y axis for CO
            co_viewbox = pg.ViewBox()
            pw.scene().addItem(co_viewbox)
            pw.getAxis("right").linkToView(co_viewbox)
            co_viewbox.setXLink(pw)
            pw.showAxis("right")
            pw.setLabel("right", "CO")

            co_pen = QPen(
                pg.mkColor(co_color), 2, Qt.PenStyle.DashLine,
            )
            co_curve = pg.PlotDataItem(pen=pg.mkPen(co_pen))
            co_viewbox.addItem(co_curve)

            self._plots.append(pw)
            self._pv_curves.append(pv_curve)
            self._sp_curves.append(sp_curve)
            self._co_curves.append(co_curve)
            self._co_viewboxes.append(co_viewbox)

            row, col = divmod(i, 2)
            grid.addLayout(container, row, col)

        # Gap #36: Synchronize X-axis zoom/pan across all 4 plots
        self._syncing_x_range = False
        for i in range(4):
            vb = self._plots[i].plotItem.vb
            vb.sigXRangeChanged.connect(
                lambda _vb, x_range, idx=i: self._on_x_range_changed(idx, x_range)
            )

        root.addLayout(grid, stretch=1)

    def update_plot(
        self,
        index: int,
        timestamps: list[float],
        pvs: list[float],
        sps: list[float],
        cos: list[float],
    ) -> None:
        """Update data for one of the 4 plots (0-3)."""
        if 0 <= index < 4:
            self._pv_curves[index].setData(timestamps, pvs)
            self._sp_curves[index].setData(timestamps, sps)
            self._co_curves[index].setData(timestamps, cos)

    def set_live_mode(self, enabled: bool) -> None:
        """Toggle live mode."""
        self._live_btn.setChecked(enabled)

    def set_available_loops(self, loops: list[str]) -> None:
        """Populate all loop selector combos."""
        for combo in self._loop_combos:
            combo.clear()
            combo.addItems(loops)

    def clear_data(self, index: int) -> None:
        """Clear plot data for the given index."""
        if 0 <= index < 4:
            self._pv_curves[index].setData([], [])
            self._sp_curves[index].setData([], [])
            self._co_curves[index].setData([], [])

    def set_mode(self, index: int, mode: str) -> None:
        """Update the displayed controller mode for a plot panel (0-3)."""
        if 0 <= index < 4:
            self._mode_labels[index].setText(mode)

    def _on_x_range_changed(self, source_idx: int, x_range: list) -> None:
        """Sync X-axis range from *source_idx* to all other plots."""
        if self._syncing_x_range:
            return
        self._syncing_x_range = True
        try:
            for i in range(4):
                if i != source_idx:
                    self._plots[i].plotItem.vb.setXRange(
                        x_range[0], x_range[1], padding=0,
                    )
        finally:
            self._syncing_x_range = False

    def apply_theme(self, theme: ThemeBase) -> None:
        """Re-apply theme colors to plots."""
        self._theme = theme
        pv_color = theme.chart_pv
        sp_color = theme.chart_sp
        co_color = theme.chart_co
        grid_bg = theme.chart_bg
        grid_color = theme.chart_grid

        for i in range(4):
            pw = self._plots[i]
            pw.setBackground(grid_bg)
            pw.getAxis("bottom").setPen(pg.mkPen(grid_color))
            pw.getAxis("left").setPen(pg.mkPen(grid_color))

            self._pv_curves[i].setPen(pg.mkPen(pv_color, width=2))
            self._sp_curves[i].setPen(pg.mkPen(sp_color, width=2))

            co_pen = QPen(
                pg.mkColor(co_color), 2, Qt.PenStyle.DashLine,
            )
            self._co_curves[i].setPen(pg.mkPen(co_pen))
