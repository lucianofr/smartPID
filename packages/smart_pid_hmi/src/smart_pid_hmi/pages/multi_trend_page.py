"""MultiTrendPage — 2x2 grid of pyqtgraph trend plots with per-chart controls."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtGui import QPen
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from smart_pid_hmi.themes.base import ThemeBase

_NONE_LABEL = "\u2014"  # em-dash for "no loop selected"


class MultiTrendPage(QWidget):
    """2x2 grid of trend plots with per-chart time window and scale controls."""

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

        # --- Header: legend showing PV / SP / CO colors ---
        header_row = QHBoxLayout()
        header_row.addStretch()
        for label_text, color, style in [
            ("PV", pv_color, Qt.PenStyle.SolidLine),
            ("SP", sp_color, Qt.PenStyle.DashLine),
            ("CO", co_color, Qt.PenStyle.DashDotLine),
        ]:
            swatch = QLabel()
            swatch.setFixedSize(24, 3)
            pen_style = "solid" if style == Qt.PenStyle.SolidLine else (
                "dashed" if style == Qt.PenStyle.DashLine else "dashdot"
            )
            swatch.setStyleSheet(
                f"background: {color}; border: none;"
                f" border-top: 3px {pen_style} {color};"
            )
            lbl = QLabel(label_text)
            lbl.setStyleSheet("font-weight: bold; padding-left: 2px; padding-right: 10px;")
            header_row.addWidget(swatch)
            header_row.addWidget(lbl)
        header_row.addStretch()
        root.addLayout(header_row)

        # --- 2x2 grid of plots ---
        grid = QGridLayout()
        self._plots: list[pg.PlotWidget] = []
        self._loop_combos: list[QComboBox] = []
        self._pv_curves: list[pg.PlotDataItem] = []
        self._sp_curves: list[pg.PlotDataItem] = []
        self._co_curves: list[pg.PlotDataItem] = []
        self._co_viewboxes: list[pg.ViewBox] = []
        self._mode_labels: list[QLabel] = []

        # Per-chart controls
        self._tw_edits: list[QLineEdit] = []
        self._tw_units: list[QComboBox] = []
        self._time_windows_s: list[int] = []
        self._auto_scale_cbs: list[QCheckBox] = []
        self._pv_min_spins: list[QDoubleSpinBox] = []
        self._pv_max_spins: list[QDoubleSpinBox] = []
        self._co_min_spins: list[QDoubleSpinBox] = []
        self._co_max_spins: list[QDoubleSpinBox] = []

        for i in range(4):
            container = QVBoxLayout()

            # Row 1: Loop selector + Mode badge
            header = QHBoxLayout()
            loop_combo = QComboBox()
            loop_combo.setObjectName(f"loop_combo_{i}")
            loop_combo.addItem(_NONE_LABEL)
            loop_combo.currentTextChanged.connect(
                lambda text, idx=i: self._on_loop_changed(idx, text),
            )
            header.addWidget(loop_combo, stretch=1)

            mode_label = QLabel(_NONE_LABEL)
            mode_label.setObjectName(f"mode_label_{i}")
            mode_label.setFixedHeight(22)
            mode_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            mode_label.setStyleSheet(
                "font-weight: bold; padding: 2px 8px; border-radius: 4px;"
                " background: #555; color: #fff; font-size: 11px;"
            )
            header.addWidget(mode_label)
            self._mode_labels.append(mode_label)

            container.addLayout(header)
            self._loop_combos.append(loop_combo)

            # Row 2: Per-chart controls (time window + scale)
            ctrl_row = QHBoxLayout()
            ctrl_row.setContentsMargins(0, 0, 0, 0)

            tw_edit = QLineEdit("1")
            tw_edit.setObjectName(f"tw_edit_{i}")
            tw_edit.setFixedWidth(40)
            tw_edit.setAlignment(Qt.AlignmentFlag.AlignRight)

            tw_unit = QComboBox()
            tw_unit.setObjectName(f"tw_unit_{i}")
            tw_unit.addItems(["s", "min"])
            tw_unit.setCurrentText("min")
            tw_unit.setFixedWidth(55)

            self._tw_edits.append(tw_edit)
            self._tw_units.append(tw_unit)
            self._time_windows_s.append(60)  # default 1 min

            tw_edit.editingFinished.connect(lambda idx=i: self._on_tw_changed(idx))
            tw_unit.currentTextChanged.connect(lambda _t, idx=i: self._on_tw_changed(idx))

            auto_cb = QCheckBox("Auto")
            auto_cb.setObjectName(f"auto_scale_{i}")
            auto_cb.setChecked(True)
            self._auto_scale_cbs.append(auto_cb)

            pv_min = self._make_scale_spin(f"pv_min_{i}", "PV min:", 0.0)
            pv_max = self._make_scale_spin(f"pv_max_{i}", "PV max:", 100.0)
            co_min = self._make_scale_spin(f"co_min_{i}", "CO min:", 0.0)
            co_max = self._make_scale_spin(f"co_max_{i}", "CO max:", 100.0)
            self._pv_min_spins.append(pv_min)
            self._pv_max_spins.append(pv_max)
            self._co_min_spins.append(co_min)
            self._co_max_spins.append(co_max)

            for spin in (pv_min, pv_max, co_min, co_max):
                spin.setEnabled(False)

            auto_cb.toggled.connect(lambda checked, idx=i: self._on_auto_scale(idx, checked))
            pv_min.valueChanged.connect(lambda _v, idx=i: self._apply_manual_scale(idx))
            pv_max.valueChanged.connect(lambda _v, idx=i: self._apply_manual_scale(idx))
            co_min.valueChanged.connect(lambda _v, idx=i: self._apply_manual_scale(idx))
            co_max.valueChanged.connect(lambda _v, idx=i: self._apply_manual_scale(idx))

            ctrl_row.addWidget(tw_edit)
            ctrl_row.addWidget(tw_unit)
            ctrl_row.addWidget(auto_cb)
            ctrl_row.addWidget(pv_min)
            ctrl_row.addWidget(pv_max)
            ctrl_row.addWidget(co_min)
            ctrl_row.addWidget(co_max)
            ctrl_row.addStretch()
            container.addLayout(ctrl_row)

            # Row 3: Plot widget
            pw = pg.PlotWidget()
            pw.setBackground(grid_bg)
            pw.showGrid(x=True, y=True, alpha=0.3)
            pw.getAxis("bottom").setPen(pg.mkPen(grid_color))
            pw.getAxis("left").setPen(pg.mkPen(grid_color))
            pw.setLabel("bottom", "Time", units="s")
            pw.setLabel("left", "PV / SP")

            # Primary curves: PV (solid) and SP (dashed)
            pv_curve = pw.plot(
                pen=pg.mkPen(pv_color, width=2, style=Qt.PenStyle.SolidLine),
                name="PV",
            )
            sp_curve = pw.plot(
                pen=pg.mkPen(sp_color, width=2, style=Qt.PenStyle.DashLine),
                name="SP",
            )

            # Secondary Y axis for CO
            co_viewbox = pg.ViewBox()
            pw.scene().addItem(co_viewbox)
            pw.getAxis("right").linkToView(co_viewbox)
            co_viewbox.setXLink(pw)
            pw.showAxis("right")
            pw.setLabel("right", "CO")

            co_pen = QPen(
                pg.mkColor(co_color), 2, Qt.PenStyle.DashDotLine,
            )
            co_curve = pg.PlotDataItem(pen=pg.mkPen(co_pen))
            co_viewbox.addItem(co_curve)

            container.addWidget(pw)

            self._plots.append(pw)
            self._pv_curves.append(pv_curve)
            self._sp_curves.append(sp_curve)
            self._co_curves.append(co_curve)
            self._co_viewboxes.append(co_viewbox)

            row, col = divmod(i, 2)
            grid.addLayout(container, row, col)

        root.addLayout(grid, stretch=1)

    # -- Static helpers --------------------------------------------------------

    @staticmethod
    def _make_scale_spin(name: str, prefix: str, default: float) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setObjectName(name)
        spin.setPrefix(prefix + " ")
        spin.setRange(-1e6, 1e6)
        spin.setValue(default)
        spin.setDecimals(1)
        spin.setFixedWidth(110)
        return spin

    # -- Loop selection --------------------------------------------------------

    def _on_loop_changed(self, index: int, text: str) -> None:
        """Clear plot and reset mode badge when 'None' is selected."""
        if text == _NONE_LABEL:
            self.clear_data(index)
            self._mode_labels[index].setText(_NONE_LABEL)

    # -- Per-chart time window -------------------------------------------------

    def _on_tw_changed(self, index: int) -> None:
        """Recalculate time window for chart *index*."""
        text = self._tw_edits[index].text().strip()
        try:
            val = max(1, int(text))
        except ValueError:
            val = 1
        unit = self._tw_units[index].currentText()
        self._time_windows_s[index] = val * 60 if unit == "min" else val

    def get_time_window_s(self, index: int) -> int:
        """Return the time window in seconds for chart *index*."""
        if 0 <= index < 4:
            return self._time_windows_s[index]
        return 60

    # -- Per-chart auto-scale / manual scale -----------------------------------

    def _on_auto_scale(self, index: int, checked: bool) -> None:
        for spin in (
            self._pv_min_spins[index], self._pv_max_spins[index],
            self._co_min_spins[index], self._co_max_spins[index],
        ):
            spin.setEnabled(not checked)

        if checked:
            self._plots[index].plotItem.vb.enableAutoRange()
            self._co_viewboxes[index].enableAutoRange()
        else:
            self._apply_manual_scale(index)

    def _apply_manual_scale(self, index: int) -> None:
        if self._auto_scale_cbs[index].isChecked():
            return
        pv_min = self._pv_min_spins[index].value()
        pv_max = self._pv_max_spins[index].value()
        co_min = self._co_min_spins[index].value()
        co_max = self._co_max_spins[index].value()

        self._plots[index].plotItem.vb.setRange(yRange=(pv_min, pv_max), padding=0)
        self._co_viewboxes[index].setRange(yRange=(co_min, co_max), padding=0)

    # -- Data API --------------------------------------------------------------

    def update_plot(
        self,
        index: int,
        timestamps: list[float],
        pvs: list[float],
        sps: list[float],
        cos: list[float],
    ) -> None:
        """Update data for one of the 4 plots (0-3)."""
        if not (0 <= index < 4):
            return
        self._pv_curves[index].setData(timestamps, pvs)
        self._sp_curves[index].setData(timestamps, sps)
        self._co_curves[index].setData(timestamps, cos)

        # Apply per-chart time window
        if timestamps:
            latest = timestamps[-1]
            window = self._time_windows_s[index]
            x_min = max(0.0, latest - window)
            self._plots[index].plotItem.setXRange(x_min, latest, padding=0.02)

    def set_available_loops(self, loops: list[str]) -> None:
        """Populate all loop selector combos, keeping the em-dash 'None' entry."""
        for combo in self._loop_combos:
            prev = combo.currentText()
            combo.blockSignals(True)
            combo.clear()
            combo.addItem(_NONE_LABEL)
            combo.addItems(loops)
            # Restore previous selection if still available
            idx = combo.findText(prev)
            if idx >= 0:
                combo.setCurrentIndex(idx)
            combo.blockSignals(False)

    def clear_data(self, index: int) -> None:
        """Clear plot data for the given index."""
        if 0 <= index < 4:
            self._pv_curves[index].setData([], [])
            self._sp_curves[index].setData([], [])
            self._co_curves[index].setData([], [])

    def set_mode(self, index: int, mode: str) -> None:
        """Update the displayed controller mode badge for a plot panel (0-3)."""
        if 0 <= index < 4:
            self._mode_labels[index].setText(mode)

    # -- Theming ---------------------------------------------------------------

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

            self._pv_curves[i].setPen(
                pg.mkPen(pv_color, width=2, style=Qt.PenStyle.SolidLine),
            )
            self._sp_curves[i].setPen(
                pg.mkPen(sp_color, width=2, style=Qt.PenStyle.DashLine),
            )

            co_pen = QPen(
                pg.mkColor(co_color), 2, Qt.PenStyle.DashDotLine,
            )
            self._co_curves[i].setPen(pg.mkPen(co_pen))
