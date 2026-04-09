"""SQLite-backed Controller repository adapter."""
from __future__ import annotations

import contextlib
import json
from pathlib import Path

import aiosqlite

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

_DDL = """
CREATE TABLE IF NOT EXISTS Controladores (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    nome                TEXT    NOT NULL,
    descricao           TEXT    NOT NULL DEFAULT '',
    modo_execucao       TEXT    NOT NULL DEFAULT 'DDC',
    scan_rate_s         REAL    NOT NULL DEFAULT 1.0,
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
    ai_limit_min        REAL    NOT NULL DEFAULT 0.1,
    ai_limit_max        REAL    NOT NULL DEFAULT 100.0,
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
    auto_dist_max_pct REAL NOT NULL DEFAULT 10.0
);
"""


class SQLiteRepository:
    """SQLite-backed implementation of ControllerRepository."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self.db: aiosqlite.Connection  # exposed for shared use by historian

    async def initialize(self) -> None:
        """Open the database, enable WAL mode, create all tables."""
        self.db = await aiosqlite.connect(self._db_path)
        self.db.row_factory = aiosqlite.Row
        await self.db.execute("PRAGMA journal_mode=WAL")
        await self.db.executescript(_DDL)
        await self._apply_migrations()
        await self.db.commit()

    async def _apply_migrations(self) -> None:
        """Add columns that may be missing from older databases."""
        new_columns = [
            ("node_id_bkcal_in", "TEXT NOT NULL DEFAULT ''"),
            ("node_id_bkcal_out", "TEXT NOT NULL DEFAULT ''"),
            ("node_id_kp", "TEXT NOT NULL DEFAULT ''"),
            ("node_id_ti", "TEXT NOT NULL DEFAULT ''"),
            ("node_id_td", "TEXT NOT NULL DEFAULT ''"),
        ]
        for col_name, col_def in new_columns:
            with contextlib.suppress(Exception):
                await self.db.execute(
                    f"ALTER TABLE Controladores ADD COLUMN {col_name} {col_def}",
                )
        # Configuracao_Simulador: auto SP / auto disturbance columns
        sim_new_columns = [
            ("auto_sp_enabled", "INTEGER NOT NULL DEFAULT 0"),
            ("auto_sp_min_pct", "REAL NOT NULL DEFAULT 30.0"),
            ("auto_sp_max_pct", "REAL NOT NULL DEFAULT 70.0"),
            ("auto_dist_enabled", "INTEGER NOT NULL DEFAULT 0"),
            ("auto_dist_max_pct", "REAL NOT NULL DEFAULT 10.0"),
        ]
        for col_name, col_def in sim_new_columns:
            with contextlib.suppress(Exception):
                await self.db.execute(
                    f"ALTER TABLE Configuracao_Simulador ADD COLUMN {col_name} {col_def}",
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
        async with self.db.execute(
            "SELECT * FROM Controladores WHERE id = ?", (controller_id,)
        ) as cur:
            row = await cur.fetchone()
        if row is None:
            raise KeyError(controller_id)
        return self._row_to_controller(row)

    async def list_all(self) -> list[Controller]:
        """Return all controllers."""
        async with self.db.execute(
            "SELECT * FROM Controladores ORDER BY id",
        ) as cur:
            rows = await cur.fetchall()
        return [self._row_to_controller(r) for r in rows]

    async def delete(self, controller_id: int) -> None:
        """Delete controller or raise KeyError."""
        async with self.db.execute(
            "SELECT id FROM Controladores WHERE id = ?",
            (controller_id,),
        ) as cur:
            row = await cur.fetchone()
        if row is None:
            raise KeyError(controller_id)
        await self.db.execute(
            "DELETE FROM Controladores WHERE id = ?", (controller_id,),
        )
        await self.db.commit()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _insert(self, c: Controller) -> Controller:
        params = self._controller_to_params(c)
        cols = ", ".join(params.keys())
        placeholders = ", ".join("?" for _ in params)
        sql = (
            f"INSERT INTO Controladores ({cols}) VALUES ({placeholders})"
        )
        async with self.db.execute(sql, list(params.values())) as cur:
            new_id = cur.lastrowid
        await self.db.commit()
        from dataclasses import replace
        return replace(c, id=new_id or 0)

    async def _update(self, c: Controller) -> None:
        params = self._controller_to_params(c)
        assignments = ", ".join(f"{k} = ?" for k in params)
        sql = (
            f"UPDATE Controladores SET {assignments},"
            " atualizado_em = datetime('now') WHERE id = ?"
        )
        await self.db.execute(sql, [*params.values(), c.id])
        await self.db.commit()

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
        }

    def _row_to_controller(self, row: aiosqlite.Row) -> Controller:
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
            ),
        )

    # ------------------------------------------------------------------
    # Projeto_Meta
    # ------------------------------------------------------------------

    async def set_meta(self, key: str, value: str) -> None:
        """Insert or replace a project metadata key-value pair."""
        await self.db.execute(
            "INSERT OR REPLACE INTO Projeto_Meta (chave, valor) VALUES (?, ?)",
            (key, value),
        )
        await self.db.commit()

    async def get_meta(self, key: str) -> str | None:
        """Return the value for *key* or ``None`` if missing."""
        async with self.db.execute(
            "SELECT valor FROM Projeto_Meta WHERE chave = ?", (key,),
        ) as cur:
            row = await cur.fetchone()
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
    ) -> None:
        """Insert or replace a simulator configuration for *controller_id*."""
        await self.db.execute(
            "INSERT OR REPLACE INTO Configuracao_Simulador"
            " (controlador_id, preset, gain, tau1, tau2, dead_time,"
            "  pid_enabled, pid_kp, pid_ti, pid_td, pid_mode,"
            "  auto_sp_enabled, auto_sp_min_pct, auto_sp_max_pct,"
            "  auto_dist_enabled, auto_dist_max_pct)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                controller_id, preset, gain, tau1, tau2, dead_time,
                int(pid_enabled), pid_kp, pid_ti, pid_td, pid_mode,
                int(auto_sp_enabled), auto_sp_min_pct, auto_sp_max_pct,
                int(auto_dist_enabled), auto_dist_max_pct,
            ),
        )
        await self.db.commit()

    async def get_sim_config(self, controller_id: int) -> dict | None:
        """Return sim config dict or ``None``."""
        async with self.db.execute(
            "SELECT * FROM Configuracao_Simulador WHERE controlador_id = ?",
            (controller_id,),
        ) as cur:
            row = await cur.fetchone()
        if row is None:
            return None
        return self._sim_row_to_dict(row)

    async def list_sim_configs(self) -> list[dict]:
        """Return all simulator configurations."""
        async with self.db.execute(
            "SELECT * FROM Configuracao_Simulador ORDER BY controlador_id",
        ) as cur:
            rows = await cur.fetchall()
        return [self._sim_row_to_dict(r) for r in rows]

    @staticmethod
    def _sim_row_to_dict(row: aiosqlite.Row) -> dict:
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
        }

    # ------------------------------------------------------------------
    # Project lifecycle
    # ------------------------------------------------------------------

    async def reopen(self, db_path: Path) -> None:
        """Close the current DB and open a new one at *db_path*."""
        await self.db.close()
        self._db_path = db_path
        await self.initialize()

    # ------------------------------------------------------------------
    # Test helpers
    # ------------------------------------------------------------------

    async def _get_table_names(self) -> list[str]:
        async with self.db.execute(
            "SELECT name FROM sqlite_master"
            " WHERE type='table' ORDER BY name",
        ) as cur:
            rows = await cur.fetchall()
        return [r["name"] for r in rows]

    async def _get_journal_mode(self) -> str:
        async with self.db.execute("PRAGMA journal_mode") as cur:
            row = await cur.fetchone()
        return str(row[0]) if row else ""

    async def close(self) -> None:
        """Close the SQLite connection, finalizing WAL."""
        await self.db.close()
