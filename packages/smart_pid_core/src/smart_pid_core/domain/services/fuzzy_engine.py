"""Fuzzy logic engine for Ki optimization.

7 linguistic levels on [-100%, +100%] with triangular (center) and
trapezoidal (extremes) membership functions, 50% overlap.
"""
from __future__ import annotations

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
# Universe: [-100, +100] (normalized % of span)
# 7 levels: NB, NM, NS, ZO, PS, PM, PB
# Spacing: ~33.33 between centers, 50% overlap

LEVELS = ("NB", "NM", "NS", "ZO", "PS", "PM", "PB")

# (type, params): "trap" = trapezoidal(a,b,c,d), "tri" = triangular(a,b,c)
MF_PARAMS: dict[str, tuple[str, tuple[float, ...]]] = {
    "NB": ("trap", (-100.0, -100.0, -67.0, -33.0)),
    "NM": ("tri", (-67.0, -33.0, 0.0)),
    "NS": ("tri", (-33.0, -16.67, 0.0)),
    "ZO": ("tri", (-16.67, 0.0, 16.67)),
    "PS": ("tri", (0.0, 16.67, 33.0)),
    "PM": ("tri", (0.0, 33.0, 67.0)),
    "PB": ("trap", (33.0, 67.0, 100.0, 100.0)),
}

# Rule matrices: RULE_MATRICES[objective][error_level_idx][delta_error_level_idx] = output_level
# Rows: error (NB..PB), Columns: delta_error (NB..PB)
# Output: one of the 7 fuzzy levels

RULE_MATRICES: dict[ControlObjective, list[list[str]]] = {
    ControlObjective.SP_TRACKING: [
        # delta_error: NB     NM     NS     ZO     PS     PM     PB
        #  error:
        ["NB", "NB", "NB", "NB", "NM", "NS", "ZO"],  # NB
        ["NB", "NB", "NB", "NM", "NS", "ZO", "PS"],  # NM
        ["NB", "NB", "NM", "NS", "ZO", "PS", "PM"],  # NS
        ["NB", "NM", "NS", "ZO", "PS", "PM", "PB"],  # ZO
        ["NM", "NS", "ZO", "PS", "PM", "PB", "PB"],  # PS
        ["NS", "ZO", "PS", "PM", "PB", "PB", "PB"],  # PM
        ["ZO", "PS", "PM", "PB", "PB", "PB", "PB"],  # PB
    ],
    ControlObjective.DISTURBANCE_REJECTION: [
        # Aggressive near zero error, minimizes offset
        ["NB", "NB", "NM", "NM", "NS", "ZO", "ZO"],  # NB
        ["NB", "NB", "NM", "NS", "NS", "ZO", "PS"],  # NM
        ["NB", "NM", "NS", "NS", "ZO", "PS", "PM"],  # NS
        ["NM", "NM", "NS", "ZO", "PS", "PM", "PM"],  # ZO
        ["NM", "NS", "ZO", "PS", "PS", "PM", "PB"],  # PS
        ["NS", "ZO", "PS", "PS", "PM", "PB", "PB"],  # PM
        ["ZO", "ZO", "PS", "PM", "PM", "PB", "PB"],  # PB
    ],
    ControlObjective.SURGE_LEVEL: [
        # Focus on valve stability
        ["ZO", "ZO", "NS", "NS", "NM", "NM", "NB"],  # NB
        ["ZO", "ZO", "NS", "NS", "NM", "NB", "NB"],  # NM
        ["PS", "ZO", "ZO", "NS", "NS", "NM", "NM"],  # NS
        ["PS", "PS", "ZO", "ZO", "ZO", "NS", "NS"],  # ZO
        ["PM", "PM", "PS", "PS", "ZO", "ZO", "NS"],  # PS
        ["PB", "PB", "PM", "PS", "PS", "ZO", "ZO"],  # PM
        ["PB", "PM", "PM", "PS", "PS", "ZO", "ZO"],  # PB
    ],
}

# Center values for defuzzification (CoG)
LEVEL_CENTERS: dict[str, float] = {
    "NB": -100.0,
    "NM": -33.0,
    "NS": -16.67,
    "ZO": 0.0,
    "PS": 16.67,
    "PM": 33.0,
    "PB": 100.0,
}

@dataclass(frozen=True)
class AIDecision:
    """Result of an AI Ki optimization computation."""

    gamma: float  # [-1.0, +1.0]
    new_ki: float  # Computed Ki
    reasoning: str  # Human-readable explanation
    membership_values: dict[str, dict[str, float]] | None  # Fuzzy debug info


class FuzzyEngine:
    """Fuzzy logic Ki optimizer.

    Pure domain service — no I/O, no threading.
    """

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
        error: float,
        delta_error: float,
        objective: ControlObjective,
    ) -> float:
        """Run full fuzzy inference: fuzzify -> apply rules -> defuzzify (CoG).

        Args:
            error: Normalized error in [-100, +100] (% of span).
            delta_error: Normalized delta_error in [-100, +100].
            objective: Control objective selecting the rule matrix.

        Returns:
            gamma in [-1.0, +1.0].
        """
        # Clamp inputs
        error = max(-100.0, min(100.0, error))
        delta_error = max(-100.0, min(100.0, delta_error))

        # Fuzzify both inputs
        error_mf = self.fuzzify(error)
        delta_mf = self.fuzzify(delta_error)

        matrix = RULE_MATRICES[objective]

        # Apply rules: for each (i, j), firing strength = min(error_mf[i], delta_mf[j])
        # Aggregate: for each output level, strength = max of all rules that fire to it
        output_strengths: dict[str, float] = {level: 0.0 for level in LEVELS}

        for i, e_level in enumerate(LEVELS):
            for j, de_level in enumerate(LEVELS):
                firing = min(error_mf[e_level], delta_mf[de_level])
                out_level = matrix[i][j]
                output_strengths[out_level] = max(output_strengths[out_level], firing)

        # Defuzzify via Center of Gravity (CoG)
        numerator = sum(
            LEVEL_CENTERS[level] * strength for level, strength in output_strengths.items()
        )
        denominator = sum(output_strengths.values())

        if denominator < 1e-10:
            return 0.0

        # CoG result is in [-100, +100], normalize to [-1, +1]
        cog = numerator / denominator
        gamma = max(-1.0, min(1.0, cog / 100.0))
        return gamma

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
        # Normalize to [-100, +100]
        if span > 0:
            error_norm = (error / span) * 100.0
            delta_error_norm = (delta_error / span) * 100.0
        else:
            error_norm = 0.0
            delta_error_norm = 0.0

        # Fuzzify (for debug output)
        error_mf = self.fuzzify(error_norm)
        delta_error_mf = self.fuzzify(delta_error_norm)

        # Infer gamma
        gamma = self.infer(error_norm, delta_error_norm, objective)

        # Apply gamma direction: Ki and Ti have OPPOSITE effects
        # Positive gamma means "more aggressive integral action"
        # For Ki: more aggressive = increase Ki  → use +gamma
        # For Ti: more aggressive = decrease Ti  → use -gamma
        sv = speed.speed_factor
        effective_gamma = gamma if integral_type == "GAIN_KI" else -gamma
        new_val = ki_current * (1.0 + effective_gamma * sv)
        new_val = max(limit_min, min(limit_max, new_val))

        param_label = "Ki" if integral_type == "GAIN_KI" else "Ti"
        reasoning = (
            f"Fuzzy({objective.value}): "
            f"e_norm={error_norm:.1f}%, de_norm={delta_error_norm:.1f}%, "
            f"gamma={gamma:.4f}, Sv={sv}, "
            f"{param_label}: {ki_current:.4f} -> {new_val:.4f}"
        )

        return AIDecision(
            gamma=gamma,
            new_ki=new_val,
            reasoning=reasoning,
            membership_values={"error": error_mf, "delta_error": delta_error_mf},
        )
