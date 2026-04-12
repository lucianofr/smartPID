"""Fuzzy logic engine for Ki optimization.

7 linguistic levels on [-100%, +100%] with triangular (center) and
trapezoidal (extremes) membership functions, 50% overlap.

Includes oscillation detection: when the error sign reverses rapidly
the engine overrides the rule-based gamma with a negative damping
proportional to the oscillation amplitude (backs off integral action).
"""
from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass

from smart_pid_domain.enums import ControlObjective, ProcessSpeed

# --- Membership function helpers ---


def triangular_mf(x: float, a: float, b: float, c: float) -> float:
    """Triangular membership function. Peak at b, zero at a and c."""
    if x < a or x > c:
        return 0.0
    if a == b == c:
        return 1.0 if x == a else 0.0
    if x <= b:
        return (x - a) / (b - a) if b != a else 1.0
    return (c - x) / (c - b) if c != b else 1.0


def trapezoidal_mf(x: float, a: float, b: float, c: float, d: float) -> float:
    """Trapezoidal membership function. Plateau between b and c."""
    if x < a or x > d:
        return 0.0
    if x <= b:
        return (x - a) / (b - a) if b != a else 1.0
    if x <= c:
        return 1.0
    return (d - x) / (d - c) if d != c else 1.0


# --- Fuzzy levels and their MF parameters ---
#
# Universe: [0, 100] (absolute values — IAE-based tuning).
# For Ti tuning the SIGN of the error is irrelevant; only magnitude
# and rate of change matter.
#
# 5 levels on [0, 100]: ZO, SM, ME, LA, VL
# Inputs:
#   |error|       — normalised |e|/span × 100
#   |delta_error| — normalised |Δe|/span × 100
# Output gamma:
#   Positive → "more integral action" → Ti decreases (offset regime)
#   Negative → "less integral action" → Ti increases (oscillation)
#   Zero     → Ti is adequate

LEVELS = ("ZO", "SM", "ME", "LA", "VL")

MF_PARAMS: dict[str, tuple[str, tuple[float, ...]]] = {
    "ZO": ("trap", (0.0, 0.0, 2.0, 5.0)),
    "SM": ("tri", (2.0, 8.0, 20.0)),
    "ME": ("tri", (10.0, 25.0, 45.0)),
    "LA": ("tri", (30.0, 55.0, 80.0)),
    "VL": ("trap", (60.0, 80.0, 100.0, 100.0)),
}

# Rule matrices: rows = |error| level, cols = |delta_error| level
# Output is one of the 5 levels interpreted as a SIGNED value.
#
# Asymmetric output centers: decreasing Ti (positive gamma) is risky because
# a peak of damped oscillation looks identical to a steady offset when |Δe|≈0.
# Increasing Ti (negative gamma) only slows convergence — cheap. So positive
# side is deliberately weaker than negative side.
#
# Logic:
#   • High |error| + low  |Δerror| = offset OR oscillation peak → mild positive
#   • High |error| + high |Δerror| = oscillating → strong negative (damp)
#   • Low  |error| + low  |Δerror| = settled → zero (Ti OK)
#   • Low  |error| + high |Δerror| = noise/settling → negative

OUTPUT_LEVELS = ("NL", "NM", "ZO", "PM", "PL")
OUTPUT_CENTERS: dict[str, float] = {
    "NL": -1.0,
    "NM": -0.5,
    "ZO": 0.0,
    "PM": 0.3,
    "PL": 0.6,
}

RULE_MATRICES: dict[ControlObjective, list[list[str]]] = {
    ControlObjective.SP_TRACKING: [
        # |Δe|:  ZO     SM     ME     LA     VL
        # |e|:
        ["ZO",  "ZO",  "NM",  "NM",  "NL"],  # ZO — settled
        ["PM",  "ZO",  "ZO",  "NM",  "NL"],  # SM — small offset
        ["PM",  "PM",  "ZO",  "NM",  "NL"],  # ME — ambiguous (offset or peak)
        ["PM",  "PM",  "ZO",  "NM",  "NL"],  # LA — ambiguous (offset or peak)
        ["PL",  "PM",  "PM",  "ZO",  "NM"],  # VL — strong offset, still cautious
    ],
    ControlObjective.DISTURBANCE_REJECTION: [
        # Slightly more aggressive offset correction than SP_TRACKING,
        # but still avoids strong positive at moderate |e| with low |Δe|.
        ["ZO",  "ZO",  "NM",  "NL",  "NL"],  # ZO
        ["PM",  "PM",  "ZO",  "NM",  "NL"],  # SM
        ["PM",  "PM",  "ZO",  "NM",  "NL"],  # ME
        ["PL",  "PM",  "PM",  "ZO",  "NM"],  # LA
        ["PL",  "PL",  "PM",  "ZO",  "NM"],  # VL
    ],
    ControlObjective.SURGE_LEVEL: [
        # Most conservative — stability over offset elimination.
        ["ZO",  "NM",  "NM",  "NL",  "NL"],  # ZO
        ["ZO",  "ZO",  "NM",  "NM",  "NL"],  # SM
        ["ZO",  "ZO",  "ZO",  "NM",  "NL"],  # ME
        ["PM",  "ZO",  "ZO",  "NM",  "NM"],  # LA
        ["PM",  "PM",  "ZO",  "NM",  "NM"],  # VL
    ],
}

# Legacy alias (used by old tests that reference LEVEL_CENTERS)
LEVEL_CENTERS = OUTPUT_CENTERS

@dataclass(frozen=True)
class AIDecision:
    """Result of an AI Ki optimization computation."""

    gamma: float  # [-1.0, +1.0]
    new_ki: float  # Computed Ki
    reasoning: str  # Human-readable explanation
    membership_values: dict[str, dict[str, float]] | None  # Fuzzy debug info


class FuzzyEngine:
    """Fuzzy logic Ki optimizer with oscillation detection.

    Pure domain service — no I/O, no threading.
    When the error sign flips rapidly (oscillation), the engine overrides
    the rule-based gamma with a negative value proportional to error
    amplitude, which increases Ti / decreases Ki to stabilise the loop.
    """

    _OSC_WINDOW = 10  # smaller window → faster detection latency
    _OSC_THRESHOLD = 2  # 2 sign flips suffice (amp gate still rejects noise)
    _OSC_MIN_AMPLITUDE = 0.025  # 2.5% of span — rejects typical measurement noise
    _OSC_DAMPING_GAIN = 3.0  # stronger Ti push per unit amplitude
    _OSC_GAMMA_CAP = 1.0  # allow full-magnitude damping when amp × gain saturates
    # If recent-half RMS / older-half RMS < this, oscillation is damping
    # on its own — don't push Ti higher, let the loop settle.
    _TREND_DAMPING_RATIO = 0.9
    # Variability gate (2σ / span, as %). Distinguishes:
    #   high variability + persistent error → oscillation (increase Ti)
    #   low variability + persistent error → steady offset (decrease Ti)
    _VAR_LOW_PCT = 2.0  # below → full trust in rules (reduce Ti for offset)
    _VAR_HIGH_PCT = 5.0  # above → force negative gamma (oscillation signature)

    def __init__(self) -> None:
        self._error_signs: deque[int] = deque(maxlen=self._OSC_WINDOW)
        self._recent_errors: deque[float] = deque(maxlen=self._OSC_WINDOW)

    def _sign_changes(self) -> int:
        changes = 0
        prev = 0
        for s in self._error_signs:
            if prev != 0 and s != 0 and s != prev:
                changes += 1
            if s != 0:
                prev = s
        return changes

    def _amplitude(self) -> float:
        if not self._recent_errors:
            return 0.0
        return math.sqrt(sum(e * e for e in self._recent_errors) / len(self._recent_errors))

    def _error_variability_pct(self) -> float:
        """Return 2σ of recent errors as % of span.

        Errors in ``_recent_errors`` are already stored as fractions of span,
        so 2σ × 100 gives the standard process-variability metric.
        Uses std (centred around mean) so a pure steady offset — every sample
        the same — yields 0 variability, while oscillation around the mean
        yields the full excursion.
        """
        n = len(self._recent_errors)
        if n < 4:
            return 0.0
        errs = list(self._recent_errors)
        mean = sum(errs) / n
        variance = sum((e - mean) ** 2 for e in errs) / n
        return 2.0 * math.sqrt(variance) * 100.0

    def _amplitude_trend(self) -> float:
        """Ratio of recent-half RMS to older-half RMS.

        Returns 1.0 when window not yet full.
        < 1.0 means amplitude is decreasing (oscillation damping).
        > 1.0 means amplitude is growing (oscillation worsening).
        """
        if len(self._recent_errors) < self._OSC_WINDOW:
            return 1.0
        half = self._OSC_WINDOW // 2
        errs = list(self._recent_errors)
        older = errs[:half]
        newer = errs[half:]
        old_rms = math.sqrt(sum(e * e for e in older) / len(older))
        new_rms = math.sqrt(sum(e * e for e in newer) / len(newer))
        if old_rms < 1e-6:
            return 1.0
        return new_rms / old_rms

    def fuzzify(self, value: float) -> dict[str, float]:
        """Compute membership degree for each fuzzy level."""
        result: dict[str, float] = {}
        for level in LEVELS:
            mf_type, params = MF_PARAMS[level]
            if mf_type == "trap":
                result[level] = trapezoidal_mf(value, *params)
            else:
                result[level] = triangular_mf(value, *params)
        return result

    def infer(
        self,
        abs_error: float,
        abs_delta_error: float,
        objective: ControlObjective,
    ) -> float:
        """Run full fuzzy inference on absolute values.

        Args:
            abs_error: |error| normalised to [0, 100] (% of span).
            abs_delta_error: |Δerror| normalised to [0, 100].
            objective: Control objective selecting the rule matrix.

        Returns:
            gamma in [-1.0, +1.0].
              Positive → more integral action (decrease Ti / increase Ki).
              Negative → less integral action (increase Ti / decrease Ki).
        """
        abs_error = max(0.0, min(100.0, abs_error))
        abs_delta_error = max(0.0, min(100.0, abs_delta_error))

        error_mf = self.fuzzify(abs_error)
        delta_mf = self.fuzzify(abs_delta_error)

        matrix = RULE_MATRICES[objective]

        # Apply rules and aggregate (max-of-mins)
        output_strengths: dict[str, float] = {level: 0.0 for level in OUTPUT_LEVELS}
        for i, e_level in enumerate(LEVELS):
            for j, de_level in enumerate(LEVELS):
                firing = min(error_mf[e_level], delta_mf[de_level])
                out_level = matrix[i][j]
                output_strengths[out_level] = max(output_strengths[out_level], firing)

        # Defuzzify via Center of Gravity
        numerator = sum(
            OUTPUT_CENTERS[level] * strength
            for level, strength in output_strengths.items()
        )
        denominator = sum(output_strengths.values())

        if denominator < 1e-10:
            return 0.0

        # OUTPUT_CENTERS are already in [-1, +1]
        gamma = numerator / denominator
        return max(-1.0, min(1.0, gamma))

    def compute_gamma(
        self,
        error: float,
        delta_error: float,
        ki_current: float,
        span: float,
        objective: ControlObjective,
        speed: ProcessSpeed,
        limit_min: float,
        limit_max: float,
        integral_type: str = "TIME_TI",
    ) -> AIDecision:
        """Full fuzzy pipeline: normalize -> fuzzify -> infer -> update Ki/Ti.

        Args:
            error: Raw error in engineering units.
            delta_error: Raw delta_error in engineering units.
            ki_current: Current integral param value (Ki or Ti).
            span: Process span (eu_max - eu_min) for normalization.
            objective: Control objective selecting the rule matrix.
            speed: Process speed selecting the speed factor.
            limit_min: Minimum allowed value.
            limit_max: Maximum allowed value.
            integral_type: "GAIN_KI" or "TIME_TI". For Ti, gamma is
                inverted because increasing Ti SLOWS the response.

        Returns:
            AIDecision with gamma, new value, reasoning, and debug info.
        """
        # Normalize to absolute [0, 100]
        if span > 0:
            abs_error_norm = abs(error / span) * 100.0
            abs_delta_norm = abs(delta_error / span) * 100.0
        else:
            abs_error_norm = 0.0
            abs_delta_norm = 0.0

        # Track oscillation (signed error for sign-change detection)
        error_frac = (error / span) if span > 0 else 0.0
        cur_sign = 1 if error_frac > 0.005 else (-1 if error_frac < -0.005 else 0)
        self._error_signs.append(cur_sign)
        self._recent_errors.append(error_frac)

        # Fuzzify absolute inputs (for debug output)
        error_mf = self.fuzzify(abs_error_norm)
        delta_error_mf = self.fuzzify(abs_delta_norm)

        # Oscillation override: if sign flips rapidly with significant amplitude
        reversals = self._sign_changes()
        amp = self._amplitude()
        oscillating = (
            reversals >= self._OSC_THRESHOLD and amp >= self._OSC_MIN_AMPLITUDE
        )

        trend = self._amplitude_trend()
        is_self_damping = oscillating and trend < self._TREND_DAMPING_RATIO
        if oscillating and not is_self_damping:
            # Growing oscillation (trend > 1) gets proportionally more aggressive
            # damping to stabilise the loop faster.
            adaptive_gain = self._OSC_DAMPING_GAIN * max(1.0, trend)
            gamma = -min(self._OSC_GAMMA_CAP, adaptive_gain * amp)
            reason_prefix = (
                f"Fuzzy(OSC_DAMP rev={reversals} amp={amp:.3f} "
                f"trend={trend:.2f} gain={adaptive_gain:.2f})"
            )
        elif is_self_damping:
            # Oscillation converging on its own — don't push Ti up further.
            gamma = 0.0
            reason_prefix = (
                f"Fuzzy(OSC_DAMPING_SELF trend={trend:.2f} amp={amp:.3f})"
            )
        else:
            # Normal fuzzy inference on absolute values
            gamma = self.infer(abs_error_norm, abs_delta_norm, objective)
            reason_prefix = f"Fuzzy({objective.value})"

        # --- Variability gate -------------------------------------------------
        # 2σ/span distinguishes oscillation (high σ) from steady offset (low σ).
        # Rules alone can't tell a mid-|e|/low-|Δe| sample at an oscillation
        # peak from a true steady offset; variability over the window does.
        # Requires a full window (else we can't tell "growing oscillation" from
        # "initial transient damping to setpoint"). Skipped when self-damping
        # is in effect so we don't fight a converging loop.
        variability_pct = self._error_variability_pct()
        window_full = len(self._recent_errors) >= self._OSC_WINDOW
        if window_full and not is_self_damping:
            if variability_pct >= self._VAR_HIGH_PCT:
                osc_gamma = -min(
                    1.0, (variability_pct - self._VAR_LOW_PCT) / 10.0,
                )
                if osc_gamma < gamma:
                    gamma = osc_gamma
                    reason_prefix += f" var={variability_pct:.1f}%(HI)"
            elif variability_pct > self._VAR_LOW_PCT and gamma > 0:
                blend = (self._VAR_HIGH_PCT - variability_pct) / (
                    self._VAR_HIGH_PCT - self._VAR_LOW_PCT
                )
                gamma = gamma * blend
                reason_prefix += f" var={variability_pct:.1f}%(MID×{blend:.2f})"
        # else: low variability, self-damping, or window not yet full — trust current gamma

        # Apply gamma direction: Ki and Ti have OPPOSITE effects
        # Positive gamma means "more integral action" → decrease Ti / increase Ki
        # For Ti: effective_gamma = -gamma → positive gamma decreases Ti
        sv = speed.speed_factor
        effective_gamma = gamma if integral_type == "GAIN_KI" else -gamma
        new_val = ki_current * (1.0 + effective_gamma * sv)
        new_val = max(limit_min, min(limit_max, new_val))

        param_label = "Ki" if integral_type == "GAIN_KI" else "Ti"
        reasoning = (
            f"{reason_prefix}: "
            f"|e|={abs_error_norm:.1f}%, |de|={abs_delta_norm:.1f}%, "
            f"gamma={gamma:.4f}, Sv={sv}, "
            f"{param_label}: {ki_current:.4f} -> {new_val:.4f}"
        )

        return AIDecision(
            gamma=gamma,
            new_ki=new_val,
            reasoning=reasoning,
            membership_values={"error": error_mf, "delta_error": delta_error_mf},
        )
