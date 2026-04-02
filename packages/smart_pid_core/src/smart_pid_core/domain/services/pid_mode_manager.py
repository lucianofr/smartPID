"""PID mode state machine.

Manages transitions between 8 operating modes:
OOS, IMan, LO, Man, Auto, Cas, RCas, ROut.

Rules from bloco_pid.md:
- Bad PV -> forces MAN
- TRK_IN_D active -> forces LO
- SHED timeout -> forces configured shed mode
- Transitions validate against permitted modes
- Man->Auto and Auto->Cas require bumpless transfer
"""
from __future__ import annotations

from dataclasses import dataclass

from smart_pid_domain.enums import ControllerMode, SignalStatus

# Modes that require bumpless transfer when entering
_BUMPLESS_REQUIRED_TARGETS = {ControllerMode.AUTO, ControllerMode.CAS, ControllerMode.RCAS}


@dataclass
class BlockStatus:
    """Current status conditions that may force mode changes."""

    pv_status: SignalStatus = SignalStatus.GOOD
    tracking_active: bool = False
    shed_timeout_expired: bool = False
    simulate_active: bool = False


@dataclass
class ModeTransition:
    """Result of a mode transition request."""

    accepted: bool
    new_mode: ControllerMode
    requires_bumpless: bool = False
    rejection_reason: str = ""


class ModeManager:
    """Stateless mode transition evaluator."""

    def request_mode(
        self,
        current: ControllerMode,
        target: ControllerMode,
        permitted: set[ControllerMode],
        block_status: BlockStatus,
    ) -> ModeTransition:
        """Evaluate a requested mode transition.

        Returns ModeTransition with accepted=True if valid,
        or accepted=False with reason if rejected.
        """
        # Check if target is in permitted modes
        if target not in permitted:
            return ModeTransition(
                accepted=False,
                new_mode=current,
                rejection_reason=f"{target.value} not in permitted modes",
            )

        # Check for forced conditions that override the request
        forced = self.evaluate_forced_transitions(current, block_status)
        if forced is not None and forced != target:
            return ModeTransition(
                accepted=False,
                new_mode=forced,
                rejection_reason=f"Forced to {forced.value} by system condition",
            )

        # Determine if bumpless transfer is needed
        requires_bumpless = (
            target in _BUMPLESS_REQUIRED_TARGETS and current != target
        )

        return ModeTransition(
            accepted=True,
            new_mode=target,
            requires_bumpless=requires_bumpless,
        )

    def evaluate_forced_transitions(
        self,
        current: ControllerMode,
        block_status: BlockStatus,
        shed_mode: ControllerMode = ControllerMode.MAN,
    ) -> ControllerMode | None:
        """Check for conditions that force an automatic mode change.

        Priority order:
        1. Tracking active -> LO
        2. Bad PV -> MAN
        3. Shed timeout -> configured shed mode

        Returns None if no forced transition is needed.
        """
        # Tracking has highest priority
        if block_status.tracking_active:
            return ControllerMode.LO

        # Bad PV forces manual
        if block_status.pv_status == SignalStatus.BAD:
            return ControllerMode.MAN

        # Shed timeout
        if block_status.shed_timeout_expired:
            return shed_mode

        return None
