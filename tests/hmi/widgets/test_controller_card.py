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


def test_mode_badge_update(qtbot, theme):
    card = ControllerCardWidget(
        controller_id=1, tag_name="FIC-101",
        min_val=0.0, max_val=100.0, theme=theme,
    )
    qtbot.addWidget(card)
    frame = {"pv": 50.0, "sp": 50.0, "co": 50.0, "mode": "AUTO"}
    card.on_telemetry(1, frame)
    assert card._badge_mode.text() == "AUTO"


def test_ai_engine_badge(qtbot, theme):
    card = ControllerCardWidget(
        controller_id=1, tag_name="FIC-101",
        min_val=0.0, max_val=100.0, theme=theme,
        ai_engine="FUZZY",
    )
    qtbot.addWidget(card)
    assert card._badge_ai_engine.text() == "FUZZY"


def test_ai_engine_badge_rl_label(qtbot, theme):
    card = ControllerCardWidget(
        controller_id=1, tag_name="FIC-101",
        min_val=0.0, max_val=100.0, theme=theme,
        ai_engine="RL",
    )
    qtbot.addWidget(card)
    assert card._badge_ai_engine.text() == "AI RL"


def test_optimizer_state_badge(qtbot, theme):
    card = ControllerCardWidget(
        controller_id=1, tag_name="FIC-101",
        min_val=0.0, max_val=100.0, theme=theme,
    )
    qtbot.addWidget(card)
    assert card._badge_opt_state.text() == "STOP"
    card.on_ai_status(1, "FUZZY", "RUN")
    assert card._badge_opt_state.text() == "RUN"
    assert card._badge_ai_engine.text() == "FUZZY"


def test_on_ai_status_ignores_other_controller(qtbot, theme):
    card = ControllerCardWidget(
        controller_id=1, tag_name="FIC-101",
        min_val=0.0, max_val=100.0, theme=theme,
    )
    qtbot.addWidget(card)
    card.on_ai_status(2, "RL", "RUN")
    assert card._badge_opt_state.text() == "STOP"
    assert card._badge_ai_engine.text() == "NONE"


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


# --- Alarm visual behaviour ---

def test_alarm_triggered_shows_strip_and_icon(qtbot, theme):
    """TRIGGERED alarm should show colored strip and icon."""
    card = ControllerCardWidget(
        controller_id=1, tag_name="FIC-101",
        min_val=0.0, max_val=100.0, theme=theme,
    )
    qtbot.addWidget(card)
    card.on_alarm(1, {
        "alarm_type": "HI", "priority": "WARNING",
        "transition": "TRIGGERED", "value": 75.0, "limit": 70.0,
    })
    assert card._alarm_priority == "WARNING"
    assert not card._alarm_icon.isHidden()
    assert card._alarm_icon.text() == "\u26a0"


def test_alarm_triggered_critical_shows_octagon(qtbot, theme):
    card = ControllerCardWidget(
        controller_id=1, tag_name="FIC-101",
        min_val=0.0, max_val=100.0, theme=theme,
    )
    qtbot.addWidget(card)
    card.on_alarm(1, {
        "alarm_type": "HIHI", "priority": "CRITICAL",
        "transition": "TRIGGERED", "value": 95.0, "limit": 90.0,
    })
    assert card._alarm_priority == "CRITICAL"
    assert card._alarm_icon.text() == "\u26d4"


def test_alarm_cleared_removes_visual(qtbot, theme):
    """CLEARED transition removes strip and icon."""
    card = ControllerCardWidget(
        controller_id=1, tag_name="FIC-101",
        min_val=0.0, max_val=100.0, theme=theme,
    )
    qtbot.addWidget(card)
    card.on_alarm(1, {
        "alarm_type": "HI", "priority": "WARNING",
        "transition": "TRIGGERED", "value": 75.0, "limit": 70.0,
    })
    assert card._alarm_priority == "WARNING"
    card.on_alarm(1, {
        "alarm_type": "HI", "priority": "WARNING",
        "transition": "CLEARED", "value": 65.0, "limit": 70.0,
    })
    assert card._alarm_priority is None
    assert card._alarm_icon.isHidden()


def test_alarm_unacknowledged_blinks(qtbot, theme):
    """TRIGGERED + UNACK should start the blink timer."""
    card = ControllerCardWidget(
        controller_id=1, tag_name="FIC-101",
        min_val=0.0, max_val=100.0, theme=theme,
    )
    qtbot.addWidget(card)
    card.on_alarm(1, {
        "alarm_type": "HI", "priority": "WARNING",
        "transition": "TRIGGERED", "value": 75.0, "limit": 70.0,
    })
    assert card._blink_timer.isActive()


def test_alarm_ack_stops_blink(qtbot, theme):
    """ACK should stop the blink timer but keep the strip visible."""
    card = ControllerCardWidget(
        controller_id=1, tag_name="FIC-101",
        min_val=0.0, max_val=100.0, theme=theme,
    )
    qtbot.addWidget(card)
    card.on_alarm(1, {
        "alarm_type": "HI", "priority": "WARNING",
        "transition": "TRIGGERED", "value": 75.0, "limit": 70.0,
    })
    assert card._blink_timer.isActive()

    card.on_alarm_ack(1, "HI")
    assert not card._blink_timer.isActive()
    # Strip should still be visible (solid color)
    assert card._alarm_priority == "WARNING"
    assert not card._alarm_icon.isHidden()


def test_alarm_ack_all_stops_blink(qtbot, theme):
    """ACK all (alarm_type=None) should stop blinking for all alarms."""
    card = ControllerCardWidget(
        controller_id=1, tag_name="FIC-101",
        min_val=0.0, max_val=100.0, theme=theme,
    )
    qtbot.addWidget(card)
    card.on_alarm(1, {
        "alarm_type": "HI", "priority": "WARNING",
        "transition": "TRIGGERED", "value": 75.0, "limit": 70.0,
    })
    card.on_alarm(1, {
        "alarm_type": "HIHI", "priority": "CRITICAL",
        "transition": "TRIGGERED", "value": 95.0, "limit": 90.0,
    })
    assert card._blink_timer.isActive()

    card.on_alarm_ack(1)  # ack all
    assert not card._blink_timer.isActive()
    # Highest priority alarm visual still active
    assert card._alarm_priority == "CRITICAL"


def test_highest_priority_alarm_wins(qtbot, theme):
    """When multiple alarms active, highest priority drives the visual."""
    card = ControllerCardWidget(
        controller_id=1, tag_name="FIC-101",
        min_val=0.0, max_val=100.0, theme=theme,
    )
    qtbot.addWidget(card)
    # Trigger WARNING first
    card.on_alarm(1, {
        "alarm_type": "HI", "priority": "WARNING",
        "transition": "TRIGGERED", "value": 75.0, "limit": 70.0,
    })
    assert card._alarm_priority == "WARNING"

    # Trigger CRITICAL — should take over
    card.on_alarm(1, {
        "alarm_type": "HIHI", "priority": "CRITICAL",
        "transition": "TRIGGERED", "value": 95.0, "limit": 90.0,
    })
    assert card._alarm_priority == "CRITICAL"

    # Clear CRITICAL — WARNING should come back
    card.on_alarm(1, {
        "alarm_type": "HIHI", "priority": "CRITICAL",
        "transition": "CLEARED", "value": 85.0, "limit": 90.0,
    })
    assert card._alarm_priority == "WARNING"


def test_alarm_ignores_other_controller(qtbot, theme):
    card = ControllerCardWidget(
        controller_id=1, tag_name="FIC-101",
        min_val=0.0, max_val=100.0, theme=theme,
    )
    qtbot.addWidget(card)
    card.on_alarm(2, {
        "alarm_type": "HI", "priority": "CRITICAL",
        "transition": "TRIGGERED", "value": 95.0, "limit": 90.0,
    })
    assert card._alarm_priority is None
    assert not card._blink_timer.isActive()


def test_alarm_ack_ignores_other_controller(qtbot, theme):
    card = ControllerCardWidget(
        controller_id=1, tag_name="FIC-101",
        min_val=0.0, max_val=100.0, theme=theme,
    )
    qtbot.addWidget(card)
    card.on_alarm(1, {
        "alarm_type": "HI", "priority": "WARNING",
        "transition": "TRIGGERED", "value": 75.0, "limit": 70.0,
    })
    assert card._blink_timer.isActive()
    card.on_alarm_ack(2, "HI")  # different controller
    assert card._blink_timer.isActive()  # still blinking


def test_blink_tick_toggles_strip(qtbot, theme):
    """Verify the blink timer callback toggles strip visibility."""
    card = ControllerCardWidget(
        controller_id=1, tag_name="FIC-101",
        min_val=0.0, max_val=100.0, theme=theme,
    )
    qtbot.addWidget(card)
    card.on_alarm(1, {
        "alarm_type": "HI", "priority": "WARNING",
        "transition": "TRIGGERED", "value": 75.0, "limit": 70.0,
    })
    # Initially visible
    assert card._blink_visible is True

    # Simulate tick
    card._on_blink_tick()
    assert card._blink_visible is False
    assert "transparent" in card._alarm_strip.styleSheet()

    # Tick again — visible
    card._on_blink_tick()
    assert card._blink_visible is True
    assert "transparent" not in card._alarm_strip.styleSheet()


def test_alarm_icon_on_right_side(qtbot, theme):
    """Alarm icon should be positioned after the tag label (right side)."""
    card = ControllerCardWidget(
        controller_id=1, tag_name="FIC-101",
        min_val=0.0, max_val=100.0, theme=theme,
    )
    qtbot.addWidget(card)
    # The icon should be in the header layout after the tag label
    # Find the header layout — it's the first layout in the content area
    header = card.layout().itemAt(1).layout().itemAt(0).layout()
    # header items: tag_label(0), alarm_icon(1), settings_btn(2)
    assert header.itemAt(0).widget() is card._tag_label
    assert header.itemAt(1).widget() is card._alarm_icon
    assert header.itemAt(2).widget() is card._settings_btn
