"""Tests for LoopManager in monitor mode."""
import uuid

import pytest

from smart_pid_core.application.event_bus import EventBus
from smart_pid_core.application.loop_manager import LoopManager
from smart_pid_domain.enums import ControllerMode
from smart_pid_domain.exceptions import DomainError
from smart_pid_domain.models.controller import Controller


@pytest.fixture
def bus():
    b = EventBus(url_prefix=f"inproc://test_loop_manager_m_{uuid.uuid4().hex[:8]}")
    b.start()
    yield b
    b.stop()


class TestLoopManagerMonitorMode:
    def test_start_loop_creates_monitor_worker(self, bus: EventBus) -> None:
        lm = LoopManager(bus, execution_mode="monitor")
        ctrl = Controller(id=1, name="test-mon")
        lm.start_loop(ctrl)

        ctx = lm.get_context(1)
        assert ctx is not None
        assert ctx.pid_worker is None
        assert ctx.monitor_worker is not None
        assert ctx.monitor_worker.is_alive()

        lm.stop_all()

    def test_start_loop_execute_creates_pid_worker(self, bus: EventBus) -> None:
        lm = LoopManager(bus, execution_mode="execute")
        ctrl = Controller(id=1, name="test-exec")
        lm.start_loop(ctrl)

        ctx = lm.get_context(1)
        assert ctx is not None
        assert ctx.pid_worker is not None
        assert ctx.monitor_worker is None

        lm.stop_all()

    def test_set_setpoint_blocked_in_monitor(self, bus: EventBus) -> None:
        lm = LoopManager(bus, execution_mode="monitor")
        ctrl = Controller(id=1, name="test-mon")
        lm.start_loop(ctrl)

        with pytest.raises(DomainError, match="monitor"):
            lm.set_setpoint(1, 50.0)

        lm.stop_all()

    def test_set_mode_blocked_in_monitor(self, bus: EventBus) -> None:
        lm = LoopManager(bus, execution_mode="monitor")
        ctrl = Controller(id=1, name="test-mon")
        lm.start_loop(ctrl)

        with pytest.raises(DomainError, match="monitor"):
            lm.set_mode(1, ControllerMode.AUTO)

        lm.stop_all()

    def test_set_output_blocked_in_monitor(self, bus: EventBus) -> None:
        lm = LoopManager(bus, execution_mode="monitor")
        ctrl = Controller(id=1, name="test-mon")
        lm.start_loop(ctrl)

        with pytest.raises(DomainError, match="monitor"):
            lm.set_output(1, 50.0)

        lm.stop_all()

    def test_is_loop_running_in_monitor(self, bus: EventBus) -> None:
        lm = LoopManager(bus, execution_mode="monitor")
        ctrl = Controller(id=1, name="test-mon")
        lm.start_loop(ctrl)

        assert lm.is_loop_running(1) is True

        lm.stop_all()
