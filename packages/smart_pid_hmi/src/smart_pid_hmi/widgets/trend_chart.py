"""TrendChartWidget — pyqtgraph dual Y-axis real-time trend."""
from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING

import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QVBoxLayout, QWidget

if TYPE_CHECKING:
    from smart_pid_hmi.themes.base import ThemeBase

_TIME_WINDOWS = {
    "1min": 60,
    "5min": 300,
    "10min": 600,
    "30min": 1800,
    "1h": 3600,
}

_DEFAULT_BUFFER = 600  # 10min at 1s scan


class TrendChartWidget(QWidget):
    """Real-time trend with PV/SP on Y1 and CO on Y2."""

    def __init__(
        self,
        theme: ThemeBase | None = None,
        buffer_size: int = _DEFAULT_BUFFER,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._controller_id: int | None = None
        self._buffer_size = buffer_size
        self._pv_data: deque[float] = deque(maxlen=buffer_size)
        self._sp_data: deque[float] = deque(maxlen=buffer_size)
        self._co_data: deque[float] = deque(maxlen=buffer_size)
        self._time_data: deque[float] = deque(maxlen=buffer_size)
        self._tick = 0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Time window selector
        ctrl_row = QHBoxLayout()
        self._combo = QComboBox()
        self._combo.addItems(list(_TIME_WINDOWS.keys()))
        self._combo.setCurrentText("10min")
        ctrl_row.addStretch()
        ctrl_row.addWidget(self._combo)
        layout.addLayout(ctrl_row)

        # Plot
        self._plot_widget = pg.PlotWidget()
        layout.addWidget(self._plot_widget)

        if theme:
            self._plot_widget.setBackground(theme.chart_bg)
            self._plot_widget.getAxis("bottom").setPen(theme.fg_primary)
            self._plot_widget.getAxis("left").setPen(theme.fg_primary)
            self._plot_widget.showGrid(x=True, y=True, alpha=0.3)

            self._pv_curve = self._plot_widget.plot(
                pen=pg.mkPen(color=theme.chart_pv, width=2, style=Qt.PenStyle.SolidLine),
                name="PV",
            )
            self._sp_curve = self._plot_widget.plot(
                pen=pg.mkPen(color=theme.chart_sp, width=1, style=Qt.PenStyle.DashLine),
                name="SP",
            )

            # Y2 axis for CO
            self._y2 = pg.ViewBox()
            self._plot_widget.scene().addItem(self._y2)
            self._plot_widget.getAxis("right").linkToView(self._y2)
            self._y2.setXLink(self._plot_widget)
            self._plot_widget.showAxis("right")

            self._co_curve = pg.PlotCurveItem(
                pen=pg.mkPen(color=theme.chart_co, width=1),
            )
            self._y2.addItem(self._co_curve)

            # Sync Y2 viewbox geometry on resize
            self._plot_widget.plotItem.vb.sigResized.connect(self._sync_y2_geometry)
        else:
            self._pv_curve = self._plot_widget.plot(pen="w", name="PV")
            self._sp_curve = self._plot_widget.plot(pen="y", name="SP")
            self._y2 = None
            self._co_curve = None

    def _sync_y2_geometry(self) -> None:
        """Sync Y2 ViewBox geometry with the main plot area."""
        if self._y2 is not None:
            self._y2.setGeometry(self._plot_widget.plotItem.vb.sceneBoundingRect())

    def on_controller_selected(self, controller_id: int) -> None:
        self._controller_id = controller_id
        self._pv_data.clear()
        self._sp_data.clear()
        self._co_data.clear()
        self._time_data.clear()
        self._tick = 0
        self._pv_curve.clear()
        self._sp_curve.clear()
        if self._co_curve:
            self._co_curve.clear()

    def on_telemetry(self, controller_id: int, frame: dict) -> None:
        if self._controller_id is None or controller_id != self._controller_id:
            return

        self._pv_data.append(frame.get("pv", 0.0))
        self._sp_data.append(frame.get("sp", 0.0))
        self._co_data.append(frame.get("co", 0.0))
        self._time_data.append(float(self._tick))
        self._tick += 1

        x = list(self._time_data)
        self._pv_curve.setData(x, list(self._pv_data))
        self._sp_curve.setData(x, list(self._sp_data))
        if self._co_curve:
            self._co_curve.setData(x, list(self._co_data))

    def set_time_window(self, window: str) -> None:
        self._combo.setCurrentText(window)
