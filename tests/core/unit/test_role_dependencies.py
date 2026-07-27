"""Unit tests for the two-role gate dependencies (spec §9.1, §9.5)."""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from smart_pid_core.adapters.inbound.api.auth import create_access_token
from smart_pid_core.adapters.inbound.api.dependencies import require_admin, require_user
from smart_pid_core.adapters.outbound.user_repo import User
from smart_pid_domain.dtos.auth import UserClaims

_SECRET = "unit-test-secret"


class _StubUserRepo:
    """The slice of ``UserRepository`` the auth path uses.

    The gates resolve every request against the stored record (E2E-044), so
    even a bare gate test needs a store — but not a real SQLite file.
    """

    def __init__(self, user: User | None) -> None:
        self._user = user

    async def get_by_id(self, user_id: int) -> User | None:
        if self._user is None or self._user.id != user_id:
            return None
        return self._user


def _make_app(
    stored_role: str | None = "user", *, active: bool = True
) -> FastAPI:
    """App whose user 1 is stored with ``stored_role`` (``None`` = no such row)."""
    app = FastAPI()

    class _Settings:
        jwt_secret = _SECRET

    app.state.settings = _Settings()
    app.state.user_repo = _StubUserRepo(
        None
        if stored_role is None
        else User(
            id=1, username="someone", password_hash="x",
            role=stored_role, created_at="", active=active,
        )
    )

    @app.get("/any")
    def any_route(user: Annotated[UserClaims, Depends(require_user)]) -> dict:
        return {"role": user.role.value}

    @app.get("/admin-only")
    def admin_route(user: Annotated[UserClaims, Depends(require_admin)]) -> dict:
        return {"role": user.role.value}

    return app


def _headers(role: str) -> dict[str, str]:
    """A token claiming ``role`` — authentication only; the store decides power."""
    token = create_access_token(
        user_id=1, username="someone", role=role, secret=_SECRET
    )
    return {"Authorization": f"Bearer {token}"}


class TestRequireUser:
    def test_user_role_passes(self) -> None:
        client = TestClient(_make_app("user"))
        resp = client.get("/any", headers=_headers("user"))
        assert resp.status_code == 200
        assert resp.json() == {"role": "user"}

    def test_admin_role_passes(self) -> None:
        client = TestClient(_make_app("admin"))
        resp = client.get("/any", headers=_headers("admin"))
        assert resp.status_code == 200
        assert resp.json() == {"role": "admin"}

    def test_missing_header_401(self) -> None:
        client = TestClient(_make_app())
        assert client.get("/any").status_code == 401


class TestRequireAdmin:
    def test_admin_role_passes(self) -> None:
        client = TestClient(_make_app("admin"))
        resp = client.get("/admin-only", headers=_headers("admin"))
        assert resp.status_code == 200

    def test_user_role_403(self) -> None:
        client = TestClient(_make_app("user"))
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


class TestStoredRoleIsAuthoritative:
    """E2E-044: the gates read the stored record, never the token's snapshot.

    The integration counterpart in
    ``tests/core/integration/test_auth_role_revocation.py`` drives the real
    demote/deactivate flow; these pin the same rule at the gate itself.
    """

    def test_admin_claim_loses_to_a_demoted_row(self) -> None:
        client = TestClient(_make_app("user"))
        assert client.get("/admin-only", headers=_headers("admin")).status_code == 403

    def test_admin_claim_reports_the_demoted_role(self) -> None:
        client = TestClient(_make_app("user"))
        resp = client.get("/any", headers=_headers("admin"))
        assert resp.json() == {"role": "user"}

    def test_user_claim_gains_a_promoted_row(self) -> None:
        """Promotion lands on the existing session — one source of truth in
        both directions (see the rationale in the integration suite)."""
        client = TestClient(_make_app("admin"))
        assert client.get("/admin-only", headers=_headers("user")).status_code == 200

    def test_deactivated_row_is_401(self) -> None:
        client = TestClient(_make_app("admin", active=False))
        assert client.get("/any", headers=_headers("admin")).status_code == 401

    def test_missing_row_is_401(self) -> None:
        client = TestClient(_make_app(None))
        assert client.get("/any", headers=_headers("admin")).status_code == 401

    def test_unmapped_stored_role_is_401(self) -> None:
        """Fail closed on a row the two-role model cannot express."""
        client = TestClient(_make_app("SUPERVISOR"))
        assert client.get("/any", headers=_headers("admin")).status_code == 401
