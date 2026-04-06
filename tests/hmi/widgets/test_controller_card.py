"""Tests for ControllerCardWidget."""
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton

from smart_pid_hmi.themes.isa101 import ISA101Theme
from smart_pid_hmi.widgets.controller_card import ControllerCardWidget


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


def test_tag_label_shows_name(qtbot, theme):
    card = ControllerCardWidget(
        controller_id=1, tag_name="FIC-101",
        min_val=0.0, max_val=100.0, theme=theme,
    )
    qtbot.addWidget(card)
    assert "FIC-101" in card._tag_label.text()


def test_tag_label_with_description(qtbot, theme):
    card = ControllerCardWidget(
        controller_id=1, tag_name="FIC-101",
        min_val=0.0, max_val=100.0, theme=theme,
        description="Flow control",
    )
    qtbot.addWidget(card)
    assert "FIC-101" in card._tag_label.text()
    assert "Flow control" in card._tag_label.text()


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
