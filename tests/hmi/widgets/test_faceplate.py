"""Tests for FaceplateWidget."""
import pytest
from PySide6.QtCore import Qt

from smart_pid_hmi.themes.isa101 import ISA101Theme
from smart_pid_hmi.widgets.faceplate import FaceplateWidget


@pytest.fixture
def theme():
    return ISA101Theme()


def test_creation(qtbot, theme):
    fp = FaceplateWidget(theme=theme)
    qtbot.addWidget(fp)
    assert fp._tag_label.text() == "\u2014"


def test_on_controller_selected(qtbot, theme):
    fp = FaceplateWidget(theme=theme)
    qtbot.addWidget(fp)
    fp.on_controller_selected(1, "FIC-101", 0.0, 100.0)
    assert fp._tag_label.text() == "FIC-101"
    assert fp._controller_id == 1


def test_on_telemetry_updates_bars(qtbot, theme):
    fp = FaceplateWidget(theme=theme)
    qtbot.addWidget(fp)
    fp.on_controller_selected(1, "FIC-101", 0.0, 100.0)
    frame = {
        "controller_id": 1, "pv": 45.0, "sp": 50.0,
        "co": 62.0, "integral_val": 0.0,
        "timestamp": "2026-04-03T10:00:00", "status": "GOOD",
        "mode": "AUTO",
    }
    fp.on_telemetry(1, frame)
    assert fp._bar_pv.value == 45.0
    assert fp._bar_co.value == 62.0


def test_ignores_other_controller_telemetry(qtbot, theme):
    fp = FaceplateWidget(theme=theme)
    qtbot.addWidget(fp)
    fp.on_controller_selected(1, "FIC-101", 0.0, 100.0)
    frame = {"controller_id": 2, "pv": 99.0, "sp": 50.0, "co": 62.0,
             "integral_val": 0.0, "timestamp": "T", "status": "GOOD"}
    fp.on_telemetry(2, frame)
    assert fp._bar_pv.value == 0.0


def test_sp_input_emits_command(qtbot, theme):
    fp = FaceplateWidget(theme=theme)
    qtbot.addWidget(fp)
    fp.on_controller_selected(1, "FIC-101", 0.0, 100.0)

    received = []
    fp.setpoint_requested.connect(lambda cid, val: received.append((cid, val)))

    fp._sp_input.setText("55.0")
    qtbot.keyPress(fp._sp_input, Qt.Key.Key_Return)

    assert len(received) == 1
    assert received[0] == (1, 55.0)


def test_mode_button_emits_command(qtbot, theme):
    fp = FaceplateWidget(theme=theme)
    qtbot.addWidget(fp)
    fp.on_controller_selected(1, "FIC-101", 0.0, 100.0)

    received = []
    fp.mode_requested.connect(lambda cid, mode: received.append((cid, mode)))

    qtbot.mouseClick(fp._btn_man, Qt.MouseButton.LeftButton)
    assert len(received) == 1
    assert received[0] == (1, "MAN")


def test_co_input_emits_command(qtbot, theme):
    fp = FaceplateWidget(theme=theme)
    qtbot.addWidget(fp)
    fp.on_controller_selected(1, "FIC-101", 0.0, 100.0)

    received = []
    fp.output_requested.connect(lambda cid, val: received.append((cid, val)))

    fp._co_input.setText("30.0")
    qtbot.keyPress(fp._co_input, Qt.Key.Key_Return)

    assert len(received) == 1
    assert received[0] == (1, 30.0)


# --- Gap #23: stats update ---

def test_stats_grid_initial(qtbot, theme):
    """Stats grid shows placeholder dashes on creation."""
    fp = FaceplateWidget(theme=theme)
    qtbot.addWidget(fp)
    assert "\u2014" in fp._stat_labels["IAE"].text()
    assert "\u2014" in fp._stat_labels["TV"].text()


def test_update_stats_formats_values(qtbot, theme):
    """update_stats() formats metrics correctly."""
    fp = FaceplateWidget(theme=theme)
    qtbot.addWidget(fp)
    fp.update_stats({"iae": 12.345, "variability_range": 3.78, "tv": 5.1})
    assert "12.35" in fp._stat_labels["IAE"].text()
    assert "3.8%" in fp._stat_labels["2\u03c3/Range"].text()
    assert "5.10" in fp._stat_labels["TV"].text()


def test_update_stats_zero(qtbot, theme):
    """update_stats() handles zero values."""
    fp = FaceplateWidget(theme=theme)
    qtbot.addWidget(fp)
    fp.update_stats({"iae": 0.0, "variability_range": 0.0})
    assert "0.00" in fp._stat_labels["IAE"].text()
    assert "0.0%" in fp._stat_labels["2\u03c3/Range"].text()


# --- Gap #24: optimizer buttons ---

def test_optimizer_run_signal(qtbot, theme):
    """RUN button emits optimizer_run_requested."""
    fp = FaceplateWidget(theme=theme)
    qtbot.addWidget(fp)
    fp.on_controller_selected(1, "FIC-101", 0.0, 100.0)
    received = []
    fp.optimizer_run_requested.connect(lambda cid: received.append(cid))
    qtbot.mouseClick(fp._btn_opt_run, Qt.MouseButton.LeftButton)
    assert received == [1]


def test_optimizer_pause_signal(qtbot, theme):
    """PAUSE button emits optimizer_pause_requested."""
    fp = FaceplateWidget(theme=theme)
    qtbot.addWidget(fp)
    fp.on_controller_selected(1, "FIC-101", 0.0, 100.0)
    received = []
    fp.optimizer_pause_requested.connect(lambda cid: received.append(cid))
    qtbot.mouseClick(fp._btn_opt_pause, Qt.MouseButton.LeftButton)
    assert received == [1]


def test_optimizer_stop_signal(qtbot, theme):
    """STOP button emits optimizer_stop_requested."""
    fp = FaceplateWidget(theme=theme)
    qtbot.addWidget(fp)
    fp.on_controller_selected(1, "FIC-101", 0.0, 100.0)
    received = []
    fp.optimizer_stop_requested.connect(lambda cid: received.append(cid))
    qtbot.mouseClick(fp._btn_opt_stop, Qt.MouseButton.LeftButton)
    assert received == [1]


def test_optimizer_buttons_no_emit_without_controller(qtbot, theme):
    """Optimizer buttons do nothing when no controller is selected."""
    fp = FaceplateWidget(theme=theme)
    qtbot.addWidget(fp)
    received = []
    fp.optimizer_run_requested.connect(lambda cid: received.append(cid))
    qtbot.mouseClick(fp._btn_opt_run, Qt.MouseButton.LeftButton)
    assert received == []
