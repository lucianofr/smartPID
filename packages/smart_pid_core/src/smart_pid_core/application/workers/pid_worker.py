"""PID Worker — high-priority daemon thread executing PID at the controller's scan rate."""
from __future__ import annotations

import contextlib
import dataclasses
import logging
import threading
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import msgpack
import zmq

from smart_pid_core.domain.services.pid_engine import PIDState
from smart_pid_core.domain.services.pid_mode_manager import BlockStatus
from smart_pid_domain.enums import (
    ControllerMode,
    ExecutionMode,
    InitSubStatus,
    LimitBits,
    SignalSeverity,
    TrackOpt,
)
from smart_pid_domain.models.controller import StatusOpts
from smart_pid_domain.models.signal import FFSignal, FFSignalStatus

if TYPE_CHECKING:
    from smart_pid_core.application.event_bus import (
        BusPublisher,
        BusSubscriber,
        EventBus,
    )
    from smart_pid_core.domain.services.pid_engine import PIDEngine
    from smart_pid_core.domain.services.pid_mode_manager import ModeManager
    from smart_pid_domain.models.controller import Controller


logger = logging.getLogger(__name__)


def _evaluate_pv_quality(signal: FFSignal, opts: StatusOpts) -> FFSignal:
    """Apply STATUS_OPTS rules to interpret signal quality.

    - If bad_if_limited and signal has any limit bits set -> treat as BAD severity
    - If use_uncertain_as_good and severity is UNCERTAIN -> treat as GOOD
    """
    severity = signal.status.severity
    limit_bits = signal.status.limit_bits

    needs_change = False

    # bad_if_limited: treat LIMITED as BAD
    if opts.bad_if_limited and limit_bits != LimitBits.NONE:
        severity = SignalSeverity.BAD
        needs_change = True

    # use_uncertain_as_good: treat UNCERTAIN as GOOD (but NOT BAD -> GOOD)
    if (
        opts.use_uncertain_as_good
        and severity == SignalSeverity.UNCERTAIN
    ):
        severity = SignalSeverity.GOOD
        needs_change = True

    if not needs_change:
        return signal

    return FFSignal(
        value=signal.value,
        status=FFSignalStatus(
            severity=severity,
            limit_bits=signal.status.limit_bits,
            sub_status=signal.status.sub_status,
        ),
        timestamp=signal.timestamp,
    )


def _deserialize_ff_signal(data: dict | float | int) -> FFSignal:
    """Deserialize an FFSignal from msgpack data.

    Backward compatible: plain float/int is wrapped as FFSignal.good(value).
    """
    if isinstance(data, (float, int)):
        return FFSignal.good(float(data))
    return FFSignal(
        value=float(data.get("value", 0.0)),
        status=FFSignalStatus(
            severity=SignalSeverity(data.get("severity", "GOOD")),
            limit_bits=LimitBits(data.get("limit_bits", "NONE")),
            sub_status=InitSubStatus(data.get("sub_status", "NONE")),
        ),
        timestamp=None,
    )


def _serialize_ff_signal(signal: FFSignal) -> dict:
    """Serialize an FFSignal to a msgpack-compatible dict."""
    return {
        "value": signal.value,
        "severity": signal.status.severity.value,
        "limit_bits": signal.status.limit_bits.value,
        "sub_status": signal.status.sub_status.value,
    }


class PIDWorker:
    def __init__(
        self,
        bus: EventBus,
        controller: Controller,
        engine: PIDEngine,
        mode_manager: ModeManager,
    ) -> None:
        self._bus = bus
        self._controller = controller
        self._engine = engine
        self._mode_manager = mode_manager
        self._state = PIDState()
        self._mode = ControllerMode.MAN
        self._block_status = BlockStatus()
        self._last_pv: FFSignal = FFSignal.good(0.0)
        self._last_sp: FFSignal = FFSignal.good(0.0)
        self._last_co: FFSignal = FFSignal.good(0.0)
        self._last_bkcal_in: FFSignal = FFSignal.good(0.0)
        self._last_bkcal_out: FFSignal = FFSignal.good(0.0)
        self._last_cas_in: FFSignal = FFSignal.good(0.0)
        self._last_rcas_in: FFSignal = FFSignal.good(0.0)
        self._last_rout_in: float = 0.0
        self._last_trk_val: float = 0.0
        self._simulate_pv: float | None = None
        self._last_good_trk_in_d: bool = False
        # SP_WRK: the rate-limited setpoint the PID actually chases while
        # sp_rate_up/sp_rate_dn are non-zero. None outside the closed-loop
        # modes, so re-entering AUTO ramps from the SP in force then instead
        # of a stale value captured before the operator went to MAN.
        self._sp_working: float | None = None
        # Mode reported by the monitored controller (SUPERVISORY only). None
        # until a telemetry frame carries one; self._mode is SmartPID's own
        # mode and is not the same fact.
        self._dcs_mode: str | None = None
        # Live PID tuning read from the monitored controller (SUPERVISORY): the
        # DCS/simulator owns kp/ti/td, so STATUS must report what io_worker read
        # back over OPC-UA, not this controller's stored config. None until a
        # telemetry frame carries params; falls back to config below.
        self._last_kp: float | None = None
        self._last_ti: float | None = None
        self._last_td: float | None = None
        self._has_telemetry = False
        self._last_telem_time: float = 0.0
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def controller_id(self) -> int:
        return self._controller.id

    @property
    def simulate_active(self) -> bool:
        return self._simulate_pv is not None

    def set_simulate_pv(self, value: float) -> None:
        """Activate simulation mode with a test PV value."""
        with self._lock:
            self._simulate_pv = value
            self._block_status.simulate_active = True

    def clear_simulate(self) -> None:
        """Deactivate simulation mode, revert to real PV."""
        with self._lock:
            self._simulate_pv = None
            self._block_status.simulate_active = False

    def start(self) -> None:
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run, daemon=True, name=f"pid-worker-{self.controller_id}"
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5.0)
            self._thread = None

    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def current_mode(self) -> ControllerMode:
        return self._mode

    def set_mode(self, mode: ControllerMode) -> None:
        with self._lock:
            self._mode = mode

    def set_sp(self, value: float) -> None:
        with self._lock:
            self._last_sp = FFSignal.good(value)

    def set_output(self, value: float) -> None:
        with self._lock:
            self._last_co = FFSignal.good(value)

    def update_controller(self, controller: Controller) -> None:
        """Swap the live config so a persisted edit takes effect on the next
        scan without a restart. The run loop reads ``self._controller.*`` every
        scan (execution_mode, limits, PID structure, control/IO options), so a
        reference swap is all it takes. ``scan_rate_s`` is cached at thread
        start and still needs a loop restart to change the cadence."""
        with self._lock:
            self._controller = controller

    def _resolve_trk_in_d(self, value: bool, is_bad: bool) -> None:
        """Apply TRACK_OPT rules to resolve TRK_IN_D discrete input."""
        track_opt = self._controller.track_opt

        if not is_bad:
            # Good quality: always use the value
            self._controller.trk_in_d = value
            self._last_good_trk_in_d = value
            return

        # Bad quality: apply track_opt
        if track_opt == TrackOpt.ALWAYS_USE_VALUE:
            self._controller.trk_in_d = value
        elif track_opt == TrackOpt.USE_LAST_GOOD:
            self._controller.trk_in_d = self._last_good_trk_in_d
        elif track_opt == TrackOpt.TRACK_IF_BAD:
            self._controller.trk_in_d = True

    def _run(self) -> None:
        telem_sub = self._bus.create_subscriber(
            f"TELEMETRY.{self.controller_id}".encode(),
        )
        ai_sub = self._bus.create_subscriber(
            f"ACTION.AI.{self.controller_id}".encode(),
        )
        reconnect_sub = self._bus.create_subscriber(
            f"SYS.RECONNECT.{self.controller_id}".encode(),
        )
        pub = self._bus.create_publisher()
        scan_s = self._controller.scan_rate_s
        time.sleep(0.02)

        try:
            self._loop(telem_sub, ai_sub, reconnect_sub, pub, scan_s)
        finally:
            # ZMQ sockets are not thread-safe and must be closed by the thread
            # that created them. Without this the context still holds four live
            # sockets per loop at shutdown, and EventBus.stop()'s ctx.destroy()
            # blocks in zmq_ctx_term() (or races into a segfault) closing them
            # cross-thread. Same reason StatsWorker/AIWorker close theirs.
            for sock in (telem_sub, ai_sub, reconnect_sub, pub):
                with contextlib.suppress(Exception):
                    sock.close()

    def _loop(
        self,
        telem_sub: BusSubscriber,
        ai_sub: BusSubscriber,
        reconnect_sub: BusSubscriber,
        pub: BusPublisher,
        scan_s: float,
    ) -> None:
        """Run the control loop until stopped. Socket lifetime is _run's job."""
        while not self._stop_event.is_set():
            try:
                tick_start = time.monotonic()
                self._drain_reconnect(reconnect_sub)
                self._drain_telemetry(telem_sub)
                self._drain_ai_actions(ai_sub)

                delta_cv = 0.0
                sp_ramping = False

                # Shed timeout detection
                if self._has_telemetry and self._controller.shed_time_s > 0:
                    elapsed_since_telem = (
                        time.monotonic() - self._last_telem_time
                    )
                    if elapsed_since_telem > self._controller.shed_time_s:
                        self._block_status.shed_timeout_expired = True
                    else:
                        self._block_status.shed_timeout_expired = False

                # Evaluate forced transitions
                forced = self._mode_manager.evaluate_forced_transitions(
                    current=self._mode,
                    block_status=self._block_status,
                    shed_mode=self._controller.shed_opt,
                )
                if forced is not None and forced != self._mode:
                    self._mode = forced
                    if forced in {
                        ControllerMode.AUTO,
                        ControllerMode.CAS,
                        ControllerMode.RCAS,
                    }:
                        self._state = self._engine.bumpless_transfer(
                            state=self._state,
                            current_pv=self._last_pv.value,
                            current_co=self._last_co.value,
                            params=self._controller.pid_params,
                        )

                # Evaluate cascade handshake
                cascade_action = (
                    self._mode_manager.evaluate_cascade_handshake(
                        current_mode=self._mode,
                        bkcal_in=self._last_bkcal_in,
                    )
                )
                if cascade_action.force_mode is not None:
                    self._mode = cascade_action.force_mode
                    if cascade_action.requires_bumpless:
                        self._state = self._engine.bumpless_transfer(
                            state=self._state,
                            current_pv=self._last_pv.value,
                            current_co=self._last_bkcal_in.value,
                            params=self._controller.pid_params,
                        )

                if self._has_telemetry:
                    # Apply STATUS_OPTS to PV signal
                    effective_pv = _evaluate_pv_quality(
                        self._last_pv, self._controller.status_opts,
                    )

                    # If simulate active, override PV value
                    if self._simulate_pv is not None:
                        effective_pv = FFSignal.good(self._simulate_pv)

                    # SP-PV tracking in certain modes
                    effective_sp = self._last_sp
                    ctrl_opts = self._controller.control_opts
                    if (
                        self._mode == ControllerMode.MAN
                        and ctrl_opts.sp_pv_track_in_man
                    ) or (
                        self._mode
                        in {ControllerMode.LO, ControllerMode.IMAN}
                        and ctrl_opts.sp_pv_track_in_lo_or_iman
                    ):
                        effective_sp = FFSignal.good(effective_pv.value)
                        self._last_sp = effective_sp

                    # CAS/RCAS SP override
                    if self._mode == ControllerMode.CAS:
                        effective_sp = FFSignal.good(
                            self._last_cas_in.value,
                        )
                        self._last_sp = effective_sp
                    elif self._mode == ControllerMode.RCAS:
                        effective_sp = FFSignal.good(
                            self._last_rcas_in.value,
                        )
                        self._last_sp = effective_sp

                    # SP rate limiting (SP_WRK). Only the closed-loop modes:
                    # MAN/LO/IMAN force SP to PV, and BYPASS passes SP to the
                    # output, so ramping either would rewrite a value that is
                    # not a setpoint. `_last_sp` deliberately keeps the TARGET
                    # -- feeding the ramped value back as the next target
                    # collapses the ramp to one scan.
                    if self._mode in {
                        ControllerMode.AUTO,
                        ControllerMode.CAS,
                        ControllerMode.RCAS,
                    }:
                        sp_target = effective_sp.value
                        working = self._engine.apply_sp_ramp(
                            sp_target=sp_target,
                            sp_current=(
                                self._sp_working
                                if self._sp_working is not None
                                else sp_target
                            ),
                            rate_up=self._controller.sp_rate_up,
                            rate_dn=self._controller.sp_rate_dn,
                            dt=scan_s,
                        )
                        self._sp_working = working
                        # apply_sp_ramp returns sp_target exactly once the ramp
                        # arrives, so equality is the arrival test -- no epsilon.
                        sp_ramping = working != sp_target
                        if sp_ramping:
                            effective_sp = dataclasses.replace(
                                effective_sp, value=working,
                            )
                    else:
                        self._sp_working = None

                    # Mode-dependent output computation
                    if (
                        self._mode == ControllerMode.IMAN
                        and cascade_action.tracking_target is not None
                    ):
                        result = self._engine.compute_iman_tracking(
                            state=self._state,
                            pv=effective_pv,
                            sp=effective_sp,
                            bkcal_in=self._last_bkcal_in,
                            direct_acting=(
                                self._controller.control_opts.direct_acting
                            ),
                        )
                        self._state = result.new_state
                        self._last_co = result.bkcal_out
                        self._last_bkcal_out = result.bkcal_out
                        delta_cv = result.delta_cv
                    elif self._mode in {
                        ControllerMode.AUTO,
                        ControllerMode.CAS,
                        ControllerMode.RCAS,
                    }:
                        params = self._controller.pid_params
                        out_limits = (
                            self._controller.out_lo_lim,
                            self._controller.out_hi_lim,
                        )
                        arw_limits = (
                            self._controller.arw_lo_lim,
                            self._controller.arw_hi_lim,
                        )
                        direct_acting = (
                            self._controller.control_opts.direct_acting
                        )
                        result = self._engine.compute(
                            params=params,
                            state=self._state,
                            pv=effective_pv,
                            sp=effective_sp,
                            bkcal_in=self._last_bkcal_in,
                            dt=scan_s,
                            out_limits=out_limits,
                            direct_acting=direct_acting,
                            arw_limits=arw_limits,
                        )
                        self._state = result.new_state
                        co_val = result.cv
                        # Increase-to-close: reverse output
                        if self._controller.io_opts.increase_to_close:
                            hi = self._controller.out_hi_lim
                            lo = self._controller.out_lo_lim
                            co_val = hi + lo - co_val
                        self._last_co = FFSignal.good(co_val)
                        self._last_bkcal_out = result.bkcal_out
                        delta_cv = result.delta_cv
                    elif self._mode == ControllerMode.MAN:
                        # In MAN: output held at _last_co (set by
                        # set_output), PID state tracks for bumpless
                        self._state = self._engine.bumpless_transfer(
                            state=self._state,
                            current_pv=effective_pv.value,
                            current_co=self._last_co.value,
                            params=self._controller.pid_params,
                        )
                    elif self._mode == ControllerMode.ROUT:
                        # ROUT: output from remote (rout_in)
                        co_val = max(
                            self._controller.out_lo_lim,
                            min(
                                self._last_rout_in,
                                self._controller.out_hi_lim,
                            ),
                        )
                        self._last_co = FFSignal.good(co_val)
                        self._state = self._engine.bumpless_transfer(
                            state=self._state,
                            current_pv=effective_pv.value,
                            current_co=co_val,
                            params=self._controller.pid_params,
                        )
                    elif self._mode == ControllerMode.LO:
                        # LO: output from track value
                        co_val = max(
                            self._controller.out_lo_lim,
                            min(
                                self._last_trk_val,
                                self._controller.out_hi_lim,
                            ),
                        )
                        self._last_co = FFSignal.good(co_val)
                        self._state = self._engine.bumpless_transfer(
                            state=self._state,
                            current_pv=effective_pv.value,
                            current_co=co_val,
                            params=self._controller.pid_params,
                        )
                    elif self._mode == ControllerMode.BYPASS:
                        # BYPASS: SP goes directly to output (clamped)
                        co_val = max(
                            self._controller.out_lo_lim,
                            min(
                                effective_sp.value,
                                self._controller.out_hi_lim,
                            ),
                        )
                        self._last_co = FFSignal.good(co_val)
                        self._state = self._engine.bumpless_transfer(
                            state=self._state,
                            current_pv=effective_pv.value,
                            current_co=co_val,
                            params=self._controller.pid_params,
                        )

                    # Publish control action
                    action_data = {
                        "controller_id": self.controller_id,
                        "co": _serialize_ff_signal(self._last_co),
                        "bkcal_out": _serialize_ff_signal(
                            self._last_bkcal_out,
                        ),
                        "integral_val": self._state.cv,
                        "delta_cv": delta_cv,
                        # The IO worker writes CO to the DCS for DDC loops only:
                        # in SUPERVISORY the DCS owns the PID and writing CO
                        # would fight its controller.
                        "execution_mode": str(self._controller.execution_mode),
                        "timestamp": datetime.now(tz=UTC).isoformat(),
                    }
                    topic = (
                        f"ACTION.CTRL.{self.controller_id}".encode()
                    )
                    pub.send(topic, msgpack.packb(action_data))

                if self._has_telemetry:
                    params = self._controller.pid_params
                    # SUPERVISORY: the DCS/simulator owns the PID, so report the
                    # tuning read back over OPC-UA (falling back to config until
                    # the first params frame). DDC: SmartPID owns tuning, report
                    # its config.
                    supervisory = (
                        self._controller.execution_mode is ExecutionMode.SUPERVISORY
                    )
                    kp_out = (
                        self._last_kp if supervisory and self._last_kp is not None else params.gain
                    )
                    ti_out = (
                        self._last_ti if supervisory and self._last_ti is not None else params.reset
                    )
                    td_out = (
                        self._last_td if supervisory and self._last_td is not None else params.rate
                    )
                    telem_data = {
                        "controller_id": self.controller_id,
                        "pv": _serialize_ff_signal(self._last_pv),
                        "sp": _serialize_ff_signal(self._last_sp),
                        "co": _serialize_ff_signal(self._last_co),
                        "bkcal_in": _serialize_ff_signal(
                            self._last_bkcal_in,
                        ),
                        "bkcal_out": _serialize_ff_signal(
                            self._last_bkcal_out,
                        ),
                        # In SUPERVISORY the DCS runs the loop, so the mode the
                        # operator needs to see is *its* mode, not PIDWorker's
                        # internal one (which defaults to MAN and only moves on
                        # a REST set_mode). Falls back to the internal mode when
                        # the producer supplies none. DDC keeps reporting the
                        # internal mode — there SmartPID owns the loop.
                        "mode": (
                            self._dcs_mode
                            if (
                                self._controller.execution_mode
                                is ExecutionMode.SUPERVISORY
                                and self._dcs_mode is not None
                            )
                            else self._mode.value
                        ),
                        "kp": kp_out,
                        "ti": ti_out,
                        "td": td_out,
                        "integral_val": self._state.cv,
                        # Consumed by AlarmWorker: deviation alarms are
                        # suppressed while the SP is still travelling, because
                        # the PV-SP gap during a ramp is expected, not a fault.
                        "sp_ramping": sp_ramping,
                        "timestamp": datetime.now(tz=UTC).isoformat(),
                    }
                    pub.send(
                        f"STATUS.{self.controller_id}".encode(),
                        msgpack.packb(telem_data),
                    )

                elapsed = time.monotonic() - tick_start
                sleep_time = scan_s - elapsed
                if sleep_time > 0:
                    self._stop_event.wait(timeout=sleep_time)
            except zmq.ZMQError:
                break
            except Exception:
                # Never let a transient error kill the worker thread silently —
                # log and keep looping so PID output keeps getting computed.
                # (matches ai_worker.py/db_worker.py/io_worker.py's _run loops;
                # this one was the sole outlier with no broad-exception guard,
                # so a NaN PV / bad config / corrupt frame died the control
                # thread with no alarm while the daemon kept reporting healthy.)
                logger.exception(
                    "pid_worker_iteration_error controller_id=%d",
                    self.controller_id,
                )
                # The normal per-tick sleep lives at the end of the try block,
                # so a fault raised before it would spin this thread flat-out
                # at 100% CPU. Pace the retry at the scan rate instead.
                self._stop_event.wait(timeout=scan_s)

    def _drain_telemetry(self, sub) -> None:  # noqa: ANN001
        while True:
            msg = sub.recv(timeout_ms=0)
            if msg is None:
                break
            _topic, payload = msg
            try:
                data = msgpack.unpackb(payload)
                self._last_pv = _deserialize_ff_signal(data["pv"])
                # SP ownership mirrors CO below: in DDC SmartPID owns the
                # setpoint (the operator writes it), so telemetry may only SEED
                # it — otherwise every scan clobbers the operator's value with
                # the PLC's stale SP node and the loop regulates to the wrong
                # target. In SUPERVISORY the DCS owns SP, so each frame wins.
                if (
                    self._controller.execution_mode is not ExecutionMode.DDC
                    or not self._has_telemetry
                ):
                    self._last_sp = _deserialize_ff_signal(data["sp"])
                if "bkcal_in" in data:
                    self._last_bkcal_in = _deserialize_ff_signal(
                        data["bkcal_in"],
                    )
                if "cas_in" in data:
                    self._last_cas_in = _deserialize_ff_signal(
                        data["cas_in"],
                    )
                if "rcas_in" in data:
                    self._last_rcas_in = _deserialize_ff_signal(
                        data["rcas_in"],
                    )
                if "rout_in" in data:
                    val = data["rout_in"]
                    self._last_rout_in = (
                        float(val)
                        if isinstance(val, (float, int))
                        else float(val.get("value", 0.0))
                    )
                if "trk_val" in data:
                    val = data["trk_val"]
                    self._last_trk_val = (
                        float(val)
                        if isinstance(val, (float, int))
                        else float(val.get("value", 0.0))
                    )
                # CO ownership mirrors SP above. In DDC SmartPID computes CO
                # and owns it, so telemetry may only SEED it. In SUPERVISORY
                # the DCS's controller owns CO, which makes the telemetry
                # value a *measurement* of its output — no different in kind
                # from PV measuring the process — so each frame wins and the
                # source's quality propagates.
                #
                # Seeding-only was the bug: CO was read from the first frame
                # and never refreshed. At startup the twin's output is 0.0, and
                # MAN (the default mode, :112) is the one branch below that
                # never reassigns _last_co, so STATUS.co published a GOOD 0.0
                # forever while the twin's valve moved. integral_val died with
                # it — MAN's bumpless_transfer seeds state.cv from _last_co.
                if (
                    self._controller.execution_mode is not ExecutionMode.DDC
                    or not self._has_telemetry
                ):
                    self._last_co = _deserialize_ff_signal(
                        data.get("co", 0.0),
                    )
                # The monitored controller's own mode, for SUPERVISORY status
                # reporting. Absent for producers that do not supply it, in
                # which case the publisher falls back to self._mode.
                if "mode" in data:
                    self._dcs_mode = str(data["mode"])
                # PID tuning read back from the DCS/simulator over OPC-UA
                # (io_worker merges these into telemetry). Kept so SUPERVISORY
                # STATUS reports the loop's real live tuning, not stored config.
                if data.get("kp") is not None:
                    self._last_kp = float(data["kp"])
                if data.get("ti") is not None:
                    self._last_ti = float(data["ti"])
                if data.get("td") is not None:
                    self._last_td = float(data["td"])
                self._has_telemetry = True
                self._last_telem_time = time.monotonic()
            except (KeyError, ValueError, msgpack.UnpackException):
                pass

    def _drain_reconnect(self, sub) -> None:  # noqa: ANN001
        """Drain SYS.RECONNECT messages and perform bumpless transfer."""
        while True:
            msg = sub.recv(timeout_ms=0)
            if msg is None:
                break
            _topic, payload = msg
            try:
                data = msgpack.unpackb(payload)
                co = float(data.get("co", 0.0))
                pv = float(data.get("pv", 0.0))
                self._state = self._engine.bumpless_transfer(
                    state=self._state,
                    current_pv=pv,
                    current_co=co,
                    params=self._controller.pid_params,
                )
            except (KeyError, ValueError, msgpack.UnpackException):
                pass

    def _drain_ai_actions(self, sub) -> None:  # noqa: ANN001
        """Adopt an optimizer Ti/Ki suggestion — only when it is authorised.

        ``apply`` is the loop's auto-apply gate (``tuning_write_mode``).
        AIWorker publishes every suggestion so the HMI can display it; a
        DDC loop must only adopt one when the operator has switched
        auto-apply on. Absent key = older publisher = do not write.
        """
        while True:
            msg = sub.recv(timeout_ms=0)
            if msg is None:
                break
            _topic, payload = msg
            try:
                data = msgpack.unpackb(payload)
                if not data.get("apply", False):
                    continue
                new_ki = data.get("new_ki")
                if new_ki is not None:
                    with self._lock:
                        self._controller.pid_params = (
                            dataclasses.replace(
                                self._controller.pid_params,
                                reset=float(new_ki),
                            )
                        )
            except (KeyError, ValueError, msgpack.UnpackException):
                pass
