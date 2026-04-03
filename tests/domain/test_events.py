from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest

from smart_pid_domain.enums import AIEngine, ConnectionState, ControlObjective, SignalStatus
from smart_pid_domain.events import (
    AIActionComputed,
    ControlActionComputed,
    StatsUpdated,
    SystemStateChanged,
    TelemetryReceived,
)
from smart_pid_domain.models.telemetry import TelemetryFrame


class TestTelemetryReceived:
    def test_auto_generates_event_id(self) -> None:
        now = datetime.now(tz=UTC)
        frame = TelemetryFrame(
            controller_id=1, pv=50.0, sp=50.0, co=25.0,
            integral_val=1.0, timestamp=now, status=SignalStatus.GOOD,
        )
        event = TelemetryReceived(controller_id=1, frame=frame)
        assert isinstance(event.event_id, UUID)

    def test_is_frozen(self) -> None:
        now = datetime.now(tz=UTC)
        frame = TelemetryFrame(
            controller_id=1, pv=50.0, sp=50.0, co=25.0,
            integral_val=1.0, timestamp=now, status=SignalStatus.GOOD,
        )
        event = TelemetryReceived(controller_id=1, frame=frame)
        with pytest.raises(AttributeError):
            event.controller_id = 2  # type: ignore[misc]


class TestControlActionComputed:
    def test_construction(self) -> None:
        now = datetime.now(tz=UTC)
        event = ControlActionComputed(
            controller_id=1, co=45.0, integral_val=1.5,
            delta_cv=0.5, timestamp=now,
        )
        assert event.delta_cv == 0.5


class TestAIActionComputed:
    def test_frozen(self):
        event = AIActionComputed(
            controller_id=1,
            gamma=0.5,
            new_ki=1.5,
            engine=AIEngine.FUZZY,
            objective=ControlObjective.SP_TRACKING,
            reasoning="test",
            timestamp=datetime.now(UTC),
        )
        with pytest.raises(AttributeError):
            event.gamma = 0.0  # type: ignore[misc]

    def test_has_event_id(self):
        event = AIActionComputed(
            controller_id=1, gamma=0.5, new_ki=1.5,
            engine=AIEngine.FUZZY, objective=ControlObjective.SP_TRACKING,
            reasoning="test", timestamp=datetime.now(UTC),
        )
        assert event.event_id is not None


class TestStatsUpdated:
    def test_frozen(self):
        event = StatsUpdated(
            controller_id=1, iae=1.0, itae=2.0, mse=0.5,
            std_dev=0.1, total_variation=3.0,
            variability_sp=0.02, variability_range=0.01,
            timestamp=datetime.now(UTC),
        )
        with pytest.raises(AttributeError):
            event.iae = 0.0  # type: ignore[misc]


class TestSystemStateChanged:
    def test_construction(self) -> None:
        event = SystemStateChanged(
            new_state=ConnectionState.RECONNECTING,
            reason="Network timeout",
        )
        assert event.new_state == ConnectionState.RECONNECTING
