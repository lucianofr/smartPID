"""Tests for AlarmWorker — verifies alarms are persisted to database."""
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import msgpack
import pytest

from smart_pid_core.application.workers.alarm_worker import AlarmWorker
from smart_pid_domain.enums import AlarmPriority, AlarmType
from smart_pid_domain.models.alarm_config import AlarmTransition


@pytest.fixture
def mock_bus():
    bus = MagicMock()
    sub = MagicMock()
    pub = MagicMock()
    sub.recv.return_value = None
    bus.create_subscriber.return_value = sub
    bus.create_publisher.return_value = pub
    return bus


@pytest.fixture
def mock_alarm_repo():
    repo = AsyncMock()
    repo.insert_alarm.return_value = 1
    repo.mark_cleared.return_value = None
    return repo


class TestPersistAlarm:
    """Test _persist_alarm directly to verify DB integration."""

    @pytest.mark.asyncio
    async def test_triggered_alarm_calls_insert(self, mock_bus, mock_alarm_repo):
        worker = AlarmWorker(
            bus=mock_bus,
            alarm_configs={},
            alarm_repo=mock_alarm_repo,
        )
        now = datetime.now(tz=UTC)
        transition = AlarmTransition(
            controller_id=1,
            alarm_type=AlarmType.HIHI,
            priority=AlarmPriority.CRITICAL,
            transition="TRIGGERED",
            value=95.0,
            limit=90.0,
            timestamp=now,
        )

        await worker._persist_alarm(transition)

        mock_alarm_repo.insert_alarm.assert_awaited_once_with(
            controller_id=1,
            alarm_type=AlarmType.HIHI,
            priority=AlarmPriority.CRITICAL,
            value=95.0,
            limit_value=90.0,
            triggered_at=now,
        )

    @pytest.mark.asyncio
    async def test_cleared_alarm_calls_mark_cleared(self, mock_bus, mock_alarm_repo):
        worker = AlarmWorker(
            bus=mock_bus,
            alarm_configs={},
            alarm_repo=mock_alarm_repo,
        )
        now = datetime.now(tz=UTC)
        transition = AlarmTransition(
            controller_id=1,
            alarm_type=AlarmType.HIHI,
            priority=AlarmPriority.CRITICAL,
            transition="CLEARED",
            value=85.0,
            limit=90.0,
            timestamp=now,
        )

        await worker._persist_alarm(transition)

        mock_alarm_repo.mark_cleared.assert_awaited_once_with(
            controller_id=1,
            alarm_type=AlarmType.HIHI,
            cleared_at=now,
        )
        mock_alarm_repo.insert_alarm.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_persist_without_repo_is_noop(self, mock_bus):
        worker = AlarmWorker(
            bus=mock_bus,
            alarm_configs={},
            alarm_repo=None,
        )
        now = datetime.now(tz=UTC)
        transition = AlarmTransition(
            controller_id=1,
            alarm_type=AlarmType.HIHI,
            priority=AlarmPriority.CRITICAL,
            transition="TRIGGERED",
            value=95.0,
            limit=90.0,
            timestamp=now,
        )

        # Should not raise
        await worker._persist_alarm(transition)

    @pytest.mark.asyncio
    async def test_persist_exception_does_not_propagate(self, mock_bus, mock_alarm_repo):
        mock_alarm_repo.insert_alarm.side_effect = RuntimeError("DB write failed")
        worker = AlarmWorker(
            bus=mock_bus,
            alarm_configs={},
            alarm_repo=mock_alarm_repo,
        )
        now = datetime.now(tz=UTC)
        transition = AlarmTransition(
            controller_id=1,
            alarm_type=AlarmType.HIHI,
            priority=AlarmPriority.CRITICAL,
            transition="TRIGGERED",
            value=95.0,
            limit=90.0,
            timestamp=now,
        )

        # Should not raise — error is logged, not propagated
        await worker._persist_alarm(transition)


class TestAlarmWorkerIntegration:
    """Integration test: AlarmWorker persists alarms to real SQLite."""

    @pytest.mark.asyncio
    async def test_alarm_persisted_to_sqlite(self, tmp_path):
        from smart_pid_core.adapters.outbound.alarm_repo import AlarmRepository
        from smart_pid_core.adapters.outbound.sqlite_repo import SQLiteRepository

        repo = SQLiteRepository(tmp_path / "test.db")
        await repo.initialize()
        alarm_repo = AlarmRepository(repo.session_factory)

        mock_bus = MagicMock()
        mock_bus.create_subscriber.return_value = MagicMock()
        mock_bus.create_publisher.return_value = MagicMock()

        worker = AlarmWorker(
            bus=mock_bus,
            alarm_configs={},
            alarm_repo=alarm_repo,
        )

        now = datetime.now(tz=UTC)
        triggered = AlarmTransition(
            controller_id=1,
            alarm_type=AlarmType.HIHI,
            priority=AlarmPriority.CRITICAL,
            transition="TRIGGERED",
            value=95.0,
            limit=90.0,
            timestamp=now,
        )

        await worker._persist_alarm(triggered)

        active = await alarm_repo.get_active(controller_id=1)
        assert len(active) == 1
        assert active[0]["alarm_type"] == "HIHI"
        assert active[0]["priority"] == "CRITICAL"
        assert active[0]["value"] == 95.0

        # Now clear it
        cleared = AlarmTransition(
            controller_id=1,
            alarm_type=AlarmType.HIHI,
            priority=AlarmPriority.CRITICAL,
            transition="CLEARED",
            value=85.0,
            limit=90.0,
            timestamp=now,
        )

        await worker._persist_alarm(cleared)

        active = await alarm_repo.get_active(controller_id=1)
        assert len(active) == 1
        assert active[0]["cleared_at"] is not None

        await repo.close()


class TestSeedActiveAlarms:
    """Tests for seeding engine state from DB active alarms."""

    def test_seed_active_alarms_sets_engine_state(self, mock_bus):
        from smart_pid_domain.models.alarm_config import AlarmConfig

        config = AlarmConfig(
            lo_enabled=True, lo_value=30.0, lo_priority=AlarmPriority.WARNING,
            deadband_percent=1.0,
        )
        worker = AlarmWorker(bus=mock_bus, alarm_configs={1: config})
        worker.seed_active_alarms([
            {"controller_id": 1, "alarm_type": "LO"},
        ])
        # Engine should have LO as active for controller 1
        state = worker._engine._states.get((1, AlarmType.LO))
        assert state is not None
        assert state.active is True

    def test_seed_skips_invalid_alarm_type(self, mock_bus):
        worker = AlarmWorker(bus=mock_bus, alarm_configs={})
        # Should not raise on invalid alarm_type
        worker.seed_active_alarms([
            {"controller_id": 1, "alarm_type": "INVALID"},
        ])
        assert len(worker._engine._states) == 0

    def test_seeded_alarm_clears_on_evaluate(self, mock_bus):
        """After seeding, engine should generate CLEARED when PV recovers."""
        from smart_pid_domain.models.alarm_config import AlarmConfig

        config = AlarmConfig(
            lo_enabled=True, lo_value=30.0, lo_priority=AlarmPriority.WARNING,
            deadband_percent=0.0,
        )
        worker = AlarmWorker(bus=mock_bus, alarm_configs={1: config})
        worker.seed_active_alarms([
            {"controller_id": 1, "alarm_type": "LO"},
        ])
        # Evaluate with PV above alarm limit
        transitions = worker._engine.evaluate(
            1, pv=50.0, sp=50.0, alarm_config=config, sp_ramping=False,
        )
        cleared = [t for t in transitions if t.alarm_type == AlarmType.LO
                   and t.transition == "CLEARED"]
        assert len(cleared) == 1


class TestAlarmWorkerEnrichment:
    """Tests for controller meta, pv_range, and remove_controller (Bug #6, #9)."""

    def test_alarm_event_includes_controller_name(self, mock_bus):
        """Alarm events must include controller_name and controller_description (Bug #6)."""
        from smart_pid_domain.models.alarm_config import AlarmConfig

        config = AlarmConfig(
            hi_enabled=True, hi_value=80.0, hi_priority=AlarmPriority.WARNING,
        )
        worker = AlarmWorker(bus=mock_bus, alarm_configs={1: config})
        worker.update_controller_meta(1, "TIC-101", "Temp Reactor A")

        assert worker._controller_meta[1] == ("TIC-101", "Temp Reactor A")

    def test_alarm_worker_update_pv_range(self, mock_bus):
        """AlarmWorker must support pv_range updates for span-based deadband."""
        worker = AlarmWorker(bus=mock_bus, alarm_configs={})
        worker.update_pv_range(1, 0.0, 200.0)

        assert worker._pv_ranges[1] == (0.0, 200.0)

    def test_alarm_worker_remove_controller(self, mock_bus):
        """AlarmWorker.remove_controller cleans up config, meta, and pv_range."""
        from smart_pid_domain.models.alarm_config import AlarmConfig

        config = AlarmConfig(
            hi_enabled=True, hi_value=80.0, hi_priority=AlarmPriority.WARNING,
        )
        worker = AlarmWorker(bus=mock_bus, alarm_configs={1: config})
        worker.update_controller_meta(1, "TIC-101", "Temp Reactor A")
        worker.update_pv_range(1, 0.0, 200.0)

        worker.remove_controller(1)

        assert 1 not in worker._alarm_configs
        assert 1 not in worker._controller_meta
        assert 1 not in worker._pv_ranges


class TestOnlyConfiguredAndEnabledAlarmsAreLive:
    """Regression: FIC-101 had no alarms configured yet announced HI at 80.

    ``Configuracao_Alarmes`` is keyed by ``controlador_id`` and SQLite reuses
    ``max(id) + 1``, so a row left behind by a deleted loop was inherited by
    whatever loop next took that id.
    """

    @pytest.mark.asyncio
    async def test_a_row_whose_controller_is_gone_is_not_loaded(self, tmp_path):
        from sqlalchemy import text

        from smart_pid_core.adapters.outbound.sqlite_repo import SQLiteRepository
        from smart_pid_core.application.workers.alarm_worker import load_alarm_configs
        from smart_pid_domain.models.controller import Controller

        repo = SQLiteRepository(tmp_path / "p.spid")
        await repo.initialize()
        try:
            live = await repo.save(Controller(id=0, name="FIC-101"))
            async with repo.session_factory() as s:
                # One row for the live loop, one orphaned by a deleted loop.
                for cid, limit in ((live.id, 90.0), (live.id + 50, 80.0)):
                    await s.execute(
                        text(
                            "INSERT INTO Configuracao_Alarmes"
                            " (controlador_id, tipo_alarme, prioridade, limite, habilitado)"
                            " VALUES (:cid, 'HI', 'WARNING', :lim, 1)"
                        ),
                        {"cid": cid, "lim": limit},
                    )
                await s.commit()

            configs = await load_alarm_configs(repo.session_factory)
            assert set(configs) == {live.id}
            assert configs[live.id].hi_value == 90.0
        finally:
            await repo.close()

    @pytest.mark.asyncio
    async def test_a_controller_with_every_alarm_disabled_gets_no_config(self, tmp_path):
        from sqlalchemy import text

        from smart_pid_core.adapters.outbound.sqlite_repo import SQLiteRepository
        from smart_pid_core.application.workers.alarm_worker import load_alarm_configs
        from smart_pid_domain.models.controller import Controller

        repo = SQLiteRepository(tmp_path / "p.spid")
        await repo.initialize()
        try:
            c = await repo.save(Controller(id=0, name="FIC-101"))
            async with repo.session_factory() as s:
                await s.execute(
                    text(
                        "INSERT INTO Configuracao_Alarmes"
                        " (controlador_id, tipo_alarme, prioridade, limite, habilitado)"
                        " VALUES (:cid, 'HI', 'WARNING', 80.0, 0)"
                    ),
                    {"cid": c.id},
                )
                await s.commit()
            assert await load_alarm_configs(repo.session_factory) == {}
        finally:
            await repo.close()

    def test_disabling_every_alarm_drops_the_live_config(self, mock_bus):
        """Symmetry with load: silencing a loop must take effect now, not at
        the next daemon restart."""
        from smart_pid_domain.models.alarm_config import AlarmConfig

        worker = AlarmWorker(bus=mock_bus, alarm_configs={})
        worker.update_config(7, AlarmConfig(hi_enabled=True, hi_value=80.0))
        assert 7 in worker._alarm_configs

        worker.update_config(7, AlarmConfig(hi_enabled=False, hi_value=80.0))
        assert 7 not in worker._alarm_configs



class TestDeviationSuppressionFromTheWire:
    """The `sp_ramping` flag has to survive the FRAME, not just the engine.

    ``AlarmEngine`` suppressed deviation alarms during an SP ramp from day one,
    but no producer ever put ``sp_ramping`` on ``STATUS.{id}`` (PIDWorker never
    called ``apply_sp_ramp``), so the consumer below always read the ``False``
    default and the suppression never once fired in production.
    """

    @staticmethod
    def _frame(*, sp_ramping: bool | None) -> bytes:
        data = {"controller_id": 1, "pv": 60.0, "sp": 50.0}
        if sp_ramping is not None:
            data["sp_ramping"] = sp_ramping
        return msgpack.packb(data)

    def _dv_events(self, payload: bytes) -> list[dict]:
        from smart_pid_domain.models.alarm_config import AlarmConfig

        config = AlarmConfig(
            dv_hi_enabled=True, dv_hi_value=5.0,
            dv_hi_priority=AlarmPriority.WARNING,
        )
        worker = AlarmWorker(bus=MagicMock(), alarm_configs={1: config})
        sub, pub = MagicMock(), MagicMock()
        # One frame, then stop: recv returning None would spin forever.
        def _recv(timeout_ms: int = 0) -> tuple[bytes, bytes] | None:  # noqa: ARG001
            worker._stop_event.set()
            return (b"STATUS.1", payload)

        sub.recv.side_effect = _recv
        worker._loop(sub, pub)
        return [
            msgpack.unpackb(call.args[1])
            for call in pub.send.call_args_list
            if call.args[0].startswith(b"EVENT.ALARM.")
        ]

    def test_a_ramping_setpoint_suppresses_the_deviation_alarm(self):
        assert self._dv_events(self._frame(sp_ramping=True)) == []

    def test_a_settled_setpoint_still_raises_it(self):
        events = self._dv_events(self._frame(sp_ramping=False))
        assert [(e["alarm_type"], e["transition"]) for e in events] == [
            ("DV_HI", "TRIGGERED"),
        ]

    def test_a_producer_that_omits_the_key_is_treated_as_settled(self):
        """MonitorWorker publishes no `sp_ramping`: monitor mode runs no local
        ramp, so the absent key must mean "not ramping", never "suppress"."""
        events = self._dv_events(self._frame(sp_ramping=None))
        assert [e["alarm_type"] for e in events] == ["DV_HI"]