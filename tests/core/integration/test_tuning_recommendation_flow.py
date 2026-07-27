"""End-to-end flow for backend-generated tuning recommendations (PRD-34/35/41).

Drives the *real* ``AIWorker`` thread over the *real* ``EventBus`` until it
identifies a FOPDT model from telemetry and parks a PENDING recommendation in
the shared ``TuningRecommendationStore``, then exercises the two command routes
against that same store.

Plant driven into the worker::

    K = 1.5 %PV/%CO,  tss = 0.20 s,  L = 0.04 s  ->  tau = (0.20-0.04)/4 = 0.04 s

IMC/lambda for SP_TRACKING (lambda = max(tau, 0.8L) = 0.04 s)::

    Kp = (2*0.04 + 0.04) / (2*1.5*(0.04 + 0.04)) = 0.12 / 0.24   = 0.5
    Ti = 0.04 + 0.04/2                                            = 0.06 s
    Td = 0.04*0.04 / 0.12                                         = 0.013333 s
"""
from __future__ import annotations

import asyncio
import threading
import time
import uuid

import msgpack
import pytest
from httpx import ASGITransport, AsyncClient

from smart_pid_core.adapters.inbound.api.app import create_app
from smart_pid_core.adapters.inbound.api.auth import create_access_token, hash_password
from smart_pid_core.adapters.outbound.alarm_repo import AlarmRepository
from smart_pid_core.adapters.outbound.audit_repo import AuditRepository
from smart_pid_core.adapters.outbound.historian import SQLiteHistorian
from smart_pid_core.adapters.outbound.sqlite_repo import SQLiteRepository
from smart_pid_core.adapters.outbound.user_repo import UserRepository
from smart_pid_core.application.event_bus import EventBus
from smart_pid_core.application.loop_manager import LoopManager
from smart_pid_core.application.tuning_store import TuningRecommendationStore
from smart_pid_core.config import CoreSettings
from smart_pid_domain.enums import (
    AIEngine,
    ControllerMode,
    ControlObjective,
    TuningRecStatus,
)
from smart_pid_domain.models.controller import (
    AIConfig,
    Controller,
    PIDParams,
    ScaleConfig,
)

_TSS_S = 0.20
_DEAD_TIME_S = 0.04
_PROCESS_GAIN = 1.5
_CURRENT_KP = 1.0
_CURRENT_TI = 10.0
_CURRENT_TD = 0.0
_MAX_CHANGE_PCT = 10.0

# Three settled operating points on PV = 1.5 * CO. The setpoint is held fixed
# throughout, so the loop is parked at a steady offset — the case a real
# P-dominant or windup-limited loop spends most of its life in.
_HELD_SP = 50.0
_OPERATING_POINTS = ((20.0, 30.0), (40.0, 60.0), (60.0, 90.0))

# Expected IMC output — see the module docstring for the hand check.
_EXPECTED_KP = 0.5
_EXPECTED_TI = 0.06
_EXPECTED_TD = 0.04 * 0.04 / 0.12


def _quiet_stats(controller_id: int) -> dict[str, float]:
    """A StatsWorker snapshot describing a loop that is completely at rest."""
    return {
        "controller_id": float(controller_id),
        "iae": 0.0, "itae": 0.0, "ise": 0.0, "mse": 0.0,
        "std_dev": 0.0, "total_variation": 0.0,
        "variability_sp": 0.0, "variability_range": 0.0,
        "mean_abs_error": 0.0, "pk_pk_error": 0.0,
        "reversals": 0.0, "zero_crossings": 0.0,
        "recent_pk_pk_error": 0.0, "recent_reversals": 0.0,
        "tv_per_sample": 0.0, "osc": 0.0, "sample_count": 60.0,
    }


class _PlantFeeder:
    """Publishes TELEMETRY + STATS for a settled loop, stepping operating point."""

    def __init__(self, bus: EventBus, controller_id: int) -> None:
        self._bus = bus
        self._cid = controller_id
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=5.0)

    def _run(self) -> None:
        pub = self._bus.create_publisher()
        time.sleep(0.05)
        telem_topic = f"TELEMETRY.{self._cid}".encode()
        stats_topic = f"STATS.{self._cid}".encode()
        stats = msgpack.packb(_quiet_stats(self._cid))
        started = time.monotonic()
        while not self._stop.is_set():
            # Hold each operating point for a little over one AI period so the
            # worker records it as a distinct settled point.
            idx = int((time.monotonic() - started) / 0.7) % len(_OPERATING_POINTS)
            co, pv = _OPERATING_POINTS[idx]
            pub.send(telem_topic, msgpack.packb({
                "pv": pv, "sp": _HELD_SP, "co": co, "mode": "AUTO",
                "integral_val": 0.0, "ti": _CURRENT_TI,
            }))
            pub.send(stats_topic, stats)
            self._stop.wait(0.02)
        pub.close()


def _make_controller(controller_id: int) -> Controller:
    return Controller(
        id=controller_id,
        name="TIC-IMC",
        scan_rate_s=0.02,
        tss_s=_TSS_S,
        pid_params=PIDParams(
            gain=_CURRENT_KP, reset=_CURRENT_TI, rate=_CURRENT_TD,
        ),
        pv_scale=ScaleConfig(eu_min=0.0, eu_max=100.0),
        max_tuning_change_pct=_MAX_CHANGE_PCT,
        ai_config=AIConfig(
            engine=AIEngine.FUZZY,
            objective=ControlObjective.SP_TRACKING,
            dead_time_l=_DEAD_TIME_S,
            limit_min=0.001,
            limit_max=1000.0,
        ),
    )


@pytest.fixture
async def flow(tmp_path):
    """Real bus + store + LoopManager + API app, sharing one recommendation store."""
    repo = SQLiteRepository(tmp_path / "test.spid")
    await repo.initialize()
    historian = SQLiteHistorian(repo.session_factory)
    user_repo = UserRepository(tmp_path / "users.db")
    await user_repo.initialize()
    alarm_repo = AlarmRepository(repo.session_factory)
    audit_repo = AuditRepository(repo.session_factory)
    bus = EventBus(url_prefix=f"inproc://test_tune_{uuid.uuid4().hex[:8]}")
    bus.start()

    store = TuningRecommendationStore()
    loop_manager = LoopManager(
        bus=bus, execution_mode="execute", tuning_store=store,
    )
    settings = CoreSettings(
        jwt_secret="test-secret-key-minimum-32-bytes!",
        execution_mode="execute",
    )  # type: ignore[call-arg]

    pw_hash = hash_password("pw")
    await user_repo.create("admin", pw_hash, "admin")     # id 1
    await user_repo.create("operator", pw_hash, "user")   # id 2

    saved = await repo.save(_make_controller(0))
    # Registers the loop and constructs the AIWorker with the shared store —
    # exactly the path main.py takes.
    loop_manager.start_loop(saved)
    # The PID worker starts in MAN and publishes that as the loop's
    # authoritative mode; AI tuning is only meaningful in closed loop.
    loop_manager.set_mode(saved.id, ControllerMode.AUTO)

    app = create_app(
        repo=repo, historian=historian, user_repo=user_repo,
        loop_manager=loop_manager, settings=settings,
        alarm_repo=alarm_repo, audit_repo=audit_repo,
        event_bus=bus, tuning_store=store,
    )

    yield {
        "app": app, "bus": bus, "store": store, "settings": settings,
        "controller_id": saved.id, "loop_manager": loop_manager,
    }

    loop_manager.stop_all()
    bus.stop()
    await user_repo.close()
    await repo.close()


def _headers(settings, *, role: str) -> dict[str, str]:
    user_id, username = (1, "admin") if role == "admin" else (2, "operator")
    token = create_access_token(
        user_id=user_id, username=username, role=role,
        secret=settings.jwt_secret,
    )
    return {"Authorization": f"Bearer {token}"}


async def _await_recommendation(store, controller_id: int, timeout_s: float = 20.0):
    """Poll the store until the worker thread parks a recommendation."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        tracked = store.get(controller_id)
        if tracked is not None:
            return tracked
        await asyncio.sleep(0.05)
    return None


class TestTuningRecommendationFlow:
    @pytest.mark.asyncio
    async def test_identifiable_loop_produces_and_applies(self, flow) -> None:
        cid = flow["controller_id"]
        feeder = _PlantFeeder(flow["bus"], cid)
        feeder.start()
        try:
            tracked = await _await_recommendation(flow["store"], cid)
            assert tracked is not None, "AIWorker never produced a recommendation"
        finally:
            feeder.stop()

        # --- the model the worker identified -------------------------------
        rec = tracked.recommendation
        assert tracked.status == TuningRecStatus.PENDING
        assert rec.controller_id == cid
        assert rec.current_kp == pytest.approx(_CURRENT_KP)
        assert rec.current_ti == pytest.approx(_CURRENT_TI)
        assert rec.current_td == pytest.approx(_CURRENT_TD)
        assert rec.recommended_kp == pytest.approx(_EXPECTED_KP, rel=1e-6)
        assert rec.recommended_ti == pytest.approx(_EXPECTED_TI, rel=1e-6)
        assert rec.recommended_td == pytest.approx(_EXPECTED_TD, rel=1e-6)
        assert "IMC" in rec.reason
        assert f"K={_PROCESS_GAIN:+.4g} %PV/%CO" in rec.reason
        assert "tau=0.04 s" in rec.reason
        assert "lambda=0.04 s" in rec.reason

        transport = ASGITransport(app=flow["app"])
        async with AsyncClient(transport=transport, base_url="http://127.0.0.1") as client:
            # --- GET is readable by an operator ----------------------------
            resp = await client.get(
                f"/commands/tuning-recommendations/{cid}",
                headers=_headers(flow["settings"], role="user"),
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["status"] == "pending"
            assert body["controller_id"] == cid
            assert body["recommended_kp"] == pytest.approx(_EXPECTED_KP, rel=1e-6)
            assert body["recommended_ti"] == pytest.approx(_EXPECTED_TI, rel=1e-6)
            assert body["recommended_td"] == pytest.approx(_EXPECTED_TD, rel=1e-6)

            # --- apply is admin-only (PRD-34) ------------------------------
            resp = await client.post(
                f"/commands/apply-tuning/{cid}",
                headers=_headers(flow["settings"], role="user"),
            )
            assert resp.status_code == 403
            assert flow["store"].get(cid).status == TuningRecStatus.PENDING

            # --- admin applies; guardrails clamp server-side (PRD-35) ------
            resp = await client.post(
                f"/commands/apply-tuning/{cid}",
                headers=_headers(flow["settings"], role="admin"),
            )
            assert resp.status_code == 200
            applied = resp.json()
            # max_tuning_change_pct = 10 %, so each parameter moves at most
            # 10 % of its current value toward the recommendation.
            assert applied["applied_kp"] == pytest.approx(0.9)
            assert applied["applied_ti"] == pytest.approx(9.0)
            assert applied["applied_td"] == pytest.approx(0.0)
            assert applied["clamped"] is True

            # --- store marked APPLIED, and a second GET reflects it --------
            tracked_after = flow["store"].get(cid)
            assert tracked_after.status == TuningRecStatus.APPLIED
            assert tracked_after.applied_by == 1

            resp = await client.get(
                f"/commands/tuning-recommendations/{cid}",
                headers=_headers(flow["settings"], role="admin"),
            )
            assert resp.status_code == 200
            assert resp.json()["status"] == "applied"

            # --- an applied recommendation cannot be re-applied ------------
            resp = await client.post(
                f"/commands/apply-tuning/{cid}",
                headers=_headers(flow["settings"], role="admin"),
            )
            assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_unidentifiable_loop_produces_nothing(self, flow) -> None:
        """A loop pinned at one operating point carries no gain information."""
        cid = flow["controller_id"]
        bus = flow["bus"]
        pub = bus.create_publisher()
        time.sleep(0.05)
        stats = msgpack.packb(_quiet_stats(cid))
        deadline = time.monotonic() + 2.5
        while time.monotonic() < deadline:
            pub.send(f"TELEMETRY.{cid}".encode(), msgpack.packb({
                "pv": 50.0, "sp": 50.0, "co": 33.0, "mode": "AUTO",
                "integral_val": 0.0, "ti": _CURRENT_TI,
            }))
            pub.send(f"STATS.{cid}".encode(), stats)
            time.sleep(0.02)
        pub.close()

        assert flow["store"].get(cid) is None

        transport = ASGITransport(app=flow["app"])
        async with AsyncClient(transport=transport, base_url="http://127.0.0.1") as client:
            resp = await client.get(
                f"/commands/tuning-recommendations/{cid}",
                headers=_headers(flow["settings"], role="admin"),
            )
            assert resp.status_code == 404
