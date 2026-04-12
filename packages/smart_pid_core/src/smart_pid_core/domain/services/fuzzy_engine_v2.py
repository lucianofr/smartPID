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
    # R3: nervous loop (oscillating + chattering valve)
    ({"osc": "OSC", "eff": "EXCESS"}, "A"),
    ({"iae": "LOW", "osc": "OSC", "eff": "MODERATE"}, "A"),
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

    _WINDOW = 20
    _DEADBAND = 0.02
    _IAE_FULL_SCALE = 0.20
    _TV_FULL_SCALE  = 0.10
    _OSC_FULL_SCALE = 0.50

    def __init__(self) -> None:
        self._errors: deque[float] = deque(maxlen=self._WINDOW)
        self._cos:    deque[float] = deque(maxlen=self._WINDOW)

    def _iae_norm(self) -> float:
        if not self._errors:
            return 0.0
        mean_abs = sum(abs(e) for e in self._errors) / len(self._errors)
        return min(1.0, mean_abs / self._IAE_FULL_SCALE)

    def _osc_norm(self) -> float:
        n = len(self._errors)
        if n < 4:
            return 0.0
        mean = sum(self._errors) / n
        variance = sum((e - mean) ** 2 for e in self._errors) / n
        sigma = math.sqrt(variance)
        return min(1.0, (2.0 * sigma) / self._OSC_FULL_SCALE)

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
        iae = self._iae_norm()
        osc = self._osc_norm()
        eff = self._eff_norm()
        delta_ti, mfs = self.infer(iae, osc, eff)
        new_ti = max(limit_min, min(limit_max, ti_current * (1.0 + delta_ti)))
        return AIDecisionV2(
            delta_ti=delta_ti,
            new_ti=new_ti,
            inputs={"IAE": iae, "OSC": osc, "EFF": eff},
            reasoning=(
                f"FuzzyV2[SP]: IAE={iae:.2f} OSC={osc:.2f} EFF={eff:.2f} "
                f"Δ_Ti={delta_ti:+.3f} Ti: {ti_current:.4f} → {new_ti:.4f}"
            ),
            membership_values=mfs,
        )


# ===========================================================================
# Strategy 2 — Disturbance Rejection
# ===========================================================================

MF_E_MAX_DR: MFSet = {
    "LOW":  ("trap", (0.0, 0.0, 0.3, 0.5)),
    "MED":  ("tri",  (0.3, 0.6, 0.9)),
    "HIGH": ("trap", (0.7, 1.0, 1.5, 1.5)),
}

MF_T_REC_DR: MFSet = {
    "FAST": ("trap", (0.0, 0.0, 1.5, 3.0)),
    "MED":  ("tri",  (2.0, 4.0, 6.0)),
    "SLOW": ("trap", (5.0, 7.0, 10.0, 10.0)),
}

MF_OSC_DR: MFSet = {
    "STABLE": ("trap", (0.0, 0.0, 0.15, 0.3)),
    "MED":    ("tri",  (0.2, 0.4, 0.6)),
    "HIGH":   ("trap", (0.5, 0.75, 1.0, 1.0)),
}

OUTPUT_CENTERS_DR: dict[str, float] = {
    "RM": -0.3, "R": -0.1, "M": 0.0, "A": +0.15, "AM": +0.4,
}

RULES_DR: list[Rule] = [
    # R1: controller slow and weak against the bump — boost integral
    ({"e_max": "HIGH", "t_rec": "SLOW", "osc": "STABLE"}, "RM"),
    ({"e_max": "HIGH", "t_rec": "SLOW", "osc": "MED"},    "R"),
    ({"e_max": "MED",  "t_rec": "SLOW", "osc": "STABLE"}, "R"),
    # R2: disturbance rejected fast but generated instability — smooth it
    ({"e_max": "LOW",  "t_rec": "FAST", "osc": "HIGH"}, "AM"),
    ({"e_max": "MED",  "t_rec": "FAST", "osc": "HIGH"},  "A"),
    # R3: big impact but optimal recovery — physics, accept it
    ({"e_max": "HIGH", "t_rec": "FAST", "osc": "MED"},    "M"),
    ({"e_max": "HIGH", "t_rec": "FAST", "osc": "STABLE"}, "M"),
    # R4: moderate everything but slow — slight push
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
    _POST_EVENT_WINDOW = 15         # samples for residual-oscillation window
    _OSC_FULL_SCALE = 0.50          # same 2σ/span normalisation as SP

    def __init__(
        self,
        tau_estimate_sec: float = 10.0,
        e_max_norm_full: float = 0.05,
        dt_sec: float = 1.0,
    ) -> None:
        self._tau = tau_estimate_sec
        self._e_max_full = e_max_norm_full
        self._dt = dt_sec
        self._state: str = "IDLE"
        self._e_max_observed: float = 0.0
        self._event_sample_count: int = 0
        self._in_band_samples: int = 0
        self._post_errors: list[float] = []
        self._decision_inputs: tuple[float, float, float] | None = None

    # ---- state transitions ----------------------------------------------

    def update_sample(self, error_frac: float) -> None:
        abs_e = abs(error_frac)
        if self._state == "IDLE":
            if abs_e > self._EVENT_TRIGGER:
                self._state = "ACTIVE"
                self._e_max_observed = abs_e
                self._event_sample_count = 1
                self._in_band_samples = 0
            return

        if self._state == "ACTIVE":
            self._event_sample_count += 1
            if abs_e > self._e_max_observed:
                self._e_max_observed = abs_e
            if abs_e <= self._EVENT_TRIGGER:
                self._in_band_samples += 1
                if self._in_band_samples >= self._EVENT_EXIT_DWELL:
                    self._state = "SETTLING"
                    self._post_errors = [error_frac]
            else:
                self._in_band_samples = 0
            return

        if self._state == "SETTLING":
            self._post_errors.append(error_frac)
            if len(self._post_errors) >= self._POST_EVENT_WINDOW:
                self._finalise_event()

    def _finalise_event(self) -> None:
        t_rec_sec = self._event_sample_count * self._dt
        t_rec_norm = t_rec_sec / self._tau
        e_max_norm = min(1.5, self._e_max_observed / self._e_max_full)
        n = len(self._post_errors)
        mean = sum(self._post_errors) / n
        variance = sum((e - mean) ** 2 for e in self._post_errors) / n
        sigma = math.sqrt(variance)
        osc_norm = min(1.0, (2.0 * sigma) / self._OSC_FULL_SCALE)
        self._decision_inputs = (e_max_norm, t_rec_norm, osc_norm)
        # Reset to IDLE for the next event
        self._state = "IDLE"
        self._e_max_observed = 0.0
        self._event_sample_count = 0
        self._in_band_samples = 0
        self._post_errors = []

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

    def compute_adjustment(
        self, ti_current: float, limit_min: float, limit_max: float,
    ) -> AIDecisionV2:
        if self._decision_inputs is None:
            return AIDecisionV2(
                delta_ti=0.0,
                new_ti=ti_current,
                inputs={},
                reasoning=f"FuzzyV2[DR]: holding (state={self._state})",
                membership_values={},
            )
        e_max, t_rec, osc = self._decision_inputs
        self._decision_inputs = None  # consume
        delta_ti, mfs = self.infer(e_max, t_rec, osc)
        new_ti = max(limit_min, min(limit_max, ti_current * (1.0 + delta_ti)))
        return AIDecisionV2(
            delta_ti=delta_ti,
            new_ti=new_ti,
            inputs={"E_MAX": e_max, "T_REC": t_rec, "OSC": osc},
            reasoning=(
                f"FuzzyV2[DR]: E_max={e_max:.2f} T_rec={t_rec:.2f}τ OSC={osc:.2f} "
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

    _WINDOW = 20
    _TV_FULL_SCALE_PER_SAMPLE = 0.05   # 5% CO change per sample → TV_norm = 1

    def __init__(self, dt_sec: float = 60.0) -> None:
        self._dt = dt_sec
        self._pvs: deque[float] = deque(maxlen=self._WINDOW)
        self._cos: deque[float] = deque(maxlen=self._WINDOW)

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
    ) -> None:
        self._objective = objective
        engine: AnyFuzzyV2Engine
        if objective == ControlObjective.SP_TRACKING:
            engine = FuzzyEngineV2()
        elif objective == ControlObjective.DISTURBANCE_REJECTION:
            engine = FuzzyEngineV2DisturbanceRejection(
                tau_estimate_sec=tau_estimate_sec,
                e_max_norm_full=e_max_norm_full,
                dt_sec=dt_sec,
            )
        elif objective == ControlObjective.SURGE_LEVEL:
            engine = FuzzyEngineV2SurgeLevel(dt_sec=dt_sec)
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
