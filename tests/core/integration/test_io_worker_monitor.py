"""Tests for IOWorker in monitor mode — no BKCAL write-back."""
import pytest
from unittest.mock import MagicMock
import zmq

from smart_pid_core.application.workers.io_worker import IOWorker


class TestIOWorkerMonitorMode:
    def test_accepts_execution_mode_param(self) -> None:
        bus = MagicMock()
        bus.ctx = zmq.Context()
        adapter = MagicMock()

        worker = IOWorker(
            bus=bus,
            opcua_adapter=adapter,
            controller_ids=[1],
            execution_mode="monitor",
        )
        assert worker._execution_mode == "monitor"
        bus.ctx.term()

    def test_monitor_mode_skips_bkcal(self) -> None:
        bus = MagicMock()
        bus.ctx = zmq.Context()
        adapter = MagicMock()

        worker = IOWorker(
            bus=bus,
            opcua_adapter=adapter,
            controller_ids=[1],
            execution_mode="monitor",
        )
        assert worker._skip_bkcal_write is True
        bus.ctx.term()

    def test_execute_mode_does_not_skip_bkcal(self) -> None:
        bus = MagicMock()
        bus.ctx = zmq.Context()
        adapter = MagicMock()

        worker = IOWorker(
            bus=bus,
            opcua_adapter=adapter,
            controller_ids=[1],
            execution_mode="execute",
        )
        assert worker._skip_bkcal_write is False
        bus.ctx.term()

    def test_default_mode_is_execute(self) -> None:
        bus = MagicMock()
        bus.ctx = zmq.Context()
        adapter = MagicMock()

        worker = IOWorker(
            bus=bus,
            opcua_adapter=adapter,
            controller_ids=[1],
        )
        assert worker._execution_mode == "execute"
        assert worker._skip_bkcal_write is False
        bus.ctx.term()
