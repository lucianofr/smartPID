"""Unit tests for FF cascade handshake in mode manager."""
from __future__ import annotations

from smart_pid_core.domain.services.pid_mode_manager import (
    BlockStatus,
    CascadeAction,
    ModeManager,
)
from smart_pid_domain.enums import (
    ControllerMode,
    InitSubStatus,
    LimitBits,
    SignalSeverity,
)
from smart_pid_domain.models.signal import FFSignal, FFSignalStatus


class TestCascadeHandshake:
    """Test evaluate_cascade_handshake decision table."""

    def setup_method(self) -> None:
        self.mgr = ModeManager()

    def test_bad_bkcal_in_cas_forces_iman(self) -> None:
        """Slave sends BAD status while in CAS -> force IMAN."""
        bkcal_in = FFSignal.bad(50.0)
        action = self.mgr.evaluate_cascade_handshake(
            current_mode=ControllerMode.CAS,
            bkcal_in=bkcal_in,
        )
        assert action.force_mode == ControllerMode.IMAN
        assert action.emit_sub_status == InitSubStatus.NI

    def test_ni_bkcal_in_cas_forces_iman(self) -> None:
        """Slave sends NI while in CAS -> force IMAN."""
        bkcal_in = FFSignal(
            value=50.0,
            status=FFSignalStatus(sub_status=InitSubStatus.NI),
        )
        action = self.mgr.evaluate_cascade_handshake(
            current_mode=ControllerMode.CAS,
            bkcal_in=bkcal_in,
        )
        assert action.force_mode == ControllerMode.IMAN
        assert action.emit_sub_status == InitSubStatus.NI

    def test_ir_in_iman_stays_iman_and_tracks(self) -> None:
        """Slave sends IR while in IMAN -> stay IMAN, track value."""
        bkcal_in = FFSignal(
            value=72.5,
            status=FFSignalStatus(sub_status=InitSubStatus.IR),
        )
        action = self.mgr.evaluate_cascade_handshake(
            current_mode=ControllerMode.IMAN,
            bkcal_in=bkcal_in,
        )
        assert action.force_mode is None  # Stay in current mode
        assert action.tracking_target == 72.5
        assert action.emit_sub_status == InitSubStatus.IA

    def test_good_cascade_in_iman_forces_cas(self) -> None:
        """Slave sends GOOD_CASCADE while in IMAN -> force CAS."""
        bkcal_in = FFSignal(
            value=72.5,
            status=FFSignalStatus(sub_status=InitSubStatus.GOOD_CASCADE),
        )
        action = self.mgr.evaluate_cascade_handshake(
            current_mode=ControllerMode.IMAN,
            bkcal_in=bkcal_in,
        )
        assert action.force_mode == ControllerMode.CAS
        assert action.requires_bumpless is True
        assert action.emit_sub_status == InitSubStatus.NONE

    def test_good_none_in_auto_no_action(self) -> None:
        """Normal operation in AUTO with GOOD/NONE -> no action."""
        bkcal_in = FFSignal.good(50.0)
        action = self.mgr.evaluate_cascade_handshake(
            current_mode=ControllerMode.AUTO,
            bkcal_in=bkcal_in,
        )
        assert action.force_mode is None
        assert action.tracking_target is None
        assert action.emit_sub_status == InitSubStatus.NONE

    def test_bad_bkcal_in_already_iman_stays(self) -> None:
        """Already in IMAN with BAD -> stay in IMAN, emit NI."""
        bkcal_in = FFSignal.bad(0.0)
        action = self.mgr.evaluate_cascade_handshake(
            current_mode=ControllerMode.IMAN,
            bkcal_in=bkcal_in,
        )
        assert action.force_mode is None
        assert action.emit_sub_status == InitSubStatus.NI

    def test_bad_bkcal_in_rcas_forces_iman(self) -> None:
        """BAD status in RCAS also forces IMAN."""
        bkcal_in = FFSignal.bad(50.0)
        action = self.mgr.evaluate_cascade_handshake(
            current_mode=ControllerMode.RCAS,
            bkcal_in=bkcal_in,
        )
        assert action.force_mode == ControllerMode.IMAN


class TestForcedTransitionsWithFF:
    """Updated forced transitions with BKCAL_IN in BlockStatus."""

    def setup_method(self) -> None:
        self.mgr = ModeManager()

    def test_bad_pv_forces_man(self) -> None:
        """Bad PV status forces MAN — unchanged behavior."""
        status = BlockStatus(
            pv=FFSignal.bad(0.0),
            bkcal_in=FFSignal.good(0.0),
        )
        forced = self.mgr.evaluate_forced_transitions(
            current=ControllerMode.AUTO,
            block_status=status,
        )
        assert forced == ControllerMode.MAN

    def test_tracking_active_forces_lo(self) -> None:
        """Tracking active forces LO — unchanged behavior."""
        status = BlockStatus(
            pv=FFSignal.good(50.0),
            bkcal_in=FFSignal.good(0.0),
            tracking_active=True,
        )
        forced = self.mgr.evaluate_forced_transitions(
            current=ControllerMode.AUTO,
            block_status=status,
        )
        assert forced == ControllerMode.LO

    def test_bad_bkcal_in_forces_iman(self) -> None:
        """Bad BKCAL_IN forces IMAN from CAS."""
        status = BlockStatus(
            pv=FFSignal.good(50.0),
            bkcal_in=FFSignal.bad(0.0),
        )
        forced = self.mgr.evaluate_forced_transitions(
            current=ControllerMode.CAS,
            block_status=status,
        )
        assert forced == ControllerMode.IMAN

    def test_ni_bkcal_in_forces_iman(self) -> None:
        """NI sub-status on BKCAL_IN forces IMAN from CAS."""
        status = BlockStatus(
            pv=FFSignal.good(50.0),
            bkcal_in=FFSignal(
                value=0.0,
                status=FFSignalStatus(sub_status=InitSubStatus.NI),
            ),
        )
        forced = self.mgr.evaluate_forced_transitions(
            current=ControllerMode.CAS,
            block_status=status,
        )
        assert forced == ControllerMode.IMAN

    def test_bad_pv_higher_priority_than_bad_bkcal(self) -> None:
        """Bad PV (forces MAN) has higher priority than bad BKCAL_IN (forces IMAN)."""
        status = BlockStatus(
            pv=FFSignal.bad(0.0),
            bkcal_in=FFSignal.bad(0.0),
        )
        forced = self.mgr.evaluate_forced_transitions(
            current=ControllerMode.CAS,
            block_status=status,
        )
        assert forced == ControllerMode.MAN

    def test_good_signals_no_force(self) -> None:
        """All signals GOOD — no forced transition."""
        status = BlockStatus(
            pv=FFSignal.good(50.0),
            bkcal_in=FFSignal.good(50.0),
        )
        forced = self.mgr.evaluate_forced_transitions(
            current=ControllerMode.AUTO,
            block_status=status,
        )
        assert forced is None
