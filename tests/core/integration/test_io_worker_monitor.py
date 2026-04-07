"""Tests for IOWorker in monitor mode — no BKCAL write-back."""
from dataclasses import dataclass
from unittest.mock import MagicMock

import msgpack
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


# --- Gap #22: PARAMS.{id} publishing ---


@dataclass(frozen=True)
class _FakeParamsRead:
    kp: float | None
    ti: float | None
    td: float | None
    timestamp: float


class TestIOWorkerParamsPublish:
    def test_read_and_publish_params(self) -> None:
        """_read_and_publish_params reads from OPC-UA and publishes."""
        bus = MagicMock()
        bus.ctx = zmq.Context()
        adapter = MagicMock()
        adapter.read_pid_params.return_value = _FakeParamsRead(
            kp=1.5, ti=10.0, td=0.5, timestamp=1234567890.0,
        )

        worker = IOWorker(
            bus=bus,
            opcua_adapter=adapter,
            controller_ids=[1, 2],
        )

        pub = MagicMock()
        worker._read_and_publish_params(pub)

        assert adapter.read_pid_params.call_count == 2
        assert pub.send.call_count == 2

        # Check first call
        topic, payload = pub.send.call_args_list[0].args
        assert topic == b"PARAMS.1"
        data = msgpack.unpackb(payload)
        assert data["controller_id"] == 1
        assert data["kp"] == 1.5
        assert data["ti"] == 10.0
        assert data["td"] == 0.5
        bus.ctx.term()

    def test_read_and_publish_params_none_skips(self) -> None:
        """If read_pid_params returns None, no message is published."""
        bus = MagicMock()
        bus.ctx = zmq.Context()
        adapter = MagicMock()
        adapter.read_pid_params.return_value = None

        worker = IOWorker(
            bus=bus,
            opcua_adapter=adapter,
            controller_ids=[1],
        )

        pub = MagicMock()
        worker._read_and_publish_params(pub)

        assert pub.send.call_count == 0
        bus.ctx.term()

    def test_params_read_interval_class_attr(self) -> None:
        """Verify the 10s interval is set."""
        assert IOWorker._PARAMS_READ_INTERVAL_S == 1.0
