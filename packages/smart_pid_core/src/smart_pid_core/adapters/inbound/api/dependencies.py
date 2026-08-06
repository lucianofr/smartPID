"""FastAPI dependency injection functions."""
from __future__ import annotations

from ipaddress import ip_address, ip_network
from typing import TYPE_CHECKING, Annotated

from fastapi import Depends, HTTPException, Request, status

from smart_pid_core.adapters.inbound.api.auth import decode_access_token
from smart_pid_domain.dtos.auth import UserClaims
from smart_pid_domain.enums import UserRole

if TYPE_CHECKING:
    from collections.abc import Sequence

    from starlette.requests import HTTPConnection

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
    from smart_pid_core.application.session_registry import SessionRegistry
    from smart_pid_core.application.trend_buffer import TrendBuffer
    from smart_pid_core.application.workers.alarm_worker import AlarmWorker
    from smart_pid_core.application.workers.io_worker import IOWorker
    from smart_pid_core.application.workers.stats_worker import StatsWorker
    from smart_pid_core.application.workers.system_event_worker import (
        SystemEventWorker,
    )
    from smart_pid_core.config import CoreSettings


def get_repo(request: Request) -> SQLiteRepository:
    return request.app.state.repo


def get_historian(request: Request) -> SQLiteHistorian:
    return request.app.state.historian


def get_trend_buffer(request: Request) -> TrendBuffer:
    return request.app.state.trend_buffer


def get_user_repo(request: Request) -> UserRepository:
    return request.app.state.user_repo


def get_loop_manager(request: Request) -> LoopManager:
    return request.app.state.loop_manager


def get_settings(request: Request) -> CoreSettings:
    return request.app.state.settings


def get_session_registry(request: Request) -> SessionRegistry:
    return request.app.state.session_registry


def _peer_is_trusted_proxy(peer: str, trusted_proxies: Sequence[str]) -> bool:
    """Is the transport peer one of the configured proxies?

    Entries are pre-validated by ``CoreSettings``, so parsing cannot fail here.
    A peer that is not an IP at all ("unknown", a UNIX socket) is never
    trusted.
    """
    try:
        address = ip_address(peer)
    except ValueError:
        return False
    return any(address in ip_network(net, strict=False) for net in trusted_proxies)


def client_ip(conn: HTTPConnection, *, trusted_proxies: Sequence[str]) -> str:
    """Source address of the caller — for the login throttle and the session panel.

    ``conn`` is a ``Request`` or a ``WebSocket``; both carry the peer address
    and the headers, and both need the SAME answer or the throttle and the
    panel would disagree about who is calling.

    ``X-Forwarded-For`` is believed ONLY when the transport peer is itself a
    configured proxy. Without that check, enabling forwarding on a deployment
    that publishes the API port would let any caller mint a fresh login-throttle
    budget per forged address and write fake addresses into the access log.

    Of the forwarded chain the RIGHTMOST hop wins: everything to its left is
    whatever the caller wrote, while the last element is the one appended by
    the proxy we trust — the peer it actually saw. It must also parse as an
    address, so nothing arbitrary reaches a registry key or an audit row.

    ponytail: assumes ONE trusted hop (Traefik). Behind a second proxy
    (Cloudflare -> Traefik) the rightmost hop is Traefik itself; that needs a
    hop count, not another header.
    """
    peer = conn.client.host if conn.client else "unknown"
    if not _peer_is_trusted_proxy(peer, trusted_proxies):
        return peer
    # Every physical header line, in order. ``headers.get`` returns only the
    # FIRST of duplicated lines, so a proxy that appends its own line instead
    # of coalescing would otherwise leave the caller's line deciding.
    hops = [
        hop.strip()
        for line in conn.headers.getlist("x-forwarded-for")
        for hop in line.split(",")
        if hop.strip()
    ]
    if not hops:
        return peer
    try:
        return str(ip_address(hops[-1]))
    except ValueError:
        return peer


async def resolve_token_principal(
    token: str,
    *,
    settings: CoreSettings,
    user_repo: UserRepository,
) -> UserClaims | None:
    """Resolve a bearer token to the CURRENT stored principal, or ``None``.

    The JWT is an *authentication* credential only: it proves which user is
    calling. Authorization is a property of the stored user record and is
    re-read on every request, so an admin's demotion or deactivation takes
    effect on the very next call instead of after the token's 8h lifetime
    (E2E-044 — a demoted admin could otherwise mint a permanent backdoor
    account that outlived their own session).

    Returns ``None`` — each caller signals rejection in its own protocol —
    when the token is unusable for any reason:

    * bad signature, expiry, or missing/malformed claims;
    * a legacy role vocabulary ("ADMIN"/"SUPERVISOR"/"OPERATOR"). That claim
      is validated purely as a *token-format marker*: its presence means a
      pre-cutover token, which is rejected wholesale so the client performs a
      single forced re-login (spec §9.5). The value is never mapped, and it
      is never used to authorize;
    * the subject no longer exists, has been deactivated, or carries a stored
      role outside the two-role model.
    """
    try:
        payload = decode_access_token(token, secret=settings.jwt_secret)
        UserClaims(
            user_id=payload["sub"],
            username=payload["username"],
            role=payload["role"],  # strict: only "admin" | "user" validate
        )
    except Exception:
        # jwt.PyJWTError, KeyError, pydantic.ValidationError — all unusable.
        return None

    user = await user_repo.get_by_id(payload["sub"])
    if user is None or not user.active:
        return None
    try:
        role = UserRole(user.role)
    except ValueError:
        return None
    return UserClaims(user_id=user.id, username=user.username, role=role)


async def get_current_user(request: Request) -> UserClaims:
    """Authenticate the caller and return their CURRENT claims.

    Single upstream of every ``require_*`` gate, so refreshing the role here
    is what makes revocation immediate everywhere. Any failure is a 401 so
    the client performs one forced re-login.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
        )
    principal = await resolve_token_principal(
        auth_header.removeprefix("Bearer "),
        settings=request.app.state.settings,
        user_repo=request.app.state.user_repo,
    )
    if principal is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    request.app.state.session_registry.touch(
        user_id=principal.user_id,
        username=principal.username,
        role=str(principal.role),
        ip=client_ip(request, trusted_proxies=request.app.state.settings.trusted_proxies),
    )
    return principal


def require_user(
    user: Annotated[UserClaims, Depends(get_current_user)],
) -> UserClaims:
    """Gate: any authenticated principal (role ``admin`` or ``user``)."""
    return user


def require_admin(
    user: Annotated[UserClaims, Depends(get_current_user)],
) -> UserClaims:
    """Gate: authenticated ``admin`` only; any other role → 403 (spec §9)."""
    if user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
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
    """Stats workers by controller id, live workers taking precedence.

    ``app.state.stats_workers`` is captured once in ``run_daemon``, so on its
    own a controller created — or a project opened — after boot 404s on
    ``/controllers/{id}/stats`` until restart. The loop manager knows the
    current set, so it wins; the snapshot still backs ids it does not own,
    which is also how tests inject a stats worker without a running loop.
    """
    snapshot: dict[int, StatsWorker] = getattr(request.app.state, "stats_workers", {})
    loop_mgr = getattr(request.app.state, "loop_manager", None)
    if loop_mgr is None:
        return snapshot
    return {**snapshot, **loop_mgr.get_stats_workers()}


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


def get_io_worker(request: Request) -> IOWorker | None:
    """Return the IOWorker used to keep the telemetry scan list in sync
    with controller create/delete (see ProjectService for the project
    open/import path). ``None`` in test fixtures that don't wire one up.
    """
    return getattr(request.app.state, "io_worker", None)


# ----- Audit helper --------------------------------------------------------


def controller_label(request: Request, controller_id: int) -> str:
    """Resolve a controller's display name for use in event/audit messages.

    Looks up the LoopManager's in-memory context (fast, no DB hit). Falls
    back to ``#<id>`` when the loop is not registered (e.g., a command
    targets a controller whose loop hasn't started yet).
    """
    lm = getattr(request.app.state, "loop_manager", None)
    if lm is not None:
        try:
            return lm.get_controller(controller_id).name
        except Exception:
            pass
    return f"#{controller_id}"


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
