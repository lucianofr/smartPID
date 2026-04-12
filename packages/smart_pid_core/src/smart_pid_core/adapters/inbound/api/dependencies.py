"""FastAPI dependency injection functions."""
from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from fastapi import Depends, HTTPException, Request, status

from smart_pid_core.adapters.inbound.api.auth import decode_access_token
from smart_pid_domain.dtos.auth import UserClaims

if TYPE_CHECKING:
    from smart_pid_core.adapters.inbound.simulator_adapter import SimulatorAdapter
    from smart_pid_core.adapters.outbound.ai_repo import AIRepository
    from smart_pid_core.adapters.outbound.alarm_repo import AlarmRepository
    from smart_pid_core.adapters.outbound.audit_repo import AuditRepository
    from smart_pid_core.adapters.outbound.historian import SQLiteHistorian
    from smart_pid_core.adapters.outbound.opcua_adapter import OPCUAAdapter
    from smart_pid_core.adapters.outbound.sqlite_repo import SQLiteRepository
    from smart_pid_core.adapters.outbound.system_event_repo import SystemEventRepository
    from smart_pid_core.adapters.outbound.user_repo import UserRepository
    from smart_pid_core.application.event_bus import EventBus
    from smart_pid_core.application.loop_manager import LoopManager
    from smart_pid_core.application.workers.alarm_worker import AlarmWorker
    from smart_pid_core.application.workers.stats_worker import StatsWorker
    from smart_pid_core.application.workers.system_event_worker import (
        SystemEventWorker,
    )
    from smart_pid_core.config import CoreSettings


def get_repo(request: Request) -> SQLiteRepository:
    return request.app.state.repo


def get_historian(request: Request) -> SQLiteHistorian:
    return request.app.state.historian


def get_user_repo(request: Request) -> UserRepository:
    return request.app.state.user_repo


def get_loop_manager(request: Request) -> LoopManager:
    return request.app.state.loop_manager


def get_settings(request: Request) -> CoreSettings:
    return request.app.state.settings


def get_current_user(request: Request) -> UserClaims:
    """Extract and validate JWT from Authorization header."""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
        )
    token = auth_header.removeprefix("Bearer ")
    settings: CoreSettings = request.app.state.settings
    try:
        payload = decode_access_token(token, secret=settings.jwt_secret)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from None
    return UserClaims(
        user_id=payload["sub"],
        username=payload["username"],
        role=payload["role"].upper(),
    )


_ROLE_LEVEL = {"OPERATOR": 0, "SUPERVISOR": 1, "ADMIN": 2}


def require_operator(
    user: Annotated[UserClaims, Depends(get_current_user)],
) -> UserClaims:
    """Verify the current user has at least operator role."""
    if _ROLE_LEVEL.get(user.role.upper(), -1) < _ROLE_LEVEL["OPERATOR"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operator access required",
        )
    return user


def require_supervisor(
    user: Annotated[UserClaims, Depends(get_current_user)],
) -> UserClaims:
    """Verify the current user has at least supervisor role."""
    if _ROLE_LEVEL.get(user.role.upper(), -1) < _ROLE_LEVEL["SUPERVISOR"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Supervisor access required",
        )
    return user


def require_admin(
    user: Annotated[UserClaims, Depends(get_current_user)],
) -> UserClaims:
    """Verify the current user has admin role."""
    if _ROLE_LEVEL.get(user.role.upper(), -1) < _ROLE_LEVEL["ADMIN"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user


def get_simulator_adapter(request: Request) -> SimulatorAdapter:
    adapter = getattr(request.app.state, "simulator_adapter", None)
    if adapter is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Simulator not enabled",
        )
    return adapter


def get_opcua_adapter(request: Request) -> OPCUAAdapter:
    adapter = getattr(request.app.state, "opcua_adapter", None)
    if adapter is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="OPC-UA not available (simulator mode active)",
        )
    return adapter


def get_opcua_adapter_optional(request: Request) -> OPCUAAdapter | None:
    return getattr(request.app.state, "opcua_adapter", None)


def get_stats_workers(request: Request) -> dict[int, StatsWorker]:
    return getattr(request.app.state, "stats_workers", {})


def get_ai_workers(request: Request) -> dict[int, object]:
    # Read live workers from loop_manager (not the static startup snapshot)
    loop_mgr = getattr(request.app.state, "loop_manager", None)
    if loop_mgr is not None:
        return loop_mgr.get_ai_workers()
    return getattr(request.app.state, "ai_workers", {})


def get_ai_repo(request: Request) -> AIRepository:
    repo = getattr(request.app.state, "ai_repo", None)
    if repo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AI repository not available",
        )
    return repo


def get_execution_mode(request: Request) -> str:
    return getattr(request.app.state, "execution_mode", "monitor")


def get_event_bus(request: Request) -> EventBus:
    bus = getattr(request.app.state, "event_bus", None)
    if bus is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Event bus not available",
        )
    return bus


def get_alarm_repo(request: Request) -> AlarmRepository:
    return request.app.state.alarm_repo


def get_alarm_worker(request: Request) -> AlarmWorker | None:
    return getattr(request.app.state, "alarm_worker", None)


def get_audit_repo(request: Request) -> AuditRepository:
    return request.app.state.audit_repo


def get_system_event_repo(request: Request) -> SystemEventRepository:
    return request.app.state.system_event_repo


def get_system_event_worker(request: Request) -> SystemEventWorker | None:
    """Return the SystemEventWorker used to broadcast user-action events
    onto EVENT.SYSTEM (displayed live in the HMI alarm panel).

    None when the backend is running in a mode without event broadcast
    (unit tests, monitor-only). Callers should treat it as best-effort.
    """
    return getattr(request.app.state, "system_event_worker", None)


# ----- Audit helper --------------------------------------------------------


async def audit_and_broadcast(
    audit_repo: AuditRepository,
    sew: SystemEventWorker | None,
    user_id: int,
    username: str,
    action,  # AuditAction
    resource: str | None,
    detail: str | None,
    *,
    severity: str = "INFO",
    message: str | None = None,
) -> None:
    """Record an audit entry AND emit a matching EVENT.SYSTEM.

    The audit trail in ``Log_Auditoria`` stays authoritative for search and
    compliance; the system event gives the HMI alarm panel a live feed of
    user actions (SP changes, mode changes, PID tuning, AI start/stop, …).
    """
    await audit_repo.record(user_id, username, action, resource, detail)
    if sew is None:
        return
    msg = message or (
        f"{username} — {action} on {resource}"
        + (f" ({detail})" if detail else "")
    )
    # Never let a broadcast failure abort the HTTP request.
    import contextlib
    with contextlib.suppress(Exception):
        sew.emit(source="USER", severity=severity, message=msg)
