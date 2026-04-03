"""Tests for SimulatorPage — preset selector, parameter sliders, disturbance controls."""
from __future__ import annotations

import pytest

from smart_pid_hmi.pages.simulator_page import SimulatorPage
from smart_pid_hmi.themes.isa101 import ISA101Theme


@pytest.fixture
def theme():
    return ISA101Theme()


def test_creation(qtbot, theme):
    page = SimulatorPage(theme=theme)
    qtbot.addWidget(page)
    assert page._preset_combo is not None
    assert page._gain_slider is not None
    assert page._tau1_slider is not None
    assert page._tau2_slider is not None
    assert page._dead_time_slider is not None


def test_preset_combo_has_all_options(qtbot, theme):
    page = SimulatorPage(theme=theme)
    qtbot.addWidget(page)
    items = [page._preset_combo.itemText(i) for i in range(page._preset_combo.count())]
    assert "FLOW" in items
    assert "PRESSURE" in items
    assert "LEVEL" in items
    assert "TEMPERATURE" in items
    assert "CUSTOM" in items


def test_tau2_disabled_for_foptd(qtbot, theme):
    page = SimulatorPage(theme=theme)
    qtbot.addWidget(page)
    page._preset_combo.setCurrentText("FLOW")
    page._on_preset_changed("FLOW")
    assert not page._tau2_slider.isEnabled()


def test_tau2_enabled_for_soptd(qtbot, theme):
    page = SimulatorPage(theme=theme)
    qtbot.addWidget(page)
    page._preset_combo.setCurrentText("LEVEL")
    page._on_preset_changed("LEVEL")
    assert page._tau2_slider.isEnabled()


def test_step_disturbance_signal(qtbot, theme):
    page = SimulatorPage(theme=theme)
    qtbot.addWidget(page)
    with qtbot.waitSignal(page.step_requested, timeout=1000) as blocker:
        page._step_amplitude.setValue(5.0)
        page._on_step_inject()
    assert blocker.args == [5.0]


def test_noise_disturbance_signal(qtbot, theme):
    page = SimulatorPage(theme=theme)
    qtbot.addWidget(page)
    with qtbot.waitSignal(page.noise_requested, timeout=1000) as blocker:
        page._noise_amplitude.setValue(0.5)
        page._on_noise_inject()
    assert blocker.args == [0.5]


def test_clear_disturbance_signal(qtbot, theme):
    page = SimulatorPage(theme=theme)
    qtbot.addWidget(page)
    with qtbot.waitSignal(page.clear_disturbance_requested, timeout=1000):
        page._on_clear_disturbance()


def test_preset_changed_signal(qtbot, theme):
    page = SimulatorPage(theme=theme)
    qtbot.addWidget(page)
    with qtbot.waitSignal(page.preset_changed, timeout=1000) as blocker:
        page._preset_combo.setCurrentText("TEMPERATURE")
        page._on_preset_selected(page._preset_combo.currentIndex())
    assert blocker.args[0] == "TEMPERATURE"
