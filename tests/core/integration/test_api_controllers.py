"""Tests for /controllers CRUD endpoints (route prefix changed from /config/controllers)."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from httpx import AsyncClient


class TestListControllers:
    @pytest.mark.asyncio
    async def test_list_empty(
        self, client: AsyncClient, user_headers: dict[str, str]
    ) -> None:
        resp = await client.get("/controllers", headers=user_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_list_requires_auth(self, client: AsyncClient) -> None:
        resp = await client.get("/controllers")
        assert resp.status_code == 401


class TestCreateController:
    @pytest.mark.asyncio
    async def test_create_as_admin(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        resp = await client.post(
            "/controllers",
            json={"name": "TIC-101", "description": "Temperature loop"},
            headers=admin_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "TIC-101"
        assert data["id"] > 0

    @pytest.mark.asyncio
    async def test_create_any_authenticated_user_allowed(
        self, client: AsyncClient, user_headers: dict[str, str]
    ) -> None:
        # Single-admin deployment: any authenticated user may create.
        resp = await client.post(
            "/controllers",
            json={"name": "TIC-101"},
            headers=user_headers,
        )
        assert resp.status_code == 201


class TestGetController:
    @pytest.mark.asyncio
    async def test_get_existing(
        self, client: AsyncClient, admin_headers: dict[str, str], user_headers: dict[str, str]
    ) -> None:
        create_resp = await client.post(
            "/controllers",
            json={"name": "TIC-101"},
            headers=admin_headers,
        )
        cid = create_resp.json()["id"]
        resp = await client.get(f"/controllers/{cid}", headers=user_headers)
        assert resp.status_code == 200
        assert resp.json()["name"] == "TIC-101"

    @pytest.mark.asyncio
    async def test_get_not_found(
        self, client: AsyncClient, user_headers: dict[str, str]
    ) -> None:
        resp = await client.get("/controllers/9999", headers=user_headers)
        assert resp.status_code == 404


class TestUpdateController:
    @pytest.mark.asyncio
    async def test_update_as_admin(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        create_resp = await client.post(
            "/controllers",
            json={"name": "TIC-101"},
            headers=admin_headers,
        )
        cid = create_resp.json()["id"]
        resp = await client.put(
            f"/controllers/{cid}",
            json={"description": "Updated"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["description"] == "Updated"


class TestDeleteController:
    @pytest.mark.asyncio
    async def test_delete_as_admin(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        create_resp = await client.post(
            "/controllers",
            json={"name": "TIC-101"},
            headers=admin_headers,
        )
        cid = create_resp.json()["id"]
        resp = await client.delete(f"/controllers/{cid}", headers=admin_headers)
        assert resp.status_code == 204

    @pytest.mark.asyncio
    async def test_delete_not_found(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        resp = await client.delete("/controllers/9999", headers=admin_headers)
        assert resp.status_code == 404


# ── Full-field CRUD tests ──────────────────────────────────────────────────────

FULL_CREATE_PAYLOAD: dict = {
    "name": "FIC-301",
    "description": "Flow control loop",
    "execution_mode": "SUPERVISORY",
    "scan_rate_s": 0.5,
    "pid_params": {
        "gain": 2.5,
        "reset": 20.0,
        "rate": 0.5,
        "alpha": 0.1,
        "deadband": 0.5,
    },
    "pid_structure": "PARALLEL",
    "integral_type": "GAIN_KI",
    "pv_scale": {"eu_min": 0.0, "eu_max": 200.0, "unit": "m3/h"},
    "out_scale": {"eu_min": 0.0, "eu_max": 100.0, "unit": "%"},
    "tag_bindings": {
        "node_id_pv": "ns=2;s=FIC301.PV",
        "node_id_sp": "ns=2;s=FIC301.SP",
        "node_id_co": "ns=2;s=FIC301.CO",
        "node_id_integral": "",
        "node_id_bkcal_in": "",
        "node_id_bkcal_out": "",
        "node_id_kp": "",
        "node_id_ti": "",
        "node_id_td": "",
        "node_id_mode_target": "",
        "node_id_mode_actual": "",
        "mode_int_map": {},
    },
    "control_opts": {
        "no_out_limits_in_manual": True,
        "obey_sp_limits_if_cas": True,
        "track_in_manual": False,
        "track_enable": False,
        "direct_acting": True,
        "sp_track_retained_target": False,
        "sp_pv_track_in_lo_or_iman": False,
        "sp_pv_track_in_rout": False,
        "sp_pv_track_in_man": False,
        "use_pv_for_bkcal_out": False,
    },
    "io_opts": {
        "low_cutoff": True,
        "target_to_man_if_fault": False,
        "fault_state_to_value": False,
        "increase_to_close": True,
        "sp_pv_track_in_lo_or_iman": False,
        "sp_pv_track_in_man": False,
    },
    "process_speed": "SLOW",
    "ai_config": {
        "engine": "FUZZY",
        "objective": "SP_TRACKING",
        "dead_time_l": 5.0,
        "limit_min": 0.2,
        "limit_max": 50.0,
    },
    "tuning_write_mode": "approval_required",
    "max_tuning_change_pct": 15.0,
    "mode_normal": "AUTO",
    "sp_hi_lim": 180.0,
    "sp_lo_lim": 10.0,
    "sp_rate_up": 5.0,
    "sp_rate_dn": 5.0,
    "out_hi_lim": 95.0,
    "out_lo_lim": 5.0,
    "arw_hi_lim": 90.0,
    "arw_lo_lim": 10.0,
    "pv_ftime": 0.5,
    "sp_ftime": 0.3,
    "low_cut": 2.0,
    "ff_enable": True,
    "ff_gain": 0.8,
    "shed_opt": "MAN",
    "shed_time_s": 30.0,
}


class TestFullFieldCreateAndGet:
    @pytest.mark.asyncio
    async def test_create_with_all_fields(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        resp = await client.post(
            "/controllers", json=FULL_CREATE_PAYLOAD, headers=admin_headers
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "FIC-301"
        assert data["execution_mode"] == "SUPERVISORY"
        assert data["scan_rate_s"] == 0.5
        assert data["pid_params"]["gain"] == 2.5
        assert data["pid_params"]["alpha"] == 0.1
        assert data["pid_structure"] == "PARALLEL"
        assert data["integral_type"] == "GAIN_KI"
        assert data["pv_scale"]["eu_max"] == 200.0
        assert data["pv_scale"]["unit"] == "m3/h"
        assert data["tag_bindings"]["node_id_pv"] == "ns=2;s=FIC301.PV"
        assert data["control_opts"]["direct_acting"] is True
        assert data["io_opts"]["increase_to_close"] is True
        assert data["ai_config"]["engine"] == "FUZZY"
        assert data["ai_config"]["objective"] == "SP_TRACKING"
        assert data["process_speed"] == "SLOW"
        assert data["sp_hi_lim"] == 180.0
        assert data["arw_hi_lim"] == 90.0
        assert data["ff_enable"] is True
        assert data["ff_gain"] == 0.8
        assert data["shed_time_s"] == 30.0

    @pytest.mark.asyncio
    async def test_get_returns_all_fields(
        self, client: AsyncClient, admin_headers: dict[str, str], user_headers: dict[str, str]
    ) -> None:
        create_resp = await client.post(
            "/controllers", json=FULL_CREATE_PAYLOAD, headers=admin_headers
        )
        cid = create_resp.json()["id"]
        resp = await client.get(f"/controllers/{cid}", headers=user_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["execution_mode"] == "SUPERVISORY"
        assert data["pid_params"]["gain"] == 2.5
        assert data["pid_params"]["deadband"] == 0.5
        assert data["pid_structure"] == "PARALLEL"
        assert data["pv_scale"]["eu_max"] == 200.0
        assert data["tag_bindings"]["node_id_sp"] == "ns=2;s=FIC301.SP"
        assert data["control_opts"]["no_out_limits_in_manual"] is True
        assert data["io_opts"]["low_cutoff"] is True
        assert data["ai_config"]["dead_time_l"] == 5.0
        assert data["arw_lo_lim"] == 10.0
        assert data["pv_ftime"] == 0.5


class TestFullFieldUpdate:
    @pytest.mark.asyncio
    async def test_update_nested_fields(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        create_resp = await client.post(
            "/controllers",
            json={"name": "LIC-400"},
            headers=admin_headers,
        )
        cid = create_resp.json()["id"]
        update_payload = {
            "pid_params": {"gain": 3.0, "reset": 15.0, "rate": 1.0, "alpha": 0.2, "deadband": 1.0},
            "pid_structure": "SERIES",
            "process_speed": "FAST",
            "ai_config": {
                "engine": "RL",
                "objective": "SURGE_LEVEL",
                "dead_time_l": 10.0,
                "limit_min": 0.5,
                "limit_max": 80.0,
            },
            "pv_scale": {"eu_min": -50.0, "eu_max": 50.0, "unit": "degC"},
            "tag_bindings": {"node_id_pv": "ns=3;s=LIC400.PV", "node_id_sp": "ns=3;s=LIC400.SP",
                            "node_id_co": "", "node_id_integral": "", "node_id_bkcal_in": "",
                            "node_id_bkcal_out": "", "node_id_kp": "", "node_id_ti": "",
                            "node_id_td": "", "node_id_mode_target": "",
                            "node_id_mode_actual": "", "mode_int_map": {}},
            "control_opts": {
                "no_out_limits_in_manual": False, "obey_sp_limits_if_cas": False,
                "track_in_manual": True, "track_enable": True, "direct_acting": False,
                "sp_track_retained_target": False, "sp_pv_track_in_lo_or_iman": False,
                "sp_pv_track_in_rout": False, "sp_pv_track_in_man": False,
                "use_pv_for_bkcal_out": True,
            },
            "arw_hi_lim": 85.0,
            "ff_enable": True,
            "ff_gain": 0.6,
            "shed_time_s": 60.0,
        }
        resp = await client.put(
            f"/controllers/{cid}", json=update_payload, headers=admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["pid_params"]["gain"] == 3.0
        assert data["pid_params"]["alpha"] == 0.2
        assert data["pid_structure"] == "SERIES"
        assert data["ai_config"]["engine"] == "RL"
        assert data["ai_config"]["objective"] == "SURGE_LEVEL"
        assert data["pv_scale"]["eu_min"] == -50.0
        assert data["pv_scale"]["unit"] == "degC"
        assert data["tag_bindings"]["node_id_pv"] == "ns=3;s=LIC400.PV"
        assert data["control_opts"]["track_in_manual"] is True
        assert data["control_opts"]["use_pv_for_bkcal_out"] is True
        assert data["arw_hi_lim"] == 85.0
        assert data["ff_enable"] is True
        assert data["shed_time_s"] == 60.0


class TestModeBindingAPI:
    @pytest.mark.asyncio
    async def test_create_with_mode_bindings(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        payload = {
            "name": "MODE-API-TEST",
            "tag_bindings": {
                "node_id_pv": "ns=2;s=PV",
                "node_id_mode_target": "ns=2;s=MODE_TGT",
                "node_id_mode_actual": "ns=2;s=MODE_ACT",
                "mode_int_map": {"MAN": 1, "AUTO": 2},
            },
            "permitted_modes": ["MAN", "AUTO", "CAS"],
        }
        resp = await client.post("/controllers", json=payload, headers=admin_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["tag_bindings"]["node_id_mode_target"] == "ns=2;s=MODE_TGT"
        assert data["tag_bindings"]["node_id_mode_actual"] == "ns=2;s=MODE_ACT"
        assert data["tag_bindings"]["mode_int_map"] == {"MAN": 1, "AUTO": 2}
        assert set(data["permitted_modes"]) == {"MAN", "AUTO", "CAS"}

    @pytest.mark.asyncio
    async def test_no_old_node_id_mode_in_response(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        payload = {"name": "NO-OLD-MODE"}
        resp = await client.post("/controllers", json=payload, headers=admin_headers)
        assert resp.status_code == 201
        assert "node_id_mode" not in resp.json()["tag_bindings"]
