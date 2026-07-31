"""Controller CRUD router."""

import json
import logging
from dataclasses import replace
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status

from smart_pid_core.adapters.inbound.api.dependencies import (
    get_alarm_repo,
    get_alarm_worker,
    get_audit_repo,
    get_repo,
    require_admin,
    require_user,
)
from smart_pid_core.adapters.outbound.alarm_repo import AlarmRepository  # noqa: TC001
from smart_pid_core.adapters.outbound.audit_repo import AuditRepository
from smart_pid_core.adapters.outbound.sqlite_repo import SQLiteRepository
from smart_pid_core.application.workers.alarm_worker import AlarmWorker  # noqa: TC001
from smart_pid_domain.dtos.alarms import (
    AlarmConfigResponse,
    AlarmConfigUpdate,
    AlarmThreshold,
)
from smart_pid_domain.dtos.auth import UserClaims
from smart_pid_domain.dtos.controllers import (
    AIConfigDTO,
    ControllerCreate,
    ControllerResponse,
    ControllerUpdate,
    ControlOptsDTO,
    IOOptsDTO,
    PIDParamsDTO,
    ScaleConfigDTO,
    TagBindingsDTO,
)
from smart_pid_domain.enums import (
    AIEngine,
    AlarmPriority,
    AuditAction,
    ControllerMode,
    ControlObjective,
    ExecutionMode,
    IntegralType,
    PIDStructure,
    ProcessSpeed,
    TuningWriteMode,
)
from smart_pid_domain.exceptions import ControllerNotFoundError
from smart_pid_domain.models.alarm_config import AlarmConfig
from smart_pid_domain.models.controller import (
    AIConfig,
    Controller,
    ControlOpts,
    IOOpts,
    PIDParams,
    ScaleConfig,
    TagBindings,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _sync_simulator_registration(
    request: Request, controller: Controller | None, controller_id: int,
) -> None:
    """Add or drop a controller's simulator state to match the database.

    Pass ``controller`` to register it, or ``None`` to unregister
    ``controller_id``. No-op when the simulator is disabled
    (``SPID_SIMULATOR_ENABLED=false`` leaves ``app.state.simulator_adapter``
    as ``None``), so controller CRUD is unaffected in that deployment.

    Registration used to happen only at daemon startup and project open, so a
    controller created through ``POST /controllers`` was invisible to the
    simulator until the daemon restarted and every ``/simulator/*`` call for
    it failed. Deregistration is the mirror: a deleted loop that stays
    registered keeps being integrated by the tick loop and keeps answering
    ``/simulator/*``.

    Failures are logged, never raised: the controller row is already
    committed by the time this runs, so turning an adapter hiccup into a 5xx
    would report failure for a create that actually succeeded.
    """
    adapter = getattr(request.app.state, "simulator_adapter", None)
    if adapter is None:
        return
    try:
        if controller is None:
            adapter.unregister_controller(controller_id)
        else:
            adapter.register_controller(
                controller.id,
                pv_min=controller.pv_scale.eu_min,
                pv_max=controller.pv_scale.eu_max,
            )
    except Exception:
        logger.exception(
            "simulator_registration_sync_failed controller_id=%d register=%s",
            controller_id,
            controller is not None,
        )


def _thresholds_to_alarm_config(thresholds: list[AlarmThreshold]) -> AlarmConfig:
    """Build an AlarmConfig from a list of AlarmThreshold DTOs."""
    by_type = {str(t.alarm_type): t for t in thresholds}
    deadband = max((t.deadband for t in thresholds), default=1.0)

    def _g(name: str) -> tuple[bool, float, AlarmPriority, float, float]:
        t = by_type.get(name)
        if t is None:
            return False, 0.0, AlarmPriority.WARNING, 0.0, 0.0
        return t.enabled, t.limit, AlarmPriority(t.priority), t.delay_on_s, t.delay_off_s

    hihi = _g("HIHI")
    hi = _g("HI")
    lo = _g("LO")
    lolo = _g("LOLO")
    dv_hi = _g("DV_HI")
    dv_lo = _g("DV_LO")
    return AlarmConfig(
        hihi_enabled=hihi[0], hihi_value=hihi[1], hihi_priority=hihi[2],
        hihi_delay_on_s=hihi[3], hihi_delay_off_s=hihi[4],
        hi_enabled=hi[0], hi_value=hi[1], hi_priority=hi[2],
        hi_delay_on_s=hi[3], hi_delay_off_s=hi[4],
        lo_enabled=lo[0], lo_value=lo[1], lo_priority=lo[2],
        lo_delay_on_s=lo[3], lo_delay_off_s=lo[4],
        lolo_enabled=lolo[0], lolo_value=lolo[1], lolo_priority=lolo[2],
        lolo_delay_on_s=lolo[3], lolo_delay_off_s=lolo[4],
        dv_hi_enabled=dv_hi[0], dv_hi_value=dv_hi[1], dv_hi_priority=dv_hi[2],
        dv_hi_delay_on_s=dv_hi[3], dv_hi_delay_off_s=dv_hi[4],
        dv_lo_enabled=dv_lo[0], dv_lo_value=dv_lo[1], dv_lo_priority=dv_lo[2],
        dv_lo_delay_on_s=dv_lo[3], dv_lo_delay_off_s=dv_lo[4],
        deadband_percent=deadband,
    )


def _to_response(c: Controller) -> ControllerResponse:
    """Convert domain Controller to API response DTO."""
    return ControllerResponse(
        id=c.id,
        name=c.name,
        description=c.description,
        mode=str(c.mode_normal),
        pv=0.0,
        sp=0.0,
        co=0.0,
        execution_mode=str(c.execution_mode),
        scan_rate_s=c.scan_rate_s,
        tss_s=c.tss_s,
        process_speed=str(c.process_speed),
        pid_params=PIDParamsDTO(
            gain=c.pid_params.gain,
            reset=c.pid_params.reset,
            rate=c.pid_params.rate,
            alpha=c.pid_params.alpha,
            deadband=c.pid_params.deadband,
        ),
        pid_structure=str(c.pid_structure),
        integral_type=str(c.integral_type),
        pv_scale=ScaleConfigDTO(
            eu_min=c.pv_scale.eu_min,
            eu_max=c.pv_scale.eu_max,
            unit=c.pv_scale.unit,
        ),
        out_scale=ScaleConfigDTO(
            eu_min=c.out_scale.eu_min,
            eu_max=c.out_scale.eu_max,
            unit=c.out_scale.unit,
        ),
        tag_bindings=TagBindingsDTO(
            node_id_pv=c.tag_bindings.node_id_pv,
            node_id_sp=c.tag_bindings.node_id_sp,
            node_id_co=c.tag_bindings.node_id_co,
            node_id_integral=c.tag_bindings.node_id_integral,
            node_id_bkcal_in=c.tag_bindings.node_id_bkcal_in,
            node_id_bkcal_out=c.tag_bindings.node_id_bkcal_out,
            node_id_kp=c.tag_bindings.node_id_kp,
            node_id_ti=c.tag_bindings.node_id_ti,
            node_id_td=c.tag_bindings.node_id_td,
            node_id_mode_target=c.tag_bindings.node_id_mode_target,
            node_id_mode_actual=c.tag_bindings.node_id_mode_actual,
            node_id_enabled=c.tag_bindings.node_id_enabled,
            mode_int_map=c.tag_bindings.mode_int_map,
        ),
        control_opts=ControlOptsDTO(
            no_out_limits_in_manual=c.control_opts.no_out_limits_in_manual,
            obey_sp_limits_if_cas=c.control_opts.obey_sp_limits_if_cas,
            track_in_manual=c.control_opts.track_in_manual,
            track_enable=c.control_opts.track_enable,
            direct_acting=c.control_opts.direct_acting,
            sp_track_retained_target=c.control_opts.sp_track_retained_target,
            sp_pv_track_in_lo_or_iman=c.control_opts.sp_pv_track_in_lo_or_iman,
            sp_pv_track_in_rout=c.control_opts.sp_pv_track_in_rout,
            sp_pv_track_in_man=c.control_opts.sp_pv_track_in_man,
            use_pv_for_bkcal_out=c.control_opts.use_pv_for_bkcal_out,
        ),
        io_opts=IOOptsDTO(
            low_cutoff=c.io_opts.low_cutoff,
            target_to_man_if_fault=c.io_opts.target_to_man_if_fault,
            fault_state_to_value=c.io_opts.fault_state_to_value,
            increase_to_close=c.io_opts.increase_to_close,
            sp_pv_track_in_lo_or_iman=c.io_opts.sp_pv_track_in_lo_or_iman,
            sp_pv_track_in_man=c.io_opts.sp_pv_track_in_man,
        ),
        ai_config=AIConfigDTO(
            engine=str(c.ai_config.engine),
            objective=str(c.ai_config.objective),
            dead_time_l=c.ai_config.dead_time_l,
            limit_min=c.ai_config.limit_min,
            limit_max=c.ai_config.limit_max,
            rl_fallback_kp=c.ai_config.rl_fallback_kp,
            rl_fallback_kd=c.ai_config.rl_fallback_kd,
            rl_learning_rate=c.ai_config.rl_learning_rate,
            rl_train_interval=c.ai_config.rl_train_interval,
        ),
        optimization_enabled=c.optimization_enabled,
        tuning_write_mode=str(c.tuning_write_mode),
        max_tuning_change_pct=c.max_tuning_change_pct,
        stability_band_pct=c.stability_band_pct,
        mode_normal=str(c.mode_normal),
        permitted_modes=sorted(str(m) for m in c.permitted_modes),
        sp_hi_lim=c.sp_hi_lim,
        sp_lo_lim=c.sp_lo_lim,
        sp_rate_up=c.sp_rate_up,
        sp_rate_dn=c.sp_rate_dn,
        out_hi_lim=c.out_hi_lim,
        out_lo_lim=c.out_lo_lim,
        arw_hi_lim=c.arw_hi_lim,
        arw_lo_lim=c.arw_lo_lim,
        pv_ftime=c.pv_ftime,
        sp_ftime=c.sp_ftime,
        low_cut=c.low_cut,
        ff_enable=c.ff_enable,
        ff_gain=c.ff_gain,
        shed_opt=str(c.shed_opt),
        shed_time_s=c.shed_time_s,
    )


def _body_to_controller(body: ControllerCreate) -> Controller:
    """Build a full domain Controller from a ControllerCreate DTO."""
    return Controller(
        id=0,
        name=body.name,
        description=body.description,
        execution_mode=ExecutionMode(body.execution_mode),
        scan_rate_s=body.scan_rate_s,
        tss_s=body.tss_s,
        process_speed=ProcessSpeed(body.process_speed),
        pid_params=PIDParams(
            gain=body.pid_params.gain,
            reset=body.pid_params.reset,
            rate=body.pid_params.rate,
            alpha=body.pid_params.alpha,
            deadband=body.pid_params.deadband,
        ),
        pid_structure=PIDStructure(body.pid_structure),
        integral_type=IntegralType(body.integral_type),
        pv_scale=ScaleConfig(
            eu_min=body.pv_scale.eu_min,
            eu_max=body.pv_scale.eu_max,
            unit=body.pv_scale.unit,
        ),
        out_scale=ScaleConfig(
            eu_min=body.out_scale.eu_min,
            eu_max=body.out_scale.eu_max,
            unit=body.out_scale.unit,
        ),
        tag_bindings=TagBindings(
            node_id_pv=body.tag_bindings.node_id_pv,
            node_id_sp=body.tag_bindings.node_id_sp,
            node_id_co=body.tag_bindings.node_id_co,
            node_id_integral=body.tag_bindings.node_id_integral,
            node_id_bkcal_in=body.tag_bindings.node_id_bkcal_in,
            node_id_bkcal_out=body.tag_bindings.node_id_bkcal_out,
            node_id_kp=body.tag_bindings.node_id_kp,
            node_id_ti=body.tag_bindings.node_id_ti,
            node_id_td=body.tag_bindings.node_id_td,
            node_id_mode_target=body.tag_bindings.node_id_mode_target,
            node_id_mode_actual=body.tag_bindings.node_id_mode_actual,
            node_id_enabled=body.tag_bindings.node_id_enabled,
            mode_int_map=body.tag_bindings.mode_int_map,
        ),
        control_opts=ControlOpts(
            no_out_limits_in_manual=body.control_opts.no_out_limits_in_manual,
            obey_sp_limits_if_cas=body.control_opts.obey_sp_limits_if_cas,
            track_in_manual=body.control_opts.track_in_manual,
            track_enable=body.control_opts.track_enable,
            direct_acting=body.control_opts.direct_acting,
            sp_track_retained_target=body.control_opts.sp_track_retained_target,
            sp_pv_track_in_lo_or_iman=body.control_opts.sp_pv_track_in_lo_or_iman,
            sp_pv_track_in_rout=body.control_opts.sp_pv_track_in_rout,
            sp_pv_track_in_man=body.control_opts.sp_pv_track_in_man,
            use_pv_for_bkcal_out=body.control_opts.use_pv_for_bkcal_out,
        ),
        io_opts=IOOpts(
            low_cutoff=body.io_opts.low_cutoff,
            target_to_man_if_fault=body.io_opts.target_to_man_if_fault,
            fault_state_to_value=body.io_opts.fault_state_to_value,
            increase_to_close=body.io_opts.increase_to_close,
            sp_pv_track_in_lo_or_iman=body.io_opts.sp_pv_track_in_lo_or_iman,
            sp_pv_track_in_man=body.io_opts.sp_pv_track_in_man,
        ),
        ai_config=AIConfig(
            engine=AIEngine(body.ai_config.engine),
            objective=ControlObjective(body.ai_config.objective),
            dead_time_l=body.ai_config.dead_time_l,
            limit_min=body.ai_config.limit_min,
            limit_max=body.ai_config.limit_max,
            rl_fallback_kp=body.ai_config.rl_fallback_kp,
            rl_fallback_kd=body.ai_config.rl_fallback_kd,
            rl_learning_rate=body.ai_config.rl_learning_rate,
            rl_train_interval=body.ai_config.rl_train_interval,
        ),
        tuning_write_mode=TuningWriteMode(body.tuning_write_mode),
        max_tuning_change_pct=body.max_tuning_change_pct,
        stability_band_pct=body.stability_band_pct,
        mode_normal=ControllerMode(body.mode_normal),
        permitted_modes={ControllerMode(m) for m in body.permitted_modes},
        sp_hi_lim=body.sp_hi_lim,
        sp_lo_lim=body.sp_lo_lim,
        sp_rate_up=body.sp_rate_up,
        sp_rate_dn=body.sp_rate_dn,
        out_hi_lim=body.out_hi_lim,
        out_lo_lim=body.out_lo_lim,
        arw_hi_lim=body.arw_hi_lim,
        arw_lo_lim=body.arw_lo_lim,
        pv_ftime=body.pv_ftime,
        sp_ftime=body.sp_ftime,
        low_cut=body.low_cut,
        ff_enable=body.ff_enable,
        ff_gain=body.ff_gain,
        shed_opt=ControllerMode(body.shed_opt),
        shed_time_s=body.shed_time_s,
    )


# Mapping from ControllerUpdate field names to domain nested-object builders
_NESTED_BUILDERS: dict[str, tuple[type, callable]] = {
    "pid_params": (PIDParamsDTO, lambda dto: PIDParams(
        gain=dto.gain, reset=dto.reset, rate=dto.rate, alpha=dto.alpha, deadband=dto.deadband,
    )),
    "pv_scale": (ScaleConfigDTO, lambda dto: ScaleConfig(
        eu_min=dto.eu_min, eu_max=dto.eu_max, unit=dto.unit,
    )),
    "out_scale": (ScaleConfigDTO, lambda dto: ScaleConfig(
        eu_min=dto.eu_min, eu_max=dto.eu_max, unit=dto.unit,
    )),
    "tag_bindings": (TagBindingsDTO, lambda dto: TagBindings(
        node_id_pv=dto.node_id_pv, node_id_sp=dto.node_id_sp, node_id_co=dto.node_id_co,
        node_id_integral=dto.node_id_integral, node_id_bkcal_in=dto.node_id_bkcal_in,
        node_id_bkcal_out=dto.node_id_bkcal_out, node_id_kp=dto.node_id_kp,
        node_id_ti=dto.node_id_ti, node_id_td=dto.node_id_td,
        node_id_mode_target=dto.node_id_mode_target,
        node_id_mode_actual=dto.node_id_mode_actual,
        node_id_enabled=dto.node_id_enabled,
        mode_int_map=dto.mode_int_map,
    )),
    "control_opts": (ControlOptsDTO, lambda dto: ControlOpts(
        no_out_limits_in_manual=dto.no_out_limits_in_manual,
        obey_sp_limits_if_cas=dto.obey_sp_limits_if_cas,
        track_in_manual=dto.track_in_manual, track_enable=dto.track_enable,
        direct_acting=dto.direct_acting, sp_track_retained_target=dto.sp_track_retained_target,
        sp_pv_track_in_lo_or_iman=dto.sp_pv_track_in_lo_or_iman,
        sp_pv_track_in_rout=dto.sp_pv_track_in_rout, sp_pv_track_in_man=dto.sp_pv_track_in_man,
        use_pv_for_bkcal_out=dto.use_pv_for_bkcal_out,
    )),
    "io_opts": (IOOptsDTO, lambda dto: IOOpts(
        low_cutoff=dto.low_cutoff, target_to_man_if_fault=dto.target_to_man_if_fault,
        fault_state_to_value=dto.fault_state_to_value, increase_to_close=dto.increase_to_close,
        sp_pv_track_in_lo_or_iman=dto.sp_pv_track_in_lo_or_iman,
        sp_pv_track_in_man=dto.sp_pv_track_in_man,
    )),
    "ai_config": (AIConfigDTO, lambda dto: AIConfig(
        engine=AIEngine(dto.engine), objective=ControlObjective(dto.objective),
        dead_time_l=dto.dead_time_l,
        limit_min=dto.limit_min, limit_max=dto.limit_max,
        rl_fallback_kp=dto.rl_fallback_kp, rl_fallback_kd=dto.rl_fallback_kd,
        rl_learning_rate=dto.rl_learning_rate, rl_train_interval=dto.rl_train_interval,
    )),
}

# Enum fields that need conversion from string
_ENUM_FIELDS: dict[str, type] = {
    "execution_mode": ExecutionMode,
    "process_speed": ProcessSpeed,
    "pid_structure": PIDStructure,
    "integral_type": IntegralType,
    "tuning_write_mode": TuningWriteMode,
    "mode_normal": ControllerMode,
    "shed_opt": ControllerMode,
}


@router.get("", response_model=list[ControllerResponse])
async def list_controllers(
    _user: Annotated[UserClaims, Depends(require_user)],
    repo: Annotated[SQLiteRepository, Depends(get_repo)],
) -> list[ControllerResponse]:
    controllers = await repo.list_all()
    return [_to_response(c) for c in controllers]


@router.post("", response_model=ControllerResponse, status_code=status.HTTP_201_CREATED)
async def create_controller(
    body: ControllerCreate,
    request: Request,
    user: Annotated[UserClaims, Depends(require_admin)],
    repo: Annotated[SQLiteRepository, Depends(get_repo)],
    audit_repo: Annotated[AuditRepository, Depends(get_audit_repo)],
) -> ControllerResponse:
    controller = _body_to_controller(body)
    saved = await repo.save(controller)
    # The simulator only learned about controllers at startup / project open,
    # so without this the new loop is a ghost to /simulator/* until restart.
    _sync_simulator_registration(request, saved, saved.id)
    await audit_repo.record(
        user.user_id, user.username, AuditAction.CREATE_CONTROLLER,
        f"controller:{saved.id}", f'{{"name": "{saved.name}"}}',
    )
    return _to_response(saved)


@router.get("/{controller_id}", response_model=ControllerResponse)
async def get_controller(
    controller_id: int,
    _user: Annotated[UserClaims, Depends(require_user)],
    repo: Annotated[SQLiteRepository, Depends(get_repo)],
) -> ControllerResponse:
    try:
        controller = await repo.get(controller_id)
    except KeyError:
        raise ControllerNotFoundError(controller_id) from None
    return _to_response(controller)


@router.put("/{controller_id}", response_model=ControllerResponse)
async def update_controller(
    controller_id: int,
    body: ControllerUpdate,
    request: Request,
    user: Annotated[UserClaims, Depends(require_admin)],
    repo: Annotated[SQLiteRepository, Depends(get_repo)],
    audit_repo: Annotated[AuditRepository, Depends(get_audit_repo)],
) -> ControllerResponse:
    try:
        controller = await repo.get(controller_id)
    except KeyError:
        raise ControllerNotFoundError(controller_id) from None

    updates: dict = {}
    body_dict = body.model_dump(exclude_unset=True)

    for field_name, value in body_dict.items():
        if value is None:
            continue
        if field_name in _NESTED_BUILDERS:
            dto = getattr(body, field_name)
            _, builder = _NESTED_BUILDERS[field_name]
            updates[field_name] = builder(dto)
        elif field_name in _ENUM_FIELDS:
            updates[field_name] = _ENUM_FIELDS[field_name](value)
        elif field_name == "permitted_modes":
            updates[field_name] = {ControllerMode(m) for m in value}
        else:
            updates[field_name] = value

    # Capture old/new for audit trail
    old_values: dict = {}
    new_values: dict = {}
    for key, new_val in updates.items():
        old_val = getattr(controller, key)
        old_values[key] = str(old_val) if hasattr(old_val, '__dataclass_fields__') else old_val
        new_values[key] = str(new_val) if hasattr(new_val, '__dataclass_fields__') else new_val

    if updates:
        controller = replace(controller, **updates)
        await repo.save(controller)

    # Re-register OPC-UA tag mappings if tag_bindings were updated
    if "tag_bindings" in updates:
        _reregister_opcua(request, controller)

    # Propagate the persisted edit to the running loop so the PIDWorker stops
    # using the controller it was started with. Without this an execution_mode
    # change never reaches the live worker: SP/CO ownership (and whether the IO
    # worker writes CO) stays on the old mode until daemon restart.
    if updates:
        loop_mgr = getattr(request.app.state, "loop_manager", None)
        if loop_mgr is not None:
            loop_mgr.update_controller(controller)

    # Push tuning to the DCS/simulator when a SUPERVISORY loop's PID params are
    # edited: SmartPID does not run that PID, so the change is only real once it
    # reaches the external controller over OPC-UA. io_worker reads it back into
    # telemetry, closing the loop so the faceplate reflects the applied value.
    if "pid_params" in updates and controller.execution_mode is ExecutionMode.SUPERVISORY:
        opcua = getattr(request.app.state, "opcua_adapter", None)
        if opcua is not None and getattr(opcua, "is_connected", False):
            p = controller.pid_params
            try:
                opcua.write_pid_params(controller.id, p.gain, p.reset, p.rate)
            except Exception:
                logger.exception(
                    "supervisory_param_write_failed controller_id=%d", controller.id,
                )

    # Hot-reload AI Worker when ai_config, process_speed, tss_s, or
    # scan_rate_s changes. The fuzzy stats window is derived from
    # tss_s / scan_rate_s, so the engine must be rebuilt when either moves.
    if (
        "ai_config" in updates
        or "process_speed" in updates
        or "tss_s" in updates
        or "scan_rate_s" in updates
    ):
        loop_mgr = getattr(request.app.state, "loop_manager", None)
        if loop_mgr is not None:
            loop_mgr.restart_ai_worker(controller)

    audit_detail = json.dumps({
        "old": {k: str(v) for k, v in old_values.items()},
        "new": {k: str(v) for k, v in new_values.items()},
    })
    sew = getattr(request.app.state, "system_event_worker", None)
    changed_keys = ", ".join(updates.keys()) if updates else "no changes"
    await audit_repo.record(
        user.user_id, user.username, AuditAction.UPDATE_CONTROLLER,
        f"controller:{controller_id}", audit_detail,
    )
    if sew is not None and updates:
        import contextlib
        with contextlib.suppress(Exception):
            sew.emit(
                source="USER",
                severity="INFO",
                message=(
                    f"{user.username} updated controller {controller.name} "
                    f"({changed_keys})"
                ),
            )
    return _to_response(controller)


def _reregister_opcua(request: Request, controller: Controller) -> None:
    """Re-register controller tag mappings with the OPC-UA adapter (if active)."""
    adapter = getattr(request.app.state, "opcua_adapter", None)
    if adapter is None:
        return
    tb = controller.tag_bindings
    if not tb.node_id_pv:
        return
    adapter.register_controller(
        controller_id=controller.id,
        node_id_pv=tb.node_id_pv,
        node_id_sp=tb.node_id_sp,
        node_id_co=tb.node_id_co,
        node_id_integral=tb.node_id_integral,
        node_id_bkcal_in=tb.node_id_bkcal_in,
        node_id_bkcal_out=tb.node_id_bkcal_out,
        node_id_kp=tb.node_id_kp,
        node_id_ti=tb.node_id_ti,
        node_id_td=tb.node_id_td,
        node_id_mode_target=tb.node_id_mode_target,
        node_id_mode_actual=tb.node_id_mode_actual,
        node_id_enabled=tb.node_id_enabled,
        mode_int_map=tb.mode_int_map,
    )


@router.delete("/{controller_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_controller(
    controller_id: int,
    request: Request,
    user: Annotated[UserClaims, Depends(require_admin)],
    repo: Annotated[SQLiteRepository, Depends(get_repo)],
    audit_repo: Annotated[AuditRepository, Depends(get_audit_repo)],
) -> Response:
    try:
        await repo.delete(controller_id)
    except KeyError:
        raise ControllerNotFoundError(controller_id) from None
    # Mirror of create: a simulator entry for a deleted loop would keep being
    # integrated and keep answering /simulator/* for a controller that is gone.
    _sync_simulator_registration(request, None, controller_id)
    await audit_repo.record(
        user.user_id, user.username, AuditAction.DELETE_CONTROLLER,
        f"controller:{controller_id}", None,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{controller_id}/alarm-config", response_model=AlarmConfigResponse)
async def get_alarm_config(
    controller_id: int,
    _user: Annotated[UserClaims, Depends(require_user)],
    repo: Annotated[SQLiteRepository, Depends(get_repo)],
    alarm_repo: Annotated[AlarmRepository, Depends(get_alarm_repo)],
) -> AlarmConfigResponse:
    """Get alarm thresholds for a controller."""
    try:
        await repo.get(controller_id)
    except KeyError:
        raise ControllerNotFoundError(controller_id) from None
    rows = await alarm_repo.get_alarm_config(controller_id)
    thresholds = [
        AlarmThreshold(
            alarm_type=r["alarm_type"],
            priority=r["priority"],
            limit=r["limit"],
            enabled=bool(r["enabled"]),
            deadband=r["deadband"],
            delay_on_s=r.get("delay_on_s", 0.0),
            delay_off_s=r.get("delay_off_s", 0.0),
        )
        for r in rows
    ]
    return AlarmConfigResponse(controller_id=controller_id, thresholds=thresholds)


@router.put("/{controller_id}/alarm-config", response_model=AlarmConfigResponse)
async def update_alarm_config(
    controller_id: int,
    body: AlarmConfigUpdate,
    user: Annotated[UserClaims, Depends(require_admin)],
    repo: Annotated[SQLiteRepository, Depends(get_repo)],
    alarm_repo: Annotated[AlarmRepository, Depends(get_alarm_repo)],
    alarm_wkr: Annotated[AlarmWorker | None, Depends(get_alarm_worker)],
    audit_repo: Annotated[AuditRepository, Depends(get_audit_repo)],
) -> AlarmConfigResponse:
    """Update alarm thresholds for a controller (requires supervisor)."""
    try:
        await repo.get(controller_id)
    except KeyError:
        raise ControllerNotFoundError(controller_id) from None
    threshold_dicts = [
        {
            "alarm_type": str(t.alarm_type),
            "priority": str(t.priority),
            "limit": t.limit,
            "enabled": t.enabled,
            "deadband": t.deadband,
            "delay_on_s": t.delay_on_s,
            "delay_off_s": t.delay_off_s,
        }
        for t in body.thresholds
    ]
    await alarm_repo.save_alarm_config(controller_id, threshold_dicts)
    # Hot-reload alarm config in the running AlarmWorker
    if alarm_wkr is not None:
        alarm_wkr.update_config(controller_id, _thresholds_to_alarm_config(body.thresholds))
    await audit_repo.record(
        user.user_id, user.username, AuditAction.CONFIG_ALARM,
        f"controller:{controller_id}",
        f'{{"thresholds": {len(body.thresholds)}}}',
    )
    return AlarmConfigResponse(controller_id=controller_id, thresholds=body.thresholds)
