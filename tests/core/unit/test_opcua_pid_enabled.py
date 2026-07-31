"""The PLC "process using this PID is running" binding, end to end in-process.

`TagBindings.node_id_enabled` is conventionally the PLC tag
`PID_[MALHA]_ENABLED` — e.g. `Process_Running` on a ControlLogix. The adapter
reads it, the IO worker republishes it on TELEMETRY every scan, and the AI
worker uses it to gate the optimizer.

The OPC-UA side is exercised through a mock adapter: these tests are about the
plumbing carrying the flag, not about asyncua.
"""
from __future__ import annotations

import time
from datetime import UTC, datetime
from unittest.mock import MagicMock, PropertyMock

import msgpack

from smart_pid_core.adapters.outbound.opcua_adapter import OPCUAAdapter
from smart_pid_core.application.event_bus import EventBus
from smart_pid_core.application.workers.io_worker import IOWorker
from smart_pid_core.config import CoreSettings
from smart_pid_domain.models.signal import FFSignal
from smart_pid_domain.models.telemetry import TelemetryFrame


def _make_settings(**overrides) -> CoreSettings:
    defaults = {"jwt_secret": "test-secret-key-minimum-32-bytes!"}
    defaults.update(overrides)
    return CoreSettings(**defaults)  # type: ignore[call-arg]


def _frame(cid: int = 1) -> TelemetryFrame:
    now = datetime.now(tz=UTC)
    return TelemetryFrame(
        controller_id=cid,
        pv=FFSignal.good(48.0, now),
        sp=FFSignal.good(50.0, now),
        co=FFSignal.good(42.0, now),
        bkcal_in=FFSignal.good(0.0, now),
        integral_val=0.0,
        timestamp=now,
    )


class TestRegistration:
    def test_register_controller_stores_the_enabled_node(self):
        adapter = OPCUAAdapter(settings=_make_settings())
        adapter.register_controller(
            controller_id=1,
            node_id_pv="ns=2;s=PV",
            node_id_sp="ns=2;s=SP",
            node_id_co="ns=2;s=CO",
            node_id_enabled="ns=2;s=Process_Running",
        )
        assert adapter._controllers[1]["enabled"] == "ns=2;s=Process_Running"

    def test_the_binding_is_optional(self):
        adapter = OPCUAAdapter(settings=_make_settings())
        adapter.register_controller(
            controller_id=1,
            node_id_pv="ns=2;s=PV",
            node_id_sp="ns=2;s=SP",
            node_id_co="ns=2;s=CO",
        )
        assert adapter._controllers[1]["enabled"] == ""


class TestReadPidEnabled:
    """An unreadable tag is 'unknown' (None), never a fabricated True/False."""

    def test_returns_none_when_no_node_mapped(self):
        adapter = OPCUAAdapter(settings=_make_settings())
        adapter.register_controller(
            controller_id=1,
            node_id_pv="ns=2;s=PV",
            node_id_sp="ns=2;s=SP",
            node_id_co="ns=2;s=CO",
        )
        assert adapter.read_pid_enabled(1) is None

    def test_returns_none_when_offline(self):
        adapter = OPCUAAdapter(settings=_make_settings())
        adapter.register_controller(
            controller_id=1,
            node_id_pv="ns=2;s=PV",
            node_id_sp="ns=2;s=SP",
            node_id_co="ns=2;s=CO",
            node_id_enabled="ns=2;s=Process_Running",
        )
        assert adapter.read_pid_enabled(1) is None

    def test_returns_none_for_an_unregistered_controller(self):
        adapter = OPCUAAdapter(settings=_make_settings())
        assert adapter.read_pid_enabled(99) is None


class TestIOWorkerPublishesTheFlag:
    """Read once per scan, ahead of the optimizer, and put it on TELEMETRY."""

    def _run_one_scan(self, pid_enabled) -> dict:
        bus = EventBus(url_prefix=f"inproc://test_enabled_{time.monotonic_ns():x}")
        bus.start()
        try:
            adapter = MagicMock()
            type(adapter).is_connected = PropertyMock(return_value=True)
            adapter.read_telemetry.return_value = _frame()
            adapter.read_actual_mode.return_value = None
            adapter.read_pid_params.return_value = None
            adapter.read_pid_enabled.return_value = pid_enabled

            worker = IOWorker(
                bus=bus, opcua_adapter=adapter,
                controller_ids=[1], scan_interval_s=0.02,
            )
            sub = bus.create_subscriber(b"TELEMETRY.1")
            time.sleep(0.05)
            worker.start()
            try:
                msg = sub.recv(timeout_ms=2000)
            finally:
                worker.stop()
            assert msg is not None, "IOWorker published no telemetry"
            assert adapter.read_pid_enabled.call_count >= 1
            adapter.read_pid_enabled.assert_called_with(1)
            return msgpack.unpackb(msg[1])
        finally:
            bus.stop()

    def test_running_process_is_published_as_true(self):
        assert self._run_one_scan(True)["pid_enabled"] is True

    def test_stopped_process_is_published_as_false(self):
        assert self._run_one_scan(False)["pid_enabled"] is False

    def test_unmapped_tag_is_published_as_none(self):
        assert self._run_one_scan(None)["pid_enabled"] is None

    def test_read_every_cycle_not_cached(self):
        """The PLC can stop the process between two scans."""
        bus = EventBus(url_prefix=f"inproc://test_enabled_cyc_{time.monotonic_ns():x}")
        bus.start()
        try:
            adapter = MagicMock()
            type(adapter).is_connected = PropertyMock(return_value=True)
            adapter.read_telemetry.return_value = _frame()
            adapter.read_actual_mode.return_value = None
            adapter.read_pid_params.return_value = None
            adapter.read_pid_enabled.side_effect = [True, True, False, False] + [False] * 50

            worker = IOWorker(
                bus=bus, opcua_adapter=adapter,
                controller_ids=[1], scan_interval_s=0.02,
            )
            sub = bus.create_subscriber(b"TELEMETRY.1")
            time.sleep(0.05)
            worker.start()
            try:
                seen = []
                for _ in range(4):
                    msg = sub.recv(timeout_ms=2000)
                    assert msg is not None
                    seen.append(msgpack.unpackb(msg[1])["pid_enabled"])
            finally:
                worker.stop()
            assert seen == [True, True, False, False], (
                f"every scan must re-read the tag, got {seen}"
            )
        finally:
            bus.stop()
