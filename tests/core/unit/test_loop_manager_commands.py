"""Tests for LoopManager command methods (get/set operations)."""
from __future__ import annotations

import time

import pytest

from smart_pid_core.application.event_bus import EventBus
from smart_pid_core.application.loop_manager import LoopManager
from smart_pid_domain.enums import ControllerMode
from smart_pid_domain.exceptions import ControllerNotFoundError, DomainError
from smart_pid_domain.models.controller import Controller, PIDParams


@pytest.fixture
def bus() -> EventBus:
    b = EventBus()
    b.start()
    time.sleep(0.05)
    yield b
    b.stop()


@pytest.fixture
def manager(bus: EventBus) -> LoopManager:
    lm = LoopManager(bus=bus)
    yield lm
    lm.stop_all()


@pytest.fixture
def controller() -> Controller:
    return Controller(
        id=1,
        name="TIC-101",
        pid_params=PIDParams(gain=1.0, reset=10.0, rate=0.0),
        sp_hi_lim=100.0,
        sp_lo_lim=0.0,
        out_hi_lim=100.0,
        out_lo_lim=0.0,
    )


class TestGetController:
    def test_get_existing_controller(
        self, manager: LoopManager, controller: Controller
    ) -> None:
        manager.start_loop(controller)
        result = manager.get_controller(1)
        assert result.name == "TIC-101"

    def test_get_nonexistent_raises(self, manager: LoopManager) -> None:
        with pytest.raises(ControllerNotFoundError):
            manager.get_controller(999)


class TestSetSetpoint:
    def test_set_valid_setpoint(
        self, manager: LoopManager, controller: Controller
    ) -> None:
        manager.start_loop(controller)
        manager.set_setpoint(1, 55.0)
        c = manager.get_controller(1)
        assert c.sp_hi_lim >= 55.0

    def test_set_setpoint_above_limit_raises(
        self, manager: LoopManager, controller: Controller
    ) -> None:
        manager.start_loop(controller)
        with pytest.raises(DomainError, match="above"):
            manager.set_setpoint(1, 150.0)

    def test_set_setpoint_below_limit_raises(
        self, manager: LoopManager, controller: Controller
    ) -> None:
        manager.start_loop(controller)
        with pytest.raises(DomainError, match="below"):
            manager.set_setpoint(1, -10.0)

    def test_set_setpoint_unknown_controller_raises(
        self, manager: LoopManager
    ) -> None:
        with pytest.raises(ControllerNotFoundError):
            manager.set_setpoint(999, 50.0)


class TestSetMode:
    def test_set_valid_mode(
        self, manager: LoopManager, controller: Controller
    ) -> None:
        manager.start_loop(controller)
        manager.set_mode(1, ControllerMode.AUTO)

    def test_set_invalid_mode_raises(
        self, manager: LoopManager, controller: Controller
    ) -> None:
        manager.start_loop(controller)
        with pytest.raises(DomainError):
            manager.set_mode(1, ControllerMode.CAS)


class TestSetOutput:
    def test_set_output_in_man_mode(
        self, manager: LoopManager, controller: Controller
    ) -> None:
        manager.start_loop(controller)
        # Worker starts in MAN mode
        manager.set_output(1, 50.0)

    def test_set_output_not_in_man_raises(
        self, manager: LoopManager, controller: Controller
    ) -> None:
        manager.start_loop(controller)
        manager.set_mode(1, ControllerMode.AUTO)
        with pytest.raises(DomainError, match="MAN"):
            manager.set_output(1, 50.0)

    def test_set_output_above_limit_raises(
        self, manager: LoopManager, controller: Controller
    ) -> None:
        manager.start_loop(controller)
        with pytest.raises(DomainError, match="above"):
            manager.set_output(1, 150.0)
