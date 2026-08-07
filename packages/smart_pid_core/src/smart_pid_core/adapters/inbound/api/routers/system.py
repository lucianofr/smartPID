"""System health-check and log-level control router."""
from __future__ import annotations

import asyncio
import logging
import smtplib
import time
from datetime import UTC, datetime
from email.message import EmailMessage
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from smart_pid_core.adapters.inbound.api.dependencies import (
    get_settings,
    require_admin,
    require_user,
)
from smart_pid_core.application.log_control import LOG_LEVEL_NAMES, levels_at_or_above
from smart_pid_core.config import CoreSettings  # noqa: TC001
from smart_pid_domain.dtos.auth import UserClaims  # noqa: TC001
from smart_pid_domain.dtos.system import (
    FeedbackRequest,
    LogLevelsResponse,
    LogLevelsUpdate,
    SystemStatusResponse,
)

logger = structlog.get_logger()

_FEEDBACK_MIN_INTERVAL_S = 60.0

router = APIRouter()


def _process_metrics() -> tuple[float | None, float | None]:
    """CPU% for this process and system memory% used.

    Returns (None, None) when psutil is unavailable so a health probe never
    fails just because an optional metrics dependency is missing. The first
    cpu_percent() call after interval=None returns 0.0 by definition, so the
    process handle is cached across requests and the value becomes meaningful
    from the second poll onward.
    """
    try:
        import psutil
    except ImportError:
        return None, None
    proc = getattr(_process_metrics, "_proc", None)
    if proc is None:
        proc = psutil.Process()
        proc.cpu_percent(interval=None)  # prime the delta baseline
        _process_metrics._proc = proc  # type: ignore[attr-defined]
    try:
        return round(proc.cpu_percent(interval=None), 1), round(
            psutil.virtual_memory().percent, 1
        )
    except Exception:  # noqa: BLE001 — metrics must never break the probe
        return None, None


@router.get("/status", response_model=SystemStatusResponse)
async def system_status(request: Request) -> SystemStatusResponse:
    """Health check — no auth required."""
    start_time = getattr(request.app.state, "start_time", time.monotonic())
    loop_manager = request.app.state.loop_manager
    cpu, mem = _process_metrics()
    return SystemStatusResponse(
        status="running",
        uptime_s=round(time.monotonic() - start_time, 1),
        active_controllers=len(loop_manager._loops),
        bus_active=True,
        api_version="2.0.0",
        cpu_percent=cpu,
        memory_percent=mem,
    )


@router.get("/log-levels", response_model=LogLevelsResponse)
async def get_log_levels(
    _admin: Annotated[UserClaims, Depends(require_admin)],
    request: Request,
) -> LogLevelsResponse:
    controller = getattr(request.app.state, "log_level_controller", None)
    if controller is None:
        # Older app builds (e.g. tests that build a bare app) never wire the
        # controller; report the root logger's own effective level instead
        # of failing a read-only probe.
        current = levels_at_or_above(logging.getLogger().getEffectiveLevel())
    else:
        current = controller.levels
    return LogLevelsResponse(levels=list(current), available=list(LOG_LEVEL_NAMES))


@router.put("/log-levels", status_code=status.HTTP_204_NO_CONTENT)
async def set_log_levels(
    body: LogLevelsUpdate,
    _admin: Annotated[UserClaims, Depends(require_admin)],
    request: Request,
) -> Response:
    controller = getattr(request.app.state, "log_level_controller", None)
    if controller is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Log level controller is not configured on this app",
        )
    controller.set_levels(body.levels)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _deliver_feedback(settings: CoreSettings, msg: EmailMessage) -> None:
    """Blocking SMTP submit — always called via ``asyncio.to_thread``."""
    assert settings.smtp_host is not None  # noqa: S101 — caller 503s on unset host
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
        smtp.starttls()
        if settings.smtp_user:
            smtp.login(settings.smtp_user, settings.smtp_password)
        smtp.send_message(msg)


@router.post("/feedback", status_code=status.HTTP_204_NO_CONTENT)
async def send_feedback(
    body: FeedbackRequest,
    user: Annotated[UserClaims, Depends(require_user)],
    settings: Annotated[CoreSettings, Depends(get_settings)],
    request: Request,
) -> Response:
    """Email the developer a message typed by a signed-in operator (demo account UX)."""
    if not settings.smtp_host:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Email delivery is not configured on this server",
        )
    # ponytail: in-process per-user cooldown (dict on app.state, lazily created like
    # log_level_controller). Lost on restart, racy across concurrent requests from the
    # same user — acceptable for a single-process daemon; budget only burns on success.
    sent: dict[int, float] = getattr(request.app.state, "feedback_last_sent", {})
    now = time.monotonic()
    prev = sent.get(user.user_id)
    if prev is not None and now - prev < _FEEDBACK_MIN_INTERVAL_S:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Wait a minute before sending another message",
        )
    msg = EmailMessage()
    msg["From"] = settings.smtp_user or settings.feedback_email_to
    msg["To"] = settings.feedback_email_to
    msg["Subject"] = f"[Smart PID] Mensagem de {user.username}"
    msg.set_content(
        f"Usuário: {user.username} (id {user.user_id})\n"
        f"Data: {datetime.now(UTC).isoformat()}\n\n{body.message}"
    )
    try:
        await asyncio.to_thread(_deliver_feedback, settings, msg)
    except (OSError, smtplib.SMTPException):
        logger.warning("feedback_email_failed", username=user.username)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="Email delivery failed"
        ) from None
    sent[user.user_id] = now
    request.app.state.feedback_last_sent = sent
    logger.info("feedback_email_sent", username=user.username)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
