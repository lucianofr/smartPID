"""Unit tests for the two-role gate dependencies (spec §9.1, §9.5)."""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from smart_pid_core.adapters.inbound.api.auth import create_access_token
from smart_pid_core.adapters.inbound.api.dependencies import require_admin, require_user
from smart_pid_domain.dtos.auth import UserClaims

_SECRET = "unit-test-secret"


def _make_app() -> FastAPI:
    app = FastAPI()

    class _Settings:
        jwt_secret = _SECRET

    app.state.settings = _Settings()

    @app.get("/any")
    def any_route(user: Annotated[UserClaims, Depends(require_user)]) -> dict:
        return {"role": user.role.value}

    @app.get("/admin-only")
    def admin_route(user: Annotated[UserClaims, Depends(require_admin)]) -> dict:
        return {"role": user.role.value}

    return app


def _headers(role: str) -> dict[str, str]:
    token = create_access_token(
        user_id=1, username="someone", role=role, secret=_SECRET
    )
    return {"Authorization": f"Bearer {token}"}


class TestRequireUser:
    def test_user_role_passes(self) -> None:
        client = TestClient(_make_app())
        resp = client.get("/any", headers=_headers("user"))
        assert resp.status_code == 200
        assert resp.json() == {"role": "user"}

    def test_admin_role_passes(self) -> None:
        client = TestClient(_make_app())
        resp = client.get("/any", headers=_headers("admin"))
        assert resp.status_code == 200
        assert resp.json() == {"role": "admin"}

    def test_missing_header_401(self) -> None:
        client = TestClient(_make_app())
        assert client.get("/any").status_code == 401


class TestRequireAdmin:
    def test_admin_role_passes(self) -> None:
        client = TestClient(_make_app())
        resp = client.get("/admin-only", headers=_headers("admin"))
        assert resp.status_code == 200

    def test_user_role_403(self) -> None:
        client = TestClient(_make_app())
        resp = client.get("/admin-only", headers=_headers("user"))
        assert resp.status_code == 403
        assert resp.json() == {"detail": "Admin privileges required"}


class TestLegacyClaimRejection:
    """Spec §9.5: legacy vocabulary is rejected with 401 — never mapped."""

    def test_legacy_roles_rejected_on_user_gate(self) -> None:
        client = TestClient(_make_app())
        for legacy in ("ADMIN", "SUPERVISOR", "OPERATOR"):
            resp = client.get("/any", headers=_headers(legacy))
            assert resp.status_code == 401, f"role={legacy!r} must be 401"

    def test_legacy_admin_rejected_on_admin_gate(self) -> None:
        client = TestClient(_make_app())
        resp = client.get("/admin-only", headers=_headers("ADMIN"))
        assert resp.status_code == 401  # 401 (invalid token), NOT 403
