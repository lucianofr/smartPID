"""Tests for SimulatorPage — preset selector, parameter sliders, disturbance controls."""
from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QComboBox, QDoubleSpinBox, QGroupBox, QPushButton

from smart_pid_hmi.pages.simulator_page import SimulatorPage
from smart_pid_hmi.themes.dark_room import DarkRoomTheme
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


# ---------------------------------------------------------------------------
# Internal PID group tests
# ---------------------------------------------------------------------------


@pytest.fixture
def pid_page(qtbot):
    t = DarkRoomTheme()
    p = SimulatorPage(theme=t)
    qtbot.addWidget(p)
    return p


class TestSimulatorPagePIDGroup:
    def test_pid_group_exists(self, pid_page: SimulatorPage) -> None:
        groups = pid_page.findChildren(QGroupBox)
        names = [g.title() for g in groups]
        assert "Internal PID" in names

    def test_pid_enable_checkbox(self, pid_page: SimulatorPage) -> None:
        cb = pid_page.findChild(QCheckBox, "pid_enable_cb")
        assert cb is not None
        assert cb.isChecked() is False

    def test_pid_mode_combo(self, pid_page: SimulatorPage) -> None:
        combo = pid_page.findChild(QComboBox, "pid_mode_combo")
        assert combo is not None
        assert combo.currentText() == "MAN"
        assert combo.count() == 2

    def test_pid_kp_spinbox(self, pid_page: SimulatorPage) -> None:
        spin = pid_page.findChild(QDoubleSpinBox, "pid_kp_spin")
        assert spin is not None
        assert spin.value() == 1.0

    def test_pid_ti_spinbox(self, pid_page: SimulatorPage) -> None:
        spin = pid_page.findChild(QDoubleSpinBox, "pid_ti_spin")
        assert spin is not None
        assert spin.value() == 10.0
        assert spin.suffix() == " s"

    def test_pid_td_spinbox(self, pid_page: SimulatorPage) -> None:
        spin = pid_page.findChild(QDoubleSpinBox, "pid_td_spin")
        assert spin is not None
        assert spin.value() == 0.0
        assert spin.suffix() == " s"

    def test_pid_apply_button(self, pid_page: SimulatorPage) -> None:
        btn = pid_page.findChild(QPushButton, "pid_apply_btn")
        assert btn is not None

    def test_controls_disabled_when_unchecked(self, pid_page: SimulatorPage) -> None:
        combo = pid_page.findChild(QComboBox, "pid_mode_combo")
        spin_kp = pid_page.findChild(QDoubleSpinBox, "pid_kp_spin")
        btn = pid_page.findChild(QPushButton, "pid_apply_btn")
        assert not combo.isEnabled()
        assert not spin_kp.isEnabled()
        assert not btn.isEnabled()

    def test_controls_enabled_when_checked(self, pid_page: SimulatorPage, qtbot) -> None:
        cb = pid_page.findChild(QCheckBox, "pid_enable_cb")
        cb.setChecked(True)
        combo = pid_page.findChild(QComboBox, "pid_mode_combo")
        spin_kp = pid_page.findChild(QDoubleSpinBox, "pid_kp_spin")
        btn = pid_page.findChild(QPushButton, "pid_apply_btn")
        assert combo.isEnabled()
        assert spin_kp.isEnabled()
        assert btn.isEnabled()


class TestSimulatorPagePIDSignals:
    def test_enable_signal(self, pid_page: SimulatorPage, qtbot) -> None:
        with qtbot.waitSignal(pid_page.pid_enabled_changed, timeout=1000) as blocker:
            cb = pid_page.findChild(QCheckBox, "pid_enable_cb")
            cb.setChecked(True)
        assert blocker.args == [True]

    def test_params_signal(self, pid_page: SimulatorPage, qtbot) -> None:
        cb = pid_page.findChild(QCheckBox, "pid_enable_cb")
        cb.setChecked(True)
        with qtbot.waitSignal(pid_page.pid_params_changed, timeout=1000) as blocker:
            btn = pid_page.findChild(QPushButton, "pid_apply_btn")
            qtbot.mouseClick(btn, Qt.MouseButton.LeftButton)
        kp, ti, td = blocker.args
        assert kp == 1.0
        assert ti == 10.0
        assert td == 0.0

    def test_mode_signal(self, pid_page: SimulatorPage, qtbot) -> None:
        cb = pid_page.findChild(QCheckBox, "pid_enable_cb")
        cb.setChecked(True)
        with qtbot.waitSignal(pid_page.pid_mode_changed, timeout=1000) as blocker:
            combo = pid_page.findChild(QComboBox, "pid_mode_combo")
            combo.setCurrentText("AUTO")
        assert blocker.args == ["AUTO"]
