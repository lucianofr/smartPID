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
   continuous. Indicators: position inside a configurable safe PV band,
   band-crossing rate, error size, valve TV. Focus: suppress valve motion;
   defend the band unconditionally when PV leaves it.

All three produce an ``AIDecisionV2`` with ``delta_ti`` applied as
``Ti_new = Ti_old × (1 + Δ_Ti)``.
"""
from __future__ import annotations

import logging
import math
from collections import deque
from dataclasses import dataclass
from typing import Union

from smart_pid_domain.enums import ControlObjective

logger = logging.getLogger(__name__)

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

# Overshoot of the last SP step(s) in the stats window, as a fraction of
# the step size. NONE tops out at 2% ("eliminated"); MOD is the
# classical quarter-decay neighbourhood; HIGH saturates at 30% — the
# reported field case reads ~0.5, i.e. fully HIGH.
MF_OVS: MFSet = {
    "NONE": ("trap", (0.0, 0.0, 0.02, 0.06)),
    "MOD":  ("tri",  (0.04, 0.12, 0.22)),
    "HIGH": ("trap", (0.15, 0.30, 1.0, 1.0)),
}

# Overshoot below this is not actionable evidence: it neither bypasses
# the min-osc-samples hold nor the AI worker's stability-band skip.
OVS_ACT_THR: float = 0.05

OUTPUT_CENTERS: dict[str, float] = {
    "RM": -0.35, "R": -0.15, "M": 0.0, "A": +0.15, "AM": +0.35,
}

# Reducing Ti is the destabilising direction: a loop already at its limit is
# pushed into a limit cycle by a faster integrator, and the tuner then spends
# several cycles undoing it. Increasing Ti only costs speed. So a reduction is
# only ever justified by POSITIVE evidence of laziness — a standing offset the
# valve is NOT working to close — and every ambiguous combination resolves
# towards damping, or towards leaving the loop alone.
#
# Overshoot on a setpoint step is the mirror image: positive evidence that the
# integrator is too fast. While the last step overshot, a "reduce" or "settled"
# verdict from the window-averaged metrics is a lie — the transient that proves
# otherwise is hidden by the settling mask — so `ovs NONE` gates them.
RULES: list[Rule] = [
    # R0: setpoint-step overshoot — the primary SP-tracking defect. Fires
    # on the per-step indicator regardless of the window-averaged
    # metrics: the transient that produced it is settling-masked, so
    # OSC/IAE structurally cannot see it.
    ({"ovs": "HIGH"}, "AM"),
    ({"ovs": "MOD"},  "A"),
    # R1: persistent offset with a calm valve → integrator genuinely
    # lazy. Only when the last step came in clean — an overshooting loop
    # is never lazy, and reducing Ti there arms the next overshoot.
    ({"iae": "HIGH", "osc": "STABLE", "eff": "SMOOTH", "ovs": "NONE"}, "R"),
    ({"iae": "HIGH", "osc": "STABLE", "eff": "MODERATE", "ovs": "NONE"}, "R"),
    # R1': offset the valve is already fighting at full stroke. NOT a
    # slow loop — a loop at its limit. Damp. (History: this rule at "RM"
    # plus a masked OSC is what drove Ti down on an oscillating loop.)
    ({"iae": "HIGH", "osc": "STABLE", "eff": "EXCESS"}, "A"),
    ({"iae": "MED",  "osc": "STABLE", "eff": "EXCESS"}, "A"),
    ({"iae": "LOW",  "osc": "STABLE", "eff": "EXCESS"}, "A"),
    # R2: limit cycle territory
    ({"iae": "HIGH", "osc": "UNSTABLE"}, "AM"),
    ({"iae": "MED",  "osc": "UNSTABLE"}, "AM"),
    ({"iae": "LOW",  "osc": "UNSTABLE"}, "A"),
    # R3: nervous loop (oscillating + chattering valve) → slow integrator
    ({"osc": "OSC", "eff": "EXCESS"}, "A"),
    # R3-gap: sustained oscillation, high error, working (not chattering)
    # valve — previously uncovered, produced a structural hold.
    ({"iae": "HIGH", "osc": "OSC", "eff": "MODERATE"}, "A"),
    # R3': mild ringing on a loop already holding low error is the normal
    # shape of a step response; damp only when it costs something — and
    # only when the step itself did not overshoot.
    ({"iae": "LOW",  "osc": "OSC", "eff": "MODERATE", "ovs": "NONE"}, "M"),
    ({"iae": "LOW",  "osc": "OSC", "eff": "SMOOTH", "ovs": "NONE"}, "M"),
    ({"iae": "MED",  "osc": "OSC", "eff": "SMOOTH"}, "A"),
    ({"iae": "HIGH", "osc": "OSC", "eff": "SMOOTH"}, "AM"),
    # R4: acceptable compromise
    ({"iae": "MED", "osc": "OSC", "eff": "MODERATE", "ovs": "NONE"}, "M"),
    # R5: settled — only settled if the last step also came in clean;
    # otherwise these M-votes dilute the OVS correction in the CoG.
    ({"iae": "LOW", "osc": "STABLE", "eff": "SMOOTH", "ovs": "NONE"}, "M"),
    ({"iae": "LOW", "osc": "STABLE", "eff": "MODERATE", "ovs": "NONE"}, "M"),
    # R6: moderate offset, calm PV and calm valve → gentle reduce
    ({"iae": "MED", "osc": "STABLE", "eff": "SMOOTH", "ovs": "NONE"}, "R"),
    ({"iae": "MED", "osc": "STABLE", "eff": "MODERATE", "ovs": "NONE"}, "R"),
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
    # Fewest non-settling samples the oscillation indicators need before
    # their verdict means anything. Below this the window is dominated by
    # masked SP-step transients and the only honest answer is "hold".
    _MIN_OSC_SAMPLES = 8

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
        self, iae: float, osc: float, eff: float, ovs: float = 0.0,
    ) -> tuple[float, dict[str, dict[str, float]]]:
        input_mfs = {
            "iae": _fuzzify(iae, MF_IAE),
            "osc": _fuzzify(osc, MF_OSC),
            "eff": _fuzzify(eff, MF_EFF),
            # ovs=0.0 means "no step observed": NONE = 1, which opens every
            # ovs-gated rule — i.e. exactly the pre-OVS behaviour.
            "ovs": _fuzzify(ovs, MF_OVS),
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
            # The internal deque carries no SP data, so no step evidence can
            # exist on this path; absent evidence leaves the gates open.
            ovs=0.0,
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
        # Per-step overshoot — the only indicator computed through the
        # settling mask, so the only one that can see a step transient.
        ovs = max(0.0, min(1.0, float(stats.get("overshoot", 0.0))))
        # How many samples the oscillation metrics were actually allowed to
        # see. StatsWorker masks SP-step transients; when the setpoint moves
        # faster than the mask decays, that masking can cover the entire
        # window and every oscillation metric collapses to a structural
        # zero. Reading that as "STABLE" is what made the tuner cut Ti on a
        # loop in a limit cycle. No evidence is a hold, not a verdict.
        # The overshoot indicator is the exception: it is measured FROM the
        # masked region, so it is valid evidence precisely when the
        # oscillation metrics are not, and a significant one must act.
        osc_n = int(stats.get("osc_sample_count", n))
        if osc_n < self._MIN_OSC_SAMPLES and ovs < OVS_ACT_THR:
            return AIDecisionV2(
                delta_ti=0.0,
                new_ti=ti_current,
                inputs={"IAE": 0.0, "OSC": 0.0, "EFF": 0.0, "OVS": ovs,
                        "osc_samples": osc_n, "window": n},
                reasoning=(
                    f"FuzzyV2[SP]: hold — only {osc_n} of {n} samples are "
                    f"admissible for oscillation analysis "
                    f"(need {self._MIN_OSC_SAMPLES})"
                ),
                membership_values={},
            )

        iae = min(1.0, (mean_abs / span if span > 0 else 0.0) / self._IAE_FULL_SCALE)
        pk_pk_frac = (pk_pk_raw / span) if span > 0 else 0.0
        # Judge the amplitude against the excitation, not against a fixed
        # slice of span: a 15 %-of-span error swing is a limit cycle when
        # the setpoint never moved and a textbook step response when the
        # setpoint jumped 40 %. With a fixed setpoint sp_pk_pk is 0 and this
        # is exactly the original fixed scale.
        sp_travel = float(stats.get("sp_pk_pk", 0.0))
        scale = max(self._OSC_PKPK_FULL_SCALE * span, sp_travel)
        amp_norm = min(1.0, pk_pk_raw / scale) if scale > 0 else 0.0
        osc = amp_norm if (zero_crossings >= 2 and reversals >= 2) else 0.0
        # TV is published in raw CO units (0..100). Normalise to fraction.
        eff = min(1.0, (tv_per / 100.0) / self._TV_FULL_SCALE)
        return self._build_decision(
            iae, osc, eff, pk_pk_frac, reversals, n,
            ti_current, limit_min, limit_max,
            ovs=ovs,
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
        ovs: float,
        zero_crossings: int | None = None,
    ) -> AIDecisionV2:
        delta_ti, mfs = self.infer(iae, osc, eff, ovs)
        new_ti = max(limit_min, min(limit_max, ti_current * (1.0 + delta_ti)))
        inputs = {"IAE": iae, "OSC": osc, "EFF": eff, "OVS": ovs,
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
                f"EFF={eff:.2f} OVS={ovs:.2f} Δ_Ti={delta_ti:+.3f} "
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
    # Inter-event overshoot detection: when an event finalises, remember the
    # initial sign of its excursion. If a *new* event starts within this many
    # τ with error of the OPPOSITE sign, the second event IS the overshoot
    # of the first (PV crossed SP during recovery). Damping is prescribed.
    _OVERSHOOT_GAP_TAU = 5.0

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
        # Inter-event overshoot tracking.
        self._active_initial_sign: int = 0   # sign at IDLE → ACTIVE transition
        self._last_event_sign: int = 0       # sign of the previous event's excursion
        self._samples_since_last_event: int = 0  # IDLE samples elapsed since then
        # Source of the last finalised event. The overshoot detector only
        # fires after a normal "event" finalisation, never after a
        # "limit_cycle" or "overshoot" firing — otherwise a sustained
        # sinusoidal oscillation's alternating half-cycles trigger spurious
        # overshoot decisions.
        self._last_event_source: str = ""
        # Persistent flag: the update_sample code detects an overshoot pattern
        # *between* events and sets this. It must survive subsequent event
        # finalisations (which would otherwise overwrite _decision_inputs) and
        # is cleared only when compute_adjustment consumes it.
        self._overshoot_pending: bool = False
        # Marks that the CURRENT in-flight event was itself flagged as the
        # overshoot of the previous one. Its finalisation must NOT stamp
        # _last_event_source / _last_event_sign, otherwise a subsequent
        # legitimate disturbance of opposite sign would be wrongly classified
        # as "overshoot of the overshoot".
        self._current_event_is_overshoot: bool = False

    # ---- state transitions ----------------------------------------------

    def update_sample(self, error_frac: float) -> None:
        abs_e = abs(error_frac)
        if self._state == "IDLE":
            self._samples_since_last_event += 1
            if abs_e > self._EVENT_TRIGGER:
                initial_sign = 1 if error_frac > 0 else (
                    -1 if error_frac < 0 else 0
                )
                # Inter-event overshoot: if the previous event finalised
                # recently as a NORMAL event (not a limit-cycle or overshoot
                # firing) AND this one starts on the opposite side of SP,
                # the second event IS the first's overshoot. Flag it; the
                # next compute_adjustment will emit damping regardless of
                # whether this new event finalises first.
                if (
                    self._last_event_source == "event"
                    and self._last_event_sign != 0
                    and initial_sign != 0
                    and initial_sign != self._last_event_sign
                    and self._samples_since_last_event
                    < int(self._OVERSHOOT_GAP_TAU * self._tau / self._dt)
                ):
                    self._overshoot_pending = True
                    self._current_event_is_overshoot = True
                    self._last_event_sign = 0
                    self._last_event_source = ""
                self._state = "ACTIVE"
                self._e_max_observed = abs_e
                self._event_sample_count = 1
                self._in_band_samples = 0
                self._active_errors = [error_frac]
                self._active_zero_crossings = 0
                self._active_last_sign = initial_sign
                self._active_initial_sign = initial_sign
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
        # ALSO check for overshoot that surfaces DURING the SETTLING
        # window: recovery dwelled on the original side long enough to
        # trigger SETTLING, then PV crossed SP. This shows up as a
        # post-event sample of opposite sign to the initial excursion
        # with magnitude above the event trigger. The σ metric above
        # can miss a brief overshoot on a mostly-quiet window, so we
        # look at the peak opposite-sign magnitude directly.
        if self._active_initial_sign != 0 and self._post_errors:
            peak_opposite = max(
                (abs(e) for e in self._post_errors
                 if e * self._active_initial_sign < 0),
                default=0.0,
            )
            if peak_opposite >= self._EVENT_TRIGGER:
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
        self._stamp_last_event("event")
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
        self._stamp_last_event("limit_cycle")
        self._reset_event_state()

    def _stamp_last_event(self, source: str) -> None:
        """Record the initial sign/source of the just-finalised event for
        the next IDLE→ACTIVE transition's overshoot comparison.

        If the current event was itself detected as an overshoot, do NOT
        stamp anything — the next event should be evaluated against the
        ORIGINAL disturbance, not against this overshoot. Stamping here
        would make a subsequent fresh disturbance look like "overshoot of
        the overshoot", a spurious double-fire.
        """
        if self._current_event_is_overshoot:
            self._last_event_sign = 0
            self._last_event_source = ""
            self._samples_since_last_event = 0
            self._current_event_is_overshoot = False
            return
        if self._active_initial_sign != 0:
            self._last_event_sign = self._active_initial_sign
            self._last_event_source = source
            self._samples_since_last_event = 0

    def _reset_event_state(self) -> None:
        """Reset per-event tracking back to IDLE.

        The inter-event tracker (`_last_event_sign` / `_last_event_source`
        / `_samples_since_last_event`) is NOT touched here — it was
        stamped by the finaliser via `_stamp_last_event()` so the next
        IDLE→ACTIVE transition can evaluate overshoot.
        """
        self._state = "IDLE"
        self._e_max_observed = 0.0
        self._event_sample_count = 0
        self._in_band_samples = 0
        self._post_errors = []
        self._active_errors = []
        self._active_zero_crossings = 0
        self._active_last_sign = 0
        self._active_initial_sign = 0

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
        # Overshoot pending flag wins over any other pending decision.
        # When update_sample saw an opposite-sign event immediately after
        # a previous one, the second event IS the first's overshoot. That
        # signal must not be drowned by the new event's own finalisation.
        if self._overshoot_pending:
            self._overshoot_pending = False
            self._decision_inputs = (0.0, 0.0, 1.0)
            self._decision_source = "overshoot"
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
        # limit-cycle or overshoot firing re-arms the cooldown; any other
        # cycle drains it.
        suppressed = False
        if source in ("limit_cycle", "overshoot"):
            self._cooldown_remaining = self._LIMIT_CYCLE_COOLDOWN_CYCLES
        else:
            if delta_ti < 0.0 and self._cooldown_remaining > 0:
                delta_ti = 0.0
                suppressed = True
            self._cooldown_remaining = max(0, self._cooldown_remaining - 1)

        new_ti = max(limit_min, min(limit_max, ti_current * (1.0 + delta_ti)))
        if source == "limit_cycle":
            tag = "DR/limit-cycle"
        elif source == "overshoot":
            tag = "DR/overshoot"
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

MF_POS_SL: MFSet = {
    # ``m`` = |PV − band centre| / band half-width: 0 = dead centre,
    # 1 = exactly on a band edge, > 1 = outside the safe band.
    "SAFE": ("trap", (0.0, 0.0, 0.55, 0.75)),
    "NEAR": ("tri",  (0.65, 0.85, 1.0)),
    "OUT":  ("trap", (0.95, 1.10, 1e9, 1e9)),
}

MF_TV_MV_SL: MFSet = {
    "LOW":    ("trap", (0.0, 0.0, 0.05, 0.15)),
    "MEDIUM": ("tri",  (0.1, 0.25, 0.4)),
    "HIGH":   ("trap", (0.3, 0.5, 1.0, 1.0)),
}

MF_DPOS_SL: MFSet = {
    # dm/dt in m-units per minute. Positive = heading for a band wall.
    "ESCAPING": ("trap", (-10.0, -10.0, -0.5, 0.0)),
    "STILL":    ("tri",  (-1.0, 0.0, 1.0)),
    "TOWARD":   ("trap", (0.5, 2.0, 10.0, 10.0)),
}

MF_ERR_SL: MFSet = {
    # |error| in % of span, normalised by the configured "small error" band.
    "SMALL": ("trap", (0.0, 0.0, 0.8, 1.2)),
    "LARGE": ("trap", (0.8, 1.5, 1e9, 1e9)),
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
    # S1: outside the band and not coming back → hardest correction there is.
    # Leaving the band is forbidden, so this outranks valve smoothness.
    # Two rules with one conclusion == the OR of their premises under the
    # max-aggregation core.
    ({"pos": "OUT", "dpos": "TOWARD"}, "RD"),
    ({"pos": "OUT", "dpos": "STILL"},  "RD"),
    # S2: outside but already returning — hold the correction that is
    # working. Staying on RD here over-tightens and drives PV straight
    # across the band into the opposite wall.
    ({"pos": "OUT", "dpos": "ESCAPING"}, "M"),
    # S3: closing on a wall from inside → boost the integral moderately.
    ({"pos": "NEAR", "dpos": "TOWARD"}, "R"),
    # S4: on the edge but stationary → hold.
    ({"pos": "NEAR", "dpos": "STILL"}, "M"),
    # S5: heading back to centre → start relaxing.
    ({"pos": "NEAR", "dpos": "ESCAPING"}, "A"),
    # S6: safe level, valve chattering → integral gain is too high.
    ({"pos": "SAFE", "tv": "HIGH"}, "AM"),
    # S7: safe and on target → push the integral to its minimum action
    # (Ti → limit_max). This is the averaging-control ideal: still valve.
    ({"pos": "SAFE", "err": "SMALL", "tv": "LOW"}, "AM"),
    # S8: same, but the valve is still moving → more reason to smooth.
    ({"pos": "SAFE", "err": "SMALL", "tv": "MEDIUM"}, "AM"),
    # S9: safe level, quiet valve, standing offset → averaging control
    # tolerates offset. Do not tighten to chase it.
    ({"pos": "SAFE", "err": "LARGE", "tv": "LOW"}, "M"),
    # S10: safe level, offset, valve working → gentle relaxation.
    ({"pos": "SAFE", "err": "LARGE", "tv": "MEDIUM"}, "A"),
]


class FuzzyEngineV2SurgeLevel:
    """Averaging / surge-level tuner: band position, rate, error, valve TV.

    Priority is static and explicit: safety (S1/S2 plus the CO-ramp gate) >
    valve smoothness (S6-S8) > error (S9/S10). The safe PV band is
    configurable as a percentage of span; ``None`` bounds resolve to 20-80 %,
    so an unconfigured loop and an explicitly 20/80 loop behave identically.

    The primary input is ``pv_frac`` (0-1 of span), NOT error; ``error_frac``
    only classifies the offset as small/large for the averaging rules. CO is
    the manipulated valve output.
    """

    _DEFAULT_WINDOW = 20
    _TV_FULL_SCALE_PER_SAMPLE = 0.05   # 5% CO change per sample → TV_norm = 1
    _DEFAULT_BAND_LO_PCT = 20.0
    _DEFAULT_BAND_HI_PCT = 80.0
    _DEFAULT_ERROR_SMALL_PCT = 5.0
    #: Δ_Ti floor forced when the CO ramp gate trips — relax, never tighten.
    _CO_RAMP_FLOOR_DELTA_TI = 0.15

    def __init__(
        self,
        dt_sec: float = 60.0,
        window_samples: int | None = None,
        band_lo_pct: float | None = None,
        band_hi_pct: float | None = None,
        error_small_pct: float = 5.0,
        co_ramp_max_pct_min: float = 10.0,
    ) -> None:
        self._dt = dt_sec
        n = window_samples if window_samples is not None else self._DEFAULT_WINDOW
        self._window_samples = max(4, int(n))
        self._pvs: deque[float] = deque(maxlen=self._window_samples)
        self._cos: deque[float] = deque(maxlen=self._window_samples)
        self._errs: deque[float] = deque(maxlen=self._window_samples)

        lo = (
            self._DEFAULT_BAND_LO_PCT if band_lo_pct is None else float(band_lo_pct)
        )
        hi = (
            self._DEFAULT_BAND_HI_PCT if band_hi_pct is None else float(band_hi_pct)
        )
        if lo >= hi:
            # Only reachable from a corrupt/legacy .spid — the DTO and the UI
            # both reject an inverted band before it can be persisted.
            logger.warning(
                "surge_level_band_invalid lo=%s hi=%s falling_back=%s-%s",
                lo, hi, self._DEFAULT_BAND_LO_PCT, self._DEFAULT_BAND_HI_PCT,
            )
            lo = self._DEFAULT_BAND_LO_PCT
            hi = self._DEFAULT_BAND_HI_PCT
        self._band_lo_pct = lo
        self._band_hi_pct = hi
        self._band_centre_pct = (lo + hi) / 2.0
        self._band_half_pct = (hi - lo) / 2.0

        if error_small_pct <= 0.0:
            logger.warning(
                "surge_level_error_small_invalid value=%s falling_back=%s",
                error_small_pct, self._DEFAULT_ERROR_SMALL_PCT,
            )
            error_small_pct = self._DEFAULT_ERROR_SMALL_PCT
        self._error_small_pct = float(error_small_pct)
        self._co_ramp_max_pct_min = max(0.0, float(co_ramp_max_pct_min))

    def update_sample(
        self, error_frac: float, pv_frac: float, co_frac: float,
    ) -> None:
        self._errs.append(error_frac)
        self._pvs.append(pv_frac)
        self._cos.append(co_frac)

    def _pos_of(self, pv_frac: float) -> float:
        """Band-relative position: 0 = centre, 1 = on an edge, > 1 = outside."""
        return abs(pv_frac * 100.0 - self._band_centre_pct) / self._band_half_pct

    def _pos(self) -> float:
        if not self._pvs:
            return 0.0
        return self._pos_of(self._pvs[-1])

    def _tv_mv(self) -> float:
        n = len(self._cos)
        if n < 2:
            return 0.0
        tv = sum(abs(self._cos[i] - self._cos[i - 1]) for i in range(1, n))
        per_sample = tv / (n - 1)
        return min(1.0, per_sample / self._TV_FULL_SCALE_PER_SAMPLE)

    def _dpos(self) -> float:
        """Signed band-position rate in m-units per minute.

        Positive = PV heading for a band wall (|PV − centre| growing).
        Negative = PV returning toward the centre.
        """
        n = len(self._pvs)
        if n < 2 or self._dt <= 0.0:
            return 0.0
        delta = self._pos_of(self._pvs[-1]) - self._pos_of(self._pvs[0])
        span_min = (n - 1) * self._dt / 60.0
        if span_min <= 0.0:
            return 0.0
        return delta / span_min

    def _err_norm(self) -> float:
        """Mean |error| over the window, in units of ``error_small_pct``.

        Windowed rather than instantaneous for the same reason SP_TRACKING is:
        one noisy sample must not flip an averaging loop between the
        small-error and large-error rule groups.
        """
        if not self._errs:
            return 0.0
        mean_abs = sum(abs(e) for e in self._errs) / len(self._errs)
        return mean_abs * 100.0 / self._error_small_pct

    def _max_co_ramp_pct_min(self) -> float:
        """Largest single-sample CO slew in the window, in % per minute."""
        n = len(self._cos)
        if n < 2 or self._dt <= 0.0:
            return 0.0
        peak = max(abs(self._cos[i] - self._cos[i - 1]) for i in range(1, n))
        return peak * 100.0 * (60.0 / self._dt)

    def infer(
        self, pos: float, dpos: float, err: float, tv: float,
    ) -> tuple[float, dict[str, dict[str, float]]]:
        input_mfs = {
            "pos":  _fuzzify(pos, MF_POS_SL),
            "dpos": _fuzzify(dpos, MF_DPOS_SL),
            "err":  _fuzzify(err, MF_ERR_SL),
            "tv":   _fuzzify(tv, MF_TV_MV_SL),
        }
        delta, output_strengths = _run_rules(
            input_mfs, RULES_SL, OUTPUT_CENTERS_SL,
        )
        # Spec allows the AM trapezoid to reach +1.5 — keep the wider clamp.
        delta = max(-1.0, min(1.5, delta))
        return delta, {**input_mfs, "output": output_strengths}

    def compute_adjustment(
        self, ti_current: float, limit_min: float, limit_max: float,
    ) -> AIDecisionV2:
        pos = self._pos()
        dpos = max(-10.0, min(10.0, self._dpos()))
        err = self._err_norm()
        tv = self._tv_mv()
        delta_ti, mfs = self.infer(pos, dpos, err, tv)

        # Crisp post-inference safety validation, NOT a fuzzy rule: a valve
        # slewing faster than the configured ramp must never be answered with
        # a tighter integral, whatever the rule base concluded.
        co_ramp = self._max_co_ramp_pct_min()
        ramp_violation = (
            self._co_ramp_max_pct_min > 0.0
            and co_ramp > self._co_ramp_max_pct_min
        )
        if ramp_violation:
            delta_ti = max(delta_ti, self._CO_RAMP_FLOOR_DELTA_TI)

        new_ti = max(limit_min, min(limit_max, ti_current * (1.0 + delta_ti)))
        reasoning = (
            f"FuzzyV2[SL]: POS={pos:.2f} dPOS={dpos:+.2f}/min ERR={err:.2f} "
            f"TV={tv:.2f} "
            f"band={self._band_lo_pct:.0f}-{self._band_hi_pct:.0f}% "
            f"Δ_Ti={delta_ti:+.3f} Ti: {ti_current:.4f} → {new_ti:.4f}"
        )
        if ramp_violation:
            reasoning += (
                f" [CO-RAMP] {co_ramp:.1f}%/min > "
                f"{self._co_ramp_max_pct_min:.1f}%/min"
            )
        return AIDecisionV2(
            delta_ti=delta_ti,
            new_ti=new_ti,
            inputs={
                "POS": pos,
                "DPOS": dpos,
                "ERR": err,
                "TV": tv,
                "CO_RAMP": co_ramp,
                "co_ramp_violation": ramp_violation,
            },
            reasoning=reasoning,
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
        sl_band_lo_pct: float | None = None,
        sl_band_hi_pct: float | None = None,
        sl_error_small_pct: float = 5.0,
        sl_co_ramp_max_pct_min: float = 10.0,
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
                dt_sec=dt_sec,
                window_samples=window_samples,
                band_lo_pct=sl_band_lo_pct,
                band_hi_pct=sl_band_hi_pct,
                error_small_pct=sl_error_small_pct,
                co_ramp_max_pct_min=sl_co_ramp_max_pct_min,
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
            self._engine.update_sample(error_frac, pv_frac, co_frac)

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
