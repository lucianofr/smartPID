"""Root test configuration for the Smart PID platform."""
from __future__ import annotations

import uuid

import httpx
import pytest

from smart_pid_core.adapters.inbound.api.app import create_app
from smart_pid_core.adapters.inbound.api.auth import create_access_token, hash_password
from smart_pid_core.adapters.outbound.alarm_repo import AlarmRepository
from smart_pid_core.adapters.outbound.audit_repo import AuditRepository
from smart_pid_core.adapters.outbound.historian import SQLiteHistorian
from smart_pid_core.adapters.outbound.sqlite_repo import SQLiteRepository
from smart_pid_core.adapters.outbound.user_repo import UserRepository
from smart_pid_core.application.event_bus import EventBus
from smart_pid_core.application.loop_manager import LoopManager
from smart_pid_core.config import CoreSettings
from smart_pid_domain.models.controller import PIDParams


@pytest.fixture
def sample_pid_params() -> PIDParams:
    return PIDParams(gain=1.5, reset=10.0, rate=2.0, alpha=0.125, deadband=0.0)


@pytest.fixture
async def api_deps(tmp_path):
    """Create all Phase 2 dependencies for API testing."""
    db_path = tmp_path / "test.spid"
    repo = SQLiteRepository(db_path)
    await repo.initialize()
    historian = SQLiteHistorian(repo.db)
    user_repo = UserRepository(repo.db)
    alarm_repo = AlarmRepository(repo.db)
    audit_repo = AuditRepository(repo.db)
    bus = EventBus(url_prefix=f"inproc://test_{uuid.uuid4().hex[:8]}")
    bus.start()
    loop_manager = LoopManager(bus=bus)
    settings = CoreSettings(jwt_secret="test-secret-key-minimum-32-bytes!")  # type: ignore[call-arg]

    # Seed admin user
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
    await repo.db.close()


@pytest.fixture
async def app(api_deps):
    """Create FastAPI app with all dependencies."""
    return create_app(
        repo=api_deps["repo"],
        historian=api_deps["historian"],
        user_repo=api_deps["user_repo"],
        loop_manager=api_deps["loop_manager"],
        settings=api_deps["settings"],
        alarm_repo=api_deps["alarm_repo"],
        audit_repo=api_deps["audit_repo"],
    )


@pytest.fixture
async def client(app):
    """httpx AsyncClient with ASGI transport."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
def admin_headers(api_deps) -> dict[str, str]:
    """Pre-authenticated admin JWT headers."""
    token = create_access_token(
        user_id=1, username="admin", role="ADMIN",
        secret=api_deps["settings"].jwt_secret,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def user_headers(api_deps) -> dict[str, str]:
    """Pre-authenticated operator JWT headers."""
    token = create_access_token(
        user_id=2, username="operator", role="OPERATOR",
        secret=api_deps["settings"].jwt_secret,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def sim_api_deps(tmp_path):
    """Create all dependencies for API testing with simulator enabled."""
    db_path = tmp_path / "test.spid"
    repo = SQLiteRepository(db_path)
    await repo.initialize()
    historian = SQLiteHistorian(repo.db)
    user_repo = UserRepository(repo.db)
    bus = EventBus(url_prefix=f"inproc://test_{uuid.uuid4().hex[:8]}")
    bus.start()
    loop_manager = LoopManager(bus=bus)
    settings = CoreSettings(
        jwt_secret="test-secret-key-minimum-32-bytes!",
        simulator_enabled=True,
        simulator_interval_ms=50,
    )  # type: ignore[call-arg]

    admin_hash = hash_password("admin")
    await user_repo.create("admin", admin_hash, "ADMIN")

    from smart_pid_core.adapters.inbound.simulator_adapter import SimulatorAdapter
    simulator_adapter = SimulatorAdapter(settings=settings)
    simulator_adapter.register_controller(1)

    yield {
        "repo": repo,
        "historian": historian,
        "user_repo": user_repo,
        "loop_manager": loop_manager,
        "settings": settings,
        "bus": bus,
        "simulator_adapter": simulator_adapter,
    }
    simulator_adapter.stop()
    loop_manager.stop_all()
    bus.stop()
    await repo.db.close()


@pytest.fixture
async def app_with_simulator(sim_api_deps):
    """Create FastAPI app with simulator enabled."""
    return create_app(
        repo=sim_api_deps["repo"],
        historian=sim_api_deps["historian"],
        user_repo=sim_api_deps["user_repo"],
        loop_manager=sim_api_deps["loop_manager"],
        settings=sim_api_deps["settings"],
        simulator_adapter=sim_api_deps["simulator_adapter"],
    )


@pytest.fixture
async def client_with_simulator(app_with_simulator):
    """httpx AsyncClient with simulator-enabled ASGI transport."""
    transport = httpx.ASGITransport(app=app_with_simulator)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
