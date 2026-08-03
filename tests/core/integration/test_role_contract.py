"""Parametrised 403-per-route authorization contract (spec §9.2, §12).

Machine-readable form of the phase-0 plan's Appendix A. Business outcomes
vary with fixture state; these assertions pin only the authentication and
role gate for every protected route.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from httpx import AsyncClient

_WINDOW = "start=2026-01-01T00:00:00&end=2026-12-31T00:00:00"

ADMIN_ONLY_ROUTES: list[tuple[str, str, dict | None]] = [
    ("post", "/controllers", {"name": "RBAC-TEST"}),
    ("put", "/controllers/9999", {"name": "renamed"}),
    ("delete", "/controllers/9999", None),
    ("put", "/controllers/9999/alarm-config", {"thresholds": []}),
    ("post", "/controllers/9999/ai/start", None),
    ("post", "/controllers/9999/ai/stop", None),
    ("post", "/controllers/9999/ai/pause", None),
    ("post", "/commands/optimization", {"controller_id": 9999, "enabled": True}),
    ("post", "/commands/tuning", {"controller_id": 9999, "kp": 1.0}),
    ("post", "/commands/apply-tuning/9999", None),
    ("get", "/opcua/browse/ns=0;i=85", None),
    ("get", "/opcua/search?q=temp", None),
    ("put", "/opcua/endpoint", {"endpoint": "opc.tcp://127.0.0.1:4840"}),
    ("post", "/opcua/connect", None),
    ("post", "/opcua/disconnect", None),
    ("post", "/project/new", {"name": "rbac-contract"}),
    ("post", "/project/open", {"name": "nonexistent"}),
    ("get", "/project/list", None),
    ("get", "/project/download", None),
    ("delete", "/project/nonexistent", None),
    ("post", "/simulator/start", None),
    ("post", "/simulator/stop", None),
    ("get", "/simulator/status", None),
    ("get", "/simulator/opcua/status", None),
    ("post", "/simulator/opcua/start", None),
    ("post", "/simulator/opcua/stop", None),
    ("post", "/simulator/preset", {"controller_id": 1, "preset": "FLOW"}),
    (
        "put",
        "/simulator/parameters",
        {"controller_id": 1, "gain": 1.0, "tau1": 1.0, "tau2": 1.0, "dead_time": 1.0},
    ),
    (
        "post",
        "/simulator/disturbance",
        {"controller_id": 1, "type": "step", "amplitude": 1.0},
    ),
    ("delete", "/simulator/disturbance/1", None),
    (
        "post",
        "/simulator/1/pid/params",
        {"controller_id": 1, "kp": 1.0, "ti": 1.0, "td": 0.0},
    ),
    ("get", "/simulator/1/pid/status", None),
    ("put", "/simulator/1/auto-sp", {"enabled": False}),
    ("put", "/simulator/1/auto-disturbance", {"enabled": False}),
    ("get", f"/audit?{_WINDOW}", None),
    ("get", "/users", None),
    ("post", "/users", {"username": "rbac-new", "password": "pw", "role": "user"}),
    ("patch", "/users/9999", {"role": "user"}),
    ("delete", "/users/9999", None),
]

USER_ALLOWED_ROUTES: list[tuple[str, str, dict | None]] = [
    ("get", "/auth/me", None),
    ("post", "/auth/refresh", None),
    ("get", "/controllers", None),
    ("get", "/controllers/9999", None),
    ("get", "/controllers/9999/alarm-config", None),
    ("get", "/controllers/stats", None),
    ("get", "/controllers/9999/stats", None),
    ("get", "/controllers/9999/ai/status", None),
    ("get", "/controllers/9999/ai/history", None),
    ("post", "/commands/setpoint", {"controller_id": 9999, "value": 50.0}),
    ("post", "/commands/mode", {"controller_id": 9999, "mode": "AUTO"}),
    ("post", "/commands/output", {"controller_id": 9999, "value": 50.0}),
    ("get", "/commands/tuning-recommendations/9999", None),
    ("get", "/history/9999", None),
    ("get", "/alarms/active", None),
    ("get", f"/alarms/history?{_WINDOW}", None),
    ("get", f"/alarms/ai-history?{_WINDOW}", None),
    ("post", "/alarms/9999/ack", None),
    ("post", "/alarms/ack-all", None),
    ("get", f"/system-events?{_WINDOW}", None),
    (
        "post",
        "/export",
        {
            "controller_id": 1,
            "start": "2026-01-01T00:00:00",
            "end": "2026-01-02T00:00:00",
            "format": "csv",
        },
    ),
    ("get", "/export/nonexistent-id", None),
    ("get", "/export/nonexistent-id/download", None),
    ("get", "/opcua/status", None),
    ("get", "/project/current", None),
    ("post", "/simulator/9999/pid/sp", {"controller_id": 9999, "value": 50.0}),
    ("post", "/simulator/9999/co", {"controller_id": 9999, "value": 50.0}),
    ("post", "/simulator/9999/pid/mode", {"controller_id": 9999, "mode": "AUTO"}),
]


def _ids(routes: list[tuple[str, str, dict | None]]) -> list[str]:
    return [f"{method.upper()} {path}" for method, path, _ in routes]


async def _request(
    client: AsyncClient,
    method: str,
    path: str,
    body: dict | None,
    headers: dict[str, str] | None,
):
    kwargs: dict = {"headers": headers} if headers else {}
    if body is not None:
        kwargs["json"] = body
    return await getattr(client, method)(path, **kwargs)


class TestRouteInventory:
    def test_admin_only_route_count(self) -> None:
        assert len(ADMIN_ONLY_ROUTES) == 39

    def test_user_allowed_route_count(self) -> None:
        assert len(USER_ALLOWED_ROUTES) == 28


class TestAdminOnlyRoutes:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("method", "path", "body"), ADMIN_ONLY_ROUTES, ids=_ids(ADMIN_ONLY_ROUTES)
    )
    async def test_user_role_gets_403(
        self,
        client: AsyncClient,
        user_headers: dict[str, str],
        method: str,
        path: str,
        body: dict | None,
    ) -> None:
        resp = await _request(client, method, path, body, user_headers)
        assert resp.status_code == 403, (
            f"{method.upper()} {path}: expected 403 for role 'user', "
            f"got {resp.status_code}: {resp.text}"
        )
        assert resp.json() == {"detail": "Admin privileges required"}

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("method", "path", "body"), ADMIN_ONLY_ROUTES, ids=_ids(ADMIN_ONLY_ROUTES)
    )
    async def test_admin_role_passes_gate(
        self,
        client: AsyncClient,
        admin_headers: dict[str, str],
        method: str,
        path: str,
        body: dict | None,
    ) -> None:
        resp = await _request(client, method, path, body, admin_headers)
        assert resp.status_code not in (401, 403), (
            f"{method.upper()} {path}: admin must pass the gate, "
            f"got {resp.status_code}: {resp.text}"
        )


class TestUserAllowedRoutes:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("method", "path", "body"), USER_ALLOWED_ROUTES, ids=_ids(USER_ALLOWED_ROUTES)
    )
    async def test_user_role_passes_gate(
        self,
        client: AsyncClient,
        user_headers: dict[str, str],
        method: str,
        path: str,
        body: dict | None,
    ) -> None:
        resp = await _request(client, method, path, body, user_headers)
        assert resp.status_code not in (401, 403), (
            f"{method.upper()} {path}: role 'user' must pass this gate, "
            f"got {resp.status_code}: {resp.text}"
        )


class TestUnauthenticated:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("method", "path", "body"),
        ADMIN_ONLY_ROUTES + USER_ALLOWED_ROUTES,
        ids=_ids(ADMIN_ONLY_ROUTES + USER_ALLOWED_ROUTES),
    )
    async def test_no_token_401(
        self, client: AsyncClient, method: str, path: str, body: dict | None
    ) -> None:
        resp = await _request(client, method, path, body, headers=None)
        assert resp.status_code == 401, (
            f"{method.upper()} {path}: expected 401 without a JWT, "
            f"got {resp.status_code}"
        )


class TestProjectImportGate:
    @pytest.mark.asyncio
    async def test_user_role_gets_403(
        self, client: AsyncClient, user_headers: dict[str, str]
    ) -> None:
        resp = await client.post(
            "/project/import",
            headers=user_headers,
            files={"file": ("x.spid", b"not-a-db", "application/octet-stream")},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_admin_role_passes_gate(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        resp = await client.post(
            "/project/import",
            headers=admin_headers,
            files={"file": ("x.spid", b"not-a-db", "application/octet-stream")},
        )
        assert resp.status_code not in (401, 403)
