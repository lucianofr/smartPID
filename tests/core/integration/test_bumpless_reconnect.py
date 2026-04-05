"""Tests for bumpless transfer after OPC-UA reconnect.

Verifies that when the OPC-UA connection drops and reconnects:
1. IOWorker publishes SYS.RECONNECT events with current field CO/PV
2. PIDWorker reinitializes PID state via bumpless_transfer()
3. Output does not bump (CV matches pre-reconnect CO)
4. PV history is reset to prevent derivative kick
"""
from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock, PropertyMock

import msgpack
import pytest

from smart_pid_core.application.event_bus import EventBus
from smart_pid_core.application.workers.io_worker import IOWorker
from smart_pid_core.application.workers.pid_worker import PIDWorker
from smart_pid_core.domain.services.pid_engine import PIDEngine, PIDState
from smart_pid_core.domain.services.pid_mode_manager import ModeManager
from smart_pid_domain.enums import ControllerMode
from smart_pid_domain.models.controller import Controller, PIDParams
from smart_pid_domain.models.signal import FFSignal
from smart_pid_domain.models.telemetry import TelemetryFrame


def _make_bus() -> EventBus:
    return EventBus(url_prefix=f"inproc://test_reconnect_{uuid.uuid4().hex[:8]}")


def _make_controller(cid: int = 1) -> Controller:
    return Controller(
        id=cid,
        name="TIC-101",
        pid_params=PIDParams(gain=1.0, reset=10.0, rate=1.0),
        scan_rate_ms=100,
    )


def _make_telemetry_frame(
    cid: int = 1, pv: float = 50.0, sp: float = 50.0, co: float = 42.0,
) -> TelemetryFrame:
    now = datetime.now(tz=UTC)
    return TelemetryFrame(
        controller_id=cid,
        pv=FFSignal.good(pv, now),
        sp=FFSignal.good(sp, now),
        co=FFSignal.good(co, now),
        bkcal_in=FFSignal.good(0.0, now),
        integral_val=0.0,
        timestamp=now,
    )


class TestIOWorkerReconnectDetection:
    """IOWorker publishes SYS.RECONNECT on OPC-UA reconnect."""

    def test_no_reconnect_event_on_first_connect(self) -> None:
        """First connection should NOT trigger reconnect events."""
        bus = _make_bus()
        bus.start()
        try:
            adapter = MagicMock()
            # Simulate: starts disconnected, then connects
            connected_seq = [False, True, True]
            type(adapter).is_connected = PropertyMock(side_effect=connected_seq)
            adapter.read_telemetry.return_value = _make_telemetry_frame()

            worker = IOWorker(
                bus=bus, opcua_adapter=adapter,
                controller_ids=[1], scan_interval_s=0.01,
            )

            sub = bus.create_subscriber(b"SYS.RECONNECT")
            time.sleep(0.05)

            worker.start()
            time.sleep(0.15)
            worker.stop()

            msg = sub.recv(timeout_ms=100)
            assert msg is None, "Should not publish reconnect on first connect"
        finally:
            bus.stop()

    def test_publishes_reconnect_after_disconnect_reconnect(self) -> None:
        """After disconnect+reconnect cycle, SYS.RECONNECT is published."""
        bus = _make_bus()
        bus.start()
        try:
            adapter = MagicMock()
            # Sequence: connected -> disconnected -> reconnected
            connected_seq = [
                True, True,   # initial connected (first connect)
                False, False,  # disconnected
                True, True, True,  # reconnected
            ]
            type(adapter).is_connected = PropertyMock(side_effect=connected_seq)
            adapter.read_telemetry.return_value = _make_telemetry_frame(
                co=65.0, pv=48.0,
            )

            worker = IOWorker(
                bus=bus, opcua_adapter=adapter,
                controller_ids=[1], scan_interval_s=0.01,
            )
            # Manually set _ever_connected to simulate prior connection
            worker._ever_connected = True
            worker._was_connected = True

            sub = bus.create_subscriber(b"SYS.RECONNECT")
            time.sleep(0.05)

            worker.start()
            time.sleep(0.2)
            worker.stop()

            msg = sub.recv(timeout_ms=500)
            assert msg is not None, "Should publish SYS.RECONNECT after reconnect"
            topic, payload = msg
            assert topic == b"SYS.RECONNECT.1"
            data = msgpack.unpackb(payload)
            assert data["controller_id"] == 1
            assert data["co"] == pytest.approx(65.0)
            assert data["pv"] == pytest.approx(48.0)
        finally:
            bus.stop()

    def test_reconnect_event_per_controller(self) -> None:
        """Each registered controller gets its own SYS.RECONNECT event."""
        bus = _make_bus()
        bus.start()
        try:
            adapter = MagicMock()
            # disconnected -> reconnected
            connected_seq = [False, True, True, True]
            type(adapter).is_connected = PropertyMock(side_effect=connected_seq)

            def read_telem(cid):
                return _make_telemetry_frame(cid=cid, co=float(cid * 10), pv=float(cid))

            adapter.read_telemetry.side_effect = read_telem

            worker = IOWorker(
                bus=bus, opcua_adapter=adapter,
                controller_ids=[1, 2], scan_interval_s=0.01,
            )
            worker._ever_connected = True  # Simulate prior connection

            sub1 = bus.create_subscriber(b"SYS.RECONNECT.1")
            sub2 = bus.create_subscriber(b"SYS.RECONNECT.2")
            time.sleep(0.05)

            worker.start()
            time.sleep(0.15)
            worker.stop()

            msg1 = sub1.recv(timeout_ms=500)
            msg2 = sub2.recv(timeout_ms=500)
            assert msg1 is not None
            assert msg2 is not None

            data1 = msgpack.unpackb(msg1[1])
            data2 = msgpack.unpackb(msg2[1])
            assert data1["controller_id"] == 1
            assert data1["co"] == pytest.approx(10.0)
            assert data2["controller_id"] == 2
            assert data2["co"] == pytest.approx(20.0)
        finally:
            bus.stop()

    def test_reconnect_tolerates_read_failure(self) -> None:
        """If telemetry read fails during reconnect, no crash."""
        bus = _make_bus()
        bus.start()
        try:
            adapter = MagicMock()
            connected_seq = [False, True, True]
            type(adapter).is_connected = PropertyMock(side_effect=connected_seq)
            adapter.read_telemetry.side_effect = ConnectionError("timeout")

            worker = IOWorker(
                bus=bus, opcua_adapter=adapter,
                controller_ids=[1], scan_interval_s=0.01,
            )
            worker._ever_connected = True

            worker.start()
            time.sleep(0.1)
            # Should not crash
            worker.stop()
        finally:
            bus.stop()


class TestPIDWorkerBumplessOnReconnect:
    """PIDWorker performs bumpless transfer upon receiving SYS.RECONNECT."""

    def test_bumpless_transfer_reinitializes_state(self) -> None:
        """After SYS.RECONNECT, PID state CV matches field CO."""
        bus = _make_bus()
        bus.start()
        try:
            controller = _make_controller()
            engine = PIDEngine()
            worker = PIDWorker(
                bus=bus, controller=controller,
                engine=engine, mode_manager=ModeManager(),
            )
            worker.set_mode(ControllerMode.AUTO)

            # Set up stale state — integral has drifted
            worker._state = PIDState(
                cv=20.0, error_prev=5.0, pv_prev=45.0, pv_prev2=44.0,
                derivative_filtered=1.5, is_saturated=False,
            )

            worker.start()
            pub = bus.create_publisher()
            time.sleep(0.05)

            # Simulate reconnect with field CO=65, PV=50
            reconnect_data = {
                "controller_id": 1, "co": 65.0, "pv": 50.0, "sp": 50.0,
            }
            pub.send(b"SYS.RECONNECT.1", msgpack.packb(reconnect_data))
            time.sleep(0.2)

            # Verify state was reinitialized
            assert worker._state.cv == pytest.approx(65.0), (
                "CV should match field CO after bumpless transfer"
            )
            assert worker._state.pv_prev == pytest.approx(50.0), (
                "PV history should be reset to current PV"
            )
            assert worker._state.pv_prev2 == pytest.approx(50.0), (
                "PV_prev2 should also be reset to prevent derivative kick"
            )
            assert worker._state.error_prev == pytest.approx(0.0), (
                "Error history should be cleared"
            )
            assert worker._state.derivative_filtered == pytest.approx(0.0), (
                "Derivative filter should be reset"
            )
        finally:
            worker.stop()
            bus.stop()

    def test_no_output_bump_after_reconnect(self) -> None:
        """After bumpless transfer, first PID output should be close to field CO."""
        bus = _make_bus()
        bus.start()
        try:
            controller = _make_controller()
            engine = PIDEngine()
            worker = PIDWorker(
                bus=bus, controller=controller,
                engine=engine, mode_manager=ModeManager(),
            )
            worker.set_mode(ControllerMode.AUTO)

            # Stale state: integral drifted far from actual plant output
            worker._state = PIDState(
                cv=20.0, error_prev=10.0, pv_prev=40.0, pv_prev2=39.0,
            )

            worker.start()
            pub = bus.create_publisher()
            action_sub = bus.create_subscriber(b"ACTION.CTRL.1")
            time.sleep(0.05)

            # Simulate reconnect: plant is at CO=65, PV=50, SP=50
            reconnect_data = {
                "controller_id": 1, "co": 65.0, "pv": 50.0, "sp": 50.0,
            }
            pub.send(b"SYS.RECONNECT.1", msgpack.packb(reconnect_data))
            time.sleep(0.05)

            # Now send telemetry — PV=50, SP=50, error=0
            now = datetime.now(tz=UTC)
            frame_data = {
                "controller_id": 1,
                "pv": {"value": 50.0, "severity": "GOOD",
                       "limit_bits": "NONE", "sub_status": "NONE"},
                "sp": {"value": 50.0, "severity": "GOOD",
                       "limit_bits": "NONE", "sub_status": "NONE"},
                "co": {"value": 65.0, "severity": "GOOD",
                       "limit_bits": "NONE", "sub_status": "NONE"},
                "bkcal_in": {"value": 0.0, "severity": "GOOD",
                             "limit_bits": "NONE", "sub_status": "NONE"},
                "integral_val": 0.0,
                "timestamp": now.isoformat(),
            }
            pub.send(b"TELEMETRY.1", msgpack.packb(frame_data))

            # Wait for PID computation
            msg = action_sub.recv(timeout_ms=2000)
            assert msg is not None, "Should receive ACTION.CTRL after reconnect"

            topic, payload = msg
            action = msgpack.unpackb(payload)
            co_value = action["co"]
            if isinstance(co_value, dict):
                co_value = co_value["value"]

            # Output should be close to 65.0 (field CO), not 20.0 (stale state)
            # With error=0 and bumpless state, delta_cv should be ~0
            assert co_value == pytest.approx(65.0, abs=1.0), (
                f"Output should be near field CO (65.0), got {co_value}"
            )
        finally:
            worker.stop()
            bus.stop()

    def test_pv_history_reset_prevents_derivative_kick(self) -> None:
        """PV history reset means no derivative spike on first scan after reconnect."""
        bus = _make_bus()
        bus.start()
        try:
            # Controller with derivative action
            controller = Controller(
                id=1, name="TIC-101",
                pid_params=PIDParams(gain=1.0, reset=10.0, rate=2.0),
                scan_rate_ms=100,
            )
            engine = PIDEngine()
            worker = PIDWorker(
                bus=bus, controller=controller,
                engine=engine, mode_manager=ModeManager(),
            )
            worker.set_mode(ControllerMode.AUTO)

            # Stale state: PV was at 40, now plant is at 50
            worker._state = PIDState(
                cv=65.0, error_prev=0.0, pv_prev=40.0, pv_prev2=39.0,
            )

            worker.start()
            pub = bus.create_publisher()
            time.sleep(0.05)

            # Reconnect with PV=50 — without bumpless, the derivative would
            # see PV jump from 40->50 causing a spike
            reconnect_data = {
                "controller_id": 1, "co": 65.0, "pv": 50.0, "sp": 50.0,
            }
            pub.send(b"SYS.RECONNECT.1", msgpack.packb(reconnect_data))
            time.sleep(0.1)

            # After bumpless transfer: pv_prev=50, pv_prev2=50
            # So d2_pv = pv - 2*pv_prev + pv_prev2 = 50 - 100 + 50 = 0
            assert worker._state.pv_prev == pytest.approx(50.0)
            assert worker._state.pv_prev2 == pytest.approx(50.0)
        finally:
            worker.stop()
            bus.stop()


class TestIOWorkerWasConnectedTracking:
    """Unit tests for the _was_connected / _ever_connected state tracking."""

    def test_initial_state(self) -> None:
        adapter = MagicMock()
        bus = MagicMock()
        worker = IOWorker(
            bus=bus, opcua_adapter=adapter,
            controller_ids=[1], scan_interval_s=0.1,
        )
        assert worker._was_connected is False
        assert worker._ever_connected is False

    def test_ever_connected_set_after_first_connect(self) -> None:
        """_ever_connected becomes True after first connection cycle."""
        bus = _make_bus()
        bus.start()
        try:
            adapter = MagicMock()
            # Start connected
            connected_seq = [True, True]
            type(adapter).is_connected = PropertyMock(side_effect=connected_seq)
            adapter.read_telemetry.return_value = _make_telemetry_frame()

            worker = IOWorker(
                bus=bus, opcua_adapter=adapter,
                controller_ids=[1], scan_interval_s=0.01,
            )
            worker.start()
            time.sleep(0.1)
            worker.stop()

            assert worker._ever_connected is True
        finally:
            bus.stop()
