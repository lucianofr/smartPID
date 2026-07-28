"""Regression tests for E2E-044 — stale-JWT privilege escalation.

Authorization is a property of the *stored* user record, never of the token:
the JWT only proves who is calling. Before the fix, ``get_current_user`` built
its claims straight from the token, so revoking a role had no effect until the
token expired (8h). Inside that window a demoted admin could still reach every
admin route — including ``POST /users``, which let them mint a *permanent*
admin account that outlived their own session.

These are attack reproductions driven through the real ASGI app, not
unit-level gate checks: each one demotes or deactivates a principal and then
drives the SAME stale token at a real admin route. ``tests/core/unit/
test_rbac.py`` still covers the pure 403-per-role gate contract.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from smart_pid_core.adapters.inbound.api.auth import create_access_token

if TYPE_CHECKING:
    from httpx import AsyncClient

_ATTACKER = "operador"
_ATTACKER_PASSWORD = "operador123"


async def _login(client: AsyncClient, username: str, password: str) -> dict[str, str]:
    """Log in for real and return usable Authorization headers."""
    resp = await client.post(
        "/auth/login", json={"username": username, "password": password}
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.fixture
async def promoted_attacker(
    client: AsyncClient, admin_headers: dict[str, str]
) -> tuple[int, dict[str, str]]:
    """E2E-044 steps 1-2: a second admin, holding a genuine fresh admin token.

    Created through the real admin surface and authenticated through the real
    login route, so the token under test is exactly what the deployment mints.
    """
    resp = await client.post(
        "/users",
        headers=admin_headers,
        json={
            "username": _ATTACKER,
            "password": _ATTACKER_PASSWORD,
            "role": "admin",
        },
    )
    assert resp.status_code == 201, resp.text
    user_id = resp.json()["id"]
    stale = await _login(client, _ATTACKER, _ATTACKER_PASSWORD)

    # The token really does carry admin power right now — otherwise the
    # revocation assertions below would pass vacuously.
    assert (await client.get("/users", headers=stale)).status_code == 200
    return user_id, stale


class TestDemotionRevokesStaleToken:
    """Step 3-4 of the transcript: demote mid-session, then reuse the token."""

    @pytest.mark.asyncio
    async def test_stale_admin_token_is_denied_admin_routes(
        self,
        client: AsyncClient,
        admin_headers: dict[str, str],
        promoted_attacker: tuple[int, dict[str, str]],
    ) -> None:
        user_id, stale = promoted_attacker

        demote = await client.patch(
            f"/users/{user_id}", headers=admin_headers, json={"role": "user"}
        )
        assert demote.status_code == 200, demote.text

        # SAME token, no relogin.
        assert (await client.get("/users", headers=stale)).status_code == 403

    @pytest.mark.asyncio
    async def test_stale_admin_token_cannot_create_backdoor_admin(
        self,
        client: AsyncClient,
        admin_headers: dict[str, str],
        promoted_attacker: tuple[int, dict[str, str]],
    ) -> None:
        """The payload that made E2E-044 critical: a permanent admin account
        minted by a demoted user, outliving the token that created it."""
        user_id, stale = promoted_attacker
        await client.patch(
            f"/users/{user_id}", headers=admin_headers, json={"role": "user"}
        )

        resp = await client.post(
            "/users",
            headers=stale,
            json={"username": "escalated", "password": "pwned123", "role": "admin"},
        )
        assert resp.status_code == 403

        listed = await client.get("/users", headers=admin_headers)
        assert listed.status_code == 200
        assert "escalated" not in {u["username"] for u in listed.json()}

    @pytest.mark.asyncio
    async def test_me_reports_current_role_after_demotion(
        self,
        client: AsyncClient,
        admin_headers: dict[str, str],
        promoted_attacker: tuple[int, dict[str, str]],
    ) -> None:
        """The SPA refetches /auth/me on a 403; it must see the new role."""
        user_id, stale = promoted_attacker
        assert (await client.get("/auth/me", headers=stale)).json()["role"] == "admin"

        await client.patch(
            f"/users/{user_id}", headers=admin_headers, json={"role": "user"}
        )

        me = await client.get("/auth/me", headers=stale)
        assert me.status_code == 200
        assert me.json()["role"] == "user"

    @pytest.mark.asyncio
    async def test_demotion_is_not_a_logout(
        self,
        client: AsyncClient,
        admin_headers: dict[str, str],
        promoted_attacker: tuple[int, dict[str, str]],
    ) -> None:
        """Demotion drops privileges, it does not invalidate the session: the
        principal stays authenticated for ``require_user`` routes."""
        user_id, stale = promoted_attacker
        await client.patch(
            f"/users/{user_id}", headers=admin_headers, json={"role": "user"}
        )

        assert (await client.get("/controllers", headers=stale)).status_code == 200

    @pytest.mark.asyncio
    async def test_refresh_mints_a_token_with_the_demoted_role(
        self,
        client: AsyncClient,
        admin_headers: dict[str, str],
        promoted_attacker: tuple[int, dict[str, str]],
    ) -> None:
        """/auth/refresh must not launder a stale admin claim into a new token."""
        user_id, stale = promoted_attacker
        await client.patch(
            f"/users/{user_id}", headers=admin_headers, json={"role": "user"}
        )

        refreshed = await client.post("/auth/refresh", headers=stale)
        assert refreshed.status_code == 200
        new = {"Authorization": f"Bearer {refreshed.json()['access_token']}"}
        assert (await client.get("/auth/me", headers=new)).json()["role"] == "user"
        assert (await client.get("/users", headers=new)).status_code == 403


class TestDeactivationRevokesStaleToken:
    """Same bug class on the ``active`` flag: a soft-deleted account must lose
    its live session immediately, not 8h later. 401 (not 403) so the SPA
    forces a re-login — and login itself will then fail."""

    @pytest.mark.asyncio
    async def test_deactivated_user_stale_token_is_rejected(
        self,
        client: AsyncClient,
        admin_headers: dict[str, str],
        promoted_attacker: tuple[int, dict[str, str]],
    ) -> None:
        user_id, stale = promoted_attacker
        # Demote first: the last-active-admin guard blocks deactivating the
        # only remaining admin, and `admin` must stay usable for the teardown.
        await client.patch(
            f"/users/{user_id}", headers=admin_headers, json={"role": "user"}
        )
        assert (await client.get("/controllers", headers=stale)).status_code == 200

        gone = await client.delete(f"/users/{user_id}", headers=admin_headers)
        assert gone.status_code == 200
        assert gone.json()["active"] is False

        assert (await client.get("/controllers", headers=stale)).status_code == 401
        assert (await client.get("/auth/me", headers=stale)).status_code == 401
        assert (await client.post("/auth/refresh", headers=stale)).status_code == 401

    @pytest.mark.asyncio
    async def test_deactivated_user_cannot_log_back_in(
        self,
        client: AsyncClient,
        admin_headers: dict[str, str],
        promoted_attacker: tuple[int, dict[str, str]],
    ) -> None:
        user_id, _ = promoted_attacker
        await client.patch(
            f"/users/{user_id}", headers=admin_headers, json={"role": "user"}
        )
        await client.delete(f"/users/{user_id}", headers=admin_headers)

        resp = await client.post(
            "/auth/login",
            json={"username": _ATTACKER, "password": _ATTACKER_PASSWORD},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_token_for_unknown_subject_is_rejected(
        self, client: AsyncClient, api_deps: dict
    ) -> None:
        """A correctly-signed token whose subject was never stored (or was
        hard-deleted) is not a principal."""
        token = create_access_token(
            user_id=4242,
            username="ghost",
            role="admin",
            secret=api_deps["settings"].jwt_secret,
        )
        resp = await client.get("/users", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401


class TestPromotionTakesEffectImmediately:
    """Deliberate behaviour change, pinned here.

    Before the fix, promotion was fail-closed by accident: the stale token
    still said ``user``, so a promoted principal had to re-login. Now the
    stored record is the single source of truth in *both* directions, so a
    promotion lands on the next request too.

    Rationale: the token is HMAC-signed, so a ``user`` claim can never be
    forged into ``admin`` — intersecting the two roles would buy no security,
    only an invisible dependency on *when* the principal logged in. Keeping
    one source of truth is also what lets ``/auth/me`` answer honestly, which
    is exactly what the SPA gates its UI on.
    """

    @pytest.mark.asyncio
    async def test_promotion_lands_on_the_existing_session(
        self,
        client: AsyncClient,
        admin_headers: dict[str, str],
        user_headers: dict[str, str],
        api_deps: dict,
    ) -> None:
        assert (await client.get("/users", headers=user_headers)).status_code == 403

        user = await api_deps["user_repo"].get_by_username("operator")
        promote = await client.patch(
            f"/users/{user.id}", headers=admin_headers, json={"role": "admin"}
        )
        assert promote.status_code == 200

        assert (await client.get("/users", headers=user_headers)).status_code == 200

    @pytest.mark.asyncio
    async def test_me_reports_the_promoted_role(
        self,
        client: AsyncClient,
        admin_headers: dict[str, str],
        user_headers: dict[str, str],
        api_deps: dict,
    ) -> None:
        assert (await client.get("/auth/me", headers=user_headers)).json()["role"] == "user"

        user = await api_deps["user_repo"].get_by_username("operator")
        await client.patch(
            f"/users/{user.id}", headers=admin_headers, json={"role": "admin"}
        )

        me = await client.get("/auth/me", headers=user_headers)
        assert me.status_code == 200
        assert me.json()["role"] == "admin"
