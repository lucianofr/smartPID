"""Tests for /commands endpoints."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pytest

from smart_pid_core.application.loop_manager import LoopContext
from smart_pid_core.application.workers.pid_worker import PIDWorker
from smart_pid_core.domain.services.pid_engine import PIDEngine
from smart_pid_core.domain.services.pid_mode_manager import ModeManager
from smart_pid_core.domain.services.tuning_guardrails import KP_MIN
from smart_pid_domain.enums import ControllerMode, ExecutionMode
from smart_pid_domain.models.controller import AIConfig, Controller, PIDParams

if TYPE_CHECKING:
    from httpx import AsyncClient


async def _create_and_start_controller(
    api_deps: dict, ctrl: Controller | None = None,
) -> int:
    """Helper: save controller to DB and register its loop (no thread start)."""
    repo = api_deps["repo"]
    if ctrl is None:
        ctrl = Controller(
            id=0, name="TIC-101", pid_params=PIDParams(gain=1.0, reset=10.0, rate=0.0),
            execution_mode=ExecutionMode.SUPERVISORY,
        )
    saved = await repo.save(ctrl)
    # Register loop context without starting the PIDWorker thread to avoid hangs
    lm = api_deps["loop_manager"]
    bus = api_deps["bus"]
    engine = PIDEngine()
    mode_manager = ModeManager()
    pid_worker = PIDWorker(bus=bus, controller=saved, engine=engine, mode_manager=mode_manager)
    # Don't call pid_worker.start() — we only need the command interface
    ctx = LoopContext(
        controller=saved, pid_worker=pid_worker, engine=engine, mode_manager=mode_manager,
    )
    lm._loops[saved.id] = ctx
    return saved.id


async def _create_and_start_ddc_controller(api_deps: dict, name: str) -> int:
    """A loop whose PID SmartPID actually runs.

    Commands on a SUPERVISORY loop are written to the DCS over OPC-UA, so with
    no adapter installed they answer 409. Tests that mean to exercise the local
    PIDWorker path need the mode where SmartPID owns the algorithm — DDC.
    """
    return await _create_and_start_controller(
        api_deps,
        Controller(
            id=0, name=name,
            pid_params=PIDParams(gain=1.0, reset=10.0, rate=0.0),
            execution_mode=ExecutionMode.DDC,
        ),
    )


class TestSetpointCommand:
    @pytest.mark.asyncio
    async def test_set_valid_setpoint(
        self, client: AsyncClient, user_headers: dict[str, str], api_deps: dict
    ) -> None:
        cid = await _create_and_start_ddc_controller(api_deps, "TIC-101a")
        resp = await client.post(
            "/commands/setpoint",
            json={"controller_id": cid, "value": 55.0},
            headers=user_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    @pytest.mark.asyncio
    async def test_setpoint_above_limit(
        self, client: AsyncClient, user_headers: dict[str, str], api_deps: dict
    ) -> None:
        cid = await _create_and_start_ddc_controller(api_deps, "TIC-101b")
        resp = await client.post(
            "/commands/setpoint",
            json={"controller_id": cid, "value": 150.0},
            headers=user_headers,
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_setpoint_unknown_controller(
        self, client: AsyncClient, user_headers: dict[str, str]
    ) -> None:
        resp = await client.post(
            "/commands/setpoint",
            json={"controller_id": 9999, "value": 50.0},
            headers=user_headers,
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_setpoint_no_auth(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/commands/setpoint",
            json={"controller_id": 1, "value": 50.0},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    @pytest.mark.parametrize("literal", ["NaN", "Infinity", "-Infinity"])
    async def test_setpoint_non_finite_literal_is_422(
        self, client: AsyncClient, user_headers: dict[str, str], literal: str
    ) -> None:
        """A non-finite JSON literal must be refused with a renderable body.

        ``json.loads`` accepts these literals, so the value reaches the DTO and
        is rejected there — but the 422 echoes it back, and JSONResponse
        renders with allow_nan=False. Without the sanitising handler the
        response itself raised and the client saw a 500.
        """
        resp = await client.post(
            "/commands/setpoint",
            content=f'{{"controller_id": 1, "value": {literal}}}',
            headers={**user_headers, "Content-Type": "application/json"},
        )
        assert resp.status_code == 422
        assert resp.json()["detail"][0]["type"] == "finite_number"


class TestModeCommand:
    @pytest.mark.asyncio
    async def test_set_valid_mode(
        self, client: AsyncClient, user_headers: dict[str, str], api_deps: dict
    ) -> None:
        cid = await _create_and_start_ddc_controller(api_deps, "TIC-102")
        resp = await client.post(
            "/commands/mode",
            json={"controller_id": cid, "mode": "MAN"},
            headers=user_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    @pytest.mark.asyncio
    async def test_set_invalid_mode(
        self, client: AsyncClient, user_headers: dict[str, str], api_deps: dict
    ) -> None:
        cid = await _create_and_start_ddc_controller(api_deps, "TIC-103")
        resp = await client.post(
            "/commands/mode",
            json={"controller_id": cid, "mode": "CAS"},
            headers=user_headers,
        )
        assert resp.status_code == 400


class TestOutputCommand:
    @pytest.mark.asyncio
    async def test_set_output_in_man_mode(
        self, client: AsyncClient, user_headers: dict[str, str], api_deps: dict
    ) -> None:
        cid = await _create_and_start_ddc_controller(api_deps, "FIC-103")
        # Worker starts in MAN mode
        resp = await client.post(
            "/commands/output",
            json={"controller_id": cid, "value": 50.0},
            headers=user_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    @pytest.mark.asyncio
    async def test_set_output_not_in_man_fails(
        self, client: AsyncClient, user_headers: dict[str, str], api_deps: dict
    ) -> None:
        cid = await _create_and_start_ddc_controller(api_deps, "FIC-104")
        # Switch to AUTO first
        await client.post(
            "/commands/mode",
            json={"controller_id": cid, "mode": "AUTO"},
            headers=user_headers,
        )
        resp = await client.post(
            "/commands/output",
            json={"controller_id": cid, "value": 50.0},
            headers=user_headers,
        )
        assert resp.status_code == 400


class _FakeOPCUA:
    """Minimal OPC-UA stub recording every write the routes can make.

    ``mode`` is what the external block reports back. It defaults to MAN because
    a CO write requires the DCS block to be in MAN, the same bar apply-tuning
    applies before writing gains.
    """

    is_connected = True

    def __init__(self, mode: ControllerMode | None = ControllerMode.MAN) -> None:
        self.written: tuple[int, float | None, float | None, float | None] | None = None
        self.params: list[tuple[int, str, float]] = []
        self.modes: list[tuple[int, ControllerMode]] = []
        self._mode = mode

    def write_pid_params(
        self, controller_id: int, kp: float | None, ti: float | None, td: float | None,
    ) -> None:
        self.written = (controller_id, kp, ti, td)

    def write_parameter(self, controller_id: int, param: str, value: float) -> None:
        self.params.append((controller_id, param, value))

    def write_target_mode(self, controller_id: int, mode: ControllerMode) -> bool:
        self.modes.append((controller_id, mode))
        return True

    def read_actual_mode(self, controller_id: int) -> ControllerMode | None:
        return self._mode


class TestWriteTuningCommand:
    @pytest.mark.asyncio
    async def test_rejects_user_role(
        self, client: AsyncClient, user_headers: dict[str, str], api_deps: dict, app
    ) -> None:
        """POST /commands/tuning is admin-only (spec §9.2 Appendix A)."""
        cid = await _create_and_start_controller(api_deps)
        fake = _FakeOPCUA()
        app.state.opcua_adapter = fake
        resp = await client.post(
            "/commands/tuning",
            json={"controller_id": cid, "kp": 5.0},
            headers=user_headers,
        )
        assert resp.status_code == 403
        assert fake.written is None

    @pytest.mark.asyncio
    async def test_no_auth_returns_401(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/commands/tuning",
            json={"controller_id": 1, "kp": 5.0},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_out_of_range_params_clamped(
        self,
        client: AsyncClient,
        supervisor_headers: dict[str, str],
        api_deps: dict,
        app,
    ) -> None:
        """A supervisor pushing a huge gain gets clamped to max_tuning_change_pct."""
        cid = await _create_and_start_controller(api_deps)
        fake = _FakeOPCUA()
        app.state.opcua_adapter = fake
        # Current gain is 1.0, max_tuning_change_pct defaults to 10% -> max 1.1
        resp = await client.post(
            "/commands/tuning",
            json={"controller_id": cid, "kp": 100.0},
            headers=supervisor_headers,
        )
        assert resp.status_code == 200
        assert fake.written is not None
        _id, written_kp, _ti, _td = fake.written
        assert written_kp is not None
        # Clamped to no more than +10% of current (1.0 -> 1.1)
        assert written_kp <= 1.1 + 1e-9

    @pytest.mark.asyncio
    async def test_invalid_body_type_rejected(
        self, client: AsyncClient, supervisor_headers: dict[str, str], api_deps: dict
    ) -> None:
        """A non-numeric kp must be rejected by Pydantic validation (422)."""
        cid = await _create_and_start_controller(api_deps)
        resp = await client.post(
            "/commands/tuning",
            json={"controller_id": cid, "kp": "not-a-number"},
            headers=supervisor_headers,
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_kp_floored_at_absolute_minimum(
        self,
        client: AsyncClient,
        supervisor_headers: dict[str, str],
        api_deps: dict,
        app,
    ) -> None:
        """The rate clamp bounds the step, not the destination.

        With max_tuning_change_pct at 100 % a single write may legitimately move
        Kp all the way to zero without tripping the rate guard, and zero gain is
        a loop that has silently stopped controlling. KP_MIN is the backstop.
        """
        cid = await _create_and_start_controller(
            api_deps,
            Controller(
                id=0, name="FIC-200",
                pid_params=PIDParams(gain=1.0, reset=10.0, rate=0.0),
                max_tuning_change_pct=100.0,
            ),
        )
        fake = _FakeOPCUA()
        app.state.opcua_adapter = fake
        resp = await client.post(
            "/commands/tuning",
            json={"controller_id": cid, "kp": 0.0},
            headers=supervisor_headers,
        )
        assert resp.status_code == 200
        assert fake.written is not None
        _id, written_kp, _ti, _td = fake.written
        assert written_kp == pytest.approx(KP_MIN)

    @pytest.mark.asyncio
    async def test_supervisory_ti_raised_into_configured_band(
        self,
        client: AsyncClient,
        supervisor_headers: dict[str, str],
        api_deps: dict,
        app,
    ) -> None:
        """A SUPERVISORY loop whose Ti already sits under the operator's own
        Ti/Ki minimum must not be left there by a manual write. The AI worker is
        held to this band; the manual route must not be the way around it.
        """
        cid = await _create_and_start_controller(
            api_deps,
            Controller(
                id=0, name="LIC-300",
                pid_params=PIDParams(gain=1.0, reset=0.5, rate=0.0),
                execution_mode=ExecutionMode.SUPERVISORY,
                ai_config=AIConfig(limit_min=1.0, limit_max=10.0),
                max_tuning_change_pct=100.0,
            ),
        )
        fake = _FakeOPCUA()
        app.state.opcua_adapter = fake
        resp = await client.post(
            "/commands/tuning",
            json={"controller_id": cid, "ti": 0.5},
            headers=supervisor_headers,
        )
        assert resp.status_code == 200
        assert fake.written is not None
        _id, _kp, written_ti, _td = fake.written
        assert written_ti == pytest.approx(1.0)


class TestDCSBranchHonoursLoopLimits:
    """The sp/out span belongs to the loop, not to whoever runs its PID.

    `_dcs_owns_loop` routes SUPERVISORY and monitor-mode commands straight to
    `opcua.write_parameter`, bypassing the LoopManager that carries the range
    check. Same command, same controller, same out-of-range value must land the
    same answer whichever branch is taken.
    """

    @pytest.mark.asyncio
    async def test_setpoint_above_limit_rejected_on_dcs_branch(
        self,
        client: AsyncClient,
        user_headers: dict[str, str],
        api_deps: dict,
        app,
    ) -> None:
        cid = await _create_and_start_controller(
            api_deps,
            Controller(
                id=0, name="TIC-400",
                pid_params=PIDParams(gain=1.0, reset=10.0, rate=0.0),
                execution_mode=ExecutionMode.SUPERVISORY,
                sp_hi_lim=100.0, sp_lo_lim=0.0,
            ),
        )
        fake = _FakeOPCUA()
        app.state.opcua_adapter = fake
        resp = await client.post(
            "/commands/setpoint",
            json={"controller_id": cid, "value": 150.0},
            headers=user_headers,
        )
        assert resp.status_code == 400
        assert fake.params == []

    @pytest.mark.asyncio
    async def test_setpoint_below_limit_rejected_on_dcs_branch(
        self,
        client: AsyncClient,
        user_headers: dict[str, str],
        api_deps: dict,
        app,
    ) -> None:
        cid = await _create_and_start_controller(
            api_deps,
            Controller(
                id=0, name="TIC-401",
                pid_params=PIDParams(gain=1.0, reset=10.0, rate=0.0),
                execution_mode=ExecutionMode.SUPERVISORY,
                sp_hi_lim=100.0, sp_lo_lim=20.0,
            ),
        )
        fake = _FakeOPCUA()
        app.state.opcua_adapter = fake
        resp = await client.post(
            "/commands/setpoint",
            json={"controller_id": cid, "value": 5.0},
            headers=user_headers,
        )
        assert resp.status_code == 400
        assert fake.params == []

    @pytest.mark.asyncio
    async def test_setpoint_inside_limits_still_reaches_dcs(
        self,
        client: AsyncClient,
        user_headers: dict[str, str],
        api_deps: dict,
        app,
    ) -> None:
        """The guard must not become a wall: in-range writes still go out."""
        cid = await _create_and_start_controller(
            api_deps,
            Controller(
                id=0, name="TIC-402",
                pid_params=PIDParams(gain=1.0, reset=10.0, rate=0.0),
                execution_mode=ExecutionMode.SUPERVISORY,
                sp_hi_lim=100.0, sp_lo_lim=0.0,
            ),
        )
        fake = _FakeOPCUA()
        app.state.opcua_adapter = fake
        resp = await client.post(
            "/commands/setpoint",
            json={"controller_id": cid, "value": 55.0},
            headers=user_headers,
        )
        assert resp.status_code == 200
        assert fake.params == [(cid, "sp", 55.0)]

    @pytest.mark.asyncio
    async def test_output_above_limit_rejected_in_monitor_mode(
        self,
        client: AsyncClient,
        user_headers: dict[str, str],
        api_deps: dict,
        app,
    ) -> None:
        from smart_pid_core.adapters.inbound.api.dependencies import get_execution_mode

        cid = await _create_and_start_controller(
            api_deps,
            Controller(
                id=0, name="FIC-403",
                pid_params=PIDParams(gain=1.0, reset=10.0, rate=0.0),
                out_hi_lim=80.0, out_lo_lim=0.0,
                execution_mode=ExecutionMode.DDC,
            ),
        )
        fake = _FakeOPCUA()
        app.state.opcua_adapter = fake
        app.dependency_overrides[get_execution_mode] = lambda: "monitor"
        try:
            resp = await client.post(
                "/commands/output",
                json={"controller_id": cid, "value": 95.0},
                headers=user_headers,
            )
        finally:
            app.dependency_overrides.pop(get_execution_mode, None)
        assert resp.status_code == 400
        assert fake.params == []

    @pytest.mark.asyncio
    async def test_output_reaches_dcs_on_supervisory_loop(
        self,
        client: AsyncClient,
        user_headers: dict[str, str],
        api_deps: dict,
        app,
    ) -> None:
        """CO is read/write over OPC-UA on a SUPERVISORY loop, same as SP.

        `set_output` gated on `execution_mode == "monitor"` while `set_setpoint`
        gated on `_dcs_owns_loop`, so on a SUPERVISORY loop in execute mode the
        setpoint went to the DCS and the output did not: it landed in the local
        PIDWorker, `io_worker` dropped it for not being DDC, and the next
        telemetry frame overwrote it. HTTP 200, DCS never saw the value.
        """
        cid = await _create_and_start_controller(
            api_deps,
            Controller(
                id=0, name="FIC-500",
                pid_params=PIDParams(gain=1.0, reset=10.0, rate=0.0),
                execution_mode=ExecutionMode.SUPERVISORY,
                out_hi_lim=100.0, out_lo_lim=0.0,
            ),
        )
        fake = _FakeOPCUA()
        app.state.opcua_adapter = fake
        resp = await client.post(
            "/commands/output",
            json={"controller_id": cid, "value": 55.0},
            headers=user_headers,
        )
        assert resp.status_code == 200
        assert fake.params == [(cid, "co", 55.0)]

    @pytest.mark.asyncio
    async def test_output_above_limit_rejected_on_supervisory_loop(
        self,
        client: AsyncClient,
        user_headers: dict[str, str],
        api_deps: dict,
        app,
    ) -> None:
        cid = await _create_and_start_controller(
            api_deps,
            Controller(
                id=0, name="FIC-501",
                pid_params=PIDParams(gain=1.0, reset=10.0, rate=0.0),
                execution_mode=ExecutionMode.SUPERVISORY,
                out_hi_lim=80.0, out_lo_lim=0.0,
            ),
        )
        fake = _FakeOPCUA()
        app.state.opcua_adapter = fake
        resp = await client.post(
            "/commands/output",
            json={"controller_id": cid, "value": 95.0},
            headers=user_headers,
        )
        assert resp.status_code == 400
        assert fake.params == []


class TestSupervisoryWithoutLinkRefuses:
    """A SUPERVISORY loop has no local PID to fall back to.

    `_dcs_owns_loop` returned False whenever no OPC-UA adapter was installed,
    documented as "there is nothing external to command, so SmartPID handles it
    locally". There is nothing local either: `io_worker` writes CO for DDC loops
    only, so the command set a value on a PIDWorker that does not drive the loop
    and answered 200 for a write nothing would ever apply. Absent link is the
    same condition as a dead link, and that already answers 409.
    """

    @staticmethod
    async def _supervisory_loop(api_deps: dict, name: str) -> int:
        return await _create_and_start_controller(
            api_deps,
            Controller(
                id=0, name=name,
                pid_params=PIDParams(gain=1.0, reset=10.0, rate=0.0),
                execution_mode=ExecutionMode.SUPERVISORY,
                sp_hi_lim=100.0, sp_lo_lim=0.0,
                out_hi_lim=100.0, out_lo_lim=0.0,
            ),
        )

    @pytest.mark.asyncio
    async def test_setpoint_refused_without_adapter(
        self, client: AsyncClient, user_headers: dict[str, str], api_deps: dict, app
    ) -> None:
        cid = await self._supervisory_loop(api_deps, "TIC-600")
        app.state.opcua_adapter = None
        resp = await client.post(
            "/commands/setpoint",
            json={"controller_id": cid, "value": 55.0},
            headers=user_headers,
        )
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_output_refused_without_adapter(
        self, client: AsyncClient, user_headers: dict[str, str], api_deps: dict, app
    ) -> None:
        cid = await self._supervisory_loop(api_deps, "TIC-601")
        app.state.opcua_adapter = None
        resp = await client.post(
            "/commands/output",
            json={"controller_id": cid, "value": 42.0},
            headers=user_headers,
        )
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_mode_refused_without_adapter(
        self, client: AsyncClient, user_headers: dict[str, str], api_deps: dict, app
    ) -> None:
        cid = await self._supervisory_loop(api_deps, "TIC-602")
        app.state.opcua_adapter = None
        resp = await client.post(
            "/commands/mode",
            json={"controller_id": cid, "mode": "AUTO"},
            headers=user_headers,
        )
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_ddc_loop_still_handled_locally(
        self, client: AsyncClient, user_headers: dict[str, str], api_deps: dict, app
    ) -> None:
        """DDC is the mode where SmartPID does own the PID, adapter or not."""
        cid = await _create_and_start_controller(
            api_deps,
            Controller(
                id=0, name="TIC-603",
                pid_params=PIDParams(gain=1.0, reset=10.0, rate=0.0),
                execution_mode=ExecutionMode.DDC,
                sp_hi_lim=100.0, sp_lo_lim=0.0,
            ),
        )
        app.state.opcua_adapter = None
        resp = await client.post(
            "/commands/setpoint",
            json={"controller_id": cid, "value": 55.0},
            headers=user_headers,
        )
        assert resp.status_code == 200


class TestSupervisoryModeReachesTheDCS:
    """The 409 path is covered above; this covers the write actually happening.

    Without it, a call site hardcoded to the local branch would leave every
    SUPERVISORY mode change silently local and the suite still green.
    """

    @pytest.mark.asyncio
    async def test_mode_written_over_opcua(
        self, client: AsyncClient, user_headers: dict[str, str], api_deps: dict, app
    ) -> None:
        cid = await _create_and_start_controller(
            api_deps,
            Controller(
                id=0, name="TIC-700",
                pid_params=PIDParams(gain=1.0, reset=10.0, rate=0.0),
                execution_mode=ExecutionMode.SUPERVISORY,
            ),
        )
        fake = _FakeOPCUA()
        app.state.opcua_adapter = fake
        resp = await client.post(
            "/commands/mode",
            json={"controller_id": cid, "mode": "AUTO"},
            headers=user_headers,
        )
        assert resp.status_code == 200
        assert fake.modes == [(cid, ControllerMode.AUTO)]


class TestTuningClampsComposeByExecutionMode:
    """The absolute clamp splits on who runs the PID, and the route must pass the
    loop's own mode rather than assume one.

    Reached through HTTP on purpose: calling the pure function directly cannot
    catch a call site that hardcodes ``ExecutionMode.SUPERVISORY``.
    """

    @pytest.mark.asyncio
    async def test_ddc_loop_keeps_zero_ti_instead_of_the_ai_band(
        self,
        client: AsyncClient,
        supervisor_headers: dict[str, str],
        api_deps: dict,
        app,
    ) -> None:
        """Under DDC the engine is ours and reads Ti=0 as P-only, so the AI band
        must not be imposed. The same request on a SUPERVISORY loop lands on 1.0.
        """
        cid = await _create_and_start_controller(
            api_deps,
            Controller(
                id=0, name="TIC-701",
                pid_params=PIDParams(gain=1.0, reset=0.5, rate=0.0),
                execution_mode=ExecutionMode.DDC,
                ai_config=AIConfig(limit_min=1.0, limit_max=10.0),
                max_tuning_change_pct=100.0,
            ),
        )
        fake = _FakeOPCUA()
        app.state.opcua_adapter = fake
        resp = await client.post(
            "/commands/tuning",
            json={"controller_id": cid, "ti": 0.0},
            headers=supervisor_headers,
        )
        assert resp.status_code == 200
        assert fake.written is not None
        _id, _kp, written_ti, _td = fake.written
        assert written_ti == pytest.approx(0.0)

    @pytest.mark.asyncio
    async def test_absolute_clamp_still_fires_after_the_rate_clamp(
        self,
        client: AsyncClient,
        supervisor_headers: dict[str, str],
        api_deps: dict,
        app,
    ) -> None:
        """Both clamps on the same term, with the rate clamp actually limiting.

        Every other tuning test uses max_tuning_change_pct=100, which makes the
        rate clamp a pass-through. Here 50 % of a current gain of 0.104 lets the
        write reach 0.052, which is itself below KP_MIN — so the rate clamp
        produces a value the absolute clamp must still correct.
        """
        cid = await _create_and_start_controller(
            api_deps,
            Controller(
                id=0, name="TIC-702",
                pid_params=PIDParams(gain=0.104, reset=10.0, rate=0.0),
                execution_mode=ExecutionMode.SUPERVISORY,
                max_tuning_change_pct=50.0,
            ),
        )
        fake = _FakeOPCUA()
        app.state.opcua_adapter = fake
        resp = await client.post(
            "/commands/tuning",
            json={"controller_id": cid, "kp": 0.0},
            headers=supervisor_headers,
        )
        assert resp.status_code == 200
        assert fake.written is not None
        _id, written_kp, _ti, _td = fake.written
        assert written_kp == pytest.approx(KP_MIN)

    @pytest.mark.asyncio
    async def test_clamped_write_is_logged(
        self,
        client: AsyncClient,
        supervisor_headers: dict[str, str],
        api_deps: dict,
        app,
        caplog,
    ) -> None:
        """Silent clamping is how a mis-scaled client retunes a loop unnoticed:
        the write reports success and the DCS runs a different number. The log is
        the only thing connecting the two, so it is part of the contract.
        """
        cid = await _create_and_start_controller(
            api_deps,
            Controller(
                id=0, name="TIC-703",
                pid_params=PIDParams(gain=1.0, reset=10.0, rate=0.0),
                execution_mode=ExecutionMode.SUPERVISORY,
                max_tuning_change_pct=100.0,
            ),
        )
        app.state.opcua_adapter = _FakeOPCUA()
        with caplog.at_level(
            logging.WARNING,
            logger="smart_pid_core.adapters.inbound.api.routers.commands",
        ):
            resp = await client.post(
                "/commands/tuning",
                json={"controller_id": cid, "kp": 0.0},
                headers=supervisor_headers,
            )
        assert resp.status_code == 200
        assert any(
            "Kp" in r.getMessage() and "clamped" in r.getMessage()
            for r in caplog.records
        ), [r.getMessage() for r in caplog.records]


class TestOutputWriteHardening:
    """Routing SUPERVISORY output through OPC-UA reached two conditions the local
    branch never had to answer for.
    """

    @staticmethod
    async def _loop(api_deps: dict, name: str) -> int:
        return await _create_and_start_controller(
            api_deps,
            Controller(
                id=0, name=name,
                pid_params=PIDParams(gain=1.0, reset=10.0, rate=0.0),
                execution_mode=ExecutionMode.SUPERVISORY,
                out_hi_lim=100.0, out_lo_lim=0.0,
            ),
        )

    @pytest.mark.asyncio
    async def test_unmapped_co_node_is_not_a_500(
        self, client: AsyncClient, user_headers: dict[str, str], api_deps: dict, app
    ) -> None:
        """A loop with no CO node bound is an ordinary configuration state.

        `OPCUAAdapter.write_parameter` raises ValueError for a missing node mapping
        and KeyError for an unregistered loop, and nothing handled either — the
        local branch never reached that code for an execute-mode SUPERVISORY loop.
        """
        cid = await self._loop(api_deps, "FIC-800")

        class _Unmapped(_FakeOPCUA):
            def write_parameter(self, controller_id: int, param: str, value: float) -> None:
                msg = f"No node mapping for parameter '{param}'"
                raise ValueError(msg)

        app.state.opcua_adapter = _Unmapped()
        resp = await client.post(
            "/commands/output",
            json={"controller_id": cid, "value": 42.0},
            headers=user_headers,
        )
        assert resp.status_code == 409
        assert "co" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_refused_when_the_external_block_is_not_in_man(
        self, client: AsyncClient, user_headers: dict[str, str], api_deps: dict, app
    ) -> None:
        """A CO write lands on the block's output, and a running PID overwrites it
        on the next scan. `LoopManager.set_output` refuses unless the loop is in
        MAN; apply-tuning already reads the external mode before writing gains, and
        an output write moves the actuator more directly than a gain does.
        """
        cid = await self._loop(api_deps, "FIC-801")
        fake = _FakeOPCUA(mode=ControllerMode.AUTO)
        app.state.opcua_adapter = fake
        resp = await client.post(
            "/commands/output",
            json={"controller_id": cid, "value": 42.0},
            headers=user_headers,
        )
        assert resp.status_code == 409
        assert "AUTO" in resp.json()["detail"]
        assert fake.params == []

    @pytest.mark.asyncio
    async def test_written_when_the_external_block_is_in_man(
        self, client: AsyncClient, user_headers: dict[str, str], api_deps: dict, app
    ) -> None:
        cid = await self._loop(api_deps, "FIC-802")
        fake = _FakeOPCUA(mode=ControllerMode.MAN)
        app.state.opcua_adapter = fake
        resp = await client.post(
            "/commands/output",
            json={"controller_id": cid, "value": 42.0},
            headers=user_headers,
        )
        assert resp.status_code == 200
        assert fake.params == [(cid, "co", 42.0)]

    @pytest.mark.asyncio
    async def test_unknown_external_mode_stays_permissive(
        self, client: AsyncClient, user_headers: dict[str, str], api_deps: dict, app
    ) -> None:
        """No mode_actual node mapped reads None. Blocking every such loop would
        make the guard a wall; apply-tuning treats None the same way.
        """
        cid = await self._loop(api_deps, "FIC-803")
        fake = _FakeOPCUA(mode=None)
        app.state.opcua_adapter = fake
        resp = await client.post(
            "/commands/output",
            json={"controller_id": cid, "value": 42.0},
            headers=user_headers,
        )
        assert resp.status_code == 200
        assert fake.params == [(cid, "co", 42.0)]
