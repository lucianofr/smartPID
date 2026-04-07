"""Tests for IOWorker AI tuning write-back to OPC-UA.

Rule: When ACTION.AI is published with a new_ki value, the IO worker
must write it back to OPC-UA using write_pid_params.
This only applies to SUPERVISORY loops (PID runs in DCS).
DDC loops are handled internally by the PID worker.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import msgpack
import zmq

from smart_pid_core.application.workers.io_worker import IOWorker


class TestIOWorkerAIWriteBack:
    """IO worker must write AI tuning decisions back to OPC-UA."""

    def test_drain_and_write_ai_tuning_writes_ti(self) -> None:
        """ACTION.AI with integral_type=TIME_TI writes to ti param."""
        bus = MagicMock()
        bus.ctx = zmq.Context()
        adapter = MagicMock()

        worker = IOWorker(
            bus=bus,
            opcua_adapter=adapter,
            controller_ids=[1],
        )

        mock_sub = MagicMock()
        payload = msgpack.packb({
            "controller_id": 1,
            "new_ki": 15.5,
            "integral_type": "TIME_TI",
            "execution_mode": "SUPERVISORY",
            "gamma": 0.3,
        })
        mock_sub.recv.side_effect = [
            (b"ACTION.AI.1", payload),
            None,  # end of drain
        ]

        worker._drain_and_write_ai_tuning(mock_sub)
        adapter.write_pid_params.assert_called_once_with(1, kp=None, ti=15.5, td=None)
        bus.ctx.term()

    def test_drain_and_write_ai_tuning_writes_ki_as_ti(self) -> None:
        """ACTION.AI with integral_type=GAIN_KI also writes to ti OPC-UA node.

        The OPC-UA node_id_ti maps to whatever integral parameter the DCS uses.
        """
        bus = MagicMock()
        bus.ctx = zmq.Context()
        adapter = MagicMock()

        worker = IOWorker(
            bus=bus,
            opcua_adapter=adapter,
            controller_ids=[1],
        )

        mock_sub = MagicMock()
        payload = msgpack.packb({
            "controller_id": 1,
            "new_ki": 0.05,
            "integral_type": "GAIN_KI",
            "execution_mode": "SUPERVISORY",
            "gamma": -0.2,
        })
        mock_sub.recv.side_effect = [
            (b"ACTION.AI.1", payload),
            None,
        ]

        worker._drain_and_write_ai_tuning(mock_sub)
        adapter.write_pid_params.assert_called_once_with(1, kp=None, ti=0.05, td=None)
        bus.ctx.term()

    def test_no_write_when_no_new_ki(self) -> None:
        """If ACTION.AI has no new_ki, nothing is written."""
        bus = MagicMock()
        bus.ctx = zmq.Context()
        adapter = MagicMock()

        worker = IOWorker(
            bus=bus,
            opcua_adapter=adapter,
            controller_ids=[1],
        )

        mock_sub = MagicMock()
        payload = msgpack.packb({
            "controller_id": 1,
            "gamma": 0.1,
            "execution_mode": "SUPERVISORY",
        })
        mock_sub.recv.side_effect = [
            (b"ACTION.AI.1", payload),
            None,
        ]

        worker._drain_and_write_ai_tuning(mock_sub)
        adapter.write_pid_params.assert_not_called()
        bus.ctx.term()

    def test_no_write_for_ddc_loops(self) -> None:
        """DDC loops don't write back via OPC-UA — PID runs internally."""
        bus = MagicMock()
        bus.ctx = zmq.Context()
        adapter = MagicMock()

        worker = IOWorker(
            bus=bus,
            opcua_adapter=adapter,
            controller_ids=[1],
        )

        mock_sub = MagicMock()
        payload = msgpack.packb({
            "controller_id": 1,
            "new_ki": 15.5,
            "integral_type": "TIME_TI",
            "execution_mode": "DDC",
            "gamma": 0.3,
        })
        mock_sub.recv.side_effect = [
            (b"ACTION.AI.1", payload),
            None,
        ]

        worker._drain_and_write_ai_tuning(mock_sub)
        adapter.write_pid_params.assert_not_called()
        bus.ctx.term()

    def test_multiple_ai_actions_written(self) -> None:
        """Multiple ACTION.AI messages are all written to OPC-UA."""
        bus = MagicMock()
        bus.ctx = zmq.Context()
        adapter = MagicMock()

        worker = IOWorker(
            bus=bus,
            opcua_adapter=adapter,
            controller_ids=[1, 2],
        )

        mock_sub = MagicMock()
        p1 = msgpack.packb({
            "controller_id": 1,
            "new_ki": 12.0,
            "integral_type": "TIME_TI",
            "execution_mode": "SUPERVISORY",
        })
        p2 = msgpack.packb({
            "controller_id": 2,
            "new_ki": 8.5,
            "integral_type": "TIME_TI",
            "execution_mode": "SUPERVISORY",
        })
        mock_sub.recv.side_effect = [
            (b"ACTION.AI.1", p1),
            (b"ACTION.AI.2", p2),
            None,
        ]

        worker._drain_and_write_ai_tuning(mock_sub)
        assert adapter.write_pid_params.call_count == 2
        adapter.write_pid_params.assert_any_call(1, kp=None, ti=12.0, td=None)
        adapter.write_pid_params.assert_any_call(2, kp=None, ti=8.5, td=None)
        bus.ctx.term()
