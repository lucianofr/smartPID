"""Tests for MultiTrendPage."""
import numpy as np
import pyqtgraph as pg
from PySide6.QtWidgets import QComboBox, QPushButton

from smart_pid_hmi.pages.multi_trend_page import MultiTrendPage


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


def test_time_range_combo(qtbot):
    page = MultiTrendPage()
    qtbot.addWidget(page)
    combo = page.findChild(QComboBox, "time_range_combo")
    assert combo is not None
    assert combo.count() == 4
    items = [combo.itemText(i) for i in range(combo.count())]
    assert "1m" in items
    assert "5m" in items
    assert "15m" in items
    assert "1h" in items


def test_live_mode_toggle(qtbot):
    page = MultiTrendPage()
    qtbot.addWidget(page)
    btn = page.findChild(QPushButton, "live_mode_btn")
    assert btn is not None
    assert btn.isCheckable()


def test_update_plot_no_crash(qtbot):
    page = MultiTrendPage()
    qtbot.addWidget(page)
    ts = [0.0, 1.0, 2.0]
    pvs = [10.0, 11.0, 12.0]
    sps = [10.0, 10.0, 10.0]
    cos = [50.0, 55.0, 60.0]
    # Should not raise
    page.update_plot(0, ts, pvs, sps, cos)


def test_set_available_loops(qtbot):
    page = MultiTrendPage()
    qtbot.addWidget(page)
    loops = ["FIC-101", "TIC-201", "LIC-301"]
    page.set_available_loops(loops)
    for combo in page._loop_combos:
        assert combo.count() == 3
        items = [combo.itemText(i) for i in range(combo.count())]
        assert "FIC-101" in items


def test_clear_data(qtbot):
    page = MultiTrendPage()
    qtbot.addWidget(page)
    page.update_plot(0, [0.0, 1.0], [10.0, 11.0], [10.0, 10.0], [50.0, 55.0])
    page.clear_data(0)
    # Should not crash; plot items should be cleared
