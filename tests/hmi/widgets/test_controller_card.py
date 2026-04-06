"""Tests for ControllerCardWidget."""
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton

from smart_pid_hmi.themes.isa101 import ISA101Theme
from smart_pid_hmi.widgets.controller_card import ControllerCardWidget, SparklineWidget


@pytest.fixture
def theme():
    return ISA101Theme()


def test_creation(qtbot, theme):
    card = ControllerCardWidget(
        controller_id=1, tag_name="FIC-101",
        min_val=0.0, max_val=100.0, theme=theme,
    )
    qtbot.addWidget(card)
    assert card.controller_id == 1
    assert card.tag_name == "FIC-101"


def test_on_telemetry_updates_bars(qtbot, theme):
    card = ControllerCardWidget(
        controller_id=1, tag_name="FIC-101",
        min_val=0.0, max_val=100.0, theme=theme,
    )
    qtbot.addWidget(card)
    frame = {
        "controller_id": 1, "pv": 45.0, "sp": 50.0,
        "co": 62.0, "integral_val": 0.0,
        "timestamp": "2026-04-03T10:00:00", "status": "GOOD",
    }
    card.on_telemetry(1, frame)
    assert card._bar_pv.value == 45.0
    assert card._bar_sp.value == 50.0
    assert card._bar_co.value == 62.0


def test_ignores_other_controller(qtbot, theme):
    card = ControllerCardWidget(
        controller_id=1, tag_name="FIC-101",
        min_val=0.0, max_val=100.0, theme=theme,
    )
    qtbot.addWidget(card)
    frame = {
        "controller_id": 2, "pv": 99.0, "sp": 50.0,
        "co": 62.0, "integral_val": 0.0,
        "timestamp": "2026-04-03T10:00:00", "status": "GOOD",
    }
    card.on_telemetry(2, frame)
    assert card._bar_pv.value == 0.0  # unchanged


def test_emits_controller_selected_on_click(qtbot, theme):
    card = ControllerCardWidget(
        controller_id=1, tag_name="FIC-101",
        min_val=0.0, max_val=100.0, theme=theme,
    )
    qtbot.addWidget(card)
    with qtbot.waitSignal(card.controller_selected, timeout=500):
        qtbot.mouseClick(card, Qt.MouseButton.LeftButton)


def test_mode_badge_update(qtbot, theme):
    card = ControllerCardWidget(
        controller_id=1, tag_name="FIC-101",
        min_val=0.0, max_val=100.0, theme=theme,
    )
    qtbot.addWidget(card)
    assert card._mode_label.text() == "\u2014"
    frame = {
        "controller_id": 1, "pv": 45.0, "sp": 50.0,
        "co": 62.0, "integral_val": 0.0,
        "timestamp": "2026-04-03T10:00:00", "status": "GOOD",
        "mode": "AUTO",
    }
    card.on_telemetry(1, frame)
    assert card._mode_label.text() == "AUTO"


# --- Gap #30: sparkline ---

def test_sparkline_creation(qtbot, theme):
    """SparklineWidget can be created and sized."""
    spark = SparklineWidget(theme=theme)
    qtbot.addWidget(spark)
    assert spark.maximumHeight() == 32
    assert len(spark.data) == 0


def test_sparkline_add_value(qtbot, theme):
    """add_value() appends to buffer."""
    spark = SparklineWidget(theme=theme, buffer_size=5)
    qtbot.addWidget(spark)
    for v in [1.0, 2.0, 3.0]:
        spark.add_value(v)
    assert list(spark.data) == [1.0, 2.0, 3.0]


def test_sparkline_buffer_overflow(qtbot, theme):
    """Buffer is capped at buffer_size."""
    spark = SparklineWidget(theme=theme, buffer_size=3)
    qtbot.addWidget(spark)
    for v in [1.0, 2.0, 3.0, 4.0, 5.0]:
        spark.add_value(v)
    assert list(spark.data) == [3.0, 4.0, 5.0]


def test_card_sparkline_fed_on_telemetry(qtbot, theme):
    """on_telemetry feeds the sparkline with PV values."""
    card = ControllerCardWidget(
        controller_id=1, tag_name="FIC-101",
        min_val=0.0, max_val=100.0, theme=theme,
    )
    qtbot.addWidget(card)
    for pv in [10.0, 20.0, 30.0]:
        frame = {"pv": pv, "sp": 50.0, "co": 50.0}
        card.on_telemetry(1, frame)
    assert list(card._sparkline.data) == [10.0, 20.0, 30.0]


# --- Gear button ---

def test_gear_button_exists(qtbot, theme):
    card = ControllerCardWidget(
        controller_id=1, tag_name="FIC-101",
        min_val=0.0, max_val=100.0, theme=theme,
    )
    qtbot.addWidget(card)
    gear = card.findChild(QPushButton, "settings_btn")
    assert gear is not None


def test_gear_emits_settings_requested(qtbot, theme):
    card = ControllerCardWidget(
        controller_id=7, tag_name="FIC-101",
        min_val=0.0, max_val=100.0, theme=theme,
    )
    qtbot.addWidget(card)
    gear = card.findChild(QPushButton, "settings_btn")
    with qtbot.waitSignal(card.settings_requested, timeout=500) as blocker:
        qtbot.mouseClick(gear, Qt.MouseButton.LeftButton)
    assert blocker.args == [7]


def test_gear_click_does_not_emit_controller_selected(qtbot, theme):
    card = ControllerCardWidget(
        controller_id=1, tag_name="FIC-101",
        min_val=0.0, max_val=100.0, theme=theme,
    )
    qtbot.addWidget(card)
    gear = card.findChild(QPushButton, "settings_btn")
    selected_emitted = []
    card.controller_selected.connect(lambda cid: selected_emitted.append(cid))
    qtbot.mouseClick(gear, Qt.MouseButton.LeftButton)
    assert selected_emitted == []
