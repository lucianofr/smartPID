"""Fuzzy engine V2 — three control-objective strategies + dispatcher.

A dispatcher (:class:`FuzzyEngineV2Dispatcher`) wraps the three engines
behind a single ``update_sample(error_frac, pv_frac, co_frac)`` and
``compute_adjustment(...)`` interface, routing to the correct engine
based on the loop's configured :class:`ControlObjective`. Callers give
it all three signals on every scan; each engine internally consumes only
what its strategy needs.

Three fuzzy tuners built on a shared Mamdani min-max + singleton-CoG core,
each with its own input indicators, MFs, and rule base matching the
physical reasoning of the objective:

1. **SP Tracking** (``FuzzyEngineV2``) — IAE, 2σ/span, TV.
   Focus: area under the error curve. Offset → reduce Ti; oscillation →
   increase Ti; excess valve effort → increase Ti.

2. **Disturbance Rejection** (``FuzzyEngineV2DisturbanceRejection``) —
   event-triggered. Indicators: peak error, recovery time (in τ), residual
   oscillation. Focus: survival and recovery, not shape.

3. **Surge Level / Averaging Control** (``FuzzyEngineV2SurgeLevel``) —
   continuous. Indicators: distance from tank centre, valve TV, margin rate
   toward limit. Focus: suppress valve motion; only defend against tank
   overflow/dry-up in emergency.

All three produce an ``AIDecisionV2`` with ``delta_ti`` applied as
``Ti_new = Ti_old × (1 + Δ_Ti)``.
"""
from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass
from typing import Union

from smart_pid_domain.enums import ControlObjective

# ---------------------------------------------------------------------------
# Shared primitives
# ---------------------------------------------------------------------------


def triangular_mf(x: float, a: float, b: float, c: float) -> float:
    if x < a or x > c:
        return 0.0
    if a == b == c:
        return 1.0 if x == a else 0.0
    if x <= b:
        return (x - a) / (b - a) if b != a else 1.0
    return (c - x) / (c - b) if c != b else 1.0


def trapezoidal_mf(
    x: float, a: float, b: float, c: float, d: float,
) -> float:
    if x < a or x > d:
        return 0.0
    if x <= b:
        return (x - a) / (b - a) if b != a else 1.0
    if x <= c:
        return 1.0
    return (d - x) / (d - c) if d != c else 1.0


MFSet = dict[str, tuple[str, tuple[float, ...]]]
Rule = tuple[dict[str, str], str]


def _fuzzify(value: float, mfs: MFSet) -> dict[str, float]:
    out: dict[str, float] = {}
    for name, (kind, params) in mfs.items():
        if kind == "trap":
            out[name] = trapezoidal_mf(value, *params)
        else:
            out[name] = triangular_mf(value, *params)
    return out


def _run_rules(
    input_mfs: dict[str, dict[str, float]],
    rules: list[Rule],
    output_centers: dict[str, float],
) -> tuple[float, dict[str, float]]:
    """Mamdani min-max aggregation with singleton Centre-of-Gravity defuzz.

    Unknown keys in a rule condition (i.e. keys absent from ``input_mfs``)
    are silently skipped so the same helper works across strategies with
    different input sets.
    """
    output_strengths: dict[str, float] = {lvl: 0.0 for lvl in output_centers}
    for condition, out_lvl in rules:
        strength = 1.0
        for key, level in condition.items():
            if key not in input_mfs:
                continue
            strength = min(strength, input_mfs[key].get(level, 0.0))
        output_strengths[out_lvl] = max(output_strengths[out_lvl], strength)
    numerator = sum(
        output_centers[lvl] * s for lvl, s in output_strengths.items()
    )
    denominator = sum(output_strengths.values())
    delta = 0.0 if denominator < 1e-10 else numerator / denominator
    return delta, output_strengths


@dataclass(frozen=True)
class AIDecisionV2:
    delta_ti: float                            # [-1.0, +1.5] depending on strategy
    new_ti: float
    inputs: dict[str, float]                   # strategy-specific indicator values
    reasoning: str
    membership_values: dict[str, dict[str, float]]


# ===========================================================================
# Strategy 1 — SP Tracking
# ===========================================================================

MF_IAE: MFSet = {
    "LOW":  ("trap", (0.0, 0.0, 0.2, 0.4)),
    "MED":  ("tri",  (0.3, 0.5, 0.7)),
    "HIGH": ("trap", (0.6, 0.8, 1.0, 1.0)),
}

MF_OSC: MFSet = {
    "STABLE":   ("trap", (0.0, 0.0, 0.2, 0.35)),
    "OSC":      ("tri",  (0.3, 0.5, 0.7)),
    "UNSTABLE": ("trap", (0.6, 0.8, 1.0, 1.0)),
}

MF_EFF: MFSet = {
    "SMOOTH":   ("trap", (0.0, 0.0, 0.2, 0.4)),
    "MODERATE": ("tri",  (0.3, 0.6, 0.8)),
    "EXCESS":   ("trap", (0.7, 0.9, 1.0, 1.0)),
}

OUTPUT_CENTERS: dict[str, float] = {
    "RM": -0.35, "R": -0.15, "M": 0.0, "A": +0.15, "AM": +0.35,
}

RULES: list[Rule] = [
    # R1: persistent offset with calm valve → integrator lazy
    ({"iae": "HIGH", "osc": "STABLE", "eff": "SMOOTH"}, "R"),
    ({"iae": "HIGH", "osc": "STABLE", "eff": "MODERATE"}, "R"),
    # R1': offset with calm osc + excessive effort → response too slow
    ({"iae": "HIGH", "osc": "STABLE", "eff": "EXCESS"}, "RM"),
    # R2: limit cycle territory
    ({"iae": "HIGH", "osc": "UNSTABLE"}, "AM"),
    ({"iae": "MED",  "osc": "UNSTABLE"}, "AM"),
    ({"iae": "LOW",  "osc": "UNSTABLE"}, "A"),
    # R3: nervous loop (oscillating + chattering valve) → slow down integrator
    ({"osc": "OSC", "eff": "EXCESS"}, "A"),
    ({"iae": "LOW", "osc": "OSC", "eff": "MODERATE"}, "A"),
    # R3': sustained PV oscillation with calm valve. Classical tuning says
    # oscillation → more damping, so increase Ti regardless of valve state.
    ({"iae": "LOW",  "osc": "OSC", "eff": "SMOOTH"}, "A"),
    ({"iae": "MED",  "osc": "OSC", "eff": "SMOOTH"}, "A"),
    ({"iae": "HIGH", "osc": "OSC", "eff": "SMOOTH"}, "AM"),
    # R4: acceptable compromise
    ({"iae": "MED", "osc": "OSC", "eff": "MODERATE"}, "M"),
    # R5: settled
    ({"iae": "LOW", "osc": "STABLE"}, "M"),
    # R6: moderate offset, mild oscillation → gentle reduce
    ({"iae": "MED", "osc": "STABLE", "eff": "SMOOTH"}, "R"),
    ({"iae": "MED", "osc": "STABLE", "eff": "MODERATE"}, "R"),
]


class FuzzyEngineV2:
    """SP Tracking tuner: IAE + 2σ/span + TV → Δ_Ti."""

    _DEFAULT_WINDOW = 20
    _DEADBAND = 0.02
    _IAE_FULL_SCALE = 0.20
    _TV_FULL_SCALE  = 0.10
    # Peak-to-peak of error / span at which the amplitude factor saturates.
    # A sustained oscillation with pk-pk ≥ 15% of span reads as UNSTABLE.
    _OSC_PKPK_FULL_SCALE = 0.15
    # Δerror below this magnitude is ignored when counting direction
    # reversals — keeps quantisation noise from inflating the freq factor.
    _OSC_REVERSAL_NOISE_THR = 0.005

    def __init__(self, window_samples: int | None = None) -> None:
        n = window_samples if window_samples is not None else self._DEFAULT_WINDOW
        self._window_samples = max(4, int(n))
        self._errors: deque[float] = deque(maxlen=self._window_samples)
        self._cos:    deque[float] = deque(maxlen=self._window_samples)

    def _iae_norm(self) -> float:
        if not self._errors:
            return 0.0
        mean_abs = sum(abs(e) for e in self._errors) / len(self._errors)
        return min(1.0, mean_abs / self._IAE_FULL_SCALE)

    def _osc_stats(self) -> tuple[float, float, int]:
        """Return (osc_norm, pk_pk, reversals).

        A sustained oscillation is characterised by non-trivial
        peak-to-peak amplitude *and* at least a couple of direction
        reversals in the window. We report amp_norm (pk-pk / span)
        gated by a minimum reversal count so a monotonic ramp or a
        single SP-change spike does not register as oscillation.
        """
        n = len(self._errors)
        if n < 4:
            return 0.0, 0.0, 0
        errs = list(self._errors)

        pk_pk = max(errs) - min(errs)
        amp_norm = min(1.0, pk_pk / self._OSC_PKPK_FULL_SCALE)

        reversals = 0
        last_dir = 0
        for i in range(1, n):
            d = errs[i] - errs[i - 1]
            if abs(d) < self._OSC_REVERSAL_NOISE_THR:
                continue
            cur_dir = 1 if d > 0 else -1
            if last_dir != 0 and cur_dir != last_dir:
                reversals += 1
            last_dir = cur_dir

        # Need ≥ 2 reversals (one full half-cycle, peak & valley) before
        # attributing amplitude to oscillation. Otherwise it is a ramp or
        # an isolated spike.
        osc = amp_norm if reversals >= 2 else 0.0
        return osc, pk_pk, reversals

    def _osc_norm(self) -> float:
        return self._osc_stats()[0]

    def _eff_norm(self) -> float:
        n = len(self._cos)
        if n < 2:
            return 0.0
        tv = sum(abs(self._cos[i] - self._cos[i - 1]) for i in range(1, n))
        tv_per_sample = tv / (n - 1)
        return min(1.0, tv_per_sample / self._TV_FULL_SCALE)

    def update_sample(self, error_frac: float, co_frac: float) -> None:
        e = error_frac if abs(error_frac) > self._DEADBAND else 0.0
        self._errors.append(e)
        self._cos.append(co_frac)

    def infer(
        self, iae: float, osc: float, eff: float,
    ) -> tuple[float, dict[str, dict[str, float]]]:
        input_mfs = {
            "iae": _fuzzify(iae, MF_IAE),
            "osc": _fuzzify(osc, MF_OSC),
            "eff": _fuzzify(eff, MF_EFF),
        }
        delta, output_strengths = _run_rules(input_mfs, RULES, OUTPUT_CENTERS)
        delta = max(-0.5, min(0.5, delta))
        return delta, {**input_mfs, "output": output_strengths}

    def compute_adjustment(
        self, ti_current: float, limit_min: float, limit_max: float,
    ) -> AIDecisionV2:
        """Legacy path: infer from the internal sample window.

        Production code uses :meth:`compute_adjustment_from_stats`; this
        method is kept so unit tests can drive the engine sample-by-sample
        without standing up a StatsWorker.
        """
        iae = self._iae_norm()
        osc, pk_pk, reversals = self._osc_stats()
        eff = self._eff_norm()
        return self._build_decision(
            iae, osc, eff, pk_pk, reversals, len(self._errors),
            ti_current, limit_min, limit_max,
        )

    def compute_adjustment_from_stats(
        self,
        stats: dict,
        span: float,
        ti_current: float,
        limit_min: float,
        limit_max: float,
    ) -> AIDecisionV2:
        """Production path: infer from a StatsCalculator snapshot.

        ``stats`` must carry the raw metrics published by StatsWorker:
        ``mean_abs_error``, ``pk_pk_error``, ``reversals``,
        ``tv_per_sample`` and ``sample_count``. This avoids maintaining a
        second rolling window inside the engine.
        """
        mean_abs = float(stats.get("mean_abs_error", 0.0))
        # OSC has to discriminate four scenarios:
        #   1. Sustained oscillation around SP — must flag.
        #   2. Loop just stabilised (stale swings in the full window) —
        #      must NOT flag.
        #   3. SP-step transient (error stays on one side until PV
        #      catches up) — must NOT flag.
        #   4. Pure drift / ramp — must NOT flag.
        #
        # Signals used:
        #   - recent_pk_pk_error  → amplitude (rejects #2; stays high in #1)
        #   - zero_crossings      → primary oscillation confirmation: true
        #                           oscillation crosses SP every half cycle;
        #                           SP-step transients give ≤ 1 crossing
        #                           (rejects #3)
        #   - reversals (full)    → shape check that the amplitude came from
        #                           repeated direction changes, not a single
        #                           ramp (rejects #4)
        # Fall back to legacy fields if recent/zero_crossings are missing.
        pk_pk_raw = float(stats.get(
            "recent_pk_pk_error", stats.get("pk_pk_error", 0.0),
        ))
        reversals = int(stats.get("reversals", 0))
        zero_crossings = int(stats.get("zero_crossings", reversals))
        tv_per = float(stats.get("tv_per_sample", 0.0))
        n = int(stats.get("sample_count", 0))

        iae = min(1.0, (mean_abs / span if span > 0 else 0.0) / self._IAE_FULL_SCALE)
        pk_pk_frac = (pk_pk_raw / span) if span > 0 else 0.0
        amp_norm = min(1.0, pk_pk_frac / self._OSC_PKPK_FULL_SCALE)
        osc = amp_norm if (zero_crossings >= 2 and reversals >= 2) else 0.0
        # TV is published in raw CO units (0..100). Normalise to fraction.
        eff = min(1.0, (tv_per / 100.0) / self._TV_FULL_SCALE)
        return self._build_decision(
            iae, osc, eff, pk_pk_frac, reversals, n,
            ti_current, limit_min, limit_max,
            zero_crossings=zero_crossings,
        )

    def _build_decision(
        self,
        iae: float,
        osc: float,
        eff: float,
        pk_pk: float,
        reversals: int,
        n: int,
        ti_current: float,
        limit_min: float,
        limit_max: float,
        zero_crossings: int | None = None,
    ) -> AIDecisionV2:
        delta_ti, mfs = self.infer(iae, osc, eff)
        new_ti = max(limit_min, min(limit_max, ti_current * (1.0 + delta_ti)))
        inputs = {"IAE": iae, "OSC": osc, "EFF": eff,
                  "pk_pk": pk_pk, "reversals": reversals, "window": n}
        if zero_crossings is not None:
            inputs["zero_crossings"] = zero_crossings
        zc_str = f" zc={zero_crossings}" if zero_crossings is not None else ""
        return AIDecisionV2(
            delta_ti=delta_ti,
            new_ti=new_ti,
            inputs=inputs,
            reasoning=(
                f"FuzzyV2[SP]: IAE={iae:.2f} OSC={osc:.2f} "
                f"(pkpk={pk_pk:.2f} rev={reversals}/{n}{zc_str}) "
                f"EFF={eff:.2f} Δ_Ti={delta_ti:+.3f} "
                f"Ti: {ti_current:.4f} → {new_ti:.4f}"
            ),
            membership_values=mfs,
        )


# ===========================================================================
# Strategy 2 — Disturbance Rejection
# ===========================================================================

# Right-edge trapezoids extend their plateau (c=d) to a very large value
# so any input past the upper shoulder stays fully-belonging — "very slow"
# is still SLOW, "very big" is still HIGH. A finite shoulder would drop
# membership back to 0 past the plateau and silence the rule base
# exactly when the indicator is most severe (e.g. T_rec=13τ producing
# Δ_Ti=0 in a real limit-cycle).
_RIGHT_SAT = 1.0e9

MF_E_MAX_DR: MFSet = {
    "LOW":  ("trap", (0.0, 0.0, 0.3, 0.5)),
    "MED":  ("tri",  (0.3, 0.6, 0.9)),
    "HIGH": ("trap", (0.7, 1.0, _RIGHT_SAT, _RIGHT_SAT)),
}

MF_T_REC_DR: MFSet = {
    "FAST": ("trap", (0.0, 0.0, 1.5, 3.0)),
    "MED":  ("tri",  (2.0, 4.0, 6.0)),
    "SLOW": ("trap", (5.0, 7.0, _RIGHT_SAT, _RIGHT_SAT)),
}

MF_OSC_DR: MFSet = {
    "STABLE": ("trap", (0.0, 0.0, 0.15, 0.3)),
    "MED":    ("tri",  (0.2, 0.4, 0.6)),
    "HIGH":   ("trap", (0.5, 0.75, _RIGHT_SAT, _RIGHT_SAT)),
}

# Asymmetric output centres: reducing Ti is high-risk (a single overshoot
# destabilises a stable loop), increasing Ti is low-risk (only costs speed).
# The reducing legs (RM/R) are capped so that two consecutive reductions
# can't out-pace a single AM/A damping correction — without this the engine
# "hunts": converges to a stable Ti, then a slow-recovery event fires R1
# and unwinds the hard-won gain in three AI cycles.
OUTPUT_CENTERS_DR: dict[str, float] = {
    "RM": -0.10, "R": -0.05, "M": 0.0, "A": +0.15, "AM": +0.40,
}

RULES_DR: list[Rule] = [
    # R1: slow recovery on a perfectly stable loop is NOT a call to reduce
    # Ti. A conservative loop may take a long time to reject a disturbance
    # without ever oscillating — that is not a bug, it is a safety margin.
    # Reducing Ti here just grinds the loop toward the edge of stability
    # and the user loses the margin. Only reduce Ti when SOME oscillation
    # is present (R1' rule, OSC=MED below). Pure STABLE ⇒ hold.
    ({"e_max": "HIGH", "t_rec": "SLOW", "osc": "STABLE"}, "M"),
    ({"e_max": "HIGH", "t_rec": "SLOW", "osc": "MED"},    "R"),
    ({"e_max": "MED",  "t_rec": "SLOW", "osc": "STABLE"}, "M"),
    # R2: disturbance rejected fast but generated instability — smooth it
    ({"e_max": "LOW",  "t_rec": "FAST", "osc": "HIGH"}, "AM"),
    ({"e_max": "MED",  "t_rec": "FAST", "osc": "HIGH"},  "A"),
    # R3: big impact but optimal recovery — physics, accept it
    ({"e_max": "HIGH", "t_rec": "FAST", "osc": "MED"},    "M"),
    ({"e_max": "HIGH", "t_rec": "FAST", "osc": "STABLE"}, "M"),
    # R4: moderate everything but slow — slight push (still has OSC=MED).
    ({"e_max": "MED", "t_rec": "MED", "osc": "MED"}, "R"),
    # R5: residual oscillation alone — damp it
    ({"osc": "HIGH"}, "A"),
    # R6: everything settled — hold
    ({"e_max": "LOW", "t_rec": "FAST", "osc": "STABLE"}, "M"),
]


class FuzzyEngineV2DisturbanceRejection:
    """Event-triggered tuner for disturbance rejection.

    State machine over the error-magnitude signal:
      IDLE     : |e| ≤ deadband. No tracking.
      ACTIVE   : |e| > deadband. Accumulate peak and count samples.
      SETTLING : |e| ≤ deadband for _EVENT_EXIT_DWELL consecutive samples.
                 Collect post-event errors for residual-oscillation metric.
      DONE     : SETTLING window full → compute decision inputs, flag ready,
                 return to IDLE.

    ``compute_adjustment`` returns Δ_Ti=0 (hold) until a decision is ready
    from a completed event; at that point it consumes the stored inputs and
    returns the computed adjustment.
    """

    _EVENT_TRIGGER = 0.02           # |e/span| above → start event
    _EVENT_EXIT_DWELL = 3           # samples in-band to end the event
    _DEFAULT_POST_EVENT_WINDOW = 15 # default residual-oscillation window
    _OSC_FULL_SCALE = 0.50          # same 2σ/span normalisation as SP
    # Sustained-oscillation escape: a true disturbance event recovers within
    # a few τ. If we are ACTIVE for longer than this *and* the error keeps
    # crossing zero, the loop is in a limit cycle, not rejecting a
    # transient. Force-finalise so the rules can prescribe damping (Ti up).
    _OSC_LOCK_TAU_THRESHOLD = 3.0   # ACTIVE for ≥ 3τ → candidate for limit cycle
    _OSC_LOCK_MIN_CROSSINGS = 2     # plus this many zero crossings → confirm
    # A transient disturbance has 0 crossings (error ramps up and back on the
    # same side of SP). Even one full half-cycle of oscillation already crosses
    # zero twice, so ≥ 2 is the tightest threshold that still safely rejects
    # lone recovery transients.
    # After a limit-cycle firing the loop sits on the edge of stability:
    # Ti was just raised because oscillation was detected. Allowing the event
    # path to immediately prescribe a reduction (e.g. rule R1 firing on the
    # first slow disturbance after damping) can tip the loop back into
    # oscillation. This cooldown suppresses reductions for N AI cycles
    # after every limit-cycle firing. N=5 is generous: at 3·TSS cadence it
    # covers ~15·TSS of observation before allowing any retreat.
    _LIMIT_CYCLE_COOLDOWN_CYCLES = 5

    def __init__(
        self,
        tau_estimate_sec: float = 10.0,
        e_max_norm_full: float = 0.05,
        dt_sec: float = 1.0,
        window_samples: int | None = None,
    ) -> None:
        self._tau = tau_estimate_sec
        self._e_max_full = e_max_norm_full
        self._dt = dt_sec
        n = window_samples if window_samples is not None else self._DEFAULT_POST_EVENT_WINDOW
        self._post_event_window = max(4, int(n))
        self._state: str = "IDLE"
        self._e_max_observed: float = 0.0
        self._event_sample_count: int = 0
        self._in_band_samples: int = 0
        self._post_errors: list[float] = []
        self._decision_inputs: tuple[float, float, float] | None = None
        self._decision_source: str = "event"  # "event" or "limit_cycle"
        # AI cycles still remaining in the post-LC cooldown (see class const).
        self._cooldown_remaining: int = 0
        # Limit-cycle detection: track all errors seen during ACTIVE plus the
        # number of sign changes (zero crossings) of the error signal.
        self._active_errors: list[float] = []
        self._active_zero_crossings: int = 0
        self._active_last_sign: int = 0

    # ---- state transitions ----------------------------------------------

    def update_sample(self, error_frac: float) -> None:
        abs_e = abs(error_frac)
        if self._state == "IDLE":
            if abs_e > self._EVENT_TRIGGER:
                self._state = "ACTIVE"
                self._e_max_observed = abs_e
                self._event_sample_count = 1
                self._in_band_samples = 0
                self._active_errors = [error_frac]
                self._active_zero_crossings = 0
                self._active_last_sign = 1 if error_frac > 0 else (
                    -1 if error_frac < 0 else 0
                )
            return

        if self._state == "ACTIVE":
            self._event_sample_count += 1
            if abs_e > self._e_max_observed:
                self._e_max_observed = abs_e
            self._active_errors.append(error_frac)
            cur_sign = 1 if error_frac > 0 else (-1 if error_frac < 0 else 0)
            if (
                cur_sign != 0
                and self._active_last_sign != 0
                and cur_sign != self._active_last_sign
            ):
                self._active_zero_crossings += 1
            if cur_sign != 0:
                self._active_last_sign = cur_sign
            if abs_e <= self._EVENT_TRIGGER:
                self._in_band_samples += 1
                if self._in_band_samples >= self._EVENT_EXIT_DWELL:
                    self._state = "SETTLING"
                    self._post_errors = [error_frac]
            else:
                self._in_band_samples = 0
            # Limit-cycle escape: if we have been ACTIVE long enough and the
            # error keeps crossing zero, this is not a transient disturbance
            # — finalise as an oscillation event so the rule base can damp it.
            if self._is_limit_cycle():
                self._finalise_oscillation()
            return

        if self._state == "SETTLING":
            self._post_errors.append(error_frac)
            if len(self._post_errors) >= self._post_event_window:
                self._finalise_event()

    # OSC threshold above which a finalised event is indistinguishable from a
    # limit-cycle half-cycle and we must default to damping. Matches the onset
    # of MED membership in MF_OSC_DR so any measurable residual oscillation
    # reroutes to the limit-cycle path.
    _EVENT_OSC_LIMIT_CYCLE_THR = 0.3

    # Minimum sign-changes of error during ACTIVE that qualify as
    # "recovery overshoot". An ideal recovery asymptotes to SP with 0
    # sign changes; a recovery that crosses SP and settles on the other
    # side has exactly 1. Ringing recoveries have ≥ 2. Even a single
    # overshoot is a tell-tale "Ti too small" signal that the post-event
    # σ usually misses (the ringing has decayed by the time SETTLING
    # starts sampling). Redirect those events to damping.
    _EVENT_OVERSHOOT_MIN_CROSSINGS = 1

    def _finalise_event(self) -> None:
        # Overshoot detection runs FIRST: if the error crossed zero at
        # least once during ACTIVE the controller overshot on recovery —
        # integral wound up and pushed PV past SP. That is a "Ti too
        # small" symptom regardless of how calm the post-event window
        # looks, so redirect to the limit-cycle path (Ti up) rather than
        # letting the rule base see a "slow recovery, stable residual"
        # and hold (R1 → M).
        if self._active_zero_crossings >= self._EVENT_OVERSHOOT_MIN_CROSSINGS:
            self._finalise_oscillation()
            return
        t_rec_sec = self._event_sample_count * self._dt
        t_rec_norm = t_rec_sec / self._tau
        e_max_norm = min(1.5, self._e_max_observed / self._e_max_full)
        n = len(self._post_errors)
        mean = sum(self._post_errors) / n
        variance = sum((e - mean) ** 2 for e in self._post_errors) / n
        sigma = math.sqrt(variance)
        osc_norm = min(1.0, (2.0 * sigma) / self._OSC_FULL_SCALE)
        # If residual oscillation is non-trivial, the event is likely a
        # limit-cycle half-cycle mis-classified as a recovery. The normal
        # rule base (e.g. HIGH/SLOW/MED → R) would then REDUCE Ti and
        # feed the oscillation. Redirect to the limit-cycle finalisation
        # so the prescription is damping (Ti up), not more action.
        if osc_norm >= self._EVENT_OSC_LIMIT_CYCLE_THR:
            self._finalise_oscillation()
            return
        self._decision_inputs = (e_max_norm, t_rec_norm, osc_norm)
        self._decision_source = "event"
        self._reset_event_state()

    def _is_limit_cycle(self) -> bool:
        """ACTIVE for ≥ 5τ with repeated zero crossings → sustained oscillation."""
        min_samples = max(
            int(self._OSC_LOCK_TAU_THRESHOLD * self._tau / self._dt), 4,
        )
        return (
            self._event_sample_count >= min_samples
            and self._active_zero_crossings >= self._OSC_LOCK_MIN_CROSSINGS
        )

    def _finalise_oscillation(self) -> None:
        """Force-finalise a limit-cycle event without waiting for SETTLING.

        A limit cycle is *not* a transient disturbance event, so feeding the
        observed e_max/t_rec into the rule base mis-fires R1' (HIGH/SLOW/MED
        → R) which prescribes a *more* aggressive Ti — exactly the wrong
        direction. Instead, present the rule base with the physical truth
        of a limit cycle: there is no transient excursion to track
        (e_max=LOW, t_rec=FAST), only a residual oscillation that must be
        damped (osc=HIGH). This matches rule R2 cleanly → AM (+0.4) plus
        R5 (osc:HIGH → A, +0.15), giving an unambiguous Ti-up decision
        of ~+0.275 per AI cycle, strong enough to escape within a handful
        of cycles.
        """
        self._decision_inputs = (0.0, 0.0, 1.0)
        self._decision_source = "limit_cycle"
        self._reset_event_state()

    def _reset_event_state(self) -> None:
        """Reset all per-event tracking back to IDLE."""
        self._state = "IDLE"
        self._e_max_observed = 0.0
        self._event_sample_count = 0
        self._in_band_samples = 0
        self._post_errors = []
        self._active_errors = []
        self._active_zero_crossings = 0
        self._active_last_sign = 0

    @property
    def state(self) -> str:
        return self._state

    @property
    def decision_ready(self) -> bool:
        return self._decision_inputs is not None

    # ---- inference ------------------------------------------------------

    def infer(
        self, e_max: float, t_rec: float, osc: float,
    ) -> tuple[float, dict[str, dict[str, float]]]:
        input_mfs = {
            "e_max": _fuzzify(e_max, MF_E_MAX_DR),
            "t_rec": _fuzzify(t_rec, MF_T_REC_DR),
            "osc":   _fuzzify(osc,   MF_OSC_DR),
        }
        delta, output_strengths = _run_rules(
            input_mfs, RULES_DR, OUTPUT_CENTERS_DR,
        )
        delta = max(-0.5, min(0.5, delta))
        return delta, {**input_mfs, "output": output_strengths}

    # Rolling-window OSC expressed as the normalised peak-to-peak error over
    # the stats window, full-scale at 15 % of span. Same amplitude term as
    # SP_TRACKING, but DR overrides the whole decision tuple when this fires
    # so the gate is stricter: we must distinguish "single big disturbance
    # still in the window" from a true sustained oscillation.
    _OSC_PKPK_FULL_SCALE = 0.15
    # Sustained-oscillation gate constants
    _OSC_MIN_ZERO_CROSSINGS = 4   # ≥ 2 full half-cycles in the window
    _OSC_MIN_REVERSALS      = 4   # ≥ 2 full direction changes
    # For a pure sinusoid mean_abs/pk_pk ≈ 0.318. A narrow spike on a quiet
    # baseline gives ratios ≪ 0.1. 0.20 cleanly separates the two regimes.
    _OSC_MIN_MEAN_ABS_RATIO = 0.20

    def _osc_from_stats(self, stats: dict, span: float) -> float:
        """Compute stats-based OSC with a sustained-oscillation gate.

        Returns the normalised pk_pk amplitude only when **all** of the
        following hold:

        - ``zero_crossings >= _OSC_MIN_ZERO_CROSSINGS``
        - ``reversals     >= _OSC_MIN_REVERSALS``
        - ``mean_abs_error / pk_pk_error >= _OSC_MIN_MEAN_ABS_RATIO``

        The first two gates reject single transients (a disturbance that
        dips and recovers has at most 2 zero crossings). The ratio test
        rejects an isolated big excursion still lingering in the window:
        a sinusoid has mean_abs/pk_pk ≈ 0.32; a spike on a quiet baseline
        is far below that. Without this test, a single step disturbance
        with a slight overshoot on recovery (zc=2, rev=2, tiny mean_abs)
        fires the limit-cycle override and Ti runs up to the guardrail.
        """
        if span <= 0.0:
            return 0.0
        pk_pk_raw = float(stats.get(
            "recent_pk_pk_error", stats.get("pk_pk_error", 0.0),
        ))
        reversals = int(stats.get("reversals", 0))
        zero_crossings = int(stats.get("zero_crossings", reversals))
        mean_abs = float(stats.get("mean_abs_error", 0.0))
        if zero_crossings < self._OSC_MIN_ZERO_CROSSINGS:
            return 0.0
        if reversals < self._OSC_MIN_REVERSALS:
            return 0.0
        if pk_pk_raw > 0.0 and (mean_abs / pk_pk_raw) < self._OSC_MIN_MEAN_ABS_RATIO:
            return 0.0
        return min(1.0, (pk_pk_raw / span) / self._OSC_PKPK_FULL_SCALE)

    def compute_adjustment_from_stats(
        self,
        stats: dict,
        span: float,
        ti_current: float,
        limit_min: float,
        limit_max: float,
    ) -> AIDecisionV2:
        """Stats-driven path modelled on SP_TRACKING.

        DR's original event-path OSC (2σ over 15 post-event samples)
        systematically undersamples real oscillations — the user's log
        reported OSC=0.18 while the StatsWorker saw pkpk=46 % span / zc=10
        / reversals=9 (OSC=1.0). When the rolling metric confirms
        oscillation (OSC ≥ onset of MED), override the pending decision
        inputs with limit-cycle semantics so the rule base fires damping
        (AM + A) instead of reducing Ti via a spurious "slow recovery"
        classification.
        """
        stats_osc = self._osc_from_stats(stats, span)
        if stats_osc >= self._EVENT_OSC_LIMIT_CYCLE_THR:
            # Oscillation confirmed by rolling stats — feed the rule base
            # limit-cycle inputs (LOW / FAST / stats_osc). Reset any
            # ACTIVE event state so the next sample window starts clean.
            self._decision_inputs = (0.0, 0.0, stats_osc)
            self._decision_source = "limit_cycle"
            self._reset_event_state()
        # Fall through to the normal decision path (honours cooldown,
        # consumes any pending event, returns hold if nothing to say).
        return self.compute_adjustment(ti_current, limit_min, limit_max)

    def compute_adjustment(
        self, ti_current: float, limit_min: float, limit_max: float,
    ) -> AIDecisionV2:
        # Eager limit-cycle check at query time. Waiting for the time-based
        # threshold in update_sample (3τ at default τ=10 s) means most AI
        # cycles return "holding" even while the loop is clearly oscillating
        # — the operator sees many Δ_Ti=0 log entries and Ti barely moves.
        # If we're still ACTIVE but already have enough zero crossings,
        # emit a damping decision now so every AI cycle makes progress.
        if (
            self._decision_inputs is None
            and self._state == "ACTIVE"
            and self._active_zero_crossings >= self._OSC_LOCK_MIN_CROSSINGS
        ):
            self._finalise_oscillation()
        if self._decision_inputs is None:
            # Even on a hold, drain cooldown so it eventually expires.
            self._cooldown_remaining = max(0, self._cooldown_remaining - 1)
            return AIDecisionV2(
                delta_ti=0.0,
                new_ti=ti_current,
                inputs={},
                reasoning=f"FuzzyV2[DR]: holding (state={self._state})",
                membership_values={},
            )
        e_max, t_rec, osc = self._decision_inputs
        source = self._decision_source
        self._decision_inputs = None  # consume
        self._decision_source = "event"
        delta_ti, mfs = self.infer(e_max, t_rec, osc)

        # Post-damping cooldown: right after a limit-cycle firing the loop
        # sits on the edge of stability. Suppress event-path reductions until
        # we've seen several AI cycles without any fresh oscillation. A
        # limit-cycle firing re-arms the cooldown; any other cycle drains it.
        suppressed = False
        if source == "limit_cycle":
            self._cooldown_remaining = self._LIMIT_CYCLE_COOLDOWN_CYCLES
        else:
            if delta_ti < 0.0 and self._cooldown_remaining > 0:
                delta_ti = 0.0
                suppressed = True
            self._cooldown_remaining = max(0, self._cooldown_remaining - 1)

        new_ti = max(limit_min, min(limit_max, ti_current * (1.0 + delta_ti)))
        if source == "limit_cycle":
            tag = "DR/limit-cycle"
        elif suppressed:
            tag = f"DR/cooldown={self._cooldown_remaining}"
        else:
            tag = "DR"
        return AIDecisionV2(
            delta_ti=delta_ti,
            new_ti=new_ti,
            inputs={"E_MAX": e_max, "T_REC": t_rec, "OSC": osc},
            reasoning=(
                f"FuzzyV2[{tag}]: E_max={e_max:.2f} T_rec={t_rec:.2f}τ OSC={osc:.2f} "
                f"Δ_Ti={delta_ti:+.3f} Ti: {ti_current:.4f} → {new_ti:.4f}"
            ),
            membership_values=mfs,
        )


# ===========================================================================
# Strategy 3 — Surge Level / Averaging Control
# ===========================================================================

MF_L_MARGIN_SL: MFSet = {
    "SAFE":     ("trap", (0.0, 0.0, 0.2, 0.35)),
    "WARNING":  ("tri",  (0.25, 0.35, 0.45)),
    "CRITICAL": ("trap", (0.4, 0.45, 0.5, 0.5)),
}

MF_TV_MV_SL: MFSet = {
    "LOW":    ("trap", (0.0, 0.0, 0.05, 0.15)),
    "MEDIUM": ("tri",  (0.1, 0.25, 0.4)),
    "HIGH":   ("trap", (0.3, 0.5, 1.0, 1.0)),
}

MF_DL_DT_SL: MFSet = {
    "ESCAPING": ("trap", (-10.0, -10.0, -0.5, 0.0)),
    "LOW":      ("tri",  (-1.0, 0.0, 1.0)),
    "HIGH":     ("trap", (0.5, 2.0, 10.0, 10.0)),
}

# Output centres — singleton CoG approximation of spec MFs.
OUTPUT_CENTERS_SL: dict[str, float] = {
    "RD": -0.65,  # Reduce Drastically (spec trap centroid ≈ -0.675)
    "R":  -0.25,
    "M":    0.0,
    "A":  +0.30,
    "AM": +1.00,  # Aumentar Muito (spec trap far out to 1.5 → cap at 1.0)
}

RULES_SL: list[Rule] = [
    # R1: safe level with valve chattering → relax hard
    ({"margin": "SAFE", "tv": "HIGH"}, "AM"),
    # R2: ideal surge operation
    ({"margin": "SAFE", "tv": "LOW", "dl_dt": "LOW"}, "M"),
    # R2': safe with moderate valve motion → gentle relax
    ({"margin": "SAFE", "tv": "MEDIUM"}, "A"),
    # R3: emergency — tank heading to the limit
    ({"margin": "CRITICAL", "dl_dt": "HIGH"}, "RD"),
    # R4: critical but recovering on its own — start relaxing back
    ({"margin": "CRITICAL", "dl_dt": "ESCAPING"}, "A"),
    # R4': critical, near-still — hold
    ({"margin": "CRITICAL", "dl_dt": "LOW"}, "M"),
    # R5: warning zone, still moving toward limit → boost integral
    ({"margin": "WARNING", "dl_dt": "HIGH"}, "R"),
    # R5': warning zone, escaping — relax
    ({"margin": "WARNING", "dl_dt": "ESCAPING"}, "A"),
    # R5'': warning zone, stable — maintain
    ({"margin": "WARNING", "dl_dt": "LOW"}, "M"),
]


class FuzzyEngineV2SurgeLevel:
    """Averaging / surge-level tuner: margin + valve TV + margin rate → Δ_Ti.

    Input is ``pv_frac`` (0–1 of span), NOT error. CO is the manipulated
    valve output.

    ``Δ_Ti`` is asymmetric — easy to relax (Ti up), hard to tighten (Ti down),
    except in the critical+racing-to-limit emergency.
    """

    _DEFAULT_WINDOW = 20
    _TV_FULL_SCALE_PER_SAMPLE = 0.05   # 5% CO change per sample → TV_norm = 1

    def __init__(
        self, dt_sec: float = 60.0, window_samples: int | None = None,
    ) -> None:
        self._dt = dt_sec
        n = window_samples if window_samples is not None else self._DEFAULT_WINDOW
        self._window_samples = max(4, int(n))
        self._pvs: deque[float] = deque(maxlen=self._window_samples)
        self._cos: deque[float] = deque(maxlen=self._window_samples)

    def update_sample(self, pv_frac: float, co_frac: float) -> None:
        self._pvs.append(pv_frac)
        self._cos.append(co_frac)

    def _l_margin(self) -> float:
        if not self._pvs:
            return 0.0
        return abs(self._pvs[-1] - 0.5)

    def _tv_mv(self) -> float:
        n = len(self._cos)
        if n < 2:
            return 0.0
        tv = sum(abs(self._cos[i] - self._cos[i - 1]) for i in range(1, n))
        per_sample = tv / (n - 1)
        return min(1.0, per_sample / self._TV_FULL_SCALE_PER_SAMPLE)

    def _dl_dt(self) -> float:
        """Signed rate toward limit in % per minute.

        Positive = |PV − 0.5| growing (tank heading for a wall).
        Negative = |PV − 0.5| shrinking (tank relaxing toward centre).
        """
        n = len(self._pvs)
        if n < 2:
            return 0.0
        margin_end = abs(self._pvs[-1] - 0.5)
        margin_start = abs(self._pvs[0] - 0.5)
        delta_margin = margin_end - margin_start
        time_span_sec = (n - 1) * self._dt
        rate_frac_per_sec = delta_margin / time_span_sec
        return rate_frac_per_sec * 100.0 * 60.0

    def infer(
        self, margin: float, tv: float, dl_dt: float,
    ) -> tuple[float, dict[str, dict[str, float]]]:
        input_mfs = {
            "margin": _fuzzify(margin, MF_L_MARGIN_SL),
            "tv":     _fuzzify(tv, MF_TV_MV_SL),
            "dl_dt":  _fuzzify(dl_dt, MF_DL_DT_SL),
        }
        delta, output_strengths = _run_rules(
            input_mfs, RULES_SL, OUTPUT_CENTERS_SL,
        )
        # Spec allows AM trapezoid to reach +1.5 — keep a wider clamp here.
        delta = max(-1.0, min(1.5, delta))
        return delta, {**input_mfs, "output": output_strengths}

    def compute_adjustment(
        self, ti_current: float, limit_min: float, limit_max: float,
    ) -> AIDecisionV2:
        margin = self._l_margin()
        tv = self._tv_mv()
        dl_dt = max(-10.0, min(10.0, self._dl_dt()))
        delta_ti, mfs = self.infer(margin, tv, dl_dt)
        new_ti = max(limit_min, min(limit_max, ti_current * (1.0 + delta_ti)))
        return AIDecisionV2(
            delta_ti=delta_ti,
            new_ti=new_ti,
            inputs={"L_MARGIN": margin, "TV_MV": tv, "DL_DT": dl_dt},
            reasoning=(
                f"FuzzyV2[SL]: margin={margin:.2f} TV={tv:.2f} "
                f"dL/dt={dl_dt:+.2f}%/min Δ_Ti={delta_ti:+.3f} "
                f"Ti: {ti_current:.4f} → {new_ti:.4f}"
            ),
            membership_values=mfs,
        )


# ===========================================================================
# Dispatcher — one entry point per loop, picks the right strategy
# ===========================================================================


AnyFuzzyV2Engine = Union[
    FuzzyEngineV2,
    "FuzzyEngineV2DisturbanceRejection",
    "FuzzyEngineV2SurgeLevel",
]


class FuzzyEngineV2Dispatcher:
    """Route samples and decisions to the strategy engine that matches the
    loop's control objective.

    Callers feed all three signals every scan; the dispatcher forwards only
    the ones the underlying engine cares about.
    """

    def __init__(
        self,
        objective: ControlObjective,
        *,
        tau_estimate_sec: float = 10.0,
        e_max_norm_full: float = 0.05,
        dt_sec: float = 1.0,
        window_samples: int | None = None,
    ) -> None:
        self._objective = objective
        engine: AnyFuzzyV2Engine
        if objective == ControlObjective.SP_TRACKING:
            engine = FuzzyEngineV2(window_samples=window_samples)
        elif objective == ControlObjective.DISTURBANCE_REJECTION:
            engine = FuzzyEngineV2DisturbanceRejection(
                tau_estimate_sec=tau_estimate_sec,
                e_max_norm_full=e_max_norm_full,
                dt_sec=dt_sec,
                window_samples=window_samples,
            )
        elif objective == ControlObjective.SURGE_LEVEL:
            engine = FuzzyEngineV2SurgeLevel(
                dt_sec=dt_sec, window_samples=window_samples,
            )
        else:
            raise ValueError(f"Unsupported control objective: {objective}")
        self._engine = engine

    @property
    def objective(self) -> ControlObjective:
        return self._objective

    @property
    def engine(self) -> AnyFuzzyV2Engine:
        return self._engine

    def update_sample(
        self, error_frac: float, pv_frac: float, co_frac: float,
    ) -> None:
        if self._objective == ControlObjective.SP_TRACKING:
            self._engine.update_sample(error_frac, co_frac)
        elif self._objective == ControlObjective.DISTURBANCE_REJECTION:
            self._engine.update_sample(error_frac)
        else:  # SURGE_LEVEL
            self._engine.update_sample(pv_frac, co_frac)

    def compute_adjustment(
        self, ti_current: float, limit_min: float, limit_max: float,
    ) -> AIDecisionV2:
        return self._engine.compute_adjustment(ti_current, limit_min, limit_max)

    def compute_adjustment_from_stats(
        self,
        stats: dict,
        span: float,
        ti_current: float,
        limit_min: float,
        limit_max: float,
    ) -> AIDecisionV2:
        """Use rolling stats from StatsWorker for SP_TRACKING and DR alike.

        SP_TRACKING derives IAE/OSC/EFF directly from the snapshot. DR keeps
        its event-driven state machine but overlays the stats-based OSC so
        genuine oscillation (confirmed by pk_pk + zero_crossings + reversals)
        reliably triggers damping — the post-event σ metric used to
        undersample the cycle and leave Ti stuck during a visible limit
        cycle. Surge Level still uses per-sample PV/CO state and falls back
        to the legacy path.
        """
        if self._objective == ControlObjective.SP_TRACKING:
            return self._engine.compute_adjustment_from_stats(
                stats, span, ti_current, limit_min, limit_max,
            )
        if self._objective == ControlObjective.DISTURBANCE_REJECTION:
            return self._engine.compute_adjustment_from_stats(
                stats, span, ti_current, limit_min, limit_max,
            )
        return self._engine.compute_adjustment(ti_current, limit_min, limit_max)
