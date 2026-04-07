"""TrendChartWidget — pyqtgraph dual Y-axis real-time trend."""
from __future__ import annotations

import csv
from collections import deque
from typing import TYPE_CHECKING

import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtGui import QPen
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

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
        self._auto_scale = True
        self._ai_markers: list[pg.InfiniteLine] = []
        self._ai_marker_color = "#FF9800"  # orange default

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Control row: time window + auto-scale + manual fields + export
        ctrl_row = QHBoxLayout()

        # Time window: numeric input + unit selector
        tw_label = QLabel("Window:")
        self._tw_spin = QSpinBox()
        self._tw_spin.setRange(1, 9999)
        self._tw_spin.setValue(10)
        self._tw_spin.setFixedWidth(70)

        self._tw_unit = QComboBox()
        self._tw_unit.addItems(["s", "min"])
        self._tw_unit.setCurrentText("min")
        self._tw_unit.setFixedWidth(55)

        self._time_window_s = 600  # 10 min default
        self._tw_spin.valueChanged.connect(self._on_time_window_changed)
        self._tw_unit.currentTextChanged.connect(self._on_time_window_changed)

        # Gap #33: auto-scale checkbox
        self._auto_scale_cb = QCheckBox("Auto-scale")
        self._auto_scale_cb.setChecked(True)
        self._auto_scale_cb.toggled.connect(self._on_auto_scale_toggled)

        # Gap #34: manual scale spinboxes
        self._pv_min_spin = QDoubleSpinBox()
        self._pv_min_spin.setPrefix("PV min: ")
        self._pv_min_spin.setRange(-1e6, 1e6)
        self._pv_min_spin.setValue(0.0)
        self._pv_min_spin.setDecimals(1)

        self._pv_max_spin = QDoubleSpinBox()
        self._pv_max_spin.setPrefix("PV max: ")
        self._pv_max_spin.setRange(-1e6, 1e6)
        self._pv_max_spin.setValue(100.0)
        self._pv_max_spin.setDecimals(1)

        self._co_min_spin = QDoubleSpinBox()
        self._co_min_spin.setPrefix("CO min: ")
        self._co_min_spin.setRange(-1e6, 1e6)
        self._co_min_spin.setValue(0.0)
        self._co_min_spin.setDecimals(1)

        self._co_max_spin = QDoubleSpinBox()
        self._co_max_spin.setPrefix("CO max: ")
        self._co_max_spin.setRange(-1e6, 1e6)
        self._co_max_spin.setValue(100.0)
        self._co_max_spin.setDecimals(1)

        # Connect manual scale changes
        self._pv_min_spin.valueChanged.connect(self._apply_manual_scale)
        self._pv_max_spin.valueChanged.connect(self._apply_manual_scale)
        self._co_min_spin.valueChanged.connect(self._apply_manual_scale)
        self._co_max_spin.valueChanged.connect(self._apply_manual_scale)

        # Initially disabled (auto-scale is on)
        for spin in (
            self._pv_min_spin, self._pv_max_spin,
            self._co_min_spin, self._co_max_spin,
        ):
            spin.setEnabled(False)

        # Gap #35: CSV export button
        self._export_btn = QPushButton("Export CSV")
        self._export_btn.clicked.connect(self._export_csv)

        ctrl_row.addStretch()
        ctrl_row.addWidget(tw_label)
        ctrl_row.addWidget(self._tw_spin)
        ctrl_row.addWidget(self._tw_unit)
        ctrl_row.addWidget(self._auto_scale_cb)
        ctrl_row.addWidget(self._pv_min_spin)
        ctrl_row.addWidget(self._pv_max_spin)
        ctrl_row.addWidget(self._co_min_spin)
        ctrl_row.addWidget(self._co_max_spin)
        ctrl_row.addWidget(self._export_btn)
        layout.addLayout(ctrl_row)

        # Plot
        self._plot_widget = pg.PlotWidget()
        layout.addWidget(self._plot_widget)

        self._theme = theme
        if theme:
            accent = getattr(theme, "accent", "")
            if accent:
                self._ai_marker_color = accent
            self._plot_widget.setBackground(theme.chart_bg)
            self._plot_widget.getAxis("bottom").setPen(theme.fg_primary)
            self._plot_widget.getAxis("left").setPen(theme.fg_primary)
            self._plot_widget.showGrid(x=True, y=True, alpha=0.3)

            self._pv_curve = self._plot_widget.plot(
                pen=pg.mkPen(
                    color=theme.chart_pv, width=2,
                    style=Qt.PenStyle.SolidLine,
                ),
                name="PV",
            )
            self._sp_curve = self._plot_widget.plot(
                pen=pg.mkPen(
                    color=theme.chart_sp, width=1,
                    style=Qt.PenStyle.DashLine,
                ),
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
            self._plot_widget.plotItem.vb.sigResized.connect(
                self._sync_y2_geometry
            )
        else:
            self._pv_curve = self._plot_widget.plot(pen="w", name="PV")
            self._sp_curve = self._plot_widget.plot(pen="y", name="SP")
            self._y2 = None
            self._co_curve = None

    def _sync_y2_geometry(self) -> None:
        """Sync Y2 ViewBox geometry with the main plot area."""
        if self._y2 is not None:
            self._y2.setGeometry(
                self._plot_widget.plotItem.vb.sceneBoundingRect()
            )

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
        # Remove AI markers
        for line in self._ai_markers:
            self._plot_widget.removeItem(line)
        self._ai_markers.clear()

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

        # Apply time window: estimate samples/sec from recent data
        if len(x) > 1:
            samples_per_window = max(
                int(self._time_window_s * 30), 60,
            )  # ~30 samples/s at 33ms refresh
            x_min = max(0, self._tick - samples_per_window)
            self._plot_widget.plotItem.setXRange(x_min, self._tick, padding=0.02)

    def _on_time_window_changed(self, _value: object = None) -> None:
        """Recalculate time window from numeric spin + unit combo."""
        val = self._tw_spin.value()
        unit = self._tw_unit.currentText()
        self._time_window_s = val * 60 if unit == "min" else val

    def set_time_window(self, window: str) -> None:
        """Legacy API — parse string like '10min' or '30s'."""
        pass

    # -- Gap #33/#34 helpers -------------------------------------------------

    def _on_auto_scale_toggled(self, checked: bool) -> None:
        """Toggle between auto-scale and manual scale mode."""
        self._auto_scale = checked
        for spin in (
            self._pv_min_spin, self._pv_max_spin,
            self._co_min_spin, self._co_max_spin,
        ):
            spin.setEnabled(not checked)

        if checked:
            self._plot_widget.plotItem.vb.enableAutoRange()
            if self._y2 is not None:
                self._y2.enableAutoRange()
        else:
            self._apply_manual_scale()

    def _apply_manual_scale(self, _value: float = 0.0) -> None:
        """Apply manual Y-axis ranges from spinboxes."""
        if self._auto_scale:
            return
        pv_min = self._pv_min_spin.value()
        pv_max = self._pv_max_spin.value()
        co_min = self._co_min_spin.value()
        co_max = self._co_max_spin.value()

        self._plot_widget.plotItem.vb.setRange(
            yRange=(pv_min, pv_max), padding=0,
        )
        if self._y2 is not None:
            self._y2.setRange(yRange=(co_min, co_max), padding=0)

    # -- Gap #35: CSV export ------------------------------------------------

    def _export_csv(self) -> None:
        """Export current trend data to CSV file."""
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Trend Data",
            "",
            "CSV Files (*.csv);;All Files (*)",
        )
        if not path:
            return
        self._write_csv(path)

    def _write_csv(self, path: str) -> None:
        """Write trend data to *path*. Separated for testability."""
        with open(path, "w", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(["time", "PV", "SP", "CO"])
            for t, pv, sp, co in zip(
                self._time_data,
                self._pv_data,
                self._sp_data,
                self._co_data,
                strict=True,
            ):
                writer.writerow([t, pv, sp, co])

    # -- Gap #31: AI action markers ----------------------------------------

    def add_ai_marker(self, timestamp: float) -> None:
        """Draw a vertical marker on the trend at *timestamp* (tick-based)."""
        pen = QPen(pg.mkColor(self._ai_marker_color), 1.5, Qt.PenStyle.DashLine)
        line = pg.InfiniteLine(
            pos=timestamp, angle=90, pen=pen, movable=False,
        )
        self._plot_widget.addItem(line)
        self._ai_markers.append(line)

    # -- Gap #48: apply_theme ----------------------------------------------

    def apply_theme(self, theme: ThemeBase) -> None:
        """Update cached theme and re-apply colors."""
        self._theme = theme
        accent = getattr(theme, "accent", "")
        if accent:
            self._ai_marker_color = accent
        self._plot_widget.setBackground(theme.chart_bg)
        self._plot_widget.getAxis("bottom").setPen(theme.fg_primary)
        self._plot_widget.getAxis("left").setPen(theme.fg_primary)
        self._pv_curve.setPen(pg.mkPen(
            color=theme.chart_pv, width=2,
            style=Qt.PenStyle.SolidLine,
        ))
        self._sp_curve.setPen(pg.mkPen(
            color=theme.chart_sp, width=1,
            style=Qt.PenStyle.DashLine,
        ))
        if self._co_curve:
            self._co_curve.setPen(pg.mkPen(
                color=theme.chart_co, width=1,
            ))
