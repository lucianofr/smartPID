"""Network-hardening middleware tests (TD-004).

Covers the minimal standalone hardening that lands before the Web HMI:
- security response headers on every response
- CORS allow-list (no credentialed wildcard)
- TrustedHost host-header validation
- config default bind host is loopback
"""
from __future__ import annotations

import uuid

import httpx
import pytest

from smart_pid_core.adapters.inbound.api.app import create_app
from smart_pid_core.adapters.outbound.alarm_repo import AlarmRepository
from smart_pid_core.adapters.outbound.audit_repo import AuditRepository
from smart_pid_core.adapters.outbound.historian import SQLiteHistorian
from smart_pid_core.adapters.outbound.sqlite_repo import SQLiteRepository
from smart_pid_core.adapters.outbound.system_event_repo import SystemEventRepository
from smart_pid_core.adapters.outbound.user_repo import UserRepository
from smart_pid_core.application.event_bus import EventBus
from smart_pid_core.application.loop_manager import LoopManager
from smart_pid_core.config import CoreSettings

ALLOWED_ORIGIN = "http://127.0.0.1:5173"
DISALLOWED_ORIGIN = "http://evil.example.com"
ALLOWED_HOST = "127.0.0.1"
TRUSTED_HOSTS = ["127.0.0.1", "localhost"]


@pytest.fixture
async def secure_client(tmp_path):
    """AsyncClient over an app built with explicit CORS/trusted-host settings."""
    db_path = tmp_path / "test.spid"
    repo = SQLiteRepository(db_path)
    await repo.initialize()
    historian = SQLiteHistorian(repo.session_factory)
    user_repo = UserRepository(tmp_path / "users.db")
    await user_repo.initialize()
    alarm_repo = AlarmRepository(repo.session_factory)
    audit_repo = AuditRepository(repo.session_factory)
    system_event_repo = SystemEventRepository(repo.session_factory)
    bus = EventBus(url_prefix=f"inproc://test_{uuid.uuid4().hex[:8]}")
    bus.start()
    loop_manager = LoopManager(bus=bus)
    settings = CoreSettings(
        jwt_secret="test-secret-key-minimum-32-bytes!",
        cors_allow_origins=[ALLOWED_ORIGIN],
        trusted_hosts=TRUSTED_HOSTS,
    )  # type: ignore[call-arg]

    app = create_app(
        repo=repo,
        historian=historian,
        user_repo=user_repo,
        loop_manager=loop_manager,
        settings=settings,
        alarm_repo=alarm_repo,
        audit_repo=audit_repo,
        system_event_repo=system_event_repo,
        event_bus=bus,
    )

    transport = httpx.ASGITransport(app=app)
    # base_url host must be in TRUSTED_HOSTS so non-host-header tests pass through.
    async with httpx.AsyncClient(
        transport=transport, base_url=f"http://{ALLOWED_HOST}"
    ) as c:
        yield c

    loop_manager.stop_all()
    bus.stop()
    await user_repo.close()
    await repo.db.close()


class TestSecurityHeaders:
    @pytest.mark.asyncio
    async def test_headers_present_on_normal_get(self, secure_client: httpx.AsyncClient) -> None:
        resp = await secure_client.get("/system/status")
        assert resp.status_code == 200
        assert resp.headers["x-content-type-options"] == "nosniff"
        assert resp.headers["x-frame-options"] == "DENY"
        assert resp.headers["referrer-policy"] == "strict-origin-when-cross-origin"
        assert resp.headers["permissions-policy"] == (
            "camera=(), microphone=(), geolocation=()"
        )
        csp = resp.headers["content-security-policy"]
        assert "default-src 'self'" in csp
        assert "frame-ancestors 'none'" in csp
        assert "object-src 'none'" in csp
        assert "base-uri 'self'" in csp


class TestCORS:
    @pytest.mark.asyncio
    async def test_preflight_allowed_origin_echoed(
        self, secure_client: httpx.AsyncClient
    ) -> None:
        resp = await secure_client.options(
            "/system/status",
            headers={
                "Origin": ALLOWED_ORIGIN,
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp.headers.get("access-control-allow-origin") == ALLOWED_ORIGIN

    @pytest.mark.asyncio
    async def test_preflight_disallowed_origin_not_allowed(
        self, secure_client: httpx.AsyncClient
    ) -> None:
        resp = await secure_client.options(
            "/system/status",
            headers={
                "Origin": DISALLOWED_ORIGIN,
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp.headers.get("access-control-allow-origin") != DISALLOWED_ORIGIN

    @pytest.mark.asyncio
    async def test_not_credentialed_wildcard(
        self, secure_client: httpx.AsyncClient
    ) -> None:
        """Guard against the allow_origins=* + allow_credentials footgun."""
        resp = await secure_client.get(
            "/system/status", headers={"Origin": ALLOWED_ORIGIN}
        )
        assert resp.headers.get("access-control-allow-origin") != "*"


class TestTrustedHost:
    @pytest.mark.asyncio
    async def test_bad_host_rejected(self, secure_client: httpx.AsyncClient) -> None:
        resp = await secure_client.get(
            "/system/status", headers={"Host": "attacker.example.com"}
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_allowed_host_ok(self, secure_client: httpx.AsyncClient) -> None:
        resp = await secure_client.get("/system/status", headers={"Host": ALLOWED_HOST})
        assert resp.status_code == 200


class TestConfigDefault:
    def test_api_host_defaults_to_loopback(self) -> None:
        settings = CoreSettings(
            _env_file=None,
            jwt_secret="test-secret-key-minimum-32-bytes!",
        )  # type: ignore[call-arg]
        assert settings.api_host == "127.0.0.1"
