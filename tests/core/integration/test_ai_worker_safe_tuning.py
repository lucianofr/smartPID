"""Safe-tuning guardrails on the online integral adjustment.

Two total-skip conditions, both evaluated once per AI cycle:

* the PLC's ``PID_[MALHA]_ENABLED`` tag (``TagBindings.node_id_enabled``,
  delivered on TELEMETRY as ``pid_enabled``) reads 0 — the process this loop
  drives is stopped;
* ``|PV - SP|`` is inside the loop's stability band, i.e. the loop is at
  steady state, where moving Ki/Ti buys nothing and arms an overshoot on the
  next setpoint step.

Either one skips the whole cycle: no ACTION.AI, no Ki/Ti move. Kp and Kd are
never touched by this worker in the first place.
"""
from __future__ import annotations

import json
import logging
import time
import uuid

import msgpack
import pytest

from smart_pid_core.application.event_bus import EventBus
from smart_pid_core.application.workers.ai_worker import AIWorker
from smart_pid_domain.enums import AIEngine, ControlObjective, ProcessSpeed
from smart_pid_domain.models.controller import AIConfig, Controller, ScaleConfig

_AI_WORKER_LOGGER = "smart_pid_core.application.workers.ai_worker"
_TEST_AI_PERIOD = 0.2
# Comfortably outside every band used here (SP=50 -> 30 % error).
_MOVING_PV = 35.0
_SP = 50.0


@pytest.fixture
def bus():
    b = EventBus(url_prefix=f"inproc://test_safe_tuning_{uuid.uuid4().hex[:8]}")
    b.start()
    yield b
    b.stop()


def _controller(
    stability_band_pct: float | None = None,
    objective: ControlObjective = ControlObjective.SP_TRACKING,
) -> Controller:
    return Controller(
        id=1,
        name="FIC-301",
        scan_rate_s=0.1,
        process_speed=ProcessSpeed.MEDIUM,
        pv_scale=ScaleConfig(eu_min=0.0, eu_max=100.0),
        stability_band_pct=stability_band_pct,
        ai_config=AIConfig(
            engine=AIEngine.FUZZY,
            objective=objective,
            dead_time_l=0.1,
            limit_min=0.1,
            limit_max=100.0,
        ),
    )


def _feed(pub, cid: int, *, pv: float, sp: float = _SP, pid_enabled=None) -> None:
    """Publish one TELEMETRY frame shaped like the one IOWorker emits."""
    frame: dict = {"pv": pv, "sp": sp, "co": 48.0, "mode": "AUTO"}
    if pid_enabled is not None:
        frame["pid_enabled"] = pid_enabled
    pub.send(f"TELEMETRY.{cid}".encode(), msgpack.packb(frame))


def _drain(sub, budget_ms: int = 300) -> list[dict]:
    """Collect every ACTION.AI still queued."""
    actions = []
    while True:
        msg = sub.recv(timeout_ms=budget_ms)
        if msg is None:
            return actions
        actions.append(msgpack.unpackb(msg[1]))
        budget_ms = 50


def _skip_reasons(caplog) -> list[str]:
    """Reasons from every ``optimizer_skip`` line, in order."""
    reasons = []
    for record in caplog.records:
        message = record.getMessage()
        if not message.startswith("optimizer_skip "):
            continue
        payload = json.loads(message[len("optimizer_skip "):])
        assert payload["malha"] == 1
        assert payload["timestamp"]
        reasons.append(payload["reason"])
    return reasons


class TestProcessRunningGate:
    """Stop condition 1: PID_ENABLED=0 skips every cycle."""

    def test_five_cycles_skipped_while_the_plc_reports_stopped(self, bus, caplog):
        worker = AIWorker(bus=bus, controller=_controller())
        worker._ai_period_s = _TEST_AI_PERIOD
        worker.start()
        try:
            pub = bus.create_publisher()
            sub = bus.create_subscriber(b"ACTION.AI.1")
            time.sleep(0.05)
            with caplog.at_level(logging.INFO, logger=_AI_WORKER_LOGGER):
                deadline = time.monotonic() + _TEST_AI_PERIOD * 6
                while time.monotonic() < deadline:
                    # PV far off SP: only the enabled gate can be skipping.
                    _feed(pub, 1, pv=_MOVING_PV, pid_enabled=False)
                    time.sleep(0.05)
                reasons = _skip_reasons(caplog)

            assert _drain(sub) == [], "a stopped process must never be tuned"
            assert reasons.count("enabled") >= 5, (
                f"expected >=5 'enabled' skips, got {reasons}"
            )
            assert set(reasons) == {"enabled"}
        finally:
            worker.stop()

    def test_an_unmapped_tag_does_not_gate(self, bus):
        """No PID_[MALHA]_ENABLED tag means unknown, not stopped."""
        worker = AIWorker(bus=bus, controller=_controller())
        worker._ai_period_s = _TEST_AI_PERIOD
        worker.start()
        try:
            pub = bus.create_publisher()
            sub = bus.create_subscriber(b"ACTION.AI.1")
            time.sleep(0.05)
            for _ in range(5):
                _feed(pub, 1, pv=_MOVING_PV)  # no pid_enabled key at all
                time.sleep(0.05)
            time.sleep(_TEST_AI_PERIOD + 0.3)
            assert _drain(sub), "an unmapped tag must leave the optimizer running"
        finally:
            worker.stop()

    def test_runtime_toggle_resumes_on_the_next_cycle(self, bus):
        """Stop condition 3: 0 -> 1 resumes optimization."""
        worker = AIWorker(bus=bus, controller=_controller())
        worker._ai_period_s = _TEST_AI_PERIOD
        worker.start()
        try:
            pub = bus.create_publisher()
            sub = bus.create_subscriber(b"ACTION.AI.1")
            time.sleep(0.05)

            deadline = time.monotonic() + _TEST_AI_PERIOD * 3
            while time.monotonic() < deadline:
                _feed(pub, 1, pv=_MOVING_PV, pid_enabled=False)
                time.sleep(0.05)
            assert _drain(sub) == [], "must stay skipped while stopped"

            deadline = time.monotonic() + _TEST_AI_PERIOD * 3
            while time.monotonic() < deadline:
                _feed(pub, 1, pv=_MOVING_PV, pid_enabled=True)
                time.sleep(0.05)
            assert _drain(sub), "must resume as soon as the PLC reports running"
        finally:
            worker.stop()


class TestStabilityBand:
    """Stop condition 2: steady state leaves the integral term alone."""

    def test_ten_cycles_at_setpoint_leave_ki_untouched(self, bus, caplog):
        controller = _controller()
        worker = AIWorker(bus=bus, controller=controller, initial_ki=12.5)
        worker._ai_period_s = _TEST_AI_PERIOD
        worker.start()
        try:
            pub = bus.create_publisher()
            sub = bus.create_subscriber(b"ACTION.AI.1")
            time.sleep(0.05)
            with caplog.at_level(logging.INFO, logger=_AI_WORKER_LOGGER):
                deadline = time.monotonic() + _TEST_AI_PERIOD * 11
                while time.monotonic() < deadline:
                    # 0.5 EU off a SP of 50 = 1 %, inside the 2 % default.
                    _feed(pub, 1, pv=_SP - 0.5, pid_enabled=True)
                    time.sleep(0.05)
                reasons = _skip_reasons(caplog)

            assert _drain(sub) == [], "steady state must not produce a tuning write"
            assert worker._ki_current == 12.5, "Ki/Ti must not move at steady state"
            assert reasons.count("stability_band") >= 10, (
                f"expected >=10 'stability_band' skips, got {reasons}"
            )
        finally:
            worker.stop()

    def test_leaving_the_band_resumes_optimization(self, bus):
        worker = AIWorker(bus=bus, controller=_controller())
        worker._ai_period_s = _TEST_AI_PERIOD
        worker.start()
        try:
            pub = bus.create_publisher()
            sub = bus.create_subscriber(b"ACTION.AI.1")
            time.sleep(0.05)
            deadline = time.monotonic() + _TEST_AI_PERIOD * 3
            while time.monotonic() < deadline:
                _feed(pub, 1, pv=_MOVING_PV, pid_enabled=True)
                time.sleep(0.05)
            assert _drain(sub), "an out-of-band error must be optimized"
        finally:
            worker.stop()


class TestBandResolution:
    """Stop condition 4: a per-loop band overrides the daemon-wide one."""

    @pytest.mark.parametrize(
        ("loop_band", "global_band", "expected"),
        [
            (None, 5.0, 5.0),   # inherits the global
            (0.5, 5.0, 0.5),    # loop override wins
            (None, 2.0, 2.0),   # documented default
        ],
    )
    def test_effective_band(self, bus, loop_band, global_band, expected):
        worker = AIWorker(
            bus=bus,
            controller=_controller(stability_band_pct=loop_band),
            stability_band_pct=global_band,
        )
        assert worker._stability_band_pct == expected

    def test_global_five_percent_and_loop_half_percent_both_hold(self, bus):
        """The same 2 EU error is inside one loop's band and outside the other's."""
        inherited = AIWorker(
            bus=bus, controller=_controller(), stability_band_pct=5.0,
        )
        overridden = AIWorker(
            bus=bus, controller=_controller(stability_band_pct=0.5),
            stability_band_pct=5.0,
        )
        for worker in (inherited, overridden):
            worker._last_sp = _SP
            worker._last_pv = _SP - 2.0  # 4 % of SP

        # 4 % < 5 % -> at rest;  4 % > 0.5 % -> still moving.
        assert inherited._optimization_skip_reason() == "stability_band"
        assert overridden._optimization_skip_reason() is None

    def test_the_enabled_gate_outranks_the_band(self, bus):
        worker = AIWorker(bus=bus, controller=_controller())
        worker._last_sp, worker._last_pv = _SP, _MOVING_PV
        worker._pid_enabled = False
        assert worker._optimization_skip_reason() == "enabled"


class TestOvershootReopensTheBand:
    """A SP step that overshot is tuning information, and it is gone by the
    time the band reopens: AI cadence is 3xTSS, so the loop has re-settled
    long before the next cycle fires. Without a bypass the evidence sitting
    in the stats window is never consumed.
    """

    @staticmethod
    def _at_setpoint(worker):
        worker._last_sp, worker._last_pv = _SP, _SP - 0.5  # 1 %, inside 2 %
        return worker

    def test_a_recorded_overshoot_reopens_an_otherwise_closed_band(self, bus):
        worker = self._at_setpoint(AIWorker(bus=bus, controller=_controller()))
        assert worker._optimization_skip_reason() == "stability_band"
        worker._latest_stats = {"overshoot": 0.30}
        assert worker._optimization_skip_reason() is None

    def test_a_negligible_overshoot_leaves_the_band_closed(self, bus):
        worker = self._at_setpoint(AIWorker(bus=bus, controller=_controller()))
        worker._latest_stats = {"overshoot": 0.02}
        assert worker._optimization_skip_reason() == "stability_band"

    def test_the_enabled_gate_still_outranks_the_bypass(self, bus):
        worker = self._at_setpoint(AIWorker(bus=bus, controller=_controller()))
        worker._latest_stats = {"overshoot": 0.30}
        worker._pid_enabled = False
        assert worker._optimization_skip_reason() == "enabled"

    def test_other_objectives_keep_todays_behaviour(self, bus):
        """The bypass is SP-tracking only: no other strategy consumes the
        overshoot indicator, so for them it is not evidence of anything."""
        worker = self._at_setpoint(AIWorker(
            bus=bus,
            controller=_controller(
                objective=ControlObjective.DISTURBANCE_REJECTION,
            ),
        ))
        worker._latest_stats = {"overshoot": 0.30}
        assert worker._optimization_skip_reason() == "stability_band"

    def test_the_cycle_actually_tunes_while_pv_sits_at_setpoint(self, bus):
        worker = AIWorker(bus=bus, controller=_controller(), initial_ki=12.5)
        worker._ai_period_s = _TEST_AI_PERIOD
        worker._latest_stats = {
            "overshoot": 0.30, "sample_count": 200, "osc_sample_count": 200,
        }
        worker.start()
        try:
            pub = bus.create_publisher()
            sub = bus.create_subscriber(b"ACTION.AI.1")
            time.sleep(0.05)
            deadline = time.monotonic() + _TEST_AI_PERIOD * 3
            while time.monotonic() < deadline:
                _feed(pub, 1, pv=_SP - 0.5, pid_enabled=True)
                time.sleep(0.05)
            actions = _drain(sub)
            assert actions, "a recorded overshoot must be tuned at setpoint"
            assert actions[0]["new_ki"] > 12.5, (
                f"Ti must be raised against an overshoot: {actions[0]}"
            )
        finally:
            worker.stop()
