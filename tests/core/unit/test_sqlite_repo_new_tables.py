"""Tests for Projeto_Meta and Configuracao_Simulador tables."""
from __future__ import annotations

import pytest

from smart_pid_core.adapters.outbound.sqlite_repo import SQLiteRepository


@pytest.fixture
async def repo(tmp_path):
    """Create a fresh SQLiteRepository for each test."""
    db_path = tmp_path / "test.spid"
    r = SQLiteRepository(db_path)
    await r.initialize()
    yield r
    await r.close()


# ── Projeto_Meta ──────────────────────────────────────────────────────


class TestProjetoMeta:
    async def test_table_exists(self, repo: SQLiteRepository) -> None:
        tables = await repo._get_table_names()
        assert "Projeto_Meta" in tables

    async def test_set_and_get_meta(self, repo: SQLiteRepository) -> None:
        await repo.set_meta("nome", "My Project")
        value = await repo.get_meta("nome")
        assert value == "My Project"

    async def test_get_meta_missing_returns_none(self, repo: SQLiteRepository) -> None:
        value = await repo.get_meta("nonexistent")
        assert value is None

    async def test_set_meta_upserts(self, repo: SQLiteRepository) -> None:
        await repo.set_meta("nome", "First")
        await repo.set_meta("nome", "Second")
        value = await repo.get_meta("nome")
        assert value == "Second"


# ── Configuracao_Simulador ────────────────────────────────────────────


class TestConfiguracaoSimulador:
    async def test_table_exists(self, repo: SQLiteRepository) -> None:
        tables = await repo._get_table_names()
        assert "Configuracao_Simulador" in tables

    async def test_save_and_get_sim_config(self, repo: SQLiteRepository) -> None:
        await repo.save_sim_config(
            controller_id=1, preset="fopdt_default",
            gain=2.0, tau1=10.0, tau2=0.0, dead_time=3.0,
        )
        cfg = await repo.get_sim_config(1)
        assert cfg is not None
        assert cfg["preset"] == "fopdt_default"
        assert cfg["gain"] == 2.0
        assert cfg["tau1"] == 10.0
        assert cfg["tau2"] == 0.0
        assert cfg["dead_time"] == 3.0
        # PID defaults
        assert cfg["pid_enabled"] is False
        assert cfg["pid_kp"] == 1.0
        assert cfg["pid_ti"] == 10.0
        assert cfg["pid_td"] == 0.0
        assert cfg["pid_mode"] == 0

    async def test_save_and_get_sim_config_with_pid(self, repo: SQLiteRepository) -> None:
        await repo.save_sim_config(
            controller_id=1, preset="fopdt_default",
            gain=2.0, tau1=10.0, tau2=0.0, dead_time=3.0,
            pid_enabled=True, pid_kp=2.5, pid_ti=8.0, pid_td=0.5, pid_mode=1,
        )
        cfg = await repo.get_sim_config(1)
        assert cfg is not None
        assert cfg["pid_enabled"] is True
        assert cfg["pid_kp"] == 2.5
        assert cfg["pid_ti"] == 8.0
        assert cfg["pid_td"] == 0.5
        assert cfg["pid_mode"] == 1

    async def test_get_sim_config_missing_returns_none(self, repo: SQLiteRepository) -> None:
        cfg = await repo.get_sim_config(999)
        assert cfg is None

    async def test_save_sim_config_upserts(self, repo: SQLiteRepository) -> None:
        await repo.save_sim_config(
            controller_id=1, preset="fopdt_default",
            gain=2.0, tau1=10.0, tau2=0.0, dead_time=3.0,
        )
        await repo.save_sim_config(
            controller_id=1, preset="sopdt_tank",
            gain=5.0, tau1=20.0, tau2=5.0, dead_time=1.0,
        )
        cfg = await repo.get_sim_config(1)
        assert cfg is not None
        assert cfg["preset"] == "sopdt_tank"
        assert cfg["gain"] == 5.0

    async def test_list_sim_configs(self, repo: SQLiteRepository) -> None:
        await repo.save_sim_config(
            controller_id=1, preset="a", gain=1.0, tau1=1.0, tau2=0.0, dead_time=1.0,
        )
        await repo.save_sim_config(
            controller_id=2, preset="b", gain=2.0, tau1=2.0, tau2=0.0, dead_time=2.0,
        )
        configs = await repo.list_sim_configs()
        assert len(configs) == 2

    async def test_list_sim_configs_empty(self, repo: SQLiteRepository) -> None:
        configs = await repo.list_sim_configs()
        assert configs == []

    async def test_save_and_get_auto_sp_disturbance(self, repo: SQLiteRepository) -> None:
        await repo.save_sim_config(
            controller_id=1, preset="FLOW",
            gain=1.2, tau1=3.0, tau2=0.0, dead_time=1.0,
            auto_sp_enabled=True, auto_sp_min_pct=20.0, auto_sp_max_pct=80.0,
            auto_dist_enabled=True, auto_dist_max_pct=15.0,
        )
        cfg = await repo.get_sim_config(1)
        assert cfg is not None
        assert cfg["auto_sp_enabled"] is True
        assert cfg["auto_sp_min_pct"] == 20.0
        assert cfg["auto_sp_max_pct"] == 80.0
        assert cfg["auto_dist_enabled"] is True
        assert cfg["auto_dist_max_pct"] == 15.0

    async def test_auto_sp_disturbance_defaults(self, repo: SQLiteRepository) -> None:
        await repo.save_sim_config(
            controller_id=1, preset="FLOW",
            gain=1.2, tau1=3.0, tau2=0.0, dead_time=1.0,
        )
        cfg = await repo.get_sim_config(1)
        assert cfg is not None
        assert cfg["auto_sp_enabled"] is False
        assert cfg["auto_sp_min_pct"] == 30.0
        assert cfg["auto_sp_max_pct"] == 70.0
        assert cfg["auto_dist_enabled"] is False
        assert cfg["auto_dist_max_pct"] == 10.0

    async def test_every_field_the_adapter_emits_survives_the_round_trip(
        self, repo: SQLiteRepository,
    ) -> None:
        """The whole config dict must round-trip, not just the fields we remembered.

        ``auto_sp_period_s`` and ``auto_dist_period_s`` were emitted by
        ``SimulatorAdapter.get_config_dict`` but had no column, no INSERT slot and
        no row mapping, so ``load_sim_config``'s ``cfg.get(..., 30.0)`` silently
        substituted the default and an operator's excitation period never
        survived a restart. Nothing failed; the value just evaporated.

        Driving this from the adapter's own dict is the point: a field added there
        later cannot pass this test without a matching column.
        """
        from unittest.mock import MagicMock, patch

        from smart_pid_core.adapters.inbound.sim_persistence import persist_sim_config
        from smart_pid_core.adapters.inbound.simulator_adapter import SimulatorAdapter
        from smart_pid_core.config import CoreSettings
        from smart_pid_domain.dtos.simulator import AutoDisturbanceRequest, AutoSPRequest

        settings = CoreSettings(
            jwt_secret="test-secret-key-minimum-32-bytes!",
            simulator_enabled=True,
        )  # type: ignore[call-arg]
        with patch(
            "smart_pid_core.adapters.inbound.simulator_adapter.OPCUAServer",
            return_value=MagicMock(controller_node_ids={}, is_running=False),
        ):
            adapter = SimulatorAdapter(settings=settings)
            try:
                adapter.register_controller(1)
                adapter.set_parameters(1, gain=1.2, tau1=22.2, tau2=10.5, dead_time=5.1)
                adapter.set_pid_params(1, kp=0.8, ti=37.0, td=2.5)
                adapter.set_pid_mode(1, 1)
                adapter.set_pid_sp(1, 61.5)
                # Well above the settling floor, so the clamp leaves it alone and
                # the value under test is the one the operator asked for.
                adapter.set_auto_sp(
                    1,
                    AutoSPRequest(
                        enabled=True, sp_min_pct=15.0, sp_max_pct=85.0, period_s=600.0,
                    ),
                )
                adapter.set_auto_disturbance(
                    1,
                    AutoDisturbanceRequest(
                        enabled=True, max_amplitude_pct=12.5, period_s=45.0,
                    ),
                )
                saved = adapter.get_config_dict(1)

                class _SyncAdapterAsClient:
                    """Async shim: drives persist_sim_config's SimulatorClient-shaped
                    contract straight off a real SimulatorAdapter, so this test still
                    exercises the adapter's actual field set (see docstring above) —
                    the round-trip under test is repo persistence, not the RPC hop."""

                    async def get_config_dict(self, controller_id: int) -> dict:
                        return adapter.get_config_dict(controller_id)

                assert await persist_sim_config(_SyncAdapterAsClient(), repo, 1) is True
            finally:
                adapter.stop()

        loaded = await repo.get_sim_config(1)
        assert loaded is not None
        # `controller_id` is the adapter's key, `controlador_id` the column's.
        dropped = {
            key
            for key in saved
            if key != "controller_id" and key not in loaded
        }
        assert dropped == set(), f"fields lost between adapter and DB: {sorted(dropped)}"
        for key, value in saved.items():
            if key == "controller_id":
                continue
            assert loaded[key] == value, f"{key}: saved {value!r}, loaded {loaded[key]!r}"


# ── reopen ────────────────────────────────────────────────────────────


class TestReopen:
    async def test_reopen_switches_database(self, repo: SQLiteRepository, tmp_path) -> None:
        await repo.set_meta("nome", "Original")
        new_path = tmp_path / "new.spid"
        await repo.reopen(new_path)
        # New DB should not have the old meta
        value = await repo.get_meta("nome")
        assert value is None
        # But tables should exist
        tables = await repo._get_table_names()
        assert "Projeto_Meta" in tables

    async def test_reopen_old_db_intact(self, repo: SQLiteRepository, tmp_path) -> None:
        old_path = repo._db_path
        await repo.set_meta("nome", "Original")
        new_path = tmp_path / "new.spid"
        await repo.reopen(new_path)
        # Reopen old DB to verify data persisted
        await repo.reopen(old_path)
        value = await repo.get_meta("nome")
        assert value == "Original"
