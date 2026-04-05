"""Tests for alarm config CRUD endpoints — Gap #19."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from smart_pid_domain.models.controller import Controller, PIDParams

if TYPE_CHECKING:
    from httpx import AsyncClient


async def _create_controller(api_deps: dict) -> int:
    """Helper: save a controller to DB."""
    repo = api_deps["repo"]
    ctrl = Controller(
        id=0, name="FIC-201", pid_params=PIDParams(gain=1.0, reset=10.0, rate=0.0),
    )
    saved = await repo.save(ctrl)
    return saved.id


class TestGetAlarmConfig:
    @pytest.mark.asyncio
    async def test_get_empty_config(
        self, client: AsyncClient, user_headers: dict[str, str], api_deps: dict,
    ) -> None:
        cid = await _create_controller(api_deps)
        resp = await client.get(
            f"/controllers/{cid}/alarm-config", headers=user_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["controller_id"] == cid
        assert data["thresholds"] == []

    @pytest.mark.asyncio
    async def test_get_config_unknown_controller(
        self, client: AsyncClient, user_headers: dict[str, str],
    ) -> None:
        resp = await client.get(
            "/controllers/9999/alarm-config", headers=user_headers,
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_config_no_auth(self, client: AsyncClient) -> None:
        resp = await client.get("/controllers/1/alarm-config")
        assert resp.status_code == 401


class TestUpdateAlarmConfig:
    @pytest.mark.asyncio
    async def test_update_alarm_config(
        self,
        client: AsyncClient,
        supervisor_headers: dict[str, str],
        user_headers: dict[str, str],
        api_deps: dict,
    ) -> None:
        cid = await _create_controller(api_deps)
        body = {
            "thresholds": [
                {
                    "alarm_type": "HIHI",
                    "priority": "CRITICAL",
                    "limit": 95.0,
                    "enabled": True,
                    "deadband": 1.0,
                },
                {
                    "alarm_type": "HI",
                    "priority": "WARNING",
                    "limit": 85.0,
                    "enabled": True,
                    "deadband": 0.5,
                },
                {
                    "alarm_type": "LO",
                    "priority": "WARNING",
                    "limit": 15.0,
                    "enabled": True,
                    "deadband": 0.5,
                },
                {
                    "alarm_type": "LOLO",
                    "priority": "CRITICAL",
                    "limit": 5.0,
                    "enabled": True,
                    "deadband": 1.0,
                },
            ],
        }
        resp = await client.put(
            f"/controllers/{cid}/alarm-config",
            json=body,
            headers=supervisor_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["controller_id"] == cid
        assert len(data["thresholds"]) == 4

        # Verify GET returns the saved config
        resp2 = await client.get(
            f"/controllers/{cid}/alarm-config", headers=user_headers,
        )
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert len(data2["thresholds"]) == 4
        types = {t["alarm_type"] for t in data2["thresholds"]}
        assert types == {"HIHI", "HI", "LO", "LOLO"}

    @pytest.mark.asyncio
    async def test_update_alarm_config_requires_supervisor(
        self, client: AsyncClient, user_headers: dict[str, str], api_deps: dict,
    ) -> None:
        cid = await _create_controller(api_deps)
        body = {
            "thresholds": [
                {"alarm_type": "HI", "priority": "WARNING", "limit": 90.0},
            ],
        }
        resp = await client.put(
            f"/controllers/{cid}/alarm-config",
            json=body,
            headers=user_headers,
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_update_alarm_config_unknown_controller(
        self, client: AsyncClient, supervisor_headers: dict[str, str],
    ) -> None:
        body = {
            "thresholds": [
                {"alarm_type": "HI", "priority": "WARNING", "limit": 90.0},
            ],
        }
        resp = await client.put(
            "/controllers/9999/alarm-config",
            json=body,
            headers=supervisor_headers,
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_update_replaces_previous_config(
        self,
        client: AsyncClient,
        supervisor_headers: dict[str, str],
        user_headers: dict[str, str],
        api_deps: dict,
    ) -> None:
        cid = await _create_controller(api_deps)
        # First update with 3 thresholds
        body1 = {
            "thresholds": [
                {"alarm_type": "HIHI", "priority": "CRITICAL", "limit": 95.0},
                {"alarm_type": "HI", "priority": "WARNING", "limit": 85.0},
                {"alarm_type": "LO", "priority": "WARNING", "limit": 15.0},
            ],
        }
        await client.put(
            f"/controllers/{cid}/alarm-config",
            json=body1,
            headers=supervisor_headers,
        )
        # Second update with only 1 threshold — replaces all
        body2 = {
            "thresholds": [
                {"alarm_type": "HI", "priority": "ADVISORY", "limit": 80.0},
            ],
        }
        resp = await client.put(
            f"/controllers/{cid}/alarm-config",
            json=body2,
            headers=supervisor_headers,
        )
        assert resp.status_code == 200
        resp2 = await client.get(
            f"/controllers/{cid}/alarm-config", headers=user_headers,
        )
        data = resp2.json()
        assert len(data["thresholds"]) == 1
        assert data["thresholds"][0]["alarm_type"] == "HI"
        assert data["thresholds"][0]["priority"] == "ADVISORY"
