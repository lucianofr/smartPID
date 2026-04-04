"""PID mode state machine with Foundation Fieldbus cascade handshake.

Manages transitions between 8 operating modes:
OOS, IMan, LO, Man, Auto, Cas, RCas, ROut.

Rules from bloco_pid.md + FF spec:
- Tracking active -> forces LO
- Bad PV -> forces MAN
- Bad/NI BKCAL_IN -> forces IMAN (cascade break)
- SHED timeout -> forces configured shed mode
- Transitions validate against permitted modes
- Man->Auto and Auto->Cas require bumpless transfer
- Cascade handshake: NI -> IR -> IA -> GOOD_CASCADE
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from smart_pid_domain.enums import ControllerMode, InitSubStatus
from smart_pid_domain.models.signal import FFSignal, FFSignalStatus

# Modes that require bumpless transfer when entering
_BUMPLESS_REQUIRED_TARGETS = {ControllerMode.AUTO, ControllerMode.CAS, ControllerMode.RCAS}

# Modes where cascade handshake break applies
_CASCADE_MODES = {ControllerMode.CAS, ControllerMode.RCAS}


@dataclass
class BlockStatus:
    """Current status conditions that may force mode changes."""

    pv: FFSignal = field(default_factory=lambda: FFSignal.good(0.0))
    bkcal_in: FFSignal = field(default_factory=lambda: FFSignal.good(0.0))
    tracking_active: bool = False
    shed_timeout_expired: bool = False
    simulate_active: bool = False


@dataclass(frozen=True)
class CascadeAction:
    """Result of cascade handshake evaluation."""

    force_mode: ControllerMode | None = None
    requires_bumpless: bool = False
    tracking_target: float | None = None
    emit_sub_status: InitSubStatus = InitSubStatus.NONE


@dataclass
class ModeTransition:
    """Result of a mode transition request."""

    accepted: bool
    new_mode: ControllerMode
    requires_bumpless: bool = False
    rejection_reason: str = ""


class ModeManager:
    """Stateless mode transition evaluator with FF cascade handshake."""

    def request_mode(
        self,
        current: ControllerMode,
        target: ControllerMode,
        permitted: set[ControllerMode],
        block_status: BlockStatus,
    ) -> ModeTransition:
        """Evaluate a requested mode transition."""
        if target not in permitted:
            return ModeTransition(
                accepted=False,
                new_mode=current,
                rejection_reason=f"{target.value} not in permitted modes",
            )

        forced = self.evaluate_forced_transitions(current, block_status)
        if forced is not None and forced != target:
            return ModeTransition(
                accepted=False,
                new_mode=forced,
                rejection_reason=f"Forced to {forced.value} by system condition",
            )

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
        3. Bad/NI BKCAL_IN in cascade mode -> IMAN
        4. Shed timeout -> configured shed mode
        """
        if block_status.tracking_active:
            return ControllerMode.LO

        if block_status.pv.status.is_bad:
            return ControllerMode.MAN

        if current in _CASCADE_MODES:
            bkcal_status = block_status.bkcal_in.status
            if bkcal_status.is_bad or bkcal_status.is_not_invited:
                return ControllerMode.IMAN

        if block_status.shed_timeout_expired:
            return shed_mode

        return None

    def evaluate_cascade_handshake(
        self,
        current_mode: ControllerMode,
        bkcal_in: FFSignal,
    ) -> CascadeAction:
        """Evaluate FF cascade handshake based on BKCAL_IN status."""
        sub = bkcal_in.status.sub_status
        is_bad = bkcal_in.status.is_bad

        # BAD or NI while in cascade -> break to IMAN
        if is_bad or sub == InitSubStatus.NI:
            if current_mode in _CASCADE_MODES:
                return CascadeAction(
                    force_mode=ControllerMode.IMAN,
                    emit_sub_status=InitSubStatus.NI,
                )
            return CascadeAction(emit_sub_status=InitSubStatus.NI)

        # IR while in IMAN -> track BKCAL_IN value
        if sub == InitSubStatus.IR and current_mode == ControllerMode.IMAN:
            return CascadeAction(
                tracking_target=bkcal_in.value,
                emit_sub_status=InitSubStatus.IA,
            )

        # GOOD_CASCADE while in IMAN -> transition to CAS
        if sub == InitSubStatus.GOOD_CASCADE and current_mode == ControllerMode.IMAN:
            return CascadeAction(
                force_mode=ControllerMode.CAS,
                requires_bumpless=True,
                emit_sub_status=InitSubStatus.NONE,
            )

        # Normal operation
        return CascadeAction()
