"""Tests for Simulator page Apply/Cancel pattern."""
from __future__ import annotations

import pytest
from PySide6.QtWidgets import QPushButton

from smart_pid_hmi.pages.simulator_page import SimulatorPage
from smart_pid_hmi.themes import ISA101Theme


@pytest.fixture
def page():
    return SimulatorPage(theme=ISA101Theme())


class TestSimulatorApplyCancel:
    def test_apply_button_exists(self, page) -> None:
        btn = page.findChild(QPushButton, "sim_apply_btn")
        assert btn is not None

    def test_cancel_button_exists(self, page) -> None:
        btn = page.findChild(QPushButton, "sim_cancel_btn")
        assert btn is not None

    def test_buttons_disabled_initially(self, page) -> None:
        assert not page._sim_apply_btn.isEnabled()
        assert not page._sim_cancel_btn.isEnabled()

    def test_changing_gain_enables_buttons(self, page) -> None:
        page._gain_slider.setValue(5.0)
        assert page._sim_apply_btn.isEnabled()
        assert page._sim_cancel_btn.isEnabled()

    def test_cancel_reverts_gain(self, page) -> None:
        original = page._gain_slider.value()
        page._gain_slider.setValue(5.0)
        page._sim_cancel_btn.click()
        assert page._gain_slider.value() == original
        assert not page._sim_apply_btn.isEnabled()

    def test_old_apply_buttons_removed(self, page) -> None:
        assert page.findChild(QPushButton, "pid_apply_btn") is None

    def test_has_unsaved_changes(self, page) -> None:
        assert not page.has_unsaved_changes()
        page._gain_slider.setValue(5.0)
        assert page.has_unsaved_changes()

    def test_apply_disables_buttons(self, page) -> None:
        page._gain_slider.setValue(5.0)
        page._sim_apply_btn.click()
        assert not page._sim_apply_btn.isEnabled()
        assert not page._sim_cancel_btn.isEnabled()

    def test_disturbance_buttons_still_immediate(self, page) -> None:
        step_btn = None
        for btn in page.findChildren(QPushButton):
            if btn.text() == "Inject Step":
                step_btn = btn
                break
        assert step_btn is not None
        assert step_btn.isEnabled()
