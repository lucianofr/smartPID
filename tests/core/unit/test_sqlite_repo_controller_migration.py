"""Regression tests for the Controladores / Configuracao_Alarmes forward migration.

Both tables gained columns after real .spid files were already on disk:

  * ``Controladores`` gained ``node_id_mode_target``, ``node_id_mode_actual``
    and ``mode_int_map`` with the mode-tag feature. ``_DDL`` was updated but
    ``_CONTROLADORES_ADDED_COLUMNS`` was not, so ``CREATE TABLE IF NOT EXISTS``
    left the old table untouched and the first ``save()`` against a pre-existing
    project died with ``table Controladores has no column named
    node_id_mode_target`` — surfacing as a 500 on ``POST /controllers``.

  * ``Configuracao_Alarmes`` gained ``delay_on_s``/``delay_off_s``, which
    ``AlarmRepository`` names in both its SELECT and its INSERT, so a stale file
    failed every read and write of a controller's alarm config.

The legacy fixtures are derived from the live ``_DDL`` minus exactly those
columns: that is the on-disk shape of every project created before the feature
landed, and deriving it keeps the fixture from rotting when unrelated columns
are added later.
"""
from __future__ import annotations

import re
import sqlite3
from typing import TYPE_CHECKING

import pytest

from smart_pid_core.adapters.outbound.alarm_repo import AlarmRepository
from smart_pid_core.adapters.outbound.sqlite_repo import _DDL, SQLiteRepository
from smart_pid_domain.models.controller import Controller, TagBindings

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.asyncio

_MODE_COLUMNS = ("node_id_mode_target", "node_id_mode_actual", "mode_int_map")
_DELAY_COLUMNS = ("delay_on_s", "delay_off_s")


def _ddl_without(*columns: str) -> str:
    """Return ``_DDL`` with the given column definitions removed.

    Reproduces the generation of the schema that predates *columns*.
    """
    dropped = "|".join(re.escape(c) for c in columns)
    return re.sub(rf"^\s*(?:{dropped})\s+[^\n]*\n", "", _DDL, flags=re.MULTILINE)


def _build_legacy_db(path: Path) -> None:
    con = sqlite3.connect(path)
    try:
        con.executescript(_ddl_without(*_MODE_COLUMNS, *_DELAY_COLUMNS))
        con.commit()
    finally:
        con.close()


def _columns(path: Path, table: str) -> list[str]:
    con = sqlite3.connect(path)
    try:
        return [r[1] for r in con.execute(f"PRAGMA table_info({table})")]
    finally:
        con.close()


class TestLegacyControllerSchemaMigration:
    """A stale .spid must be brought forward to the current DDL on open."""

    async def test_legacy_db_gains_the_mode_and_delay_columns(
        self, tmp_path: Path,
    ) -> None:
        db_path = tmp_path / "legacy.spid"
        _build_legacy_db(db_path)
        assert "node_id_mode_target" not in _columns(db_path, "Controladores"), (
            "fixture must start stale"
        )
        assert "delay_on_s" not in _columns(db_path, "Configuracao_Alarmes"), (
            "fixture must start stale"
        )

        repo = SQLiteRepository(db_path)
        await repo.initialize()
        try:
            ctrl_cols = _columns(db_path, "Controladores")
            alarm_cols = _columns(db_path, "Configuracao_Alarmes")
        finally:
            await repo.close()

        assert [c for c in _MODE_COLUMNS if c not in ctrl_cols] == []
        assert [c for c in _DELAY_COLUMNS if c not in alarm_cols] == []

    async def test_save_controller_succeeds_on_migrated_legacy_db(
        self, tmp_path: Path,
    ) -> None:
        """This is the exact call that raised 'no column named node_id_mode_target'."""
        db_path = tmp_path / "legacy_save.spid"
        _build_legacy_db(db_path)

        repo = SQLiteRepository(db_path)
        await repo.initialize()
        try:
            saved = await repo.save(
                Controller(
                    id=0,
                    name="TIC-900",
                    tag_bindings=TagBindings(
                        node_id_mode_target="ns=2;i=9",
                        node_id_mode_actual="ns=2;i=8",
                        mode_int_map={"MAN": 0, "AUTO": 1},
                    ),
                ),
            )
            reloaded = await repo.get(saved.id)
        finally:
            await repo.close()

        assert reloaded.tag_bindings.node_id_mode_target == "ns=2;i=9"
        assert reloaded.tag_bindings.node_id_mode_actual == "ns=2;i=8"
        assert reloaded.tag_bindings.mode_int_map == {"MAN": 0, "AUTO": 1}

    async def test_alarm_config_round_trips_on_migrated_legacy_db(
        self, tmp_path: Path,
    ) -> None:
        db_path = tmp_path / "legacy_alarms.spid"
        _build_legacy_db(db_path)

        repo = SQLiteRepository(db_path)
        await repo.initialize()
        try:
            ctrl = await repo.save(Controller(id=0, name="TIC-901"))
            alarms = AlarmRepository(repo.session_factory)
            await alarms.save_alarm_config(
                ctrl.id,
                [
                    {
                        "alarm_type": "HI",
                        "priority": "WARNING",
                        "limit": 80.0,
                        "enabled": True,
                        "deadband": 1.0,
                        "delay_on_s": 3.0,
                        "delay_off_s": 5.0,
                    },
                ],
            )
            config = await alarms.get_alarm_config(ctrl.id)
        finally:
            await repo.close()

        assert len(config) == 1
        assert config[0]["delay_on_s"] == 3.0
        assert config[0]["delay_off_s"] == 5.0

    async def test_migration_is_idempotent_and_keeps_existing_rows(
        self, tmp_path: Path,
    ) -> None:
        """ALTER TABLE ADD COLUMN must keep old rows and default the new columns."""
        db_path = tmp_path / "legacy_rows.spid"
        _build_legacy_db(db_path)
        con = sqlite3.connect(db_path)
        con.execute("INSERT INTO Controladores (nome) VALUES ('legacy-loop')")
        con.commit()
        con.close()

        repo = SQLiteRepository(db_path)
        await repo.initialize()
        await repo.close()

        # Second open must be a no-op, not a duplicate-column error.
        repo2 = SQLiteRepository(db_path)
        await repo2.initialize()
        try:
            reloaded = await repo2.get(1)
        finally:
            await repo2.close()

        assert reloaded.name == "legacy-loop"
        assert reloaded.tag_bindings.node_id_mode_target == ""
        assert reloaded.tag_bindings.mode_int_map == {}
