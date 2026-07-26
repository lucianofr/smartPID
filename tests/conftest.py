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
from smart_pid_core.adapters.outbound.system_event_repo import SystemEventRepository
from smart_pid_core.adapters.outbound.user_repo import UserRepository
from smart_pid_core.application.event_bus import EventBus
from smart_pid_core.application.loop_manager import LoopManager
from smart_pid_core.application.project_service import ProjectService
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
    historian = SQLiteHistorian(repo.session_factory)
    user_db_path = tmp_path / "users.db"
    user_repo = UserRepository(user_db_path)
    await user_repo.initialize()
    alarm_repo = AlarmRepository(repo.session_factory)
    audit_repo = AuditRepository(repo.session_factory)
    system_event_repo = SystemEventRepository(repo.session_factory)
    bus = EventBus(url_prefix=f"inproc://test_{uuid.uuid4().hex[:8]}")
    bus.start()
    loop_manager = LoopManager(bus=bus)
    settings = CoreSettings(
        jwt_secret="test-secret-key-minimum-32-bytes!",
        execution_mode="execute",
        max_upload_bytes=1 * 1024 * 1024,  # 1 MB cap for upload-size tests
    )  # type: ignore[call-arg]

    # Seed admin user
    admin_hash = hash_password("admin")
    await user_repo.create("admin", admin_hash, "admin")

    projects_dir = tmp_path / "projects"
    projects_dir.mkdir()
    project_service = ProjectService(
        repo=repo, loop_manager=loop_manager,
        projects_dir=projects_dir,
    )

    yield {
        "repo": repo,
        "historian": historian,
        "user_repo": user_repo,
        "alarm_repo": alarm_repo,
        "audit_repo": audit_repo,
        "system_event_repo": system_event_repo,
        "loop_manager": loop_manager,
        "project_service": project_service,
        "projects_dir": projects_dir,
        "settings": settings,
        "bus": bus,
    }
    loop_manager.stop_all()
    bus.stop()
    await user_repo.close()
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
        project_service=api_deps["project_service"],
        alarm_repo=api_deps["alarm_repo"],
        audit_repo=api_deps["audit_repo"],
        system_event_repo=api_deps["system_event_repo"],
        event_bus=api_deps["bus"],
    )


@pytest.fixture
async def client(app):
    """httpx AsyncClient with ASGI transport.

    base_url host is 127.0.0.1 so requests satisfy TrustedHostMiddleware
    (default trusted_hosts = 127.0.0.1, localhost).
    """
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1") as c:
        yield c


@pytest.fixture
def admin_headers(api_deps) -> dict[str, str]:
    """Pre-authenticated admin JWT headers."""
    token = create_access_token(
        user_id=1, username="admin", role="admin",
        secret=api_deps["settings"].jwt_secret,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def user_headers(api_deps) -> dict[str, str]:
    """Pre-authenticated user-role JWT headers."""
    token = create_access_token(
        user_id=2, username="operator", role="user",
        secret=api_deps["settings"].jwt_secret,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def system_event_repo(api_deps):
    return api_deps["system_event_repo"]


@pytest.fixture
async def alarm_repo(api_deps):
    return api_deps["alarm_repo"]


@pytest.fixture
def supervisor_headers(api_deps) -> dict[str, str]:
    """TEMPORARY alias of admin_headers (distinct identity, user_id 3).

    The SUPERVISOR tier no longer exists (spec §9.4 maps it to admin).
    Removed in the call-site-switch task once consumers migrate to
    admin_headers.
    """
    token = create_access_token(
        user_id=3, username="supervisor", role="admin",
        secret=api_deps["settings"].jwt_secret,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def sim_api_deps(tmp_path):
    """Create all dependencies for API testing with simulator enabled."""
    db_path = tmp_path / "test.spid"
    repo = SQLiteRepository(db_path)
    await repo.initialize()
    historian = SQLiteHistorian(repo.session_factory)
    user_db_path = tmp_path / "users.db"
    user_repo = UserRepository(user_db_path)
    await user_repo.initialize()
    bus = EventBus(url_prefix=f"inproc://test_{uuid.uuid4().hex[:8]}")
    bus.start()
    loop_manager = LoopManager(bus=bus)
    settings = CoreSettings(
        jwt_secret="test-secret-key-minimum-32-bytes!",
        simulator_enabled=True,
        simulator_interval_ms=50,
    )  # type: ignore[call-arg]

    admin_hash = hash_password("admin")
    await user_repo.create("admin", admin_hash, "admin")

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
    await user_repo.close()
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
    """httpx AsyncClient with simulator-enabled ASGI transport.

    base_url host is 127.0.0.1 to satisfy TrustedHostMiddleware.
    """
    transport = httpx.ASGITransport(app=app_with_simulator)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://127.0.0.1"
    ) as c:
        yield c
