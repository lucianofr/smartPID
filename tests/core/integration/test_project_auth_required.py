"""Project routes require the authenticated admin (mono-user contract).

Contract (fatia 7): every /project route requires a JWT. Without an
Authorization header the route returns 401 (NOT 403 — this is a single-admin
deployment with no role tiers). Asserted directly: the backend security
hardening (auth on /project/*) is already merged on this branch.
"""
from __future__ import annotations

import httpx
import pytest


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/project/list"),
        ("get", "/project/current"),
        ("post", "/project/new"),
        ("post", "/project/open"),
        ("get", "/project/download"),
        ("delete", "/project/sample"),
    ],
)
async def test_project_routes_require_auth(
    client: httpx.AsyncClient, method: str, path: str
) -> None:
    # No Authorization header -> 401 (NOT 403-by-role; mono-user model).
    # POSTs carry a valid body so auth (401) wins over body-validation (422).
    kwargs = {"json": {"name": "x"}} if method == "post" else {}
    resp = await getattr(client, method)(path, **kwargs)
    assert resp.status_code == 401, (
        f"{method.upper()} {path} should be 401 without a JWT, "
        f"got {resp.status_code}"
    )
