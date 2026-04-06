"""Tests for monitor-mode gating on /commands endpoints and apply-tuning."""
from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import MagicMock

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
from smart_pid_core.application.loop_manager import LoopContext, LoopManager
from smart_pid_core.application.workers.pid_worker import PIDWorker
from smart_pid_core.config import CoreSettings
from smart_pid_domain.enums import ControllerMode
from smart_pid_core.domain.services.pid_engine import PIDEngine
from smart_pid_core.domain.services.pid_mode_manager import ModeManager
from smart_pid_domain.models.controller import Controller, PIDParams


@dataclass
class _FakeRec:
    """Minimal tuning recommendation for testing."""
    current_kp: float = 1.0
    current_ti: float = 10.0
    current_td: float = 0.5
    recommended_kp: float = 1.2
    recommended_ti: float = 9.0
    recommended_td: float = 0.6


@pytest.fixture
async def monitor_deps(tmp_path):
    """Create API deps with execution_mode=monitor."""
    import uuid

    db_path = tmp_path / "test.spid"
    repo = SQLiteRepository(db_path)
    await repo.initialize()
    historian = SQLiteHistorian(repo.db)
    user_db_path = tmp_path / "users.db"
    user_repo = UserRepository(user_db_path)
    await user_repo.initialize()
    alarm_repo = AlarmRepository(repo.db)
    audit_repo = AuditRepository(repo.db)
    bus = EventBus(url_prefix=f"inproc://test_{uuid.uuid4().hex[:8]}")
    bus.start()
    loop_manager = LoopManager(bus=bus, execution_mode="monitor")
    settings = CoreSettings(
        jwt_secret="test-secret-key-minimum-32-bytes!",
        execution_mode="monitor",
    )  # type: ignore[call-arg]

    admin_hash = hash_password("admin")
    await user_repo.create("admin", admin_hash, "ADMIN")

    yield {
        "repo": repo,
        "historian": historian,
        "user_repo": user_repo,
        "alarm_repo": alarm_repo,
        "audit_repo": audit_repo,
        "loop_manager": loop_manager,
        "settings": settings,
        "bus": bus,
    }
    loop_manager.stop_all()
    bus.stop()
    await user_repo.close()
    await repo.db.close()


@pytest.fixture
async def monitor_app(monitor_deps):
    return create_app(
        repo=monitor_deps["repo"],
        historian=monitor_deps["historian"],
        user_repo=monitor_deps["user_repo"],
        loop_manager=monitor_deps["loop_manager"],
        settings=monitor_deps["settings"],
        alarm_repo=monitor_deps["alarm_repo"],
        audit_repo=monitor_deps["audit_repo"],
    )


@pytest.fixture
async def monitor_client(monitor_app):
    transport = ASGITransport(app=monitor_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
def operator_headers(monitor_deps) -> dict[str, str]:
    token = create_access_token(
        user_id=2, username="operator", role="OPERATOR",
        secret=monitor_deps["settings"].jwt_secret,
    )
    return {"Authorization": f"Bearer {token}"}


class TestMonitorModeGating:
    """Verify SP, mode, and output commands are blocked in monitor mode."""

    @pytest.mark.asyncio
    async def test_setpoint_blocked_in_monitor(
        self, monitor_client: AsyncClient, operator_headers: dict[str, str],
    ) -> None:
        resp = await monitor_client.post(
            "/commands/setpoint",
            json={"controller_id": 1, "value": 50.0},
            headers=operator_headers,
        )
        assert resp.status_code == 409
        assert "monitor mode" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_mode_blocked_in_monitor(
        self, monitor_client: AsyncClient, operator_headers: dict[str, str],
    ) -> None:
        resp = await monitor_client.post(
            "/commands/mode",
            json={"controller_id": 1, "mode": "MAN"},
            headers=operator_headers,
        )
        assert resp.status_code == 409
        assert "monitor mode" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_output_blocked_in_monitor(
        self, monitor_client: AsyncClient, operator_headers: dict[str, str],
    ) -> None:
        resp = await monitor_client.post(
            "/commands/output",
            json={"controller_id": 1, "value": 50.0},
            headers=operator_headers,
        )
        assert resp.status_code == 409
        assert "monitor mode" in resp.json()["detail"].lower()


class TestApplyTuning:
    """Tests for POST /commands/apply-tuning/{controller_id}."""

    @pytest.fixture
    async def execute_deps(self, tmp_path):
        """Deps with execution_mode=execute for apply-tuning tests."""
        import uuid

        db_path = tmp_path / "test.spid"
        repo = SQLiteRepository(db_path)
        await repo.initialize()
        historian = SQLiteHistorian(repo.db)
        user_db_path = tmp_path / "users.db"
        user_repo = UserRepository(user_db_path)
        await user_repo.initialize()
        alarm_repo = AlarmRepository(repo.db)
        audit_repo = AuditRepository(repo.db)
        bus = EventBus(url_prefix=f"inproc://test_{uuid.uuid4().hex[:8]}")
        bus.start()
        loop_manager = LoopManager(bus=bus, execution_mode="execute")
        settings = CoreSettings(
            jwt_secret="test-secret-key-minimum-32-bytes!",
            execution_mode="execute",
        )  # type: ignore[call-arg]

        admin_hash = hash_password("admin")
        await user_repo.create("admin", admin_hash, "ADMIN")

        yield {
            "repo": repo,
            "historian": historian,
            "user_repo": user_repo,
            "alarm_repo": alarm_repo,
            "audit_repo": audit_repo,
            "loop_manager": loop_manager,
            "settings": settings,
            "bus": bus,
        }
        loop_manager.stop_all()
        bus.stop()
        await user_repo.close()
        await repo.db.close()

    async def _register_controller(self, deps: dict) -> int:
        """Save controller and register loop context."""
        repo = deps["repo"]
        ctrl = Controller(
            id=0, name="TIC-201",
            pid_params=PIDParams(gain=1.0, reset=10.0, rate=0.5),
        )
        saved = await repo.save(ctrl)
        lm = deps["loop_manager"]
        bus = deps["bus"]
        engine = PIDEngine()
        mode_manager = ModeManager()
        pid_worker = PIDWorker(
            bus=bus, controller=saved, engine=engine, mode_manager=mode_manager,
        )
        ctx = LoopContext(
            controller=saved, pid_worker=pid_worker,
            engine=engine, mode_manager=mode_manager,
        )
        lm._loops[saved.id] = ctx
        return saved.id

    @pytest.mark.asyncio
    async def test_no_pending_recommendation_returns_404(self, execute_deps) -> None:
        app = create_app(
            repo=execute_deps["repo"],
            historian=execute_deps["historian"],
            user_repo=execute_deps["user_repo"],
            loop_manager=execute_deps["loop_manager"],
            settings=execute_deps["settings"],
            alarm_repo=execute_deps["alarm_repo"],
            audit_repo=execute_deps["audit_repo"],
        )
        headers = {
            "Authorization": "Bearer " + create_access_token(
                user_id=1, username="admin", role="ADMIN",
                secret=execute_deps["settings"].jwt_secret,
            ),
        }
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/commands/apply-tuning/1", headers=headers,
            )
        assert resp.status_code == 404
        assert "No pending tuning recommendation" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_external_pid_not_auto_returns_409(self, execute_deps) -> None:
        cid = await self._register_controller(execute_deps)

        mock_opcua = MagicMock()
        mock_opcua.read_actual_mode.return_value = ControllerMode.MAN

        app = create_app(
            repo=execute_deps["repo"],
            historian=execute_deps["historian"],
            user_repo=execute_deps["user_repo"],
            loop_manager=execute_deps["loop_manager"],
            settings=execute_deps["settings"],
            alarm_repo=execute_deps["alarm_repo"],
            audit_repo=execute_deps["audit_repo"],
            opcua_adapter=mock_opcua,
        )
        app.state.tuning_recommendations = {cid: _FakeRec()}

        headers = {
            "Authorization": "Bearer " + create_access_token(
                user_id=1, username="admin", role="ADMIN",
                secret=execute_deps["settings"].jwt_secret,
            ),
        }
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                f"/commands/apply-tuning/{cid}", headers=headers,
            )
        assert resp.status_code == 409
        assert "MAN" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_apply_tuning_success(self, execute_deps) -> None:
        cid = await self._register_controller(execute_deps)

        mock_opcua = MagicMock()
        mock_opcua.read_actual_mode.return_value = ControllerMode.AUTO

        app = create_app(
            repo=execute_deps["repo"],
            historian=execute_deps["historian"],
            user_repo=execute_deps["user_repo"],
            loop_manager=execute_deps["loop_manager"],
            settings=execute_deps["settings"],
            alarm_repo=execute_deps["alarm_repo"],
            audit_repo=execute_deps["audit_repo"],
            opcua_adapter=mock_opcua,
        )
        app.state.tuning_recommendations = {cid: _FakeRec()}

        headers = {
            "Authorization": "Bearer " + create_access_token(
                user_id=1, username="admin", role="ADMIN",
                secret=execute_deps["settings"].jwt_secret,
            ),
        }
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                f"/commands/apply-tuning/{cid}", headers=headers,
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["controller_id"] == cid
        assert "applied_kp" in data
        assert "applied_ti" in data
        assert "applied_td" in data
        assert "clamped" in data

        # Verify OPC-UA write was called
        mock_opcua.write_pid_params.assert_called_once()
