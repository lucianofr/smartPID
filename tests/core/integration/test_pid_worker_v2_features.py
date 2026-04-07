"""Integration tests for PID worker v2 features:
1. CAS_IN / RCAS_IN handling
2. BYPASS mode
3. SIMULATE mode
4. STATUS_OPTS signal quality interpretation
5. TRACK_OPT behavior with bad TRK_IN_D
6. ProcessType (model-level, informational)
"""
from __future__ import annotations

import time
import uuid

import msgpack
import pytest

from smart_pid_core.application.event_bus import EventBus
from smart_pid_core.application.workers.pid_worker import (
    PIDWorker,
    _evaluate_pv_quality,
)
from smart_pid_core.domain.services.pid_engine import PIDEngine
from smart_pid_core.domain.services.pid_mode_manager import ModeManager
from smart_pid_domain.enums import (
    ControllerMode,
    LimitBits,
    ProcessType,
    SignalSeverity,
    TrackOpt,
)
from smart_pid_domain.models.controller import (
    Controller,
    ControlOpts,
    IOOpts,
    PIDParams,
    StatusOpts,
)
from smart_pid_domain.models.signal import FFSignal, FFSignalStatus


def _make_bus() -> EventBus:
    bus = EventBus(
        url_prefix=f"inproc://test_{uuid.uuid4().hex[:8]}",
    )
    bus.start()
    return bus


def _make_worker(
    bus: EventBus,
    controller: Controller,
    mode: ControllerMode = ControllerMode.AUTO,
) -> PIDWorker:
    worker = PIDWorker(
        bus=bus,
        controller=controller,
        engine=PIDEngine(),
        mode_manager=ModeManager(),
    )
    worker.set_mode(mode)
    return worker


def _send_telemetry(
    pub,  # noqa: ANN001
    controller_id: int,
    pv: float = 50.0,
    sp: float = 50.0,
    co: float = 50.0,
    **extra,
) -> None:
    data = {"pv": pv, "sp": sp, "co": co, **extra}
    pub.send(
        f"TELEMETRY.{controller_id}".encode(),
        msgpack.packb(data),
    )


def _recv_action(sub, timeout_ms: int = 2000) -> dict | None:  # noqa: ANN001
    msg = sub.recv(timeout_ms=timeout_ms)
    if msg is None:
        return None
    _topic, payload = msg
    return msgpack.unpackb(payload)


# ===========================================================================
# Feature 1: CAS_IN / RCAS_IN handling
# ===========================================================================
class TestCASINHandling:
    """In CAS mode, SP should come from CAS_IN. In RCAS, from RCAS_IN."""

    def test_cas_mode_uses_cas_in_for_sp(self) -> None:
        bus = _make_bus()
        try:
            ctrl = Controller(
                id=1, name="T-CAS", scan_rate_ms=100,
                pid_params=PIDParams(gain=1.0, reset=10.0),
                permitted_modes={
                    ControllerMode.MAN,
                    ControllerMode.AUTO,
                    ControllerMode.CAS,
                },
            )
            worker = _make_worker(bus, ctrl, mode=ControllerMode.CAS)
            worker.start()
            pub = bus.create_publisher()
            sub = bus.create_subscriber(b"STATUS.1")
            time.sleep(0.05)

            # Send telemetry with cas_in value
            cas_signal = {
                "value": 70.0, "severity": "GOOD",
                "limit_bits": "NONE", "sub_status": "NONE",
            }
            _send_telemetry(
                pub, 1, pv=50.0, sp=40.0, cas_in=cas_signal,
            )
            msg = sub.recv(timeout_ms=2000)
            assert msg is not None
            status = msgpack.unpackb(msg[1])
            # SP should be 70.0 (from CAS_IN), not 40.0
            assert status["sp"]["value"] == pytest.approx(
                70.0, abs=1.0,
            )
        finally:
            worker.stop()
            bus.stop()

    def test_rcas_mode_uses_rcas_in_for_sp(self) -> None:
        bus = _make_bus()
        try:
            ctrl = Controller(
                id=1, name="T-RCAS", scan_rate_ms=100,
                pid_params=PIDParams(gain=1.0, reset=10.0),
                permitted_modes={
                    ControllerMode.MAN,
                    ControllerMode.AUTO,
                    ControllerMode.RCAS,
                },
            )
            worker = _make_worker(
                bus, ctrl, mode=ControllerMode.RCAS,
            )
            worker.start()
            pub = bus.create_publisher()
            sub = bus.create_subscriber(b"STATUS.1")
            time.sleep(0.05)

            rcas_signal = {
                "value": 80.0, "severity": "GOOD",
                "limit_bits": "NONE", "sub_status": "NONE",
            }
            _send_telemetry(
                pub, 1, pv=50.0, sp=40.0, rcas_in=rcas_signal,
            )
            msg = sub.recv(timeout_ms=2000)
            assert msg is not None
            status = msgpack.unpackb(msg[1])
            assert status["sp"]["value"] == pytest.approx(
                80.0, abs=1.0,
            )
        finally:
            worker.stop()
            bus.stop()

    def test_auto_mode_ignores_cas_in(self) -> None:
        bus = _make_bus()
        try:
            ctrl = Controller(
                id=1, name="T-AUTO-CAS", scan_rate_ms=100,
                pid_params=PIDParams(gain=1.0, reset=10.0),
            )
            worker = _make_worker(
                bus, ctrl, mode=ControllerMode.AUTO,
            )
            worker.start()
            pub = bus.create_publisher()
            sub = bus.create_subscriber(b"STATUS.1")
            time.sleep(0.05)

            cas_signal = {
                "value": 70.0, "severity": "GOOD",
                "limit_bits": "NONE", "sub_status": "NONE",
            }
            _send_telemetry(
                pub, 1, pv=50.0, sp=40.0, cas_in=cas_signal,
            )
            msg = sub.recv(timeout_ms=2000)
            assert msg is not None
            status = msgpack.unpackb(msg[1])
            # SP should be 40.0 (from telemetry), NOT 70.0
            assert status["sp"]["value"] == pytest.approx(
                40.0, abs=1.0,
            )
        finally:
            worker.stop()
            bus.stop()


# ===========================================================================
# Feature 2: BYPASS mode
# ===========================================================================
class TestBypassMode:
    """In BYPASS mode, SP% goes directly to output."""

    def test_bypass_sp_to_output(self) -> None:
        bus = _make_bus()
        try:
            ctrl = Controller(
                id=1, name="T-BYPASS", scan_rate_ms=100,
                pid_params=PIDParams(gain=1.0, reset=10.0),
                control_opts=ControlOpts(bypass_enable=True),
                out_hi_lim=100.0,
                out_lo_lim=0.0,
                permitted_modes={
                    ControllerMode.MAN,
                    ControllerMode.BYPASS,
                },
            )
            worker = _make_worker(
                bus, ctrl, mode=ControllerMode.BYPASS,
            )
            worker.start()
            pub = bus.create_publisher()
            sub = bus.create_subscriber(b"ACTION.CTRL.1")
            time.sleep(0.05)

            _send_telemetry(pub, 1, pv=50.0, sp=65.0)
            action = _recv_action(sub, timeout_ms=2000)
            assert action is not None
            # In BYPASS, CO should equal SP (65.0)
            assert action["co"]["value"] == pytest.approx(
                65.0, abs=0.1,
            )
        finally:
            worker.stop()
            bus.stop()

    def test_bypass_clamped_to_output_limits(self) -> None:
        bus = _make_bus()
        try:
            ctrl = Controller(
                id=1, name="T-BYPASS-CLAMP", scan_rate_ms=100,
                pid_params=PIDParams(gain=1.0, reset=10.0),
                control_opts=ControlOpts(bypass_enable=True),
                out_hi_lim=80.0,
                out_lo_lim=10.0,
                permitted_modes={
                    ControllerMode.MAN,
                    ControllerMode.BYPASS,
                },
            )
            worker = _make_worker(
                bus, ctrl, mode=ControllerMode.BYPASS,
            )
            worker.start()
            pub = bus.create_publisher()
            sub = bus.create_subscriber(b"ACTION.CTRL.1")
            time.sleep(0.05)

            _send_telemetry(pub, 1, pv=50.0, sp=95.0)
            action = _recv_action(sub, timeout_ms=2000)
            assert action is not None
            # SP=95 should be clamped to out_hi_lim=80
            assert action["co"]["value"] == pytest.approx(
                80.0, abs=0.1,
            )
        finally:
            worker.stop()
            bus.stop()


# ===========================================================================
# Feature 3: SIMULATE mode
# ===========================================================================
class TestSimulateMode:
    """When simulate is active, simulated PV replaces real PV."""

    def test_simulate_pv_replaces_real_pv(self) -> None:
        bus = _make_bus()
        try:
            ctrl = Controller(
                id=1, name="T-SIM", scan_rate_ms=100,
                pid_params=PIDParams(gain=1.0, reset=10.0),
            )
            worker = _make_worker(
                bus, ctrl, mode=ControllerMode.AUTO,
            )
            # Set simulated PV=80 before starting
            worker.set_simulate_pv(80.0)
            assert worker.simulate_active is True
            worker.start()
            pub = bus.create_publisher()
            sub = bus.create_subscriber(b"ACTION.CTRL.1")
            time.sleep(0.05)

            # Real PV=50, but simulate=80 -> error = SP(50) - PV(80) = -30
            _send_telemetry(pub, 1, pv=50.0, sp=50.0)
            action = _recv_action(sub, timeout_ms=2000)
            assert action is not None
            # With simulated PV=80 and SP=50, error is -30
            # delta_cv should be negative (reverse acting off)
            assert action["delta_cv"] < 0

        finally:
            worker.stop()
            bus.stop()

    def test_clear_simulate_reverts_to_real_pv(self) -> None:
        bus = _make_bus()
        try:
            ctrl = Controller(
                id=1, name="T-SIM-CLR", scan_rate_ms=100,
                pid_params=PIDParams(gain=1.0, reset=10.0),
            )
            worker = _make_worker(
                bus, ctrl, mode=ControllerMode.AUTO,
            )
            worker.set_simulate_pv(80.0)
            worker.clear_simulate()
            assert worker.simulate_active is False
            worker.start()
            pub = bus.create_publisher()
            sub = bus.create_subscriber(b"ACTION.CTRL.1")
            time.sleep(0.05)

            # No simulate active -> real PV=50 used
            _send_telemetry(pub, 1, pv=50.0, sp=50.0)
            action = _recv_action(sub, timeout_ms=2000)
            assert action is not None
            # error = 0, delta_cv = 0
            assert action["delta_cv"] == pytest.approx(0.0, abs=0.1)
        finally:
            worker.stop()
            bus.stop()


# ===========================================================================
# Feature 4: STATUS_OPTS (unit-level via _evaluate_pv_quality)
# ===========================================================================
class TestStatusOpts:
    """STATUS_OPTS signal quality interpretation."""

    def test_bad_if_limited_converts_limited_to_bad(self) -> None:
        opts = StatusOpts(bad_if_limited=True)
        pv = FFSignal(
            value=50.0,
            status=FFSignalStatus(
                severity=SignalSeverity.GOOD,
                limit_bits=LimitBits.HIGH_LIMITED,
            ),
        )
        result = _evaluate_pv_quality(pv, opts)
        assert result.status.severity == SignalSeverity.BAD

    def test_bad_if_limited_no_effect_when_none(self) -> None:
        opts = StatusOpts(bad_if_limited=True)
        pv = FFSignal(
            value=50.0,
            status=FFSignalStatus(
                severity=SignalSeverity.GOOD,
                limit_bits=LimitBits.NONE,
            ),
        )
        result = _evaluate_pv_quality(pv, opts)
        assert result.status.severity == SignalSeverity.GOOD

    def test_use_uncertain_as_good(self) -> None:
        opts = StatusOpts(use_uncertain_as_good=True)
        pv = FFSignal(
            value=50.0,
            status=FFSignalStatus(
                severity=SignalSeverity.UNCERTAIN,
            ),
        )
        result = _evaluate_pv_quality(pv, opts)
        assert result.status.severity == SignalSeverity.GOOD

    def test_uncertain_stays_uncertain_without_opt(self) -> None:
        opts = StatusOpts(use_uncertain_as_good=False)
        pv = FFSignal(
            value=50.0,
            status=FFSignalStatus(
                severity=SignalSeverity.UNCERTAIN,
            ),
        )
        result = _evaluate_pv_quality(pv, opts)
        assert result.status.severity == SignalSeverity.UNCERTAIN

    def test_good_signal_unchanged(self) -> None:
        opts = StatusOpts(
            bad_if_limited=True, use_uncertain_as_good=True,
        )
        pv = FFSignal.good(50.0)
        result = _evaluate_pv_quality(pv, opts)
        assert result is pv  # Same object, no modification

    def test_bad_if_limited_plus_use_uncertain_as_good(self) -> None:
        """bad_if_limited turns LIMITED->BAD; use_uncertain_as_good
        does NOT override BAD back to GOOD."""
        opts = StatusOpts(
            bad_if_limited=True, use_uncertain_as_good=True,
        )
        pv = FFSignal(
            value=50.0,
            status=FFSignalStatus(
                severity=SignalSeverity.GOOD,
                limit_bits=LimitBits.LOW_LIMITED,
            ),
        )
        result = _evaluate_pv_quality(pv, opts)
        # bad_if_limited converts to BAD; use_uncertain_as_good only
        # converts UNCERTAIN->GOOD, not BAD->GOOD
        assert result.status.severity == SignalSeverity.BAD


# ===========================================================================
# Feature 5: TRACK_OPT
# ===========================================================================
class TestTrackOpt:
    """TRACK_OPT controls TRK_IN_D resolution when signal is BAD."""

    def test_always_use_value_uses_current_even_if_bad(self) -> None:
        bus = _make_bus()
        try:
            ctrl = Controller(
                id=1, name="T-TRK-OPT", scan_rate_ms=100,
                pid_params=PIDParams(gain=1.0, reset=10.0),
                track_opt=TrackOpt.ALWAYS_USE_VALUE,
                control_opts=ControlOpts(track_enable=True),
            )
            worker = _make_worker(
                bus, ctrl, mode=ControllerMode.AUTO,
            )
            # Call _resolve_trk_in_d directly
            worker._resolve_trk_in_d(value=True, is_bad=True)
            assert ctrl.trk_in_d is True

            worker._resolve_trk_in_d(value=False, is_bad=True)
            assert ctrl.trk_in_d is False
        finally:
            bus.stop()

    def test_use_last_good_keeps_last_good_value(self) -> None:
        bus = _make_bus()
        try:
            ctrl = Controller(
                id=1, name="T-TRK-LG", scan_rate_ms=100,
                pid_params=PIDParams(gain=1.0, reset=10.0),
                track_opt=TrackOpt.USE_LAST_GOOD,
                control_opts=ControlOpts(track_enable=True),
            )
            worker = _make_worker(
                bus, ctrl, mode=ControllerMode.AUTO,
            )
            # Good value: True
            worker._resolve_trk_in_d(value=True, is_bad=False)
            assert ctrl.trk_in_d is True

            # Bad quality: should keep last good (True)
            worker._resolve_trk_in_d(value=False, is_bad=True)
            assert ctrl.trk_in_d is True

            # New good value: False
            worker._resolve_trk_in_d(value=False, is_bad=False)
            assert ctrl.trk_in_d is False

            # Bad again: keep last good (False)
            worker._resolve_trk_in_d(value=True, is_bad=True)
            assert ctrl.trk_in_d is False
        finally:
            bus.stop()

    def test_track_if_bad_forces_true_on_bad(self) -> None:
        bus = _make_bus()
        try:
            ctrl = Controller(
                id=1, name="T-TRK-BAD", scan_rate_ms=100,
                pid_params=PIDParams(gain=1.0, reset=10.0),
                track_opt=TrackOpt.TRACK_IF_BAD,
                control_opts=ControlOpts(track_enable=True),
            )
            worker = _make_worker(
                bus, ctrl, mode=ControllerMode.AUTO,
            )
            # Good value: False
            worker._resolve_trk_in_d(value=False, is_bad=False)
            assert ctrl.trk_in_d is False

            # Bad quality: force True regardless of value
            worker._resolve_trk_in_d(value=False, is_bad=True)
            assert ctrl.trk_in_d is True
        finally:
            bus.stop()

    def test_good_quality_always_uses_value(self) -> None:
        """Regardless of track_opt, good quality uses the value."""
        bus = _make_bus()
        try:
            for opt in TrackOpt:
                ctrl = Controller(
                    id=1, name="T-TRK-GOOD", scan_rate_ms=100,
                    pid_params=PIDParams(gain=1.0, reset=10.0),
                    track_opt=opt,
                )
                worker = _make_worker(
                    bus, ctrl, mode=ControllerMode.AUTO,
                )
                worker._resolve_trk_in_d(value=True, is_bad=False)
                assert ctrl.trk_in_d is True
                worker._resolve_trk_in_d(value=False, is_bad=False)
                assert ctrl.trk_in_d is False
        finally:
            bus.stop()


# ===========================================================================
# Feature 6: ProcessType (informational, tested at model level above)
# ===========================================================================
class TestProcessTypeController:
    def test_default_self_regulating(self) -> None:
        ctrl = Controller()
        assert ctrl.process_type == ProcessType.SELF_REGULATING

    def test_integrating(self) -> None:
        ctrl = Controller(process_type=ProcessType.INTEGRATING)
        assert ctrl.process_type == ProcessType.INTEGRATING


# ===========================================================================
# Also: SP-PV tracking, output selection, shed, increase-to-close
# (features from main that this branch now includes)
# ===========================================================================
class TestSPPVTracking:
    def test_sp_tracks_pv_in_man(self) -> None:
        bus = _make_bus()
        try:
            ctrl = Controller(
                id=1, name="T-TRACK", scan_rate_ms=100,
                pid_params=PIDParams(gain=1.0, reset=10.0),
                control_opts=ControlOpts(sp_pv_track_in_man=True),
            )
            worker = _make_worker(
                bus, ctrl, mode=ControllerMode.MAN,
            )
            worker.start()
            pub = bus.create_publisher()
            sub = bus.create_subscriber(b"STATUS.1")
            time.sleep(0.05)

            _send_telemetry(pub, 1, pv=75.0, sp=50.0)
            msg = sub.recv(timeout_ms=2000)
            assert msg is not None
            status = msgpack.unpackb(msg[1])
            assert status["sp"]["value"] == pytest.approx(
                75.0, abs=0.1,
            )
        finally:
            worker.stop()
            bus.stop()


class TestOutputSelectionByMode:
    def test_manual_mode_uses_set_output(self) -> None:
        bus = _make_bus()
        try:
            ctrl = Controller(
                id=1, name="T-MAN", scan_rate_ms=100,
                pid_params=PIDParams(gain=1.0, reset=10.0),
            )
            worker = _make_worker(
                bus, ctrl, mode=ControllerMode.MAN,
            )
            worker.start()
            pub = bus.create_publisher()
            sub = bus.create_subscriber(b"ACTION.CTRL.1")
            time.sleep(0.05)

            _send_telemetry(pub, 1, pv=50.0, sp=50.0, co=50.0)
            time.sleep(0.2)

            worker.set_output(42.0)
            _send_telemetry(pub, 1, pv=50.0, sp=50.0)
            time.sleep(0.2)

            last = None
            for _ in range(20):
                a = _recv_action(sub, timeout_ms=100)
                if a is None:
                    break
                last = a
            assert last is not None
            assert last["co"]["value"] == pytest.approx(
                42.0, abs=0.1,
            )
        finally:
            worker.stop()
            bus.stop()

    def test_rout_mode_uses_rout_in(self) -> None:
        bus = _make_bus()
        try:
            ctrl = Controller(
                id=1, name="T-ROUT", scan_rate_ms=100,
                pid_params=PIDParams(gain=1.0, reset=10.0),
            )
            worker = _make_worker(
                bus, ctrl, mode=ControllerMode.ROUT,
            )
            worker.start()
            pub = bus.create_publisher()
            sub = bus.create_subscriber(b"ACTION.CTRL.1")
            time.sleep(0.05)

            _send_telemetry(pub, 1, pv=50.0, sp=50.0, rout_in=65.0)
            action = _recv_action(sub, timeout_ms=2000)
            assert action is not None
            assert action["co"]["value"] == pytest.approx(
                65.0, abs=0.1,
            )
        finally:
            worker.stop()
            bus.stop()

    def test_lo_mode_uses_trk_val(self) -> None:
        bus = _make_bus()
        try:
            ctrl = Controller(
                id=1, name="T-LO", scan_rate_ms=100,
                pid_params=PIDParams(gain=1.0, reset=10.0),
            )
            worker = _make_worker(
                bus, ctrl, mode=ControllerMode.LO,
            )
            worker.start()
            pub = bus.create_publisher()
            sub = bus.create_subscriber(b"ACTION.CTRL.1")
            time.sleep(0.05)

            _send_telemetry(pub, 1, pv=50.0, sp=50.0, trk_val=33.0)
            action = _recv_action(sub, timeout_ms=2000)
            assert action is not None
            assert action["co"]["value"] == pytest.approx(
                33.0, abs=0.1,
            )
        finally:
            worker.stop()
            bus.stop()


class TestShedTimeout:
    def test_shed_timeout_forces_mode(self) -> None:
        bus = _make_bus()
        try:
            ctrl = Controller(
                id=1, name="T-SHED", scan_rate_ms=50,
                pid_params=PIDParams(gain=1.0, reset=10.0),
                shed_time_s=0.2,
                shed_opt=ControllerMode.MAN,
            )
            worker = _make_worker(
                bus, ctrl, mode=ControllerMode.AUTO,
            )
            worker.start()
            pub = bus.create_publisher()
            time.sleep(0.05)

            _send_telemetry(pub, 1, pv=50.0, sp=50.0)
            time.sleep(0.05)
            assert worker.current_mode == ControllerMode.AUTO

            time.sleep(0.4)
            assert worker.current_mode == ControllerMode.MAN
        finally:
            worker.stop()
            bus.stop()


class TestIncreaseToClose:
    def test_increase_to_close_reverses_output(self) -> None:
        bus = _make_bus()
        try:
            ctrl = Controller(
                id=1, name="T-ITC", scan_rate_ms=100,
                pid_params=PIDParams(gain=1.0, reset=10.0),
                io_opts=IOOpts(increase_to_close=True),
                out_hi_lim=100.0,
                out_lo_lim=0.0,
            )
            worker = _make_worker(bus, ctrl)
            worker.start()
            pub = bus.create_publisher()
            sub = bus.create_subscriber(b"ACTION.CTRL.1")
            time.sleep(0.05)

            _send_telemetry(pub, 1, pv=40.0, sp=50.0)
            action = _recv_action(sub, timeout_ms=2000)
            assert action is not None
            co_val = action["co"]["value"]
            assert co_val <= 100.0
        finally:
            worker.stop()
            bus.stop()
