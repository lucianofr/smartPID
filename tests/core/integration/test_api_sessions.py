"""Live session view + platform access log (GET/POST under /auth).

The httpx ASGI transport reports 127.0.0.1 as the transport peer, which is what
these tests assert against when no trusted proxy is configured.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from httpx import AsyncClient

_CREDS = {"username": "admin", "password": "admin"}
_PEER = "127.0.0.1"


async def _sessions(client: AsyncClient, headers: dict[str, str]) -> list[dict]:
    resp = await client.get("/auth/sessions", headers=headers)
    assert resp.status_code == 200
    return resp.json()


async def test_login_registers_a_session_with_its_source_address(
    client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    assert (await client.post("/auth/login", json=_CREDS)).status_code == 200

    rows = [s for s in await _sessions(client, admin_headers) if s["username"] == "admin"]
    assert len(rows) == 1, "three requests from one browser are ONE session"
    assert rows[0]["ip"] == _PEER
    assert rows[0]["role"] == "admin"
    # `online` tracks realtime sockets; this client never opens /ws/realtime.
    assert rows[0]["online"] is False
    assert rows[0]["since"] <= rows[0]["last_seen"]


async def test_every_authenticated_caller_appears_once_per_identity(
    client: AsyncClient, admin_headers: dict[str, str], user_headers: dict[str, str]
) -> None:
    assert (await client.get("/auth/me", headers=user_headers)).status_code == 200

    rows = await _sessions(client, admin_headers)
    assert {s["username"] for s in rows} == {"admin", "operator"}
    assert {s["role"] for s in rows} == {"admin", "user"}


async def test_logout_ends_the_session_at_once(
    client: AsyncClient, admin_headers: dict[str, str], user_headers: dict[str, str]
) -> None:
    await client.get("/auth/me", headers=user_headers)
    assert "operator" in {s["username"] for s in await _sessions(client, admin_headers)}

    assert (await client.post("/auth/logout", headers=user_headers)).status_code == 204

    # No idle window to wait out: a browser that pressed Sair must stop being
    # listed as connected on the very next read.
    assert "operator" not in {s["username"] for s in await _sessions(client, admin_headers)}


async def test_access_log_keeps_sign_in_and_sign_out_with_the_address(
    client: AsyncClient, admin_headers: dict[str, str], user_headers: dict[str, str]
) -> None:
    await client.post("/auth/login", json=_CREDS)
    await client.post("/auth/logout", headers=user_headers)

    resp = await client.get("/auth/access-log", headers=admin_headers)
    assert resp.status_code == 200
    rows = resp.json()
    assert [r["event"] for r in rows[:2]] == ["LOGOUT", "LOGIN"], "newest first"
    assert rows[0]["username"] == "operator"
    assert rows[1]["username"] == "admin"
    assert {r["ip"] for r in rows[:2]} == {_PEER}


async def test_access_log_survives_deleting_the_account(
    client: AsyncClient, admin_headers: dict[str, str], user_headers: dict[str, str]
) -> None:
    await client.get("/auth/me", headers=user_headers)
    await client.post("/auth/logout", headers=user_headers)
    assert (await client.delete("/users/2", headers=admin_headers)).status_code == 200

    rows = (await client.get("/auth/access-log", headers=admin_headers)).json()
    assert "operator" in {r["username"] for r in rows}


async def test_access_log_limit_is_bounded(
    client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    assert (
        await client.get("/auth/access-log?limit=100000", headers=admin_headers)
    ).status_code == 422


class TestForwardedFor:
    """`X-Forwarded-For` is honoured only when the peer is a trusted proxy."""

    async def test_ignored_when_no_proxy_is_trusted(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        await client.get(
            "/auth/me", headers={**admin_headers, "X-Forwarded-For": "203.0.113.9"}
        )

        assert {s["ip"] for s in await _sessions(client, admin_headers)} == {_PEER}

    async def test_ignored_when_the_caller_is_not_one_of_the_trusted_proxies(
        self, api_deps, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        # Forwarding enabled, but the transport peer (127.0.0.1) is NOT the
        # named proxy — the header is back to being caller-supplied text.
        api_deps["settings"].trusted_proxies = ["10.42.0.0/16"]

        await client.get(
            "/auth/me", headers={**admin_headers, "X-Forwarded-For": "203.0.113.9"}
        )

        assert {s["ip"] for s in await _sessions(client, admin_headers)} == {_PEER}

    async def test_last_hop_wins_when_the_proxy_is_trusted(
        self, api_deps, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        api_deps["settings"].trusted_proxies = [_PEER]

        # Leftmost entry is whatever the caller wrote; the rightmost is the one
        # the trusted proxy appended, i.e. the peer it actually saw.
        await client.get(
            "/auth/me",
            headers={**admin_headers, "X-Forwarded-For": "1.2.3.4, 203.0.113.9"},
        )

        rows = await _sessions(client, admin_headers)
        assert "203.0.113.9" in {s["ip"] for s in rows}
        assert "1.2.3.4" not in {s["ip"] for s in rows}

    async def test_a_forwarded_hop_that_is_not_an_address_is_refused(
        self, api_deps, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        # Nothing arbitrary may reach a registry key or an audit row, even from
        # a trusted proxy.
        api_deps["settings"].trusted_proxies = [_PEER]

        await client.get(
            "/auth/me", headers={**admin_headers, "X-Forwarded-For": "A" * 300}
        )

        assert {s["ip"] for s in await _sessions(client, admin_headers)} == {_PEER}

    async def test_login_throttle_is_per_forwarded_client(
        self, api_deps, client: AsyncClient
    ) -> None:
        # Behind Traefik every operator shares one transport peer, so a per-peer
        # budget was a platform-wide lockout: five bad guesses from one browser
        # locked out everybody. The budget has to follow the forwarded address.
        api_deps["settings"].trusted_proxies = [_PEER]
        attacker = {"X-Forwarded-For": "203.0.113.9"}
        bystander = {"X-Forwarded-For": "198.51.100.7"}
        bad = {"username": "admin", "password": "wrong"}

        for _ in range(5):
            assert (
                await client.post("/auth/login", json=bad, headers=attacker)
            ).status_code == 401
        assert (
            await client.post("/auth/login", json=bad, headers=attacker)
        ).status_code == 429

        assert (
            await client.post("/auth/login", json=_CREDS, headers=bystander)
        ).status_code == 200

    async def test_an_untrusted_caller_cannot_mint_a_fresh_throttle_budget(
        self, client: AsyncClient
    ) -> None:
        # The evasion the allow-list exists to stop: rotate the header per
        # attempt and every guess gets its own budget. With no trusted proxy
        # configured the peer decides, so the budget is shared and runs out.
        bad = {"username": "admin", "password": "wrong"}

        for hop in range(5):
            resp = await client.post(
                "/auth/login", json=bad, headers={"X-Forwarded-For": f"203.0.113.{hop}"}
            )
            assert resp.status_code == 401

        blocked = await client.post(
            "/auth/login", json=bad, headers={"X-Forwarded-For": "203.0.113.200"}
        )
        assert blocked.status_code == 429
