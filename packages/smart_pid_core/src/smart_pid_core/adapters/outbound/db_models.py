"""Declarative models mapping the EXISTING SQLite tables verbatim — spec §10.

Two metadata scopes, one per database file:
- ``SpidBase``  — tables inside a ``.spid`` project file (engines A and B).
- ``UsersBase`` — the standalone ``users.db`` (engine C).

These models NEVER create tables. The DDL bootstrap (``_DDL`` +
``_apply_migrations()`` in ``sqlite_repo.py``, ``_USERS_DDL`` in
``user_repo.py``) remains the only source of schema, running on every
open/reopen exactly as before the port. ``tests/core/unit/test_db_models.py``
asserts column-set parity between these models and a bootstrapped file.

No ForeignKey objects and no server defaults on purpose: FK enforcement is
OFF by PRAGMA (cascades stay inert), and INSERT paths either supply values
explicitly or rely on the SQLite-side DDL defaults.
"""
from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class SpidBase(DeclarativeBase):
    """Tables that live inside a .spid project file."""


class UsersBase(DeclarativeBase):
    """Tables that live in the standalone users.db."""


class Controladores(SpidBase):
    __tablename__ = "Controladores"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str]
    descricao: Mapped[str]
    modo_execucao: Mapped[str]
    scan_rate_s: Mapped[float]
    tss_s: Mapped[float]
    # PID params
    kp_manual: Mapped[float]
    ki_inicial: Mapped[float]
    kd_manual: Mapped[float]
    alpha: Mapped[float]
    deadband: Mapped[float]
    # PID structure
    pid_structure: Mapped[str]
    integral_type: Mapped[str]
    # Scale
    pv_min: Mapped[float]
    pv_max: Mapped[float]
    pv_unit: Mapped[str]
    co_min: Mapped[float]
    co_max: Mapped[float]
    co_unit: Mapped[str]
    # Tag bindings
    node_id_pv: Mapped[str]
    node_id_sp: Mapped[str]
    node_id_co: Mapped[str]
    node_id_integral: Mapped[str]
    node_id_bkcal_in: Mapped[str]
    node_id_bkcal_out: Mapped[str]
    node_id_kp: Mapped[str]
    node_id_ti: Mapped[str]
    node_id_td: Mapped[str]
    node_id_mode_target: Mapped[str]
    node_id_mode_actual: Mapped[str]
    node_id_enabled: Mapped[str]
    mode_int_map: Mapped[str]
    # SP limits
    sp_hi_lim: Mapped[float]
    sp_lo_lim: Mapped[float]
    sp_rate_up: Mapped[float]
    sp_rate_dn: Mapped[float]
    # Output limits
    out_hi_lim: Mapped[float]
    out_lo_lim: Mapped[float]
    # ARW limits
    arw_hi_lim: Mapped[float]
    arw_lo_lim: Mapped[float]
    # Filter
    pv_ftime: Mapped[float]
    sp_ftime: Mapped[float]
    low_cut: Mapped[float]
    # Shed
    shed_opt: Mapped[str]
    shed_time_s: Mapped[float]
    # Modes
    permitted_modes: Mapped[str]
    mode_normal: Mapped[str]
    # Control opts (boolean flags as integers)
    no_out_limits_in_manual: Mapped[int]
    obey_sp_limits_if_cas: Mapped[int]
    track_in_manual: Mapped[int]
    track_enable: Mapped[int]
    direct_acting: Mapped[int]
    sp_track_retained_target: Mapped[int]
    ctrl_sp_pv_track_in_lo_or_iman: Mapped[int]
    sp_pv_track_in_rout: Mapped[int]
    ctrl_sp_pv_track_in_man: Mapped[int]
    use_pv_for_bkcal_out: Mapped[int]
    bypass_enable: Mapped[int]
    # IO opts
    low_cutoff: Mapped[int]
    target_to_man_if_fault: Mapped[int]
    fault_state_to_value: Mapped[int]
    increase_to_close: Mapped[int]
    io_sp_pv_track_in_lo_or_iman: Mapped[int]
    io_sp_pv_track_in_man: Mapped[int]
    # Status opts
    bad_if_limited: Mapped[int]
    use_uncertain_as_good: Mapped[int]
    # Track opt / process type
    track_opt: Mapped[str]
    process_type: Mapped[str]
    # AI config
    ai_engine: Mapped[str]
    objetivo_controle: Mapped[str]
    process_speed: Mapped[str]
    tempo_morto_l: Mapped[float]
    ai_limit_min: Mapped[float]
    ai_limit_max: Mapped[float]
    optimization_enabled: Mapped[int]
    tuning_write_mode: Mapped[str]
    max_tuning_change_pct: Mapped[float]
    stability_band_pct: Mapped[float | None]
    sl_band_lo_pct: Mapped[float | None]
    sl_band_hi_pct: Mapped[float | None]
    sl_error_small_pct: Mapped[float]
    sl_co_ramp_max_pct_min: Mapped[float]
    # Timestamps (TEXT, SQLite-side datetime('now') defaults)
    criado_em: Mapped[str]
    atualizado_em: Mapped[str]
    # Columns guaranteed by _apply_migrations() (absent from _DDL on purpose)
    rl_fallback_kp: Mapped[float]
    rl_fallback_kd: Mapped[float]
    rl_learning_rate: Mapped[float]
    rl_train_interval: Mapped[int]


class ConfiguracaoAlarmes(SpidBase):
    __tablename__ = "Configuracao_Alarmes"

    id: Mapped[int] = mapped_column(primary_key=True)
    controlador_id: Mapped[int]
    tipo_alarme: Mapped[str]
    prioridade: Mapped[str]
    limite: Mapped[float]
    habilitado: Mapped[int]
    histerese: Mapped[float]
    delay_on_s: Mapped[float]
    delay_off_s: Mapped[float]
    mensagem: Mapped[str]
    criado_em: Mapped[str]


class LogProcesso(SpidBase):
    __tablename__ = "Log_Processo"

    id: Mapped[int] = mapped_column(primary_key=True)
    controlador_id: Mapped[int]
    timestamp: Mapped[str]
    pv: Mapped[float]
    sp: Mapped[float]
    co: Mapped[float]
    integral_val: Mapped[float]


class LogSintoniaIA(SpidBase):
    __tablename__ = "Log_Sintonia_IA"

    id: Mapped[int] = mapped_column(primary_key=True)
    controlador_id: Mapped[int]
    timestamp: Mapped[str]
    motor: Mapped[str]
    kp_antes: Mapped[float | None]
    ki_antes: Mapped[float | None]
    kd_antes: Mapped[float | None]
    kp_depois: Mapped[float | None]
    ki_depois: Mapped[float | None]
    kd_depois: Mapped[float | None]
    objetivo: Mapped[str | None]
    metrica: Mapped[float | None]
    aprovado: Mapped[int]


class LogAuditoria(SpidBase):
    __tablename__ = "Log_Auditoria"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int | None]
    username: Mapped[str]
    timestamp: Mapped[str]
    acao: Mapped[str]
    entidade: Mapped[str]
    entidade_id: Mapped[int | None]
    detalhe: Mapped[str]
    ip_origem: Mapped[str]


class ModelosIA(SpidBase):
    __tablename__ = "Modelos_IA"

    id: Mapped[int] = mapped_column(primary_key=True)
    controlador_id: Mapped[int]
    algoritmo: Mapped[str]
    episodios: Mapped[int]
    reward_medio: Mapped[float]
    caminho_modelo: Mapped[str]
    criado_em: Mapped[str]


class LogAlarmes(SpidBase):
    __tablename__ = "Log_Alarmes"

    id: Mapped[int] = mapped_column(primary_key=True)
    controlador_id: Mapped[int]
    timestamp: Mapped[str]
    tipo_alarme: Mapped[str]
    prioridade: Mapped[str]
    valor: Mapped[float | None]
    limite: Mapped[float | None]
    cleared_at: Mapped[str | None]
    reconhecido: Mapped[int]
    reconhecido_por: Mapped[str | None]
    reconhecido_em: Mapped[str | None]


class ProjetoMeta(SpidBase):
    __tablename__ = "Projeto_Meta"

    chave: Mapped[str] = mapped_column(primary_key=True)
    valor: Mapped[str]


class LogSystemEvents(SpidBase):
    __tablename__ = "Log_System_Events"

    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[str]
    source: Mapped[str]
    severity: Mapped[str]
    message: Mapped[str]


class ConfiguracaoSimulador(SpidBase):
    __tablename__ = "Configuracao_Simulador"

    controlador_id: Mapped[int] = mapped_column(primary_key=True)
    preset: Mapped[str]
    gain: Mapped[float]
    tau1: Mapped[float]
    tau2: Mapped[float]
    dead_time: Mapped[float]
    pid_enabled: Mapped[int]
    pid_kp: Mapped[float]
    pid_ti: Mapped[float]
    pid_td: Mapped[float]
    pid_mode: Mapped[int]
    auto_sp_enabled: Mapped[int]
    auto_sp_min_pct: Mapped[float]
    auto_sp_max_pct: Mapped[float]
    auto_dist_enabled: Mapped[int]
    auto_dist_max_pct: Mapped[float]
    pid_sp: Mapped[float]
    auto_sp_period_s: Mapped[float]
    auto_dist_period_s: Mapped[float]


class Usuarios(UsersBase):
    __tablename__ = "Usuarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str]
    senha_hash: Mapped[str]
    perfil: Mapped[str]
    ativo: Mapped[int]
    criado_em: Mapped[str]
    tema: Mapped[str | None]


# Core table handles for Core-statement call sites (spec §10 pins
# ``insert(log_processo)`` for the historian hot path).
controladores = Controladores.__table__
configuracao_alarmes = ConfiguracaoAlarmes.__table__
log_processo = LogProcesso.__table__
log_sintonia_ia = LogSintoniaIA.__table__
log_auditoria = LogAuditoria.__table__
modelos_ia = ModelosIA.__table__
log_alarmes = LogAlarmes.__table__
projeto_meta = ProjetoMeta.__table__
log_system_events = LogSystemEvents.__table__
configuracao_simulador = ConfiguracaoSimulador.__table__
usuarios = Usuarios.__table__
