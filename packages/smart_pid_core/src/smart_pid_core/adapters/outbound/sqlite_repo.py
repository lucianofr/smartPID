"""SQLite-backed Controller repository adapter (SQLAlchemy 2.0 async, engine A)."""
from __future__ import annotations

import json
from collections.abc import Mapping  # noqa: TC003
from pathlib import Path
from typing import TYPE_CHECKING

from sqlalchemy import func, insert, text, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from smart_pid_core.adapters.outbound.db_engine import create_sqlite_engine
from smart_pid_core.adapters.outbound.db_models import controladores
from smart_pid_domain.enums import (
    AIEngine,
    ControllerMode,
    ControlObjective,
    ExecutionMode,
    IntegralType,
    PIDStructure,
    ProcessSpeed,
    ProcessType,
    TrackOpt,
)
from smart_pid_domain.models.controller import (
    AIConfig,
    Controller,
    ControlOpts,
    IOOpts,
    PIDParams,
    ScaleConfig,
    StatusOpts,
    TagBindings,
)

if TYPE_CHECKING:
    import aiosqlite

_DDL = """
CREATE TABLE IF NOT EXISTS Controladores (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    nome                TEXT    NOT NULL,
    descricao           TEXT    NOT NULL DEFAULT '',
    modo_execucao       TEXT    NOT NULL DEFAULT 'DDC',
    scan_rate_s         REAL    NOT NULL DEFAULT 1.0,
    tss_s               REAL    NOT NULL DEFAULT 60.0,
    -- PID params
    kp_manual           REAL    NOT NULL DEFAULT 1.0,
    ki_inicial          REAL    NOT NULL DEFAULT 10.0,
    kd_manual           REAL    NOT NULL DEFAULT 0.0,
    alpha               REAL    NOT NULL DEFAULT 0.125,
    deadband            REAL    NOT NULL DEFAULT 0.0,
    -- PID structure
    pid_structure       TEXT    NOT NULL DEFAULT 'ISA',
    integral_type       TEXT    NOT NULL DEFAULT 'TIME_TI',
    -- Scale
    pv_min              REAL    NOT NULL DEFAULT 0.0,
    pv_max              REAL    NOT NULL DEFAULT 100.0,
    pv_unit             TEXT    NOT NULL DEFAULT '',
    co_min              REAL    NOT NULL DEFAULT 0.0,
    co_max              REAL    NOT NULL DEFAULT 100.0,
    co_unit             TEXT    NOT NULL DEFAULT '',
    -- Tag bindings
    node_id_pv          TEXT    NOT NULL DEFAULT '',
    node_id_sp          TEXT    NOT NULL DEFAULT '',
    node_id_co          TEXT    NOT NULL DEFAULT '',
    node_id_integral    TEXT    NOT NULL DEFAULT '',
    node_id_bkcal_in    TEXT    NOT NULL DEFAULT '',
    node_id_bkcal_out   TEXT    NOT NULL DEFAULT '',
    node_id_kp          TEXT    NOT NULL DEFAULT '',
    node_id_ti          TEXT    NOT NULL DEFAULT '',
    node_id_td          TEXT    NOT NULL DEFAULT '',
    node_id_mode_target TEXT    NOT NULL DEFAULT '',
    node_id_mode_actual TEXT    NOT NULL DEFAULT '',
    node_id_enabled     TEXT    NOT NULL DEFAULT '',
    mode_int_map        TEXT    NOT NULL DEFAULT '{}',
    -- SP limits
    sp_hi_lim           REAL    NOT NULL DEFAULT 100.0,
    sp_lo_lim           REAL    NOT NULL DEFAULT 0.0,
    sp_rate_up          REAL    NOT NULL DEFAULT 0.0,
    sp_rate_dn          REAL    NOT NULL DEFAULT 0.0,
    -- Output limits
    out_hi_lim          REAL    NOT NULL DEFAULT 100.0,
    out_lo_lim          REAL    NOT NULL DEFAULT 0.0,
    -- ARW limits
    arw_hi_lim          REAL    NOT NULL DEFAULT 100.0,
    arw_lo_lim          REAL    NOT NULL DEFAULT 0.0,
    -- Filter
    pv_ftime            REAL    NOT NULL DEFAULT 0.0,
    sp_ftime            REAL    NOT NULL DEFAULT 0.0,
    low_cut             REAL    NOT NULL DEFAULT 0.0,
    -- Shed
    shed_opt            TEXT    NOT NULL DEFAULT 'MAN',
    shed_time_s         REAL    NOT NULL DEFAULT 10.0,
    -- Modes
    permitted_modes     TEXT    NOT NULL DEFAULT 'MAN,AUTO',
    mode_normal         TEXT    NOT NULL DEFAULT 'AUTO',
    -- Control opts (boolean flags as integers)
    no_out_limits_in_manual         INTEGER NOT NULL DEFAULT 0,
    obey_sp_limits_if_cas           INTEGER NOT NULL DEFAULT 0,
    track_in_manual                 INTEGER NOT NULL DEFAULT 0,
    track_enable                    INTEGER NOT NULL DEFAULT 0,
    direct_acting                   INTEGER NOT NULL DEFAULT 0,
    sp_track_retained_target        INTEGER NOT NULL DEFAULT 0,
    ctrl_sp_pv_track_in_lo_or_iman  INTEGER NOT NULL DEFAULT 0,
    sp_pv_track_in_rout             INTEGER NOT NULL DEFAULT 0,
    ctrl_sp_pv_track_in_man         INTEGER NOT NULL DEFAULT 0,
    use_pv_for_bkcal_out            INTEGER NOT NULL DEFAULT 0,
    bypass_enable                   INTEGER NOT NULL DEFAULT 0,
    -- IO opts
    low_cutoff                      INTEGER NOT NULL DEFAULT 0,
    target_to_man_if_fault          INTEGER NOT NULL DEFAULT 0,
    fault_state_to_value            INTEGER NOT NULL DEFAULT 0,
    increase_to_close               INTEGER NOT NULL DEFAULT 0,
    io_sp_pv_track_in_lo_or_iman    INTEGER NOT NULL DEFAULT 0,
    io_sp_pv_track_in_man           INTEGER NOT NULL DEFAULT 0,
    -- Status opts
    bad_if_limited                  INTEGER NOT NULL DEFAULT 0,
    use_uncertain_as_good           INTEGER NOT NULL DEFAULT 1,
    -- Track opt
    track_opt           TEXT    NOT NULL DEFAULT 'ALWAYS_USE_VALUE',
    -- Process type
    process_type        TEXT    NOT NULL DEFAULT 'SELF_REGULATING',
    -- AI config
    ai_engine           TEXT    NOT NULL DEFAULT 'NONE',
    objetivo_controle   TEXT    NOT NULL DEFAULT 'DISTURBANCE_REJECTION',
    process_speed       TEXT    NOT NULL DEFAULT 'MEDIUM',
    tempo_morto_l       REAL    NOT NULL DEFAULT 1.0,
    ai_limit_min        REAL    NOT NULL DEFAULT 1.0,
    ai_limit_max        REAL    NOT NULL DEFAULT 10.0,
    -- ENABLE_OPTIMIZER: master enable for the online tuning optimizer
    optimization_enabled INTEGER NOT NULL DEFAULT 1,
    stability_band_pct  REAL,
    -- Surge Level safe-band tuning (NULL bounds → engine default 20-80 %)
    sl_band_lo_pct      REAL,
    sl_band_hi_pct      REAL,
    sl_error_small_pct  REAL    NOT NULL DEFAULT 5.0,
    sl_co_ramp_max_pct_min REAL NOT NULL DEFAULT 10.0,
    -- Timestamps
    criado_em           TEXT    NOT NULL DEFAULT (datetime('now')),
    atualizado_em       TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS Configuracao_Alarmes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    controlador_id  INTEGER NOT NULL REFERENCES Controladores(id) ON DELETE CASCADE,
    tipo_alarme     TEXT    NOT NULL,
    prioridade      TEXT    NOT NULL DEFAULT 'WARNING',
    limite          REAL    NOT NULL DEFAULT 0.0,
    habilitado      INTEGER NOT NULL DEFAULT 1,
    histerese       REAL    NOT NULL DEFAULT 0.0,
    delay_on_s      REAL    NOT NULL DEFAULT 0.0,
    delay_off_s     REAL    NOT NULL DEFAULT 0.0,
    mensagem        TEXT    NOT NULL DEFAULT '',
    criado_em       TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS Log_Processo (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    controlador_id  INTEGER NOT NULL,
    timestamp       TEXT    NOT NULL,
    pv              REAL    NOT NULL,
    sp              REAL    NOT NULL,
    co              REAL    NOT NULL,
    integral_val    REAL    NOT NULL DEFAULT 0.0
);

CREATE INDEX IF NOT EXISTS idx_log_processo_ctrl_ts
    ON Log_Processo (controlador_id, timestamp);

CREATE TABLE IF NOT EXISTS Log_Sintonia_IA (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    controlador_id  INTEGER NOT NULL REFERENCES Controladores(id) ON DELETE CASCADE,
    timestamp       TEXT    NOT NULL DEFAULT (datetime('now')),
    motor           TEXT    NOT NULL DEFAULT 'NONE',
    kp_antes        REAL,
    ki_antes        REAL,
    kd_antes        REAL,
    kp_depois       REAL,
    ki_depois       REAL,
    kd_depois       REAL,
    objetivo        TEXT,
    metrica         REAL,
    aprovado        INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS Log_Auditoria (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id      INTEGER,
    username        TEXT    NOT NULL DEFAULT '',
    timestamp       TEXT    NOT NULL DEFAULT (datetime('now')),
    acao            TEXT    NOT NULL,
    entidade        TEXT    NOT NULL DEFAULT '',
    entidade_id     INTEGER,
    detalhe         TEXT    NOT NULL DEFAULT '',
    ip_origem       TEXT    NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS Modelos_IA (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    controlador_id  INTEGER NOT NULL REFERENCES Controladores(id) ON DELETE CASCADE,
    algoritmo       TEXT    NOT NULL DEFAULT 'SAC',
    episodios       INTEGER NOT NULL DEFAULT 0,
    reward_medio    REAL    NOT NULL DEFAULT 0.0,
    caminho_modelo  TEXT    NOT NULL DEFAULT '',
    criado_em       TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS Log_Alarmes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    controlador_id  INTEGER NOT NULL,
    timestamp       TEXT    NOT NULL DEFAULT (datetime('now')),
    tipo_alarme     TEXT    NOT NULL,
    prioridade      TEXT    NOT NULL DEFAULT 'WARNING',
    valor           REAL,
    limite          REAL,
    cleared_at      TEXT,
    reconhecido     INTEGER NOT NULL DEFAULT 0,
    reconhecido_por TEXT,
    reconhecido_em  TEXT
);

CREATE TABLE IF NOT EXISTS Projeto_Meta (
    chave TEXT PRIMARY KEY,
    valor TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS Log_System_Events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       TEXT    NOT NULL DEFAULT (datetime('now')),
    source          TEXT    NOT NULL,
    severity        TEXT    NOT NULL CHECK(severity IN ('CRITICAL','WARNING','INFO')),
    message         TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sysevents_timestamp ON Log_System_Events(timestamp);
CREATE INDEX IF NOT EXISTS idx_sysevents_severity ON Log_System_Events(severity);

CREATE TABLE IF NOT EXISTS Configuracao_Simulador (
    controlador_id    INTEGER PRIMARY KEY REFERENCES Controladores(id) ON DELETE CASCADE,
    preset            TEXT NOT NULL DEFAULT 'fopdt_default',
    gain              REAL NOT NULL,
    tau1              REAL NOT NULL,
    tau2              REAL NOT NULL,
    dead_time         REAL NOT NULL,
    pid_enabled       INTEGER NOT NULL DEFAULT 0,
    pid_kp            REAL NOT NULL DEFAULT 1.0,
    pid_ti            REAL NOT NULL DEFAULT 10.0,
    pid_td            REAL NOT NULL DEFAULT 0.0,
    pid_mode          INTEGER NOT NULL DEFAULT 0,
    auto_sp_enabled   INTEGER NOT NULL DEFAULT 0,
    auto_sp_min_pct   REAL NOT NULL DEFAULT 30.0,
    auto_sp_max_pct   REAL NOT NULL DEFAULT 70.0,
    auto_dist_enabled INTEGER NOT NULL DEFAULT 0,
    auto_dist_max_pct REAL NOT NULL DEFAULT 10.0,
    pid_sp            REAL NOT NULL DEFAULT 50.0
);
"""

# ----------------------------------------------------------------------
# Forward migrations for pre-existing .spid files
#
# Any column added to _DDL after a project file could already exist MUST be
# repeated here with the SAME default, because CREATE TABLE IF NOT EXISTS is a
# no-op on an existing table. Applied by _apply_migrations() on every
# open/reopen; see _add_missing_columns() for the idempotency contract.
# ----------------------------------------------------------------------

_CONTROLADORES_ADDED_COLUMNS: tuple[tuple[str, str], ...] = (
    ("node_id_bkcal_in", "TEXT NOT NULL DEFAULT ''"),
    ("node_id_bkcal_out", "TEXT NOT NULL DEFAULT ''"),
    ("node_id_kp", "TEXT NOT NULL DEFAULT ''"),
    ("node_id_ti", "TEXT NOT NULL DEFAULT ''"),
    ("node_id_td", "TEXT NOT NULL DEFAULT ''"),
    # AIConfig RL-specific columns + ENABLE_OPTIMIZER master flag
    ("rl_fallback_kp", "REAL NOT NULL DEFAULT 0.6"),
    ("rl_fallback_kd", "REAL NOT NULL DEFAULT 0.2"),
    ("rl_learning_rate", "REAL NOT NULL DEFAULT 0.0003"),
    ("rl_train_interval", "INTEGER NOT NULL DEFAULT 32"),
    ("optimization_enabled", "INTEGER NOT NULL DEFAULT 1"),
    # scan_rate_s is normally created by _migrate_scan_rate() (which converts
    # the legacy ms value); this entry only covers a file that has neither.
    ("scan_rate_s", "REAL NOT NULL DEFAULT 1.0"),
    ("tss_s", "REAL NOT NULL DEFAULT 60.0"),
    # PLC process-running gate and the per-loop optimizer stability band
    ("node_id_enabled", "TEXT NOT NULL DEFAULT ''"),
    ("stability_band_pct", "REAL"),
    # Surge Level safe-band tuning; NULL bounds mean "engine default 20-80 %".
    ("sl_band_lo_pct", "REAL"),
    ("sl_band_hi_pct", "REAL"),
    ("sl_error_small_pct", "REAL NOT NULL DEFAULT 5.0"),
    ("sl_co_ramp_max_pct_min", "REAL NOT NULL DEFAULT 10.0"),
)

# Configuracao_Simulador shipped in three generations: 6 columns, then +pid_*
# (11), then +auto_*/pid_sp (17). The pid_* group was added to _DDL without a
# matching back-fill, so gen1 files hit "no column named pid_enabled" on the
# save_sim_config INSERT. Every column that INSERT names is listed here.
_SIM_ADDED_COLUMNS: tuple[tuple[str, str], ...] = (
    ("pid_enabled", "INTEGER NOT NULL DEFAULT 0"),
    ("pid_kp", "REAL NOT NULL DEFAULT 1.0"),
    ("pid_ti", "REAL NOT NULL DEFAULT 10.0"),
    ("pid_td", "REAL NOT NULL DEFAULT 0.0"),
    ("pid_mode", "INTEGER NOT NULL DEFAULT 0"),
    ("auto_sp_enabled", "INTEGER NOT NULL DEFAULT 0"),
    ("auto_sp_min_pct", "REAL NOT NULL DEFAULT 30.0"),
    ("auto_sp_max_pct", "REAL NOT NULL DEFAULT 70.0"),
    ("auto_dist_enabled", "INTEGER NOT NULL DEFAULT 0"),
    ("auto_dist_max_pct", "REAL NOT NULL DEFAULT 10.0"),
    ("pid_sp", "REAL NOT NULL DEFAULT 50.0"),
)


class SQLiteRepository:
    """SQLite-backed implementation of ControllerRepository.

    Owns engine A (active .spid, main loop) and the .spid session factory.
    The session factory's OBJECT IDENTITY is stable across reopen(): it is
    re-bound in place, so injected copies held by other repositories never
    go stale (this is what fixes the SystemEventRepository bug).
    """

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self.engine: AsyncEngine  # created by initialize()
        self.session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
            expire_on_commit=False,
        )

    @property
    def db_path(self) -> Path:
        """Filesystem path of the active .spid file."""
        return self._db_path

    async def initialize(self) -> None:
        """Create engine A, run DDL bootstrap + back-fill (every open/reopen)."""
        self.engine = create_sqlite_engine(self._db_path)
        self.session_factory.configure(bind=self.engine)
        await self._bootstrap()


    async def _bootstrap(self) -> None:
        """Run CREATE TABLE IF NOT EXISTS + idempotent add-column back-fill.

        Executed through the raw aiosqlite driver connection (executescript
        needs script support), exactly as before the port. Old .spid files
        depend on this running on every open/reopen.
        """
        async with self.engine.connect() as conn:
            raw = await conn.get_raw_connection()
            driver = raw.driver_connection  # the real aiosqlite.Connection
            await driver.executescript(_DDL)
            await self._apply_migrations(driver)
            await driver.commit()

    @staticmethod
    async def _table_columns(driver: aiosqlite.Connection, table: str) -> set[str]:
        """Return the column names currently present on *table* (empty if absent)."""
        cursor = await driver.execute(f"PRAGMA table_info({table})")
        return {row[1] for row in await cursor.fetchall()}

    async def _add_missing_columns(
        self,
        driver: aiosqlite.Connection,
        table: str,
        columns: tuple[tuple[str, str], ...],
    ) -> None:
        """Idempotently ``ADD COLUMN`` every entry of *columns* not yet present.

        Presence is decided from ``PRAGMA table_info`` rather than by swallowing
        the resulting "duplicate column name" error, so re-running on an
        already-current file is a no-op *and* a genuine ALTER failure still
        propagates instead of being silently lost.
        """
        present = await self._table_columns(driver, table)
        for name, definition in columns:
            if name in present:
                continue
            await driver.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")

    async def _apply_migrations(self, driver: aiosqlite.Connection) -> None:
        """Bring a pre-existing .spid forward to the current ``_DDL``.

        ``CREATE TABLE IF NOT EXISTS`` leaves an older table untouched, so every
        column added to ``_DDL`` after a project file was created must also be
        listed here. Additive ``ALTER TABLE ADD COLUMN`` only, with defaults
        identical to ``_DDL``, and safe to re-run on a current file.
        """
        # scan_rate_ms → scan_rate_s must run BEFORE the declarative pass below
        # would add scan_rate_s with its plain default, or the ms→s conversion
        # is silently skipped.
        await self._migrate_scan_rate(driver)
        await self._add_missing_columns(driver, "Controladores", _CONTROLADORES_ADDED_COLUMNS)
        await self._add_missing_columns(
            driver, "Configuracao_Simulador", _SIM_ADDED_COLUMNS,
        )

    async def _migrate_scan_rate(self, driver: aiosqlite.Connection) -> None:
        """Convert a legacy ``scan_rate_ms`` column into ``scan_rate_s``."""
        col_names = await self._table_columns(driver, "Controladores")
        if "scan_rate_ms" in col_names and "scan_rate_s" not in col_names:
            await driver.execute(
                "ALTER TABLE Controladores ADD COLUMN scan_rate_s REAL NOT NULL DEFAULT 1.0"
            )
            await driver.execute(
                "UPDATE Controladores SET scan_rate_s = scan_rate_ms / 1000.0"
            )

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    async def save(self, controller: Controller) -> Controller:
        """INSERT (id==0) or UPDATE (id>0). Returns Controller with assigned id."""
        if controller.id == 0:
            return await self._insert(controller)
        await self._update(controller)
        return controller

    async def get(self, controller_id: int) -> Controller:
        """Return Controller or raise KeyError."""
        async with self.session_factory() as session:
            result = await session.execute(
                text("SELECT * FROM Controladores WHERE id = :cid"),
                {"cid": controller_id},
            )
            row = result.mappings().first()
        if row is None:
            raise KeyError(controller_id)
        return self._row_to_controller(row)

    async def list_all(self) -> list[Controller]:
        """Return all controllers."""
        async with self.session_factory() as session:
            result = await session.execute(
                text("SELECT * FROM Controladores ORDER BY id"),
            )
            rows = result.mappings().all()
        return [self._row_to_controller(r) for r in rows]

    async def delete(self, controller_id: int) -> None:
        """Delete controller or raise KeyError."""
        async with self.session_factory() as session:
            found = (
                await session.execute(
                    text("SELECT id FROM Controladores WHERE id = :cid"),
                    {"cid": controller_id},
                )
            ).first()
            if found is None:
                raise KeyError(controller_id)
            await session.execute(
                text("DELETE FROM Controladores WHERE id = :cid"),
                {"cid": controller_id},
            )
            await session.commit()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _insert(self, c: Controller) -> Controller:
        params = self._controller_to_params(c)
        async with self.session_factory() as session:
            result = await session.execute(insert(controladores).values(**params))
            new_id = result.lastrowid
            await session.commit()
        from dataclasses import replace
        return replace(c, id=new_id or 0)

    async def _update(self, c: Controller) -> None:
        params = self._controller_to_params(c)
        async with self.session_factory() as session:
            await session.execute(
                update(controladores)
                .where(controladores.c.id == c.id)
                .values(**params, atualizado_em=func.datetime("now"))
            )
            await session.commit()

    def _controller_to_params(self, c: Controller) -> dict:
        """Map Controller fields to Controladores column dict."""
        permitted = ",".join(
            sorted(str(m) for m in c.permitted_modes),
        )
        return {
            "nome": c.name,
            "descricao": c.description,
            "modo_execucao": str(c.execution_mode),
            "scan_rate_s": c.scan_rate_s,
            "tss_s": c.tss_s,
            "kp_manual": c.pid_params.gain,
            "ki_inicial": c.pid_params.reset,
            "kd_manual": c.pid_params.rate,
            "alpha": c.pid_params.alpha,
            "deadband": c.pid_params.deadband,
            "pid_structure": str(c.pid_structure),
            "integral_type": str(c.integral_type),
            "pv_min": c.pv_scale.eu_min,
            "pv_max": c.pv_scale.eu_max,
            "pv_unit": c.pv_scale.unit,
            "co_min": c.out_scale.eu_min,
            "co_max": c.out_scale.eu_max,
            "co_unit": c.out_scale.unit,
            "node_id_pv": c.tag_bindings.node_id_pv,
            "node_id_sp": c.tag_bindings.node_id_sp,
            "node_id_co": c.tag_bindings.node_id_co,
            "node_id_integral": c.tag_bindings.node_id_integral,
            "node_id_bkcal_in": c.tag_bindings.node_id_bkcal_in,
            "node_id_bkcal_out": c.tag_bindings.node_id_bkcal_out,
            "node_id_kp": c.tag_bindings.node_id_kp,
            "node_id_ti": c.tag_bindings.node_id_ti,
            "node_id_td": c.tag_bindings.node_id_td,
            "node_id_mode_target": c.tag_bindings.node_id_mode_target,
            "node_id_mode_actual": c.tag_bindings.node_id_mode_actual,
            "node_id_enabled": c.tag_bindings.node_id_enabled,
            "mode_int_map": json.dumps(c.tag_bindings.mode_int_map),
            "sp_hi_lim": c.sp_hi_lim,
            "sp_lo_lim": c.sp_lo_lim,
            "sp_rate_up": c.sp_rate_up,
            "sp_rate_dn": c.sp_rate_dn,
            "out_hi_lim": c.out_hi_lim,
            "out_lo_lim": c.out_lo_lim,
            "arw_hi_lim": c.arw_hi_lim,
            "arw_lo_lim": c.arw_lo_lim,
            "pv_ftime": c.pv_ftime,
            "sp_ftime": c.sp_ftime,
            "low_cut": c.low_cut,
            "shed_opt": str(c.shed_opt),
            "shed_time_s": c.shed_time_s,
            "permitted_modes": permitted,
            "mode_normal": str(c.mode_normal),
            # ControlOpts
            "no_out_limits_in_manual": int(
                c.control_opts.no_out_limits_in_manual,
            ),
            "obey_sp_limits_if_cas": int(
                c.control_opts.obey_sp_limits_if_cas,
            ),
            "track_in_manual": int(c.control_opts.track_in_manual),
            "track_enable": int(c.control_opts.track_enable),
            "direct_acting": int(c.control_opts.direct_acting),
            "sp_track_retained_target": int(
                c.control_opts.sp_track_retained_target,
            ),
            "ctrl_sp_pv_track_in_lo_or_iman": int(
                c.control_opts.sp_pv_track_in_lo_or_iman,
            ),
            "sp_pv_track_in_rout": int(
                c.control_opts.sp_pv_track_in_rout,
            ),
            "ctrl_sp_pv_track_in_man": int(
                c.control_opts.sp_pv_track_in_man,
            ),
            "use_pv_for_bkcal_out": int(
                c.control_opts.use_pv_for_bkcal_out,
            ),
            "bypass_enable": int(c.control_opts.bypass_enable),
            # IOOpts
            "low_cutoff": int(c.io_opts.low_cutoff),
            "target_to_man_if_fault": int(
                c.io_opts.target_to_man_if_fault,
            ),
            "fault_state_to_value": int(
                c.io_opts.fault_state_to_value,
            ),
            "increase_to_close": int(c.io_opts.increase_to_close),
            "io_sp_pv_track_in_lo_or_iman": int(
                c.io_opts.sp_pv_track_in_lo_or_iman,
            ),
            "io_sp_pv_track_in_man": int(c.io_opts.sp_pv_track_in_man),
            # StatusOpts
            "bad_if_limited": int(c.status_opts.bad_if_limited),
            "use_uncertain_as_good": int(
                c.status_opts.use_uncertain_as_good,
            ),
            # TrackOpt
            "track_opt": str(c.track_opt),
            # ProcessType
            "process_type": str(c.process_type),
            # AIConfig
            "ai_engine": str(c.ai_config.engine),
            "objetivo_controle": str(c.ai_config.objective),
            "process_speed": str(c.process_speed),
            "tempo_morto_l": c.ai_config.dead_time_l,
            "ai_limit_min": c.ai_config.limit_min,
            "ai_limit_max": c.ai_config.limit_max,
            "rl_fallback_kp": c.ai_config.rl_fallback_kp,
            "rl_fallback_kd": c.ai_config.rl_fallback_kd,
            "rl_learning_rate": c.ai_config.rl_learning_rate,
            "rl_train_interval": c.ai_config.rl_train_interval,
            "optimization_enabled": int(c.optimization_enabled),
            "stability_band_pct": c.stability_band_pct,
            "sl_band_lo_pct": c.ai_config.sl_band_lo_pct,
            "sl_band_hi_pct": c.ai_config.sl_band_hi_pct,
            "sl_error_small_pct": c.ai_config.sl_error_small_pct,
            "sl_co_ramp_max_pct_min": c.ai_config.sl_co_ramp_max_pct_min,
        }

    def _row_to_controller(self, row: Mapping) -> Controller:
        """Convert a DB row to a Controller dataclass."""
        permitted_modes: set[ControllerMode] = {
            ControllerMode(m)
            for m in str(row["permitted_modes"]).split(",")
            if m
        }
        return Controller(
            id=row["id"],
            name=row["nome"],
            description=row["descricao"],
            execution_mode=ExecutionMode(row["modo_execucao"]),
            scan_rate_s=row["scan_rate_s"],
            tss_s=row["tss_s"],
            process_speed=ProcessSpeed(row["process_speed"]),
            process_type=ProcessType(row["process_type"]),
            pid_params=PIDParams(
                gain=row["kp_manual"],
                reset=row["ki_inicial"],
                rate=row["kd_manual"],
                alpha=row["alpha"],
                deadband=row["deadband"],
            ),
            pid_structure=PIDStructure(row["pid_structure"]),
            integral_type=IntegralType(row["integral_type"]),
            pv_scale=ScaleConfig(
                eu_min=row["pv_min"],
                eu_max=row["pv_max"],
                unit=row["pv_unit"],
            ),
            out_scale=ScaleConfig(
                eu_min=row["co_min"],
                eu_max=row["co_max"],
                unit=row["co_unit"],
            ),
            tag_bindings=TagBindings(
                node_id_pv=row["node_id_pv"],
                node_id_sp=row["node_id_sp"],
                node_id_co=row["node_id_co"],
                node_id_integral=row["node_id_integral"],
                node_id_bkcal_in=row["node_id_bkcal_in"],
                node_id_bkcal_out=row["node_id_bkcal_out"],
                node_id_kp=row["node_id_kp"],
                node_id_ti=row["node_id_ti"],
                node_id_td=row["node_id_td"],
                node_id_mode_target=row["node_id_mode_target"],
                node_id_mode_actual=row["node_id_mode_actual"],
                node_id_enabled=row["node_id_enabled"],
                mode_int_map=json.loads(row["mode_int_map"]),
            ),
            sp_hi_lim=row["sp_hi_lim"],
            sp_lo_lim=row["sp_lo_lim"],
            sp_rate_up=row["sp_rate_up"],
            sp_rate_dn=row["sp_rate_dn"],
            out_hi_lim=row["out_hi_lim"],
            out_lo_lim=row["out_lo_lim"],
            arw_hi_lim=row["arw_hi_lim"],
            arw_lo_lim=row["arw_lo_lim"],
            pv_ftime=row["pv_ftime"],
            sp_ftime=row["sp_ftime"],
            low_cut=row["low_cut"],
            shed_opt=ControllerMode(row["shed_opt"]),
            shed_time_s=row["shed_time_s"],
            permitted_modes=permitted_modes,
            mode_normal=ControllerMode(row["mode_normal"]),
            control_opts=ControlOpts(
                no_out_limits_in_manual=bool(
                    row["no_out_limits_in_manual"],
                ),
                obey_sp_limits_if_cas=bool(
                    row["obey_sp_limits_if_cas"],
                ),
                track_in_manual=bool(row["track_in_manual"]),
                track_enable=bool(row["track_enable"]),
                direct_acting=bool(row["direct_acting"]),
                sp_track_retained_target=bool(
                    row["sp_track_retained_target"],
                ),
                sp_pv_track_in_lo_or_iman=bool(
                    row["ctrl_sp_pv_track_in_lo_or_iman"],
                ),
                sp_pv_track_in_rout=bool(row["sp_pv_track_in_rout"]),
                sp_pv_track_in_man=bool(row["ctrl_sp_pv_track_in_man"]),
                use_pv_for_bkcal_out=bool(
                    row["use_pv_for_bkcal_out"],
                ),
                bypass_enable=bool(row["bypass_enable"]),
            ),
            io_opts=IOOpts(
                low_cutoff=bool(row["low_cutoff"]),
                target_to_man_if_fault=bool(
                    row["target_to_man_if_fault"],
                ),
                fault_state_to_value=bool(row["fault_state_to_value"]),
                increase_to_close=bool(row["increase_to_close"]),
                sp_pv_track_in_lo_or_iman=bool(
                    row["io_sp_pv_track_in_lo_or_iman"],
                ),
                sp_pv_track_in_man=bool(row["io_sp_pv_track_in_man"]),
            ),
            status_opts=StatusOpts(
                bad_if_limited=bool(row["bad_if_limited"]),
                use_uncertain_as_good=bool(
                    row["use_uncertain_as_good"],
                ),
            ),
            track_opt=TrackOpt(row["track_opt"]),
            ai_config=AIConfig(
                engine=AIEngine(row["ai_engine"]),
                objective=ControlObjective(row["objetivo_controle"]),
                dead_time_l=row["tempo_morto_l"],
                limit_min=row["ai_limit_min"],
                limit_max=row["ai_limit_max"],
                rl_fallback_kp=row["rl_fallback_kp"],
                rl_fallback_kd=row["rl_fallback_kd"],
                rl_learning_rate=row["rl_learning_rate"],
                rl_train_interval=row["rl_train_interval"],
                sl_band_lo_pct=row["sl_band_lo_pct"],
                sl_band_hi_pct=row["sl_band_hi_pct"],
                sl_error_small_pct=row["sl_error_small_pct"],
                sl_co_ramp_max_pct_min=row["sl_co_ramp_max_pct_min"],
            ),
            optimization_enabled=bool(row["optimization_enabled"]),
            stability_band_pct=row["stability_band_pct"],
        )

    # ------------------------------------------------------------------
    # Projeto_Meta
    # ------------------------------------------------------------------

    async def set_meta(self, key: str, value: str) -> None:
        """Insert or replace a project metadata key-value pair."""
        async with self.session_factory() as session:
            await session.execute(
                text("INSERT OR REPLACE INTO Projeto_Meta (chave, valor) VALUES (:k, :v)"),
                {"k": key, "v": value},
            )
            await session.commit()

    async def get_meta(self, key: str) -> str | None:
        """Return the value for *key* or ``None`` if missing."""
        async with self.session_factory() as session:
            result = await session.execute(
                text("SELECT valor FROM Projeto_Meta WHERE chave = :k"),
                {"k": key},
            )
            row = result.mappings().first()
        return str(row["valor"]) if row else None

    # ------------------------------------------------------------------
    # Configuracao_Simulador
    # ------------------------------------------------------------------

    async def save_sim_config(
        self,
        controller_id: int,
        preset: str,
        gain: float,
        tau1: float,
        tau2: float,
        dead_time: float,
        pid_enabled: bool = False,
        pid_kp: float = 1.0,
        pid_ti: float = 10.0,
        pid_td: float = 0.0,
        pid_mode: int = 0,
        auto_sp_enabled: bool = False,
        auto_sp_min_pct: float = 30.0,
        auto_sp_max_pct: float = 70.0,
        auto_dist_enabled: bool = False,
        auto_dist_max_pct: float = 10.0,
        pid_sp: float = 50.0,
    ) -> None:
        """Insert or replace a simulator configuration for *controller_id*."""
        async with self.session_factory() as session:
            await session.execute(
                text(
                    "INSERT OR REPLACE INTO Configuracao_Simulador"
                    " (controlador_id, preset, gain, tau1, tau2, dead_time,"
                    "  pid_enabled, pid_kp, pid_ti, pid_td, pid_mode,"
                    "  auto_sp_enabled, auto_sp_min_pct, auto_sp_max_pct,"
                    "  auto_dist_enabled, auto_dist_max_pct, pid_sp)"
                    " VALUES (:cid, :preset, :gain, :tau1, :tau2, :dead_time,"
                    "  :pid_enabled, :pid_kp, :pid_ti, :pid_td, :pid_mode,"
                    "  :auto_sp_enabled, :auto_sp_min_pct, :auto_sp_max_pct,"
                    "  :auto_dist_enabled, :auto_dist_max_pct, :pid_sp)"
                ),
                {
                    "cid": controller_id, "preset": preset, "gain": gain,
                    "tau1": tau1, "tau2": tau2, "dead_time": dead_time,
                    "pid_enabled": int(pid_enabled), "pid_kp": pid_kp,
                    "pid_ti": pid_ti, "pid_td": pid_td, "pid_mode": pid_mode,
                    "auto_sp_enabled": int(auto_sp_enabled),
                    "auto_sp_min_pct": auto_sp_min_pct,
                    "auto_sp_max_pct": auto_sp_max_pct,
                    "auto_dist_enabled": int(auto_dist_enabled),
                    "auto_dist_max_pct": auto_dist_max_pct,
                    "pid_sp": pid_sp,
                },
            )
            await session.commit()

    async def get_sim_config(self, controller_id: int) -> dict | None:
        """Return sim config dict or ``None``."""
        async with self.session_factory() as session:
            result = await session.execute(
                text("SELECT * FROM Configuracao_Simulador WHERE controlador_id = :cid"),
                {"cid": controller_id},
            )
            row = result.mappings().first()
        if row is None:
            return None
        return self._sim_row_to_dict(row)

    async def list_sim_configs(self) -> list[dict]:
        """Return all simulator configurations."""
        async with self.session_factory() as session:
            result = await session.execute(
                text("SELECT * FROM Configuracao_Simulador ORDER BY controlador_id"),
            )
            rows = result.mappings().all()
        return [self._sim_row_to_dict(r) for r in rows]

    @staticmethod
    def _sim_row_to_dict(row: Mapping) -> dict:
        return {
            "controlador_id": row["controlador_id"],
            "preset": row["preset"],
            "gain": row["gain"],
            "tau1": row["tau1"],
            "tau2": row["tau2"],
            "dead_time": row["dead_time"],
            "pid_enabled": bool(row["pid_enabled"]),
            "pid_kp": row["pid_kp"],
            "pid_ti": row["pid_ti"],
            "pid_td": row["pid_td"],
            "pid_mode": row["pid_mode"],
            "auto_sp_enabled": bool(row["auto_sp_enabled"]),
            "auto_sp_min_pct": row["auto_sp_min_pct"],
            "auto_sp_max_pct": row["auto_sp_max_pct"],
            "auto_dist_enabled": bool(row["auto_dist_enabled"]),
            "auto_dist_max_pct": row["auto_dist_max_pct"],
            "pid_sp": row.get("pid_sp", 50.0),
        }

    # ------------------------------------------------------------------
    # Project lifecycle
    # ------------------------------------------------------------------

    async def checkpoint(self) -> None:
        """PRAGMA wal_checkpoint(TRUNCATE) on engine A.

        Folds the WAL into the main file and truncates it to zero bytes, so
        the bare .spid can be streamed (download) or the file abandoned
        (reopen) without losing tail writes. Runs on the raw driver
        connection: PRAGMA must not sit inside an autobegun transaction.
        """
        async with self.engine.connect() as conn:
            raw = await conn.get_raw_connection()
            await raw.driver_connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")

    async def reopen(self, db_path: Path) -> None:
        """Switch the active .spid — spec §10 lifecycle, engine-A half.

        Order: (1) wal_checkpoint(TRUNCATE) on A, (2) dispose A — no pooled
        handle survives and SQLite removes the -wal/-shm siblings on the last
        close, (3) re-create the engine against the new path and re-run
        bootstrap + back-fill. Engine B's half is handled by ProjectService,
        which stops the DB worker (drain + dispose on its own loop) BEFORE
        calling this and restarts it after.
        """
        await self.checkpoint()
        await self.engine.dispose()
        self._db_path = db_path
        await self.initialize()

    # ------------------------------------------------------------------
    # Test helpers
    # ------------------------------------------------------------------

    async def _get_table_names(self) -> list[str]:
        async with self.session_factory() as session:
            result = await session.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"),
            )
            rows = result.mappings().all()
        return [r["name"] for r in rows]

    async def _get_journal_mode(self) -> str:
        async with self.session_factory() as session:
            row = (await session.execute(text("PRAGMA journal_mode"))).first()
        return str(row[0]) if row else ""

    async def close(self) -> None:
        """Dispose engine A (finalizes WAL on the pooled connection)."""
        await self.engine.dispose()
