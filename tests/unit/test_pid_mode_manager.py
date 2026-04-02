"""Unit tests for PID mode state machine."""
from __future__ import annotations

import pytest

from smart_pid.domain.models.controller import PIDMode, SignalStatus
from smart_pid.domain.services.pid_mode_manager import (
    BlockStatus,
    ModeManager,
    ModeTransition,
)
from smart_pid.exceptions import InvalidModeTransition


class TestModeTransitions:
    """Test valid and invalid mode transitions."""

    def setup_method(self) -> None:
        self.mgr = ModeManager()
        self.permitted = {PIDMode.OOS, PIDMode.MAN, PIDMode.AUTO, PIDMode.CAS}

    def test_man_to_auto_allowed(self) -> None:
        result = self.mgr.request_mode(
            current=PIDMode.MAN,
            target=PIDMode.AUTO,
            permitted=self.permitted,
            block_status=BlockStatus(),
        )
        assert result.accepted is True
        assert result.new_mode == PIDMode.AUTO
        assert result.requires_bumpless is True

    def test_auto_to_man_allowed(self) -> None:
        result = self.mgr.request_mode(
            current=PIDMode.AUTO,
            target=PIDMode.MAN,
            permitted=self.permitted,
            block_status=BlockStatus(),
        )
        assert result.accepted is True
        assert result.new_mode == PIDMode.MAN

    def test_transition_to_unpermitted_mode_rejected(self) -> None:
        permitted = {PIDMode.MAN, PIDMode.AUTO}
        result = self.mgr.request_mode(
            current=PIDMode.MAN,
            target=PIDMode.CAS,
            permitted=permitted,
            block_status=BlockStatus(),
        )
        assert result.accepted is False
        assert result.rejection_reason == "CAS not in permitted modes"

    def test_auto_to_cas_allowed(self) -> None:
        result = self.mgr.request_mode(
            current=PIDMode.AUTO,
            target=PIDMode.CAS,
            permitted=self.permitted,
            block_status=BlockStatus(),
        )
        assert result.accepted is True
        assert result.new_mode == PIDMode.CAS

    def test_oos_to_man_allowed(self) -> None:
        result = self.mgr.request_mode(
            current=PIDMode.OOS,
            target=PIDMode.MAN,
            permitted=self.permitted,
            block_status=BlockStatus(),
        )
        assert result.accepted is True


class TestForcedTransitions:
    """Test automatic mode changes from system conditions."""

    def setup_method(self) -> None:
        self.mgr = ModeManager()

    def test_bad_pv_forces_manual(self) -> None:
        """Bad PV status forces transition to MAN."""
        status = BlockStatus(pv_status=SignalStatus.BAD)
        forced = self.mgr.evaluate_forced_transitions(
            current=PIDMode.AUTO,
            block_status=status,
        )
        assert forced == PIDMode.MAN

    def test_tracking_active_forces_lo(self) -> None:
        """Active tracking input forces Local Override mode."""
        status = BlockStatus(tracking_active=True)
        forced = self.mgr.evaluate_forced_transitions(
            current=PIDMode.AUTO,
            block_status=status,
        )
        assert forced == PIDMode.LO

    def test_good_pv_no_force(self) -> None:
        """Good PV and no tracking — no forced transition."""
        status = BlockStatus(pv_status=SignalStatus.GOOD)
        forced = self.mgr.evaluate_forced_transitions(
            current=PIDMode.AUTO,
            block_status=status,
        )
        assert forced is None

    def test_shed_timeout_forces_configured_mode(self) -> None:
        """Connection loss timeout forces SHED_OPT mode."""
        status = BlockStatus(shed_timeout_expired=True)
        forced = self.mgr.evaluate_forced_transitions(
            current=PIDMode.AUTO,
            block_status=status,
            shed_mode=PIDMode.MAN,
        )
        assert forced == PIDMode.MAN
