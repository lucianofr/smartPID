"""Integration tests for alarm REST endpoints."""
from __future__ import annotations

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient  # noqa: TC002

from smart_pid_core.adapters.outbound.alarm_repo import AlarmRepository  # noqa: TC001
from smart_pid_domain.enums import AlarmPriority, AlarmType


@pytest.fixture
def alarm_repo(api_deps) -> AlarmRepository:
    return api_deps["alarm_repo"]


class TestActiveAlarms:
    @pytest.mark.asyncio
    async def test_get_active_empty(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        resp = await client.get("/alarms/active", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_get_active_with_alarm(
        self, client: AsyncClient, admin_headers: dict[str, str], alarm_repo: AlarmRepository
    ) -> None:
        await alarm_repo.insert_alarm(
            1, AlarmType.HIHI, AlarmPriority.CRITICAL, 95.0, 90.0, datetime.now(tz=UTC)
        )
        resp = await client.get("/alarms/active", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["alarm_type"] == "HIHI"
        assert data[0]["priority"] == "CRITICAL"

    @pytest.mark.asyncio
    async def test_get_active_filter_by_controller(
        self, client: AsyncClient, admin_headers: dict[str, str], alarm_repo: AlarmRepository
    ) -> None:
        await alarm_repo.insert_alarm(
            1, AlarmType.HIHI, AlarmPriority.CRITICAL, 95.0, 90.0, datetime.now(tz=UTC)
        )
        await alarm_repo.insert_alarm(
            2, AlarmType.HI, AlarmPriority.WARNING, 85.0, 80.0, datetime.now(tz=UTC)
        )
        resp = await client.get(
            "/alarms/active", params={"controller_id": 1}, headers=admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["controller_id"] == 1

    @pytest.mark.asyncio
    async def test_get_active_requires_auth(self, client: AsyncClient) -> None:
        resp = await client.get("/alarms/active")
        assert resp.status_code == 401


class TestAckAlarm:
    @pytest.mark.asyncio
    async def test_ack_single(
        self, client: AsyncClient, admin_headers: dict[str, str], alarm_repo: AlarmRepository
    ) -> None:
        alarm_id = await alarm_repo.insert_alarm(
            1, AlarmType.HIHI, AlarmPriority.CRITICAL, 95.0, 90.0, datetime.now(tz=UTC)
        )
        resp = await client.post(f"/alarms/{alarm_id}/ack", headers=admin_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "acknowledged"
        assert body["id"] == alarm_id
        assert body["controller_id"] == 1
        assert body["alarm_type"] == "HIHI"
        assert body["priority"] == "CRITICAL"
        assert body["acknowledged"] is True

    @pytest.mark.asyncio
    async def test_ack_all(
        self, client: AsyncClient, admin_headers: dict[str, str], alarm_repo: AlarmRepository
    ) -> None:
        await alarm_repo.insert_alarm(
            1, AlarmType.HIHI, AlarmPriority.CRITICAL, 95.0, 90.0, datetime.now(tz=UTC)
        )
        await alarm_repo.insert_alarm(
            1, AlarmType.HI, AlarmPriority.WARNING, 85.0, 80.0, datetime.now(tz=UTC)
        )
        resp = await client.post("/alarms/ack-all", headers=admin_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "acknowledged"
        assert body["acknowledged_count"] == 2
        assert body["controller_ids"] == [1]


class TestAlarmHistory:
    @pytest.mark.asyncio
    async def test_get_history(
        self, client: AsyncClient, admin_headers: dict[str, str], alarm_repo: AlarmRepository
    ) -> None:
        await alarm_repo.insert_alarm(
            1, AlarmType.HIHI, AlarmPriority.CRITICAL, 95.0, 90.0, datetime.now(tz=UTC)
        )
        now = datetime.now(tz=UTC)
        resp = await client.get(
            "/alarms/history",
            params={
                "start": now.replace(hour=0, minute=0, second=0).isoformat(),
                "end": now.isoformat(),
            },
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1

    @pytest.mark.asyncio
    async def test_history_requires_start_end(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        resp = await client.get("/alarms/history", headers=admin_headers)
        assert resp.status_code == 422  # missing required query params
