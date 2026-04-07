"""Tests for MultiTrendPage."""
import pyqtgraph as pg
from PySide6.QtWidgets import QCheckBox, QComboBox, QLabel, QLineEdit

from smart_pid_hmi.pages.multi_trend_page import _NONE_LABEL, MultiTrendPage


def test_creation(qtbot):
    page = MultiTrendPage()
    qtbot.addWidget(page)
    assert page is not None


def test_has_four_plots(qtbot):
    page = MultiTrendPage()
    qtbot.addWidget(page)
    assert len(page._plots) == 4
    for pw in page._plots:
        assert isinstance(pw, pg.PlotWidget)


# --- Loop combos with None option ---


def test_loop_combos_have_none_option(qtbot):
    page = MultiTrendPage()
    qtbot.addWidget(page)
    for combo in page._loop_combos:
        assert combo.itemText(0) == _NONE_LABEL


def test_set_available_loops(qtbot):
    page = MultiTrendPage()
    qtbot.addWidget(page)
    loops = ["FIC-101", "TIC-201", "LIC-301"]
    page.set_available_loops(loops)
    for combo in page._loop_combos:
        assert combo.count() == 4  # None + 3 loops
        assert combo.itemText(0) == _NONE_LABEL
        items = [combo.itemText(i) for i in range(1, combo.count())]
        assert "FIC-101" in items


def test_set_available_loops_preserves_selection(qtbot):
    page = MultiTrendPage()
    qtbot.addWidget(page)
    page.set_available_loops(["FIC-101", "TIC-201"])
    page._loop_combos[0].setCurrentText("TIC-201")
    page.set_available_loops(["FIC-101", "TIC-201", "LIC-301"])
    assert page._loop_combos[0].currentText() == "TIC-201"


def test_selecting_none_clears_data(qtbot):
    page = MultiTrendPage()
    qtbot.addWidget(page)
    page.set_available_loops(["FIC-101"])
    page._loop_combos[0].setCurrentText("FIC-101")
    page.update_plot(0, [0.0, 1.0], [10.0, 11.0], [10.0, 10.0], [50.0, 55.0])
    page._loop_combos[0].setCurrentText(_NONE_LABEL)
    # Mode badge should reset
    assert page._mode_labels[0].text() == _NONE_LABEL


# --- No LIVE button ---


def test_no_live_button(qtbot):
    """LIVE button was removed — charts are always active."""
    page = MultiTrendPage()
    qtbot.addWidget(page)
    from PySide6.QtWidgets import QPushButton
    btn = page.findChild(QPushButton, "live_mode_btn")
    assert btn is None


# --- Per-chart time window ---


def test_per_chart_time_window_widgets(qtbot):
    page = MultiTrendPage()
    qtbot.addWidget(page)
    for i in range(4):
        edit = page.findChild(QLineEdit, f"tw_edit_{i}")
        unit = page.findChild(QComboBox, f"tw_unit_{i}")
        assert edit is not None
        assert unit is not None
        assert edit.text() == "1"
        assert unit.currentText() == "min"


def test_time_window_default_60s(qtbot):
    page = MultiTrendPage()
    qtbot.addWidget(page)
    for i in range(4):
        assert page.get_time_window_s(i) == 60


def test_time_window_change_seconds(qtbot):
    page = MultiTrendPage()
    qtbot.addWidget(page)
    page._tw_edits[0].setText("30")
    page._tw_units[0].setCurrentText("s")
    page._on_tw_changed(0)
    assert page.get_time_window_s(0) == 30


def test_time_window_change_minutes(qtbot):
    page = MultiTrendPage()
    qtbot.addWidget(page)
    page._tw_edits[1].setText("5")
    page._tw_units[1].setCurrentText("min")
    page._on_tw_changed(1)
    assert page.get_time_window_s(1) == 300


def test_time_window_invalid_input_defaults_to_1(qtbot):
    page = MultiTrendPage()
    qtbot.addWidget(page)
    page._tw_edits[0].setText("abc")
    page._tw_units[0].setCurrentText("s")
    page._on_tw_changed(0)
    assert page.get_time_window_s(0) == 1


# --- Per-chart auto-scale and manual scale ---


def test_auto_scale_default_on(qtbot):
    page = MultiTrendPage()
    qtbot.addWidget(page)
    for i in range(4):
        cb = page.findChild(QCheckBox, f"auto_scale_{i}")
        assert cb is not None
        assert cb.isChecked()


def test_auto_scale_off_enables_spins(qtbot):
    page = MultiTrendPage()
    qtbot.addWidget(page)
    # Spinboxes start disabled
    assert not page._pv_min_spins[0].isEnabled()
    # Uncheck auto-scale for chart 0
    page._auto_scale_cbs[0].setChecked(False)
    assert page._pv_min_spins[0].isEnabled()
    assert page._pv_max_spins[0].isEnabled()
    assert page._co_min_spins[0].isEnabled()
    assert page._co_max_spins[0].isEnabled()
    # Other charts unaffected
    assert not page._pv_min_spins[1].isEnabled()


def test_auto_scale_rechecked_disables_spins(qtbot):
    page = MultiTrendPage()
    qtbot.addWidget(page)
    page._auto_scale_cbs[2].setChecked(False)
    page._auto_scale_cbs[2].setChecked(True)
    assert not page._pv_min_spins[2].isEnabled()


def test_scale_spin_defaults(qtbot):
    page = MultiTrendPage()
    qtbot.addWidget(page)
    for i in range(4):
        assert page._pv_min_spins[i].value() == 0.0
        assert page._pv_max_spins[i].value() == 100.0
        assert page._co_min_spins[i].value() == 0.0
        assert page._co_max_spins[i].value() == 100.0


# --- Data update ---


def test_update_plot_no_crash(qtbot):
    page = MultiTrendPage()
    qtbot.addWidget(page)
    ts = [0.0, 1.0, 2.0]
    pvs = [10.0, 11.0, 12.0]
    sps = [10.0, 10.0, 10.0]
    cos = [50.0, 55.0, 60.0]
    page.update_plot(0, ts, pvs, sps, cos)


def test_update_plot_applies_time_window(qtbot):
    page = MultiTrendPage()
    qtbot.addWidget(page)
    page._time_windows_s[0] = 10
    ts = list(range(20))
    vals = [float(x) for x in ts]
    page.update_plot(0, ts, vals, vals, vals)
    # x-range should be clipped to [10, 19] roughly
    vb = page._plots[0].plotItem.vb
    x_range = vb.viewRange()[0]
    assert x_range[0] >= 8  # ~latest - window


def test_clear_data(qtbot):
    page = MultiTrendPage()
    qtbot.addWidget(page)
    page.update_plot(0, [0.0, 1.0], [10.0, 11.0], [10.0, 10.0], [50.0, 55.0])
    page.clear_data(0)


# --- Mode labels ---


def test_mode_labels_exist(qtbot):
    page = MultiTrendPage()
    qtbot.addWidget(page)
    assert len(page._mode_labels) == 4
    for i in range(4):
        label = page.findChild(QLabel, f"mode_label_{i}")
        assert label is not None
        assert label.text() == _NONE_LABEL


def test_set_mode(qtbot):
    page = MultiTrendPage()
    qtbot.addWidget(page)
    page.set_mode(0, "AUTO")
    assert page._mode_labels[0].text() == "AUTO"
    page.set_mode(2, "MAN")
    assert page._mode_labels[2].text() == "MAN"


def test_set_mode_out_of_range(qtbot):
    page = MultiTrendPage()
    qtbot.addWidget(page)
    page.set_mode(5, "AUTO")
    page.set_mode(-1, "MAN")


# --- SP curve exists in each plot ---


def test_sp_curves_exist(qtbot):
    page = MultiTrendPage()
    qtbot.addWidget(page)
    assert len(page._sp_curves) == 4
    for curve in page._sp_curves:
        assert isinstance(curve, pg.PlotDataItem)
