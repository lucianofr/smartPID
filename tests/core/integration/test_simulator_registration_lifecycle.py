"""Controller CRUD must keep the simulator's controller set in sync.

Registration used to happen only at daemon startup (``main.py``) and project
open (``ProjectService._load_simulator_configs``), so a controller created
through ``POST /controllers`` was invisible to the simulator until the daemon
restarted: ``POST /simulator/preset`` answered 500 (bare ``KeyError``) and the
``/simulator/{id}/pid/*`` routes answered 404. Deletion had the mirror gap —
the entry survived the controller.
"""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import httpx
import pytest

from smart_pid_core.adapters.inbound.api.app import create_app
from smart_pid_core.adapters.inbound.api.auth import create_access_token, hash_password
from smart_pid_core.adapters.inbound.simulator_adapter import SimulatorAdapter
from smart_pid_core.adapters.outbound.audit_repo import AuditRepository
from smart_pid_core.adapters.outbound.historian import SQLiteHistorian
from smart_pid_core.adapters.outbound.sqlite_repo import SQLiteRepository
from smart_pid_core.adapters.outbound.user_repo import UserRepository
from smart_pid_core.application.event_bus import EventBus
from smart_pid_core.application.loop_manager import LoopManager
from smart_pid_core.config import CoreSettings

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from fastapi import FastAPI


@pytest.fixture
async def deps(tmp_path) -> AsyncIterator[dict]:
    """Backend dependencies with an *empty* simulator.

    Deliberately not the shared ``sim_api_deps`` fixture: that one calls
    ``register_controller(1)`` up front, which is precisely the state this bug
    hides in — the first controller created through the API is assigned id 1,
    so a pre-registered id 1 would make every assertion here pass vacuously.

    ``SimulatorAdapter`` is the real thing. Its ``OPCUAServer`` is constructed
    but never started, so nothing binds a port; ``register_controller`` falls
    through to the pre-start branch that only records the id.
    """
    repo = SQLiteRepository(tmp_path / "test.spid")
    await repo.initialize()
    user_repo = UserRepository(tmp_path / "users.db")
    await user_repo.initialize()
    bus = EventBus(url_prefix=f"inproc://test_{uuid.uuid4().hex[:8]}")
    bus.start()
    settings = CoreSettings(
        jwt_secret="test-secret-key-minimum-32-bytes!",
        simulator_enabled=True,
        simulator_interval_ms=50,
    )  # type: ignore[call-arg]
    admin = await user_repo.create("admin", hash_password("admin"), "admin")
    adapter = SimulatorAdapter(settings=settings)

    yield {
        "repo": repo,
        "historian": SQLiteHistorian(repo.session_factory),
        "user_repo": user_repo,
        "audit_repo": AuditRepository(repo.session_factory),
        "loop_manager": LoopManager(bus=bus),
        "settings": settings,
        "simulator_adapter": adapter,
        "headers": {
            "Authorization": "Bearer "
            + create_access_token(
                user_id=admin.id, username=admin.username, role="admin",
                secret=settings.jwt_secret,
            ),
        },
    }

    adapter.stop()
    bus.stop()
    await user_repo.close()
    await repo.close()


def _build_app(deps: dict, *, simulator: bool) -> FastAPI:
    """Wire an app with the simulator either attached or absent.

    ``simulator=False`` reproduces ``SPID_SIMULATOR_ENABLED=false``, where
    ``AdapterFactory.simulator_adapter`` is ``None``.
    """
    return create_app(
        repo=deps["repo"],
        historian=deps["historian"],
        user_repo=deps["user_repo"],
        loop_manager=deps["loop_manager"],
        settings=deps["settings"],
        audit_repo=deps["audit_repo"],
        simulator_adapter=deps["simulator_adapter"] if simulator else None,
    )


async def _client(app: FastAPI) -> httpx.AsyncClient:
    """base_url host is 127.0.0.1 to satisfy TrustedHostMiddleware."""
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1",
    )


@pytest.fixture
async def client(deps) -> AsyncIterator[httpx.AsyncClient]:
    async with await _client(_build_app(deps, simulator=True)) as c:
        yield c


@pytest.fixture
async def client_no_sim(deps) -> AsyncIterator[httpx.AsyncClient]:
    async with await _client(_build_app(deps, simulator=False)) as c:
        yield c


async def _create(client: httpx.AsyncClient, deps: dict, **body: object) -> int:
    resp = await client.post(
        "/controllers", json={"name": "TIC-101", **body}, headers=deps["headers"],
    )
    assert resp.status_code == 201, resp.text
    return int(resp.json()["id"])


class TestCreateRegistersWithSimulator:
    @pytest.mark.asyncio
    async def test_preset_works_without_a_daemon_restart(
        self, client: httpx.AsyncClient, deps: dict,
    ) -> None:
        """The reported bug: POST /controllers then POST /simulator/preset.

        Before the fix this was a 500 with ``KeyError: <id>`` raised from
        ``SimulatorAdapter.set_preset``.
        """
        cid = await _create(client, deps)
        assert deps["simulator_adapter"].has_controller(cid)

        resp = await client.post(
            "/simulator/preset",
            json={"controller_id": cid, "preset": "FLOW"},
            headers=deps["headers"],
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["ok"] is True

    @pytest.mark.asyncio
    async def test_pid_routes_reachable_without_a_daemon_restart(
        self, client: httpx.AsyncClient, deps: dict,
    ) -> None:
        """The same bug surfacing as a 404 on the /pid/* routes."""
        cid = await _create(client, deps)
        for path, body in (
            (
                f"/simulator/{cid}/pid/params",
                {"controller_id": cid, "kp": 2.0, "ti": 5.0, "td": 1.0},
            ),
        ):
            resp = await client.post(path, json=body, headers=deps["headers"])
            assert resp.status_code == 200, f"{path}: {resp.text}"

    @pytest.mark.asyncio
    async def test_pv_scale_is_forwarded_to_the_simulation_state(
        self, client: httpx.AsyncClient, deps: dict,
    ) -> None:
        """pv_min/pv_max drive auto-excitation span, so they must not default.

        Reads private sim state — the same idiom the existing
        ``test_simulator_adapter.py`` unit tests use — because no public
        endpoint reports the registered span.
        """
        cid = await _create(
            client, deps, pv_scale={"eu_min": 20.0, "eu_max": 200.0, "unit": "degC"},
        )
        sim = deps["simulator_adapter"]._controllers[cid]
        assert (sim.pv_min, sim.pv_max) == (20.0, 200.0)


class TestSimulatorLoopsAreIndependentOfControllers:
    """The simulator is a standalone module.

    Its loops used to be created and destroyed as a side effect of
    controller CRUD, so you could not add a twin to experiment with
    without also adding a real loop, and deleting a real loop silently
    destroyed the twin someone was tuning against. Lifecycle now lives on
    ``/simulator/loops``.
    """

    @pytest.mark.asyncio
    async def test_deleting_a_controller_leaves_its_twin_running(
        self, client: httpx.AsyncClient, deps: dict,
    ) -> None:
        adapter = deps["simulator_adapter"]
        cid = await _create(client, deps)
        assert adapter.has_controller(cid)

        resp = await client.delete(f"/controllers/{cid}", headers=deps["headers"])
        assert resp.status_code == 204, resp.text
        assert adapter.has_controller(cid)

    @pytest.mark.asyncio
    async def test_a_loop_can_be_created_without_any_controller(
        self, client: httpx.AsyncClient, deps: dict,
    ) -> None:
        adapter = deps["simulator_adapter"]
        resp = await client.post(
            "/simulator/loops",
            json={"controller_id": 4242, "pv_min": 0.0, "pv_max": 100.0},
            headers=deps["headers"],
        )
        assert resp.status_code == 200, resp.text
        assert adapter.has_controller(4242)

    @pytest.mark.asyncio
    async def test_create_allocates_an_id_when_none_is_given(
        self, client: httpx.AsyncClient, deps: dict,
    ) -> None:
        adapter = deps["simulator_adapter"]
        resp = await client.post(
            "/simulator/loops",
            json={"controller_id": None, "pv_min": 0.0, "pv_max": 100.0},
            headers=deps["headers"],
        )
        assert resp.status_code == 200, resp.text
        assert any(adapter.has_controller(i) for i in range(1, 50))

    @pytest.mark.asyncio
    async def test_creating_an_existing_loop_is_a_conflict(
        self, client: httpx.AsyncClient, deps: dict,
    ) -> None:
        """Silently returning the existing loop would let the caller believe
        it got a fresh one and then wonder why it came pre-configured."""
        body = {"controller_id": 77, "pv_min": 0.0, "pv_max": 100.0}
        first = await client.post(
            "/simulator/loops", json=body, headers=deps["headers"],
        )
        assert first.status_code == 200, first.text
        second = await client.post(
            "/simulator/loops", json=body, headers=deps["headers"],
        )
        assert second.status_code == 409, second.text

    @pytest.mark.asyncio
    async def test_delete_drops_the_loop_and_routes_stop_answering(
        self, client: httpx.AsyncClient, deps: dict,
    ) -> None:
        adapter = deps["simulator_adapter"]
        cid = await _create(client, deps)
        assert adapter.has_controller(cid)

        resp = await client.delete(
            f"/simulator/loops/{cid}", headers=deps["headers"],
        )
        assert resp.status_code == 204, resp.text
        assert not adapter.has_controller(cid)

        ghost = await client.post(
            "/simulator/preset",
            json={"controller_id": cid, "preset": "FLOW"},
            headers=deps["headers"],
        )
        assert ghost.status_code == 404, ghost.text

    @pytest.mark.asyncio
    async def test_delete_of_an_unknown_loop_is_a_404(
        self, client: httpx.AsyncClient, deps: dict,
    ) -> None:
        resp = await client.delete(
            "/simulator/loops/31337", headers=deps["headers"],
        )
        assert resp.status_code == 404, resp.text

    @pytest.mark.asyncio
    async def test_new_loop_binds_its_opcua_nodes_to_the_client_adapter(
        self, deps: dict, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A loop minted at runtime must reach the OPC-UA client immediately.

        ``POST /simulator/loops`` mints the loop and its nodes on the twin,
        but the daemon's ``OPCUAAdapter`` (the only telemetry path) answers
        only for controllers registered against it — without this binding
        every read for the new loop raised KeyError and its trend chart
        stayed empty until a daemon restart. Same rule ``POST /controllers``
        applies via ``_sync_opcua_registration``.
        """
        from smart_pid_core.adapters.inbound.api.routers import simulator as sim_router

        bound: list[tuple[int, ...]] = []

        def _fake_bind(opcua_adapter, simulator_adapter, controller_ids):
            ids = tuple(controller_ids)
            bound.append(ids)
            return list(ids)

        monkeypatch.setattr(sim_router, "bind_opcua_client", _fake_bind)

        app = create_app(
            repo=deps["repo"],
            historian=deps["historian"],
            user_repo=deps["user_repo"],
            loop_manager=deps["loop_manager"],
            settings=deps["settings"],
            audit_repo=deps["audit_repo"],
            simulator_adapter=deps["simulator_adapter"],
            opcua_adapter=object(),  # presence alone must trigger the bind
        )
        adapter = deps["simulator_adapter"]
        before = set(adapter.get_status())
        async with await _client(app) as client:
            resp = await client.post(
                "/simulator/loops",
                json={"controller_id": None, "pv_min": 0.0, "pv_max": 100.0},
                headers=deps["headers"],
            )
            assert resp.status_code == 200, resp.text
        new_ids = set(adapter.get_status()) - before
        assert len(new_ids) == 1, f"expected one new loop, got {new_ids}"
        cid = new_ids.pop()
        assert any(cid in ids for ids in bound), (
            f"loop {cid} never bound on the OPC-UA client"
        )


class TestUnknownIdIsAnHonest404:
    """No ``/simulator/*`` route may leak a bare KeyError as an opaque 500.

    ``/preset``, ``/parameters`` and ``/disturbance`` had no translation at
    all; ``/{id}/co`` had the opposite failure and reported success, because
    ``write_output`` looks its controller up with ``dict.get``.
    """

    UNKNOWN = 999

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("method", "path", "body"),
        [
            ("post", "/simulator/preset", {"controller_id": UNKNOWN, "preset": "FLOW"}),
            (
                "put",
                "/simulator/parameters",
                {
                    "controller_id": UNKNOWN, "gain": 3.0, "tau1": 15.0,
                    "tau2": 8.0, "dead_time": 4.0,
                },
            ),
            (
                "post",
                "/simulator/disturbance",
                {"controller_id": UNKNOWN, "type": "step", "amplitude": 5.0},
            ),
            (
                "post",
                f"/simulator/{UNKNOWN}/co",
                {"controller_id": UNKNOWN, "sp": 42.0},
            ),
            (
                "post",
                f"/simulator/{UNKNOWN}/pid/sp",
                {"controller_id": UNKNOWN, "sp": 42.0},
            ),
            (
                "post",
                f"/simulator/{UNKNOWN}/pid/mode",
                {"controller_id": UNKNOWN, "mode": "AUTO"},
            ),
            ("delete", f"/simulator/disturbance/{UNKNOWN}", None),
            ("get", f"/simulator/{UNKNOWN}/pid/status", None),
            (
                "put",
                f"/simulator/{UNKNOWN}/auto-sp",
                {"enabled": True, "sp_min_pct": 30.0, "sp_max_pct": 70.0},
            ),
            (
                "put",
                f"/simulator/{UNKNOWN}/auto-disturbance",
                {"enabled": True, "max_amplitude_pct": 10.0},
            ),
        ],
    )
    async def test_unknown_controller_yields_404(
        self,
        client: httpx.AsyncClient,
        deps: dict,
        method: str,
        path: str,
        body: dict | None,
    ) -> None:
        kwargs: dict = {"headers": deps["headers"]}
        if body is not None:
            kwargs["json"] = body
        resp = await getattr(client, method)(path, **kwargs)
        assert resp.status_code == 404, f"{method.upper()} {path}: {resp.text}"
        assert str(self.UNKNOWN) in resp.json()["detail"]


class TestSimulatorDisabled:
    """``simulator_adapter is None`` must not affect controller CRUD."""

    @pytest.mark.asyncio
    async def test_create_and_delete_still_succeed(
        self, client_no_sim: httpx.AsyncClient, deps: dict,
    ) -> None:
        cid = await _create(client_no_sim, deps)
        resp = await client_no_sim.delete(
            f"/controllers/{cid}", headers=deps["headers"],
        )
        assert resp.status_code == 204, resp.text

    @pytest.mark.asyncio
    async def test_simulator_routes_report_the_simulator_is_off(
        self, client_no_sim: httpx.AsyncClient, deps: dict,
    ) -> None:
        """404 "Simulator not enabled" comes from the dependency, not the guard."""
        cid = await _create(client_no_sim, deps)
        resp = await client_no_sim.post(
            "/simulator/preset",
            json={"controller_id": cid, "preset": "FLOW"},
            headers=deps["headers"],
        )
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Simulator not enabled"
