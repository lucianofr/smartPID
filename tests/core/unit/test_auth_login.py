"""Tests for `POST /auth/login` hardening: rate limiting and length caps."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from fastapi import HTTPException

from smart_pid_core.adapters.inbound.api.routers.auth import LoginRateLimiter

if TYPE_CHECKING:
    from httpx import AsyncClient


class _FakeClock:
    """Manually-advanced clock so limiter tests need no real sleeping."""

    def __init__(self, start: float = 0.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now


class TestLoginRateLimiter:
    def test_sixth_check_within_window_raises_429(self) -> None:
        clock = _FakeClock()
        limiter = LoginRateLimiter(clock=clock)
        ip = "10.0.0.1"
        for _ in range(5):
            limiter.check(ip)  # first 5 attempts in the window are allowed
        with pytest.raises(HTTPException) as exc_info:
            limiter.check(ip)  # 6th is over budget
        assert exc_info.value.status_code == 429

    def test_check_allowed_again_once_window_elapses(self) -> None:
        clock = _FakeClock()
        limiter = LoginRateLimiter(clock=clock)
        ip = "10.0.0.2"
        for _ in range(5):
            limiter.check(ip)
        clock.now += 61.0  # sliding window has fully elapsed
        limiter.check(ip)  # does not raise

    def test_record_success_resets_budget(self) -> None:
        clock = _FakeClock()
        limiter = LoginRateLimiter(clock=clock)
        ip = "10.0.0.3"
        for _ in range(5):
            limiter.check(ip)
        limiter.record_success(ip)
        limiter.check(ip)  # budget cleared, does not raise


class TestLoginRoute:
    @pytest.mark.asyncio
    async def test_sixth_wrong_attempt_returns_429(self, client: AsyncClient) -> None:
        for _ in range(5):
            resp = await client.post(
                "/auth/login", json={"username": "admin", "password": "wrong"}
            )
            assert resp.status_code == 401
        resp = await client.post(
            "/auth/login", json={"username": "admin", "password": "wrong"}
        )
        assert resp.status_code == 429

    @pytest.mark.asyncio
    async def test_successful_logins_reset_budget_each_time(
        self, client: AsyncClient
    ) -> None:
        # 6 correct logins in a row would trip a 5-per-minute budget that never
        # resets; each success clears its IP's budget, so all 6 succeed.
        for _ in range(6):
            resp = await client.post(
                "/auth/login", json={"username": "admin", "password": "admin"}
            )
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_oversize_username_returns_422(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/auth/login",
            json={"username": "a" * 255, "password": "admin"},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_oversize_password_returns_422(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/auth/login",
            json={"username": "admin", "password": "a" * 201},
        )
        assert resp.status_code == 422
