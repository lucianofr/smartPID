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
    async def test_create_rejects_user_role(
        self, client: AsyncClient, user_headers: dict[str, str]
    ) -> None:
        # POST /controllers is admin-only (spec §9.2 Appendix A).
        resp = await client.post(
            "/controllers",
            json={"name": "TIC-101"},
            headers=user_headers,
        )
        assert resp.status_code == 403


class TestInvalidEnumIsRejected:
    """Enum-valued fields arrive as plain strings, so the domain enum is the
    first thing that rejects a bad value. That ValueError used to escape the
    handler and answer 500; a client typo must be a 422 instead."""

    @pytest.mark.asyncio
    async def test_create_with_unknown_execution_mode(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        resp = await client.post(
            "/controllers",
            json={"name": "TIC-BAD", "execution_mode": "SIMULATOR"},
            headers=admin_headers,
        )
        assert resp.status_code == 422
        assert "ExecutionMode" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_create_with_unknown_process_speed(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        resp = await client.post(
            "/controllers",
            json={"name": "TIC-BAD2", "process_speed": "WARP"},
            headers=admin_headers,
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_update_with_unknown_execution_mode(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        created = await client.post(
            "/controllers", json={"name": "TIC-ENUM"}, headers=admin_headers,
        )
        controller_id = created.json()["id"]
        resp = await client.put(
            f"/controllers/{controller_id}",
            json={"execution_mode": "SIMULATOR"},
            headers=admin_headers,
        )
        assert resp.status_code == 422
        assert "ExecutionMode" in resp.json()["detail"]


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


class TestSafeTuningFields:
    """`node_id_enabled` and `stability_band_pct` survive create -> GET -> PUT -> GET."""

    @pytest.mark.asyncio
    async def test_defaults_are_unmapped_tag_and_inherited_band(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        resp = await client.post(
            "/controllers", json={"name": "TIC-500"}, headers=admin_headers
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["tag_bindings"]["node_id_enabled"] == ""
        # None = inherit the daemon-wide band, not "no guardrail".
        assert data["stability_band_pct"] is None

    @pytest.mark.asyncio
    async def test_round_trip_through_put_and_get(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        cid = (
            await client.post(
                "/controllers", json={"name": "TIC-501"}, headers=admin_headers
            )
        ).json()["id"]

        put = await client.put(
            f"/controllers/{cid}",
            json={
                "integral_type": "GAIN_KI",
                "stability_band_pct": 0.5,
                "tag_bindings": {
                    "node_id_pv": "ns=2;s=TIC501.PV",
                    "node_id_enabled": "ns=2;s=Process_Running",
                },
            },
            headers=admin_headers,
        )
        assert put.status_code == 200

        data = (
            await client.get(f"/controllers/{cid}", headers=admin_headers)
        ).json()
        assert data["integral_type"] == "GAIN_KI"
        assert data["stability_band_pct"] == 0.5
        assert data["tag_bindings"]["node_id_enabled"] == "ns=2;s=Process_Running"


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


class TestWriteBoundsAtTheBoundary:
    """Editing a SUPERVISORY loop's `pid_params` writes them to the DCS over
    OPC-UA (the config dialog is how tuning reaches an external controller), and
    that write carried no bound at all.

    These are 422s rather than clamps because the route persists before it
    writes: clamping would store one number and send another, leaving the dialog
    showing a value the DCS is not running. `inf` used to persist outright and
    `nan` used to surface as an uncaught IntegrityError 500 — neither told the
    operator which field was wrong.
    """

    @pytest.mark.asyncio
    async def test_infinite_gain_refused_and_never_written(
        self, client: AsyncClient, admin_headers: dict[str, str], app
    ) -> None:
        create_resp = await client.post(
            "/controllers", json=FULL_CREATE_PAYLOAD, headers=admin_headers,
        )
        cid = create_resp.json()["id"]

        written: list[tuple] = []

        class _FakeOPCUA:
            is_connected = True

            def write_pid_params(self, *args: object) -> None:
                written.append(args)

        app.state.opcua_adapter = _FakeOPCUA()
        try:
            resp = await client.put(
                f"/controllers/{cid}",
                # httpx cannot serialise inf, and a real client would not either:
                # the value arrives as the bare `Infinity` literal Python's json
                # module accepts on the way in.
                content=(
                    '{"pid_params": {"gain": Infinity, "reset": 10.0, '
                    '"rate": 0.0, "alpha": 0.125, "deadband": 0.0}}'
                ),
                headers={**admin_headers, "Content-Type": "application/json"},
            )
        finally:
            app.state.opcua_adapter = None
        assert resp.status_code == 422
        assert written == []

    @pytest.mark.asyncio
    async def test_zero_gain_refused(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        create_resp = await client.post(
            "/controllers", json=FULL_CREATE_PAYLOAD, headers=admin_headers,
        )
        cid = create_resp.json()["id"]
        resp = await client.put(
            f"/controllers/{cid}",
            json={"pid_params": {
                "gain": 0.0, "reset": 10.0, "rate": 0.0,
                "alpha": 0.125, "deadband": 0.0,
            }},
            headers=admin_headers,
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_nan_span_refused_with_field_name(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        """Previously an uncaught sqlite3.IntegrityError, i.e. a bare 500."""
        create_resp = await client.post(
            "/controllers", json=FULL_CREATE_PAYLOAD, headers=admin_headers,
        )
        cid = create_resp.json()["id"]
        resp = await client.put(
            f"/controllers/{cid}",
            content='{"sp_hi_lim": NaN}',
            headers={**admin_headers, "Content-Type": "application/json"},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_zero_scan_rate_refused_on_create(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        """Persisted, a zero scan rate spins the PIDWorker thread every boot."""
        resp = await client.post(
            "/controllers",
            json={**FULL_CREATE_PAYLOAD, "name": "SPIN-1", "scan_rate_s": 0.0},
            headers=admin_headers,
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_valid_tuning_edit_still_reaches_the_dcs(
        self, client: AsyncClient, admin_headers: dict[str, str], app
    ) -> None:
        """The guard must not become a wall: a legitimate edit still writes."""
        create_resp = await client.post(
            "/controllers", json=FULL_CREATE_PAYLOAD, headers=admin_headers,
        )
        cid = create_resp.json()["id"]

        written: list[tuple] = []

        class _FakeOPCUA:
            is_connected = True

            def write_pid_params(self, *args: object) -> None:
                written.append(args)

        app.state.opcua_adapter = _FakeOPCUA()
        try:
            resp = await client.put(
                f"/controllers/{cid}",
                json={"pid_params": {
                    "gain": 2.0, "reset": 15.0, "rate": 0.5,
                    "alpha": 0.125, "deadband": 0.0,
                }},
                headers=admin_headers,
            )
        finally:
            app.state.opcua_adapter = None
        assert resp.status_code == 200
        assert written == [(cid, 2.0, 15.0, 0.5)]


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


class TestOptimizationEnabledInResponse:
    @pytest.mark.asyncio
    async def test_response_defaults_optimization_enabled_true(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        resp = await client.post(
            "/controllers", json={"name": "OPT-DEFAULT"}, headers=admin_headers
        )
        assert resp.status_code == 201
        assert resp.json()["optimization_enabled"] is True

    @pytest.mark.asyncio
    async def test_get_reflects_saved_optimization_enabled_false(
        self, client: AsyncClient, user_headers: dict[str, str], api_deps: dict
    ) -> None:
        from smart_pid_domain.models.controller import Controller

        repo = api_deps["repo"]
        saved = await repo.save(
            Controller(id=0, name="OPT-OFF", optimization_enabled=False)
        )
        resp = await client.get(f"/controllers/{saved.id}", headers=user_headers)
        assert resp.status_code == 200
        assert resp.json()["optimization_enabled"] is False

    @pytest.mark.asyncio
    async def test_list_reflects_saved_optimization_enabled_false(
        self, client: AsyncClient, user_headers: dict[str, str], api_deps: dict
    ) -> None:
        from smart_pid_domain.models.controller import Controller

        repo = api_deps["repo"]
        await repo.save(Controller(id=0, name="OPT-OFF-LIST", optimization_enabled=False))
        resp = await client.get("/controllers", headers=user_headers)
        assert resp.status_code == 200
        match = next(c for c in resp.json() if c["name"] == "OPT-OFF-LIST")
        assert match["optimization_enabled"] is False
