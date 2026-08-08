"""AI optimization router — status, history, and start/stop/pause controls."""

import json
from typing import TYPE_CHECKING, Annotated

import msgpack
from fastapi import APIRouter, Depends, HTTPException, Request, status

from smart_pid_core.adapters.inbound.api.dependencies import (
    get_ai_repo,
    get_ai_workers,
    get_audit_repo,
    get_event_bus,
    get_settings,
    require_admin,
    require_user,
)
from smart_pid_core.adapters.outbound.ai_repo import AIRepository  # noqa: TC001
from smart_pid_core.adapters.outbound.audit_repo import AuditRepository  # noqa: TC001
from smart_pid_core.application.event_bus import EventBus  # noqa: TC001
from smart_pid_core.config import CoreSettings
from smart_pid_core.domain.services.fuzzy_engine_v2 import InferenceTrace, MFSet
from smart_pid_domain.dtos.ai import (
    AIHistoryResponse,
    AIStatusResponse,
    AITuningLogEntry,
    FuzzyInputTrace,
    FuzzyMembershipFunction,
    FuzzyOutputTrace,
    FuzzyRuleTrace,
    FuzzyTraceResponse,
)
from smart_pid_domain.dtos.auth import UserClaims  # noqa: TC001
from smart_pid_domain.enums import AIEngine, AuditAction, ControlObjective

if TYPE_CHECKING:
    from smart_pid_core.application.workers.ai_worker import AIWorker

router = APIRouter()


async def _get_ai_worker(
    controller_id: int,
    settings: Annotated[CoreSettings, Depends(get_settings)],
    ai_workers: Annotated[dict[int, "AIWorker"], Depends(get_ai_workers)],
) -> "AIWorker":
    """Retrieve AI worker for controller, or raise 404."""
    worker = ai_workers.get(controller_id)
    if worker is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No AI worker for controller {controller_id}",
        )
    return worker


_SATURATED_BREAKPOINT = 1.0e6
_FALLBACK_DOMAIN_SPAN = 1.0


def _mfset_domain(mfset: MFSet) -> tuple[float, float]:
    """Plot bounds for one input's membership functions.

    Disturbance Rejection models an unbounded upper tail with a trapezoid
    plateau pinned to a very large sentinel (``_RIGHT_SAT`` in
    fuzzy_engine_v2.py) so "very slow"/"very big" stays fully-belonging
    past the last real breakpoint. Including that sentinel verbatim would
    collapse the plotted x-axis to a vertical line, so breakpoints at or
    beyond 1e6 are treated as saturated and excluded from the max.
    """
    breakpoints = [p for _, params in mfset.values() for p in params]
    lo = min(breakpoints)
    finite = [p for p in breakpoints if p < _SATURATED_BREAKPOINT]
    hi = max(finite) if finite else lo
    if hi <= lo:
        hi = lo + _FALLBACK_DOMAIN_SPAN
    return lo, hi


def _fuzzy_input_trace(name: str, value: float, trace: InferenceTrace) -> FuzzyInputTrace:
    mfset = trace.mfsets[name]
    domain_min, domain_max = _mfset_domain(mfset)
    # Keep the crisp-value marker on-canvas even if it sits outside the
    # MF-derived domain.
    domain_min = min(domain_min, value)
    domain_max = max(domain_max, value)
    degrees = trace.memberships[name]
    functions = [
        FuzzyMembershipFunction(
            label=label, kind=kind, params=list(params),
            degree=degrees.get(label, 0.0),
        )
        for label, (kind, params) in mfset.items()
    ]
    return FuzzyInputTrace(
        name=name, value=value, domain_min=domain_min, domain_max=domain_max,
        functions=functions,
    )


def _fuzzy_trace_response(
    controller_id: int, objective: ControlObjective, trace: InferenceTrace,
) -> FuzzyTraceResponse:
    rules = [
        FuzzyRuleTrace(
            index=i, conditions=dict(condition), output=out_lvl,
            strength=strength, fired=strength > 0.0,
        )
        for i, ((condition, out_lvl), strength) in enumerate(
            zip(trace.rules, trace.rule_strengths, strict=True),
        )
    ]
    outputs = [
        FuzzyOutputTrace(label=label, center=center, strength=trace.output_strengths[label])
        for label, center in trace.output_centers.items()
    ]
    return FuzzyTraceResponse(
        controller_id=controller_id,
        objective=objective,
        timestamp=trace.timestamp,
        inputs=[
            _fuzzy_input_trace(name, value, trace)
            for name, value in trace.values.items()
        ],
        rules=rules,
        outputs=outputs,
        delta_ti=trace.delta,
    )


@router.get("/{controller_id}/ai/status", response_model=AIStatusResponse)
async def get_ai_status(
    controller_id: int,
    user: Annotated[UserClaims, Depends(require_user)],
    settings: Annotated[CoreSettings, Depends(get_settings)],
    ai_workers: Annotated[dict[int, "AIWorker"], Depends(get_ai_workers)],
    audit_repo: Annotated[AuditRepository, Depends(get_audit_repo)],
) -> AIStatusResponse:
    """Return AI status for controller."""
    worker = ai_workers.get(controller_id)
    if worker is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No AI worker for controller {controller_id}",
        )
    return AIStatusResponse(
        controller_id=controller_id,
        # `engine` is required on AIStatusResponse and was never passed, so
        # this endpoint raised a Pydantic ValidationError -> 500 on every call
        # and the HMI could never show AI state.
        engine=worker._ai_config.engine,
        objective=worker._ai_config.objective,
        speed=worker._controller.process_speed,
        current_ki=worker._ki_current,
        enabled=worker.is_enabled,
        paused=worker.is_paused,
    )


@router.get("/{controller_id}/ai/history", response_model=AIHistoryResponse)
async def get_ai_history(
    controller_id: int,
    user: Annotated[UserClaims, Depends(require_user)],
    settings: Annotated[CoreSettings, Depends(get_settings)],
    ai_repo: Annotated[AIRepository, Depends(get_ai_repo)],
) -> AIHistoryResponse:
    """Return AI history for controller optimization."""
    entries = await ai_repo.get_tuning_history(controller_id=controller_id, limit=50)
    return AIHistoryResponse(
        controller_id=controller_id,
        entries=[AITuningLogEntry(**e) for e in entries],
    )


@router.get("/{controller_id}/ai/fuzzy", response_model=FuzzyTraceResponse)
async def get_ai_fuzzy_trace(
    controller_id: int,
    user: Annotated[UserClaims, Depends(require_user)],
    worker: Annotated["AIWorker", Depends(_get_ai_worker)],
) -> FuzzyTraceResponse:
    """Return the last fuzzy inference trace for controller, for HMI plotting."""
    if worker._ai_config.engine != AIEngine.FUZZY:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Controller {controller_id} AI engine is not FUZZY",
        )
    trace: InferenceTrace | None = worker._engine.last_trace
    if trace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No fuzzy inference has run yet for controller {controller_id}",
        )
    return _fuzzy_trace_response(controller_id, worker._engine.objective, trace)


@router.post("/{controller_id}/ai/start")
async def start_ai(
    _admin: Annotated[UserClaims, Depends(require_admin)],
    controller_id: int,
    settings: Annotated[CoreSettings, Depends(get_settings)],
    ai_workers: Annotated[dict[int, "AIWorker"], Depends(get_ai_workers)],
    audit_repo: Annotated[AuditRepository, Depends(get_audit_repo)],
    request: Request,
    bus: Annotated[EventBus, Depends(get_event_bus)],
) -> dict:
    """Start AI optimization for a controller loop."""
    worker = ai_workers.get(controller_id)
    if worker is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No AI worker for controller {controller_id}",
        )
    await audit_repo.record(
        _admin.user_id,
        _admin.username,
        AuditAction.START_AI_OPTIMIZATION,
        f"controller:{controller_id}",
        json.dumps({"action": "start"}),
    )
    # Set directly first: the CMD below travels on a publisher created and
    # closed within this request, which can lose its first message to the
    # ZeroMQ slow-joiner race. The bus send is kept for other subscribers.
    worker.set_enabled(True)
    worker.set_paused(False)
    pub = bus.create_publisher()
    cmd = {"controller_id": controller_id, "action": "start"}
    pub.send(f"CMD.AI.{controller_id}".encode(), msgpack.packb(cmd))
    pub.close()
    return {"ok": True, "controller_id": controller_id, "detail": "AI start command sent"}


@router.post("/{controller_id}/ai/stop")
async def stop_ai(
    _admin: Annotated[UserClaims, Depends(require_admin)],
    controller_id: int,
    settings: Annotated[CoreSettings, Depends(get_settings)],
    ai_workers: Annotated[dict[int, "AIWorker"], Depends(get_ai_workers)],
    audit_repo: Annotated[AuditRepository, Depends(get_audit_repo)],
    request: Request,
    bus: Annotated[EventBus, Depends(get_event_bus)],
) -> dict:
    """Stop AI optimization for a controller loop."""
    worker = ai_workers.get(controller_id)
    if worker is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No AI worker for controller {controller_id}",
        )
    await audit_repo.record(
        _admin.user_id,
        _admin.username,
        AuditAction.STOP_AI_OPTIMIZATION,
        f"controller:{controller_id}",
        json.dumps({"action": "stop"}),
    )
    worker.set_enabled(False)
    worker.set_paused(False)
    pub = bus.create_publisher()
    cmd = {"controller_id": controller_id, "action": "stop"}
    pub.send(f"CMD.AI.{controller_id}".encode(), msgpack.packb(cmd))
    pub.close()
    return {"ok": True, "controller_id": controller_id, "detail": "AI stop command sent"}


@router.post("/{controller_id}/ai/pause")
async def pause_ai(
    _admin: Annotated[UserClaims, Depends(require_admin)],
    controller_id: int,
    settings: Annotated[CoreSettings, Depends(get_settings)],
    ai_workers: Annotated[dict[int, "AIWorker"], Depends(get_ai_workers)],
    audit_repo: Annotated[AuditRepository, Depends(get_audit_repo)],
    request: Request,
    bus: Annotated[EventBus, Depends(get_event_bus)],
) -> dict:
    """Pause AI optimization for a controller loop."""
    worker = ai_workers.get(controller_id)
    if worker is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No AI worker for controller {controller_id}",
        )
    await audit_repo.record(
        _admin.user_id,
        _admin.username,
        AuditAction.PAUSE_AI_OPTIMIZATION,
        f"controller:{controller_id}",
        json.dumps({"action": "pause"}),
    )
    worker.set_paused(True)
    pub = bus.create_publisher()
    cmd = {"controller_id": controller_id, "action": "pause"}
    pub.send(f"CMD.AI.{controller_id}".encode(), msgpack.packb(cmd))
    pub.close()
    return {"ok": True, "controller_id": controller_id, "detail": "AI pause command sent"}
