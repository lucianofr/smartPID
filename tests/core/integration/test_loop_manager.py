from __future__ import annotations
import time
import pytest
from smart_pid_domain.models.controller import Controller
from smart_pid_core.application.event_bus import EventBus
from smart_pid_core.application.loop_manager import LoopManager


class TestLoopManager:
    def test_start_and_stop_loop(self) -> None:
        bus = EventBus()
        bus.start()
        try:
            manager = LoopManager(bus=bus)
            controller = Controller(id=1, name="TIC-101", scan_rate_ms=100)
            manager.start_loop(controller)
            time.sleep(0.1)
            assert manager.is_loop_running(1)
            manager.stop_loop(1)
            time.sleep(0.1)
            assert not manager.is_loop_running(1)
        finally:
            bus.stop()

    def test_stop_all_loops(self) -> None:
        bus = EventBus()
        bus.start()
        try:
            manager = LoopManager(bus=bus)
            ctrl1 = Controller(id=1, name="TIC-101", scan_rate_ms=100)
            ctrl2 = Controller(id=2, name="FIC-201", scan_rate_ms=100)
            manager.start_loop(ctrl1)
            manager.start_loop(ctrl2)
            time.sleep(0.1)
            assert manager.is_loop_running(1)
            assert manager.is_loop_running(2)
            manager.stop_all()
            time.sleep(0.1)
            assert not manager.is_loop_running(1)
            assert not manager.is_loop_running(2)
        finally:
            bus.stop()

    def test_double_start_is_safe(self) -> None:
        bus = EventBus()
        bus.start()
        try:
            manager = LoopManager(bus=bus)
            controller = Controller(id=1, name="TIC-101", scan_rate_ms=100)
            manager.start_loop(controller)
            manager.start_loop(controller)  # Should not raise or create duplicate
            time.sleep(0.1)
            assert manager.is_loop_running(1)
            manager.stop_all()
        finally:
            bus.stop()

    def test_stop_nonexistent_is_safe(self) -> None:
        bus = EventBus()
        bus.start()
        try:
            manager = LoopManager(bus=bus)
            manager.stop_loop(999)  # Should not raise
        finally:
            bus.stop()
