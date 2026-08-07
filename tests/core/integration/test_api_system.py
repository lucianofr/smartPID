"""Tests for /system endpoints."""
from __future__ import annotations

import smtplib
from typing import TYPE_CHECKING, Any

import pytest

from smart_pid_core.adapters.inbound.api.routers import system as system_router

if TYPE_CHECKING:
    from email.message import EmailMessage

    from httpx import AsyncClient


class TestSystemStatus:
    @pytest.mark.asyncio
    async def test_status_returns_running(self, client: AsyncClient) -> None:
        resp = await client.get("/system/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "running"
        assert data["api_version"] == "2.0.0"
        assert "uptime_s" in data
        assert "active_controllers" in data
        assert "bus_active" in data

    @pytest.mark.asyncio
    async def test_status_no_auth_required(self, client: AsyncClient) -> None:
        resp = await client.get("/system/status")
        assert resp.status_code == 200


class TestFeedback:
    """POST /system/feedback — Loops-page message to the developer."""

    @staticmethod
    def _capture(sent: list[EmailMessage]) -> Any:
        def fake(_settings: Any, msg: EmailMessage) -> None:
            sent.append(msg)

        return fake

    @pytest.mark.asyncio
    async def test_requires_auth(self, client: AsyncClient) -> None:
        resp = await client.post("/system/feedback", json={"message": "hi"})
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_503_when_smtp_unconfigured(
        self, client: AsyncClient, user_headers: dict[str, str]
    ) -> None:
        resp = await client.post(
            "/system/feedback", json={"message": "hi"}, headers=user_headers
        )
        assert resp.status_code == 503
        assert resp.json()["detail"] == "Email delivery is not configured on this server"

    @pytest.mark.asyncio
    async def test_sends_email_and_returns_204(
        self,
        client: AsyncClient,
        user_headers: dict[str, str],
        api_deps: dict[str, Any],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        api_deps["settings"].smtp_host = "smtp.test"
        sent: list[EmailMessage] = []
        monkeypatch.setattr(system_router, "_deliver_feedback", self._capture(sent))

        resp = await client.post(
            "/system/feedback",
            json={"message": "  a ideia é ótima  "},
            headers=user_headers,
        )

        assert resp.status_code == 204
        assert len(sent) == 1
        msg = sent[0]
        assert msg["To"] == "luciano82@gmail.com"
        assert msg["Subject"] == "[Smart PID] Mensagem de operator"
        body = msg.get_content()
        assert "a ideia é ótima" in body
        assert "operator (id" in body

    @pytest.mark.asyncio
    async def test_cooldown_429_on_second_send(
        self,
        client: AsyncClient,
        user_headers: dict[str, str],
        api_deps: dict[str, Any],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        api_deps["settings"].smtp_host = "smtp.test"
        monkeypatch.setattr(system_router, "_deliver_feedback", self._capture([]))

        first = await client.post(
            "/system/feedback", json={"message": "one"}, headers=user_headers
        )
        second = await client.post(
            "/system/feedback", json={"message": "two"}, headers=user_headers
        )

        assert first.status_code == 204
        assert second.status_code == 429
        assert second.json()["detail"] == "Wait a minute before sending another message"

    @pytest.mark.asyncio
    async def test_502_when_smtp_fails(
        self,
        client: AsyncClient,
        user_headers: dict[str, str],
        api_deps: dict[str, Any],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        api_deps["settings"].smtp_host = "smtp.test"

        def boom(_settings: Any, _msg: EmailMessage) -> None:
            raise smtplib.SMTPException("boom")

        monkeypatch.setattr(system_router, "_deliver_feedback", boom)

        first = await client.post(
            "/system/feedback", json={"message": "one"}, headers=user_headers
        )
        assert first.status_code == 502
        assert first.json()["detail"] == "Email delivery failed"

        # A failed send must not burn the cooldown budget, or one flaky SMTP
        # hiccup would lock the operator out for a minute with nothing sent.
        second = await client.post(
            "/system/feedback", json={"message": "two"}, headers=user_headers
        )
        assert second.status_code == 502

    @pytest.mark.asyncio
    async def test_422_on_blank_message(
        self, client: AsyncClient, user_headers: dict[str, str]
    ) -> None:
        resp = await client.post(
            "/system/feedback", json={"message": "   "}, headers=user_headers
        )
        assert resp.status_code == 422
