"""Process models for simulator — FOPTD/SOPTD via scipy.signal."""
from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np
from scipy import signal
from scipy.interpolate import pade as pade_approx

if TYPE_CHECKING:
    from smart_pid_domain.models.process_preset import ProcessPreset

_PADE_ORDER = 3


def _pade_dead_time(dead_time: float, order: int) -> tuple[np.ndarray, np.ndarray]:
    """Compute Padé approximation coefficients for e^(-dead_time * s).

    Uses scipy.interpolate.pade with the Taylor series of e^(-L*s).
    Returns (numerator, denominator) as 1D numpy arrays (highest power first).
    """
    taylor = [(-dead_time) ** k / math.factorial(k) for k in range(2 * order + 1)]
    num_poly, den_poly = pade_approx(taylor, order)
    return np.array(num_poly.coefficients), np.array(den_poly.coefficients)


def _build_tf(
    gain: float, tau1: float, tau2: float | None, dead_time: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Build continuous-time transfer function numerator/denominator arrays.

    FOPTD: G(s) = K / (tau1*s + 1) * Pade(L)
    SOPTD: G(s) = K / ((tau1*s + 1)(tau2*s + 1)) * Pade(L)
    """
    if tau2 is not None and tau2 > 0:
        num_p = np.array([gain], dtype=float)
        den_p = np.polymul([tau1, 1.0], [tau2, 1.0])
    else:
        num_p = np.array([gain], dtype=float)
        den_p = np.array([tau1, 1.0], dtype=float)

    if dead_time > 0:
        num_d, den_d = _pade_dead_time(dead_time, _PADE_ORDER)
        num = np.polymul(num_p, num_d)
        den = np.polymul(den_p, den_d)
    else:
        num = num_p
        den = den_p

    return num, den


class ProcessModel:
    """Continuous-time process model simulated step-by-step.

    Uses scipy.signal.cont2discrete to convert the transfer function to
    a discrete-time state-space representation, then advances one sample
    per call to step().
    """

    def __init__(
        self,
        gain: float,
        tau1: float,
        tau2: float | None,
        dead_time: float,
    ) -> None:
        self._gain = gain
        self._tau1 = tau1
        self._tau2 = tau2
        self._dead_time = dead_time
        self._dt: float = 0.0
        self._state: np.ndarray | None = None
        self._Ad: np.ndarray | None = None
        self._Bd: np.ndarray | None = None
        self._Cd: np.ndarray | None = None
        self._Dd: np.ndarray | None = None
        self._pv: float = 0.0

    @classmethod
    def from_preset(cls, preset: ProcessPreset) -> ProcessModel:
        return cls(
            gain=preset.gain, tau1=preset.tau1,
            tau2=preset.tau2, dead_time=preset.dead_time,
        )

    @property
    def pv(self) -> float:
        return self._pv

    def _discretize(self, dt: float) -> None:
        """(Re-)discretize the continuous TF at the given sample period."""
        num, den = _build_tf(self._gain, self._tau1, self._tau2, self._dead_time)
        sys_c = signal.tf2ss(num, den)
        sys_d = signal.cont2discrete(sys_c, dt, method="zoh")
        self._Ad, self._Bd, self._Cd, self._Dd = (
            np.asarray(sys_d[0]),
            np.asarray(sys_d[1]),
            np.asarray(sys_d[2]),
            np.asarray(sys_d[3]),
        )
        n = self._Ad.shape[0]
        if self._state is None or self._state.shape[0] != n:
            self._state = np.zeros((n, 1))
        self._dt = dt

    def step(
        self, co: float, dt: float, pv_limits: tuple[float, float] | None = None,
    ) -> float:
        """Advance one time step. Returns the new PV value.

        ``pv_limits`` saturates the reading at the instrument range. A real
        transmitter cannot report past its span; without a limit this linear
        transfer function happily returns PV = K x CO = 240 %, which is not
        a process, it is an unbounded gain block.

        Only the OUTPUT is clamped -- the state is left alone deliberately.
        This transfer function is always asymptotically stable (every pole
        comes from a positive tau), so the state converges to a finite value
        and cannot wind up behind the limit: drop CO and the reading leaves
        saturation on the very next sample. Back-propagating the clamp into
        the state would instead destroy the model, because the Pade dead-time
        approximation opens with a genuine inverse response that dips below
        the low limit -- re-seeding there zeroes the dynamics every tick and
        the process never responds at all.
        """
        if dt != self._dt or self._Ad is None:
            self._discretize(dt)

        u = np.array([[co]])
        y = self._Cd @ self._state + self._Dd @ u
        self._state = self._Ad @ self._state + self._Bd @ u
        pv = float(y[0, 0])

        if pv_limits is not None:
            lo, hi = pv_limits
            if lo > hi:
                lo, hi = hi, lo
            pv = min(hi, max(lo, pv))

        self._pv = pv
        return self._pv

    def reset(self) -> None:
        """Reset internal state to initial conditions (PV=0)."""
        if self._state is not None:
            self._state[:] = 0.0
        self._pv = 0.0

    def update_parameters(
        self,
        gain: float,
        tau1: float,
        tau2: float | None,
        dead_time: float,
    ) -> None:
        """Change TF parameters in place, preserving the current PV.

        Re-discretizes at the current dt. If the state dimension changes
        (e.g., FOPTD ↔ SOPTD or dead_time crossing zero), the new state
        is seeded via least-squares so that `Cd @ x ≈ previous pv`,
        avoiding a spurious jump to zero on the next step.
        """
        self._gain = gain
        self._tau1 = tau1
        self._tau2 = tau2
        self._dead_time = dead_time
        if self._dt <= 0.0:
            # No discretization yet — first step() will build everything fresh.
            self._Ad = None
            return

        prev_pv = self._pv
        prev_state = self._state
        prev_n = prev_state.shape[0] if prev_state is not None else 0

        num, den = _build_tf(self._gain, self._tau1, self._tau2, self._dead_time)
        sys_c = signal.tf2ss(num, den)
        sys_d = signal.cont2discrete(sys_c, self._dt, method="zoh")
        self._Ad, self._Bd, self._Cd, self._Dd = (
            np.asarray(sys_d[0]),
            np.asarray(sys_d[1]),
            np.asarray(sys_d[2]),
            np.asarray(sys_d[3]),
        )
        new_n = self._Ad.shape[0]
        if prev_state is not None and prev_n == new_n:
            # Same state dimension: reuse state. The basis may differ slightly
            # from the previous TF, but for continuous parameter tweaks this
            # preserves far more continuity than zeroing out.
            self._state = prev_state
        else:
            # Dimension changed — seed with minimum-norm state whose output
            # matches prev_pv: x = Cd^T (Cd Cd^T)^-1 prev_pv
            self._state = np.zeros((new_n, 1))
            try:
                cct = self._Cd @ self._Cd.T
                rhs = np.array([[prev_pv]]) - (self._Dd @ np.array([[0.0]]))
                self._state = self._Cd.T @ np.linalg.solve(cct, rhs)
            except np.linalg.LinAlgError:
                pass
        self._pv = prev_pv
