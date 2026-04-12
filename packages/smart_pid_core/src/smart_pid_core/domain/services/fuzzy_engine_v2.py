"""Fuzzy engine V2 — 3-input strategy based on normalized indicators.

Inputs (all normalized to [0, 1]):
- IAE: mean |error| / span (accumulated error magnitude).
- OSC: 2σ / span (oscillation index — distinguishes noise from limit cycle).
- EFF: mean |ΔCO| / span (control effort / total variation per sample).

Output:
- Δ_Ti ∈ [-0.5, +0.5], applied as Ti_new = Ti_old × (1 + Δ_Ti).

The rule base directly encodes the "physical meaning":
- High IAE + Stable + Smooth effort → **Reduce Ti** (integrator sluggish).
- High IAE + Unstable oscillation → **Increase Ti a lot** (limit cycle).
- Oscillatory + Excess effort → **Increase Ti** (nervous loop, save valve).
- Low IAE + Stable → **Maintain** (don't fix what isn't broken).

Independent from FuzzyEngine (v1) — this module coexists during A/B testing.
"""
from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Membership function helpers (reused from v1 semantics)
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


# ---------------------------------------------------------------------------
# Input MFs (universe [0, 1])
# ---------------------------------------------------------------------------

MF_IAE: dict[str, tuple[str, tuple[float, ...]]] = {
    "LOW":  ("trap", (0.0, 0.0, 0.2, 0.4)),
    "MED":  ("tri",  (0.3, 0.5, 0.7)),
    "HIGH": ("trap", (0.6, 0.8, 1.0, 1.0)),
}

MF_OSC: dict[str, tuple[str, tuple[float, ...]]] = {
    "STABLE":   ("trap", (0.0, 0.0, 0.2, 0.35)),
    "OSC":      ("tri",  (0.3, 0.5, 0.7)),
    "UNSTABLE": ("trap", (0.6, 0.8, 1.0, 1.0)),
}

MF_EFF: dict[str, tuple[str, tuple[float, ...]]] = {
    "SMOOTH":   ("trap", (0.0, 0.0, 0.2, 0.4)),
    "MODERATE": ("tri",  (0.3, 0.6, 0.8)),
    "EXCESS":   ("trap", (0.7, 0.9, 1.0, 1.0)),
}


# ---------------------------------------------------------------------------
# Output MFs (Δ_Ti universe [-0.5, +0.5])
# Singleton centroids are used for Centre-of-Gravity defuzzification.
# ---------------------------------------------------------------------------

OUTPUT_CENTERS: dict[str, float] = {
    "RM": -0.35,  # Reduce Much — integrator much more aggressive
    "R":  -0.15,  # Reduce — fine adjustment for residual offset
    "M":    0.0,  # Maintain — "team that's winning doesn't change"
    "A":   +0.15,  # Increase — smooth the loop to stop oscillation
    "AM": +0.35,  # Increase Much — emergency damping of instability
}


# ---------------------------------------------------------------------------
# Rule base
#
# Each rule is ((conditions), output_level). A condition may omit any input,
# in which case that input is "don't care" for the rule.
# ---------------------------------------------------------------------------

Rule = tuple[dict[str, str], str]

RULES: list[Rule] = [
    # R1 — persistent offset, no oscillation, calm actuator → integrator lazy
    ({"iae": "HIGH", "osc": "STABLE", "eff": "SMOOTH"}, "R"),
    ({"iae": "HIGH", "osc": "STABLE", "eff": "MODERATE"}, "R"),
    # R1' — offset with quiet valve and no oscillation → reduce more aggressively
    ({"iae": "HIGH", "osc": "STABLE", "eff": "EXCESS"}, "RM"),
    # R2 — limit cycle territory: high IAE + unstable osc → strong Ti increase
    ({"iae": "HIGH", "osc": "UNSTABLE"}, "AM"),
    ({"iae": "MED",  "osc": "UNSTABLE"}, "AM"),
    ({"iae": "LOW",  "osc": "UNSTABLE"}, "A"),
    # R3 — nervous loop (lots of valve motion with oscillation)
    ({"osc": "OSC",  "eff": "EXCESS"}, "A"),
    ({"iae": "LOW",  "osc": "OSC", "eff": "MODERATE"}, "A"),
    # R4 — acceptable compromise
    ({"iae": "MED",  "osc": "OSC", "eff": "MODERATE"}, "M"),
    # R5 — settled: don't touch it
    ({"iae": "LOW",  "osc": "STABLE"}, "M"),
    # R6 — moderate offset with mild oscillation: gentle reduce (resolve offset
    # without provoking more oscillation)
    ({"iae": "MED",  "osc": "STABLE", "eff": "SMOOTH"}, "R"),
    ({"iae": "MED",  "osc": "STABLE", "eff": "MODERATE"}, "R"),
]


@dataclass(frozen=True)
class AIDecisionV2:
    delta_ti: float                       # [-0.5, +0.5]
    new_ti: float                         # post-update, clamped
    iae_norm: float                       # raw normalized input
    osc_norm: float
    eff_norm: float
    reasoning: str
    membership_values: dict[str, dict[str, float]]


class FuzzyEngineV2:
    """3-input fuzzy tuner: IAE + 2σ/range + TV → Δ_Ti.

    Pure domain service — no I/O, no threading. Maintains a rolling window
    of recent normalized errors and CO values to compute the input indicators.
    """

    _WINDOW = 20
    # Error deadband (fractional): samples with |e/span| below this are
    # treated as zero for window metrics — prevents noise from triggering
    # spurious Ti drift.
    _DEADBAND = 0.02
    # Normalization scales — map physical ranges to [0, 1] universe.
    # These match the "well-tuned loop" baseline referenced in the spec.
    _IAE_FULL_SCALE = 0.20   # 20% mean |e|/span → IAE_norm = 1.0
    _TV_FULL_SCALE  = 0.10   # 10% mean |ΔCO|/span per sample → EFF_norm = 1.0
    _OSC_FULL_SCALE = 0.50   # 2σ/span = 0.5 → OSC_norm = 1.0 (hard limit-cycle)

    def __init__(self) -> None:
        self._errors: deque[float] = deque(maxlen=self._WINDOW)
        self._cos:    deque[float] = deque(maxlen=self._WINDOW)

    # ---- indicators ------------------------------------------------------

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

    # ---- fuzzy machinery -------------------------------------------------

    @staticmethod
    def _fuzzify(
        value: float,
        mfs: dict[str, tuple[str, tuple[float, ...]]],
    ) -> dict[str, float]:
        out: dict[str, float] = {}
        for name, (kind, params) in mfs.items():
            if kind == "trap":
                out[name] = trapezoidal_mf(value, *params)
            else:
                out[name] = triangular_mf(value, *params)
        return out

    def infer(
        self, iae: float, osc: float, eff: float,
    ) -> tuple[float, dict[str, dict[str, float]]]:
        """Run the rule base and return (Δ_Ti, memberships)."""
        iae_mf = self._fuzzify(iae, MF_IAE)
        osc_mf = self._fuzzify(osc, MF_OSC)
        eff_mf = self._fuzzify(eff, MF_EFF)

        output_strengths: dict[str, float] = {lvl: 0.0 for lvl in OUTPUT_CENTERS}
        for condition, out_lvl in RULES:
            strength = 1.0
            if "iae" in condition:
                strength = min(strength, iae_mf[condition["iae"]])
            if "osc" in condition:
                strength = min(strength, osc_mf[condition["osc"]])
            if "eff" in condition:
                strength = min(strength, eff_mf[condition["eff"]])
            output_strengths[out_lvl] = max(output_strengths[out_lvl], strength)

        numerator = sum(
            OUTPUT_CENTERS[lvl] * strength
            for lvl, strength in output_strengths.items()
        )
        denominator = sum(output_strengths.values())
        delta_ti = 0.0 if denominator < 1e-10 else numerator / denominator
        delta_ti = max(-0.5, min(0.5, delta_ti))

        return delta_ti, {
            "iae": iae_mf, "osc": osc_mf, "eff": eff_mf,
            "output": output_strengths,
        }

    # ---- public API ------------------------------------------------------

    def update_sample(self, error_frac: float, co_frac: float) -> None:
        """Feed a new sample (error / span, CO / 100) into the engine's window.

        Call every scan (or each tuning cadence) before invoking compute.
        """
        e = error_frac if abs(error_frac) > self._DEADBAND else 0.0
        self._errors.append(e)
        self._cos.append(co_frac)

    def compute_adjustment(
        self,
        ti_current: float,
        limit_min: float,
        limit_max: float,
    ) -> AIDecisionV2:
        """Compute Δ_Ti and the new Ti from the current window state."""
        iae = self._iae_norm()
        osc = self._osc_norm()
        eff = self._eff_norm()

        delta_ti, mfs = self.infer(iae, osc, eff)
        new_ti = ti_current * (1.0 + delta_ti)
        new_ti = max(limit_min, min(limit_max, new_ti))

        reasoning = (
            f"FuzzyV2: IAE={iae:.2f} OSC={osc:.2f} EFF={eff:.2f} "
            f"Δ_Ti={delta_ti:+.3f} Ti: {ti_current:.4f} → {new_ti:.4f}"
        )
        return AIDecisionV2(
            delta_ti=delta_ti,
            new_ti=new_ti,
            iae_norm=iae,
            osc_norm=osc,
            eff_norm=eff,
            reasoning=reasoning,
            membership_values=mfs,
        )
