# Phase 3a: PySide6 HMI Desktop — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the PySide6 desktop HMI client that displays real-time telemetry, allows process control, and visualizes alarm states — consuming data from the Smart PID backend via ZMQ SUB + REST.

**Architecture:** Pure network client. ZMQ SUB daemon thread receives telemetry → SimpleQueue → QTimer (33ms) drains to typed Qt Signals → widgets update. REST calls via sync httpx.Client for commands and login. Mock service layer for offline dev/test.

**Tech Stack:** PySide6 >=6.7, pyqtgraph >=0.13, httpx >=0.27, pyzmq >=26, msgpack >=1.0, pydantic-settings >=2.0, pytest-qt

**Spec:** `docs/superpowers/specs/2026-04-03-phase3a-hmi-desktop-design.md`

**Deviation from spec:** API client uses sync `httpx.Client` (not async) for PySide6 compatibility. Avoids mixing asyncio with Qt event loop. Protocol methods are sync. API calls from UI run in background threads.

**Backend ZMQ format:** Multipart `[topic_bytes, msgpack_payload]`. Topics: `STATUS.{controller_id}` (telemetry: pv, sp, co, integral_val, timestamp, status), `ACTION.CTRL.{controller_id}` (control action: co, integral_val, delta_cv, timestamp). The HMI subscribes to `STATUS.` prefix for telemetry frames.

---

## File Structure

```
packages/smart_pid_hmi/
├── pyproject.toml                           # Updated with all dependencies
├── src/smart_pid_hmi/
│   ├── __init__.py                          # Existing (version 0.1.0)
│   ├── main.py                              # QApplication + MainWindow bootstrap
│   ├── config.py                            # HMISettings (pydantic-settings, SPID_HMI_ prefix)
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── ports.py                         # TelemetrySourcePort + APIClientPort Protocols
│   │   ├── session.py                       # JWT token storage, login state
│   │   ├── api_client.py                    # httpx sync REST client
│   │   ├── telemetry_sub.py                 # ZMQ SUB daemon thread → SimpleQueue
│   │   └── mock_service.py                  # MockTelemetrySource + MockAPIClient
│   │
│   ├── bus_bridge.py                        # QTimer 33ms drains SimpleQueue → Qt Signals
│   │
│   ├── themes/
│   │   ├── __init__.py
│   │   ├── base.py                          # ThemeBase(Protocol)
│   │   └── isa101.py                        # ISA-101 concrete theme (QSS)
│   │
│   ├── pages/
│   │   ├── __init__.py
│   │   ├── connection_page.py               # Login + server URL
│   │   └── dashboard_page.py                # Cards grid + trend/faceplate + alarm bar
│   │
│   └── widgets/
│       ├── __init__.py
│       ├── analog_bar.py                    # Horizontal bar PV/SP/CO
│       ├── controller_card.py               # Summary card per loop
│       ├── faceplate.py                     # Detailed operation panel
│       ├── trend_chart.py                   # pyqtgraph dual Y-axis
│       └── alarm_bar.py                     # Footer with last 10 alarms
│
├── tests/hmi/
│   ├── conftest.py                          # Shared fixtures (theme, bus_bridge, qtbot)
│   ├── test_config.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── test_session.py
│   │   ├── test_api_client.py
│   │   ├── test_telemetry_sub.py
│   │   └── test_mock_service.py
│   ├── test_bus_bridge.py
│   ├── themes/
│   │   ├── __init__.py
│   │   └── test_isa101.py
│   ├── widgets/
│   │   ├── __init__.py
│   │   ├── test_analog_bar.py
│   │   ├── test_controller_card.py
│   │   ├── test_faceplate.py
│   │   ├── test_trend_chart.py
│   │   └── test_alarm_bar.py
│   ├── pages/
│   │   ├── __init__.py
│   │   ├── test_connection_page.py
│   │   └── test_dashboard_page.py
│   └── test_integration.py

packages/smart_pid_domain/
└── src/smart_pid_domain/
    └── models/
        └── alarm.py                         # AlarmEvent frozen dataclass (new)
```

---

## Task 1: Package Setup — pyproject.toml + config.py

**Files:**
- Modify: `packages/smart_pid_hmi/pyproject.toml`
- Create: `packages/smart_pid_hmi/src/smart_pid_hmi/config.py`
- Create: `tests/hmi/__init__.py`
- Create: `tests/hmi/test_config.py`

- [ ] **Step 1: Write test for HMISettings defaults**

```python
# tests/hmi/test_config.py
"""Tests for HMI configuration."""
from smart_pid_hmi.config import HMISettings


def test_default_settings():
    settings = HMISettings()
    assert settings.server_url == "http://localhost:8000"
    assert settings.zmq_url == "tcp://localhost:5555"
    assert settings.theme == "isa101"
    assert settings.mock_mode is False
    assert settings.refresh_ms == 33


def test_override_via_env(monkeypatch):
    monkeypatch.setenv("SPID_HMI_SERVER_URL", "http://10.0.0.1:9000")
    monkeypatch.setenv("SPID_HMI_MOCK_MODE", "true")
    settings = HMISettings()
    assert settings.server_url == "http://10.0.0.1:9000"
    assert settings.mock_mode is True
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/hmi/test_config.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'smart_pid_hmi.config'`

- [ ] **Step 3: Update pyproject.toml with dependencies**

```toml
# packages/smart_pid_hmi/pyproject.toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "smart-pid-hmi"
version = "0.1.0"
description = "Smart PID — Desktop HMI Client"
requires-python = ">=3.13"
dependencies = [
    "smart-pid-domain",
    "PySide6>=6.7",
    "pyqtgraph>=0.13",
    "httpx>=0.27",
    "pyzmq>=26",
    "msgpack>=1.0",
    "pydantic-settings>=2.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-qt>=4.4",
    "mypy>=1.10",
    "ruff>=0.4",
]

[tool.hatch.build.targets.wheel]
packages = ["src/smart_pid_hmi"]
```

- [ ] **Step 4: Implement config.py**

```python
# packages/smart_pid_hmi/src/smart_pid_hmi/config.py
"""HMI configuration via pydantic-settings."""
from __future__ import annotations

from pydantic_settings import BaseSettings


class HMISettings(BaseSettings):
    """Desktop HMI client settings, loaded from env vars with SPID_HMI_ prefix."""

    model_config = {"env_prefix": "SPID_HMI_"}

    server_url: str = "http://localhost:8000"
    zmq_url: str = "tcp://localhost:5555"
    theme: str = "isa101"
    mock_mode: bool = False
    refresh_ms: int = 33
```

- [ ] **Step 5: Run uv sync and verify tests pass**

```bash
uv sync --all-packages && uv run pytest tests/hmi/test_config.py -v
```
Expected: 2 PASSED

- [ ] **Step 6: Commit**

```bash
git add packages/smart_pid_hmi/pyproject.toml \
       packages/smart_pid_hmi/src/smart_pid_hmi/config.py \
       tests/hmi/__init__.py tests/hmi/test_config.py
git commit -m "feat(hmi): add HMISettings config with SPID_HMI_ prefix"
```

---

## Task 2: AlarmEvent Domain Model

**Files:**
- Create: `packages/smart_pid_domain/src/smart_pid_domain/models/alarm.py`
- Modify: `packages/smart_pid_domain/src/smart_pid_domain/models/__init__.py` (if exists, add export)
- Create: `tests/hmi/test_alarm_event.py`

- [ ] **Step 1: Write test for AlarmEvent**

```python
# tests/hmi/test_alarm_event.py
"""Tests for AlarmEvent domain model."""
from datetime import datetime, timezone

from smart_pid_domain.enums import AlarmPriority, AlarmType
from smart_pid_domain.models.alarm import AlarmEvent


def test_alarm_event_creation():
    now = datetime.now(tz=timezone.utc)
    event = AlarmEvent(
        controller_id=1,
        controller_name="FIC-101",
        alarm_type=AlarmType.HIHI,
        priority=AlarmPriority.CRITICAL,
        value=95.3,
        limit=90.0,
        timestamp=now,
    )
    assert event.controller_id == 1
    assert event.controller_name == "FIC-101"
    assert event.alarm_type == AlarmType.HIHI
    assert event.priority == AlarmPriority.CRITICAL
    assert event.value == 95.3
    assert event.limit == 90.0
    assert event.timestamp == now


def test_alarm_event_is_frozen():
    now = datetime.now(tz=timezone.utc)
    event = AlarmEvent(
        controller_id=1,
        controller_name="FIC-101",
        alarm_type=AlarmType.HI,
        priority=AlarmPriority.WARNING,
        value=85.0,
        limit=80.0,
        timestamp=now,
    )
    try:
        event.value = 99.0  # type: ignore[misc]
        raise AssertionError("Should be frozen")
    except AttributeError:
        pass
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/hmi/test_alarm_event.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'smart_pid_domain.models.alarm'`

- [ ] **Step 3: Implement AlarmEvent**

```python
# packages/smart_pid_domain/src/smart_pid_domain/models/alarm.py
"""Alarm event model."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from smart_pid_domain.enums import AlarmPriority, AlarmType

if TYPE_CHECKING:
    from datetime import datetime


@dataclass(frozen=True)
class AlarmEvent:
    """Immutable alarm event snapshot."""

    controller_id: int
    controller_name: str
    alarm_type: AlarmType
    priority: AlarmPriority
    value: float
    limit: float
    timestamp: datetime
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/hmi/test_alarm_event.py -v
```
Expected: 2 PASSED

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_domain/src/smart_pid_domain/models/alarm.py \
       tests/hmi/test_alarm_event.py
git commit -m "feat(domain): add AlarmEvent frozen dataclass"
```

---

## Task 3: Service Ports (Protocols)

**Files:**
- Create: `packages/smart_pid_hmi/src/smart_pid_hmi/services/__init__.py`
- Create: `packages/smart_pid_hmi/src/smart_pid_hmi/services/ports.py`

- [ ] **Step 1: Create services package and ports**

```python
# packages/smart_pid_hmi/src/smart_pid_hmi/services/__init__.py
"""HMI service layer."""
```

```python
# packages/smart_pid_hmi/src/smart_pid_hmi/services/ports.py
"""Service port protocols — contracts for API client and telemetry source."""
from __future__ import annotations

from queue import SimpleQueue
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from datetime import datetime

    from smart_pid_domain.dtos import (
        CommandResponse,
        ControllerResponse,
        HistoryResponse,
        TokenResponse,
    )


class TelemetrySourcePort(Protocol):
    """Contract for real-time telemetry data source."""

    def start(self) -> None: ...
    def stop(self) -> None: ...

    @property
    def queue(self) -> SimpleQueue: ...


class APIClientPort(Protocol):
    """Contract for REST API client (sync)."""

    def login(self, username: str, password: str) -> TokenResponse: ...
    def list_controllers(self) -> list[ControllerResponse]: ...
    def get_controller(self, controller_id: int) -> ControllerResponse: ...
    def set_setpoint(self, controller_id: int, value: float) -> CommandResponse: ...
    def set_mode(self, controller_id: int, mode: str) -> CommandResponse: ...
    def set_output(self, controller_id: int, value: float) -> CommandResponse: ...
    def get_history(
        self, controller_id: int, start: datetime, end: datetime
    ) -> HistoryResponse: ...
```

- [ ] **Step 2: Verify import works**

```bash
uv run python -c "from smart_pid_hmi.services.ports import TelemetrySourcePort, APIClientPort; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add packages/smart_pid_hmi/src/smart_pid_hmi/services/
git commit -m "feat(hmi): add service port protocols (TelemetrySourcePort, APIClientPort)"
```

---

## Task 4: Session Management

**Files:**
- Create: `packages/smart_pid_hmi/src/smart_pid_hmi/services/session.py`
- Create: `tests/hmi/services/__init__.py`
- Create: `tests/hmi/services/test_session.py`

- [ ] **Step 1: Write tests for Session**

```python
# tests/hmi/services/test_session.py
"""Tests for JWT session management."""
import base64
import json
import time

from smart_pid_hmi.services.session import Session


def _make_fake_token(username: str = "operator", exp_offset: int = 3600) -> str:
    """Create a fake JWT token (header.payload.signature) for testing."""
    header = base64.urlsafe_b64encode(b'{"alg":"HS256","typ":"JWT"}').rstrip(b"=").decode()
    payload_data = {
        "sub": "1",
        "username": username,
        "role": "operator",
        "exp": int(time.time()) + exp_offset,
    }
    payload = base64.urlsafe_b64encode(
        json.dumps(payload_data).encode()
    ).rstrip(b"=").decode()
    return f"{header}.{payload}.fakesig"


def test_initial_state():
    session = Session()
    assert session.is_authenticated is False
    assert session.token is None
    assert session.username is None


def test_store_token():
    session = Session()
    token = _make_fake_token("admin_user")
    session.store_token(token)
    assert session.is_authenticated is True
    assert session.token == token
    assert session.username == "admin_user"


def test_clear():
    session = Session()
    session.store_token(_make_fake_token())
    session.clear()
    assert session.is_authenticated is False
    assert session.token is None


def test_expired_token():
    session = Session()
    token = _make_fake_token(exp_offset=-10)  # already expired
    session.store_token(token)
    assert session.is_authenticated is False


def test_auth_header():
    session = Session()
    token = _make_fake_token()
    session.store_token(token)
    assert session.auth_header == {"Authorization": f"Bearer {token}"}


def test_auth_header_none_when_unauthenticated():
    session = Session()
    assert session.auth_header == {}
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/hmi/services/test_session.py -v
```
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement Session**

```python
# packages/smart_pid_hmi/src/smart_pid_hmi/services/session.py
"""JWT session management — stores token in memory, parses claims."""
from __future__ import annotations

import base64
import json
import time


class Session:
    """In-memory JWT session for the HMI client."""

    def __init__(self) -> None:
        self._token: str | None = None
        self._username: str | None = None
        self._exp: float = 0.0

    @property
    def is_authenticated(self) -> bool:
        return self._token is not None and time.time() < self._exp

    @property
    def token(self) -> str | None:
        if self.is_authenticated:
            return self._token
        return None

    @property
    def username(self) -> str | None:
        if self.is_authenticated:
            return self._username
        return None

    @property
    def auth_header(self) -> dict[str, str]:
        t = self.token
        if t is not None:
            return {"Authorization": f"Bearer {t}"}
        return {}

    def store_token(self, token: str) -> None:
        """Parse JWT payload (no verification — backend is trusted) and store."""
        try:
            payload_b64 = token.split(".")[1]
            # Add padding
            padding = 4 - len(payload_b64) % 4
            if padding != 4:
                payload_b64 += "=" * padding
            payload = json.loads(base64.urlsafe_b64decode(payload_b64))
            self._token = token
            self._username = payload.get("username")
            self._exp = float(payload.get("exp", 0))
        except (IndexError, json.JSONDecodeError, ValueError):
            self._token = None
            self._username = None
            self._exp = 0.0

    def clear(self) -> None:
        self._token = None
        self._username = None
        self._exp = 0.0
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/hmi/services/test_session.py -v
```
Expected: 6 PASSED

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_hmi/src/smart_pid_hmi/services/session.py \
       tests/hmi/services/__init__.py tests/hmi/services/test_session.py
git commit -m "feat(hmi): add Session JWT management (in-memory, no verify)"
```

---

## Task 5: API Client (httpx sync)

**Files:**
- Create: `packages/smart_pid_hmi/src/smart_pid_hmi/services/api_client.py`
- Create: `tests/hmi/services/test_api_client.py`

- [ ] **Step 1: Write tests for APIClient**

```python
# tests/hmi/services/test_api_client.py
"""Tests for REST API client using httpx mock transport."""
from unittest.mock import MagicMock

import httpx

from smart_pid_hmi.services.api_client import APIClient
from smart_pid_hmi.services.session import Session


def _mock_transport(status: int, json_body: dict | list) -> httpx.MockTransport:
    """Create a mock transport that always returns the given response."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json=json_body)
    return httpx.MockTransport(handler)


def test_login_success():
    transport = _mock_transport(200, {"access_token": "tok123", "token_type": "bearer"})
    session = Session()
    client = APIClient(base_url="http://test:8000", session=session, transport=transport)
    resp = client.login("admin", "pass")
    assert resp.access_token == "tok123"


def test_list_controllers():
    data = [
        {
            "id": 1, "name": "FIC-101", "description": "Flow",
            "mode": "AUTO", "pv": 45.0, "sp": 50.0, "co": 62.0,
        },
    ]
    transport = _mock_transport(200, data)
    session = Session()
    client = APIClient(base_url="http://test:8000", session=session, transport=transport)
    controllers = client.list_controllers()
    assert len(controllers) == 1
    assert controllers[0].name == "FIC-101"


def test_set_setpoint():
    transport = _mock_transport(200, {"ok": True, "controller_id": 1, "detail": "SP set to 55.0"})
    session = Session()
    client = APIClient(base_url="http://test:8000", session=session, transport=transport)
    resp = client.set_setpoint(1, 55.0)
    assert resp.ok is True


def test_set_mode():
    transport = _mock_transport(
        200, {"ok": True, "controller_id": 1, "detail": "Mode set to MAN"},
    )
    session = Session()
    client = APIClient(base_url="http://test:8000", session=session, transport=transport)
    resp = client.set_mode(1, "MAN")
    assert resp.ok is True


def test_set_output():
    transport = _mock_transport(
        200, {"ok": True, "controller_id": 1, "detail": "Output set to 30.0"},
    )
    session = Session()
    client = APIClient(base_url="http://test:8000", session=session, transport=transport)
    resp = client.set_output(1, 30.0)
    assert resp.ok is True


def test_get_history():
    from datetime import datetime, timezone

    data = {
        "controller_id": 1,
        "frames": [
            {"timestamp": "2026-04-03T10:00:00Z", "pv": 45.0, "sp": 50.0,
             "co": 62.0, "mode": "AUTO", "status": "GOOD"},
        ],
        "count": 1,
    }
    transport = _mock_transport(200, data)
    session = Session()
    client = APIClient(base_url="http://test:8000", session=session, transport=transport)
    resp = client.get_history(
        1, datetime(2026, 4, 3, 9, 0, tzinfo=timezone.utc),
        datetime(2026, 4, 3, 11, 0, tzinfo=timezone.utc),
    )
    assert resp.count == 1
    assert resp.frames[0].pv == 45.0


def test_auth_header_injected():
    """Verify that session auth header is sent with requests."""
    received_headers: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        received_headers.update(dict(request.headers))
        return httpx.Response(200, json=[])

    transport = httpx.MockTransport(handler)
    session = MagicMock()
    session.auth_header = {"Authorization": "Bearer mytoken"}
    client = APIClient(base_url="http://test:8000", session=session, transport=transport)
    client.list_controllers()
    assert "authorization" in received_headers
    assert received_headers["authorization"] == "Bearer mytoken"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/hmi/services/test_api_client.py -v
```
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement APIClient**

```python
# packages/smart_pid_hmi/src/smart_pid_hmi/services/api_client.py
"""Sync REST API client using httpx."""
from __future__ import annotations

from typing import TYPE_CHECKING

import httpx

from smart_pid_domain.dtos import (
    CommandResponse,
    ControllerResponse,
    HistoryResponse,
    TokenResponse,
)

if TYPE_CHECKING:
    from datetime import datetime

    from smart_pid_hmi.services.session import Session


class APIClient:
    """Synchronous REST client for the Smart PID backend."""

    def __init__(
        self,
        base_url: str,
        session: Session,
        transport: httpx.BaseTransport | None = None,
        timeout: float = 5.0,
    ) -> None:
        self._session = session
        kwargs: dict = {"base_url": base_url, "timeout": timeout}
        if transport is not None:
            kwargs["transport"] = transport
        self._http = httpx.Client(**kwargs)

    def _headers(self) -> dict[str, str]:
        return self._session.auth_header

    def login(self, username: str, password: str) -> TokenResponse:
        resp = self._http.post(
            "/auth/login",
            json={"username": username, "password": password},
        )
        resp.raise_for_status()
        return TokenResponse.model_validate(resp.json())

    def list_controllers(self) -> list[ControllerResponse]:
        resp = self._http.get("/controllers", headers=self._headers())
        resp.raise_for_status()
        return [ControllerResponse.model_validate(c) for c in resp.json()]

    def get_controller(self, controller_id: int) -> ControllerResponse:
        resp = self._http.get(f"/controllers/{controller_id}", headers=self._headers())
        resp.raise_for_status()
        return ControllerResponse.model_validate(resp.json())

    def set_setpoint(self, controller_id: int, value: float) -> CommandResponse:
        resp = self._http.post(
            "/commands/setpoint",
            json={"controller_id": controller_id, "value": value},
            headers=self._headers(),
        )
        resp.raise_for_status()
        return CommandResponse.model_validate(resp.json())

    def set_mode(self, controller_id: int, mode: str) -> CommandResponse:
        resp = self._http.post(
            "/commands/mode",
            json={"controller_id": controller_id, "mode": mode},
            headers=self._headers(),
        )
        resp.raise_for_status()
        return CommandResponse.model_validate(resp.json())

    def set_output(self, controller_id: int, value: float) -> CommandResponse:
        resp = self._http.post(
            "/commands/output",
            json={"controller_id": controller_id, "value": value},
            headers=self._headers(),
        )
        resp.raise_for_status()
        return CommandResponse.model_validate(resp.json())

    def get_history(
        self, controller_id: int, start: datetime, end: datetime
    ) -> HistoryResponse:
        resp = self._http.get(
            f"/history/{controller_id}",
            params={"start": start.isoformat(), "end": end.isoformat()},
            headers=self._headers(),
        )
        resp.raise_for_status()
        return HistoryResponse.model_validate(resp.json())

    def close(self) -> None:
        self._http.close()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/hmi/services/test_api_client.py -v
```
Expected: 7 PASSED

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_hmi/src/smart_pid_hmi/services/api_client.py \
       tests/hmi/services/test_api_client.py
git commit -m "feat(hmi): add sync APIClient (httpx) with full REST coverage"
```

---

## Task 6: Telemetry Subscriber (ZMQ SUB Thread)

**Files:**
- Create: `packages/smart_pid_hmi/src/smart_pid_hmi/services/telemetry_sub.py`
- Create: `tests/hmi/services/test_telemetry_sub.py`

- [ ] **Step 1: Write tests for TelemetrySub**

```python
# tests/hmi/services/test_telemetry_sub.py
"""Tests for ZMQ SUB telemetry subscriber thread."""
import time

import msgpack
import zmq

from smart_pid_hmi.services.telemetry_sub import TelemetrySub


def test_receives_telemetry_frame():
    """Start a real ZMQ PUB, send a frame, verify subscriber enqueues it."""
    ctx = zmq.Context()
    pub = ctx.socket(zmq.PUB)
    pub.bind("tcp://127.0.0.1:15555")

    try:
        sub = TelemetrySub(zmq_url="tcp://127.0.0.1:15555")
        sub.start()
        time.sleep(0.3)  # let SUB connect and subscribe

        frame_data = {
            "controller_id": 1, "pv": 45.0, "sp": 50.0,
            "co": 62.0, "integral_val": 0.5,
            "timestamp": "2026-04-03T10:00:00", "status": "GOOD",
        }
        topic = b"STATUS.1"
        pub.send_multipart([topic, msgpack.packb(frame_data)])
        time.sleep(0.2)

        assert not sub.queue.empty()
        msg_topic, msg_data = sub.queue.get_nowait()
        assert msg_topic == "STATUS.1"
        assert msg_data["pv"] == 45.0
        assert msg_data["controller_id"] == 1

        sub.stop()
    finally:
        pub.close()
        ctx.term()


def test_stop_cleanly():
    sub = TelemetrySub(zmq_url="tcp://127.0.0.1:15556")
    sub.start()
    time.sleep(0.1)
    sub.stop()
    assert not sub._thread.is_alive()


def test_queue_property():
    sub = TelemetrySub(zmq_url="tcp://127.0.0.1:15557")
    assert sub.queue is not None
    assert sub.queue.empty()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/hmi/services/test_telemetry_sub.py -v
```
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement TelemetrySub**

```python
# packages/smart_pid_hmi/src/smart_pid_hmi/services/telemetry_sub.py
"""ZMQ SUB daemon thread — receives telemetry and enqueues into SimpleQueue."""
from __future__ import annotations

import threading
from queue import SimpleQueue

import msgpack
import zmq


# Topics to subscribe to
_SUBSCRIBE_TOPICS = [b"STATUS.", b"ACTION.CTRL."]


class TelemetrySub:
    """Background thread that receives ZMQ multipart [topic, msgpack_payload]."""

    def __init__(self, zmq_url: str = "tcp://localhost:5555") -> None:
        self._zmq_url = zmq_url
        self._queue: SimpleQueue = SimpleQueue()
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    @property
    def queue(self) -> SimpleQueue:
        return self._queue

    def start(self) -> None:
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self._thread.join(timeout=2.0)

    def _run(self) -> None:
        ctx = zmq.Context()
        socket = ctx.socket(zmq.SUB)
        socket.setsockopt(zmq.RCVTIMEO, 100)  # 100ms poll
        socket.setsockopt(zmq.LINGER, 0)

        for topic in _SUBSCRIBE_TOPICS:
            socket.subscribe(topic)

        socket.connect(self._zmq_url)

        try:
            while not self._stop_event.is_set():
                try:
                    parts = socket.recv_multipart()
                    if len(parts) == 2:
                        topic_str = parts[0].decode("utf-8", errors="replace")
                        data = msgpack.unpackb(parts[1], raw=False)
                        self._queue.put((topic_str, data))
                except zmq.Again:
                    continue
        finally:
            socket.close()
            ctx.term()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/hmi/services/test_telemetry_sub.py -v
```
Expected: 3 PASSED

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_hmi/src/smart_pid_hmi/services/telemetry_sub.py \
       tests/hmi/services/test_telemetry_sub.py
git commit -m "feat(hmi): add TelemetrySub ZMQ daemon thread with SimpleQueue"
```

---

## Task 7: Mock Service

**Files:**
- Create: `packages/smart_pid_hmi/src/smart_pid_hmi/services/mock_service.py`
- Create: `tests/hmi/services/test_mock_service.py`

- [ ] **Step 1: Write tests for MockTelemetrySource and MockAPIClient**

```python
# tests/hmi/services/test_mock_service.py
"""Tests for mock service implementations."""
import time

from smart_pid_hmi.services.mock_service import MockAPIClient, MockTelemetrySource


def test_mock_telemetry_generates_frames():
    source = MockTelemetrySource(interval_ms=50)
    source.start()
    time.sleep(0.3)
    source.stop()

    assert not source.queue.empty()
    topic, data = source.queue.get_nowait()
    assert topic.startswith("STATUS.")
    assert "pv" in data
    assert "sp" in data
    assert "co" in data
    assert "controller_id" in data


def test_mock_telemetry_three_controllers():
    source = MockTelemetrySource(interval_ms=50)
    source.start()
    time.sleep(0.5)
    source.stop()

    seen_ids: set[int] = set()
    while not source.queue.empty():
        _, data = source.queue.get_nowait()
        seen_ids.add(data["controller_id"])
    assert len(seen_ids) == 3


def test_mock_api_login():
    client = MockAPIClient()
    resp = client.login("admin", "pass")
    assert resp.access_token
    assert resp.token_type == "bearer"


def test_mock_api_list_controllers():
    client = MockAPIClient()
    controllers = client.list_controllers()
    assert len(controllers) == 3
    names = {c.name for c in controllers}
    assert "FIC-101" in names
    assert "LIC-201" in names
    assert "TIC-301" in names


def test_mock_api_set_setpoint():
    client = MockAPIClient()
    resp = client.set_setpoint(1, 55.0)
    assert resp.ok is True


def test_mock_api_set_mode():
    client = MockAPIClient()
    resp = client.set_mode(1, "MAN")
    assert resp.ok is True


def test_mock_api_set_output():
    client = MockAPIClient()
    resp = client.set_output(1, 30.0)
    assert resp.ok is True


def test_mock_api_get_history():
    from datetime import datetime, timezone

    client = MockAPIClient()
    resp = client.get_history(
        1,
        datetime(2026, 4, 3, 9, 0, tzinfo=timezone.utc),
        datetime(2026, 4, 3, 11, 0, tzinfo=timezone.utc),
    )
    assert resp.controller_id == 1
    assert resp.count >= 0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/hmi/services/test_mock_service.py -v
```
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement MockTelemetrySource and MockAPIClient**

```python
# packages/smart_pid_hmi/src/smart_pid_hmi/services/mock_service.py
"""Mock service implementations for offline dev/test."""
from __future__ import annotations

import math
import random
import threading
import time
from datetime import datetime, timezone
from queue import SimpleQueue
from typing import TYPE_CHECKING

from smart_pid_domain.dtos import (
    CommandResponse,
    ControllerResponse,
    HistoryResponse,
    TelemetryFrameDTO,
    TokenResponse,
)

if TYPE_CHECKING:
    pass

# Mock controller definitions
_MOCK_CONTROLLERS = [
    {"id": 1, "name": "FIC-101", "description": "Flow control", "sp": 50.0,
     "sp_hi_lim": 100.0, "sp_lo_lim": 0.0, "out_hi_lim": 100.0, "out_lo_lim": 0.0},
    {"id": 2, "name": "LIC-201", "description": "Level control", "sp": 65.0,
     "sp_hi_lim": 100.0, "sp_lo_lim": 0.0, "out_hi_lim": 100.0, "out_lo_lim": 0.0},
    {"id": 3, "name": "TIC-301", "description": "Temperature control", "sp": 180.0,
     "sp_hi_lim": 300.0, "sp_lo_lim": 0.0, "out_hi_lim": 100.0, "out_lo_lim": 0.0},
]


class MockTelemetrySource:
    """Generates synthetic telemetry frames at a configurable interval."""

    def __init__(self, interval_ms: int = 100) -> None:
        self._interval = interval_ms / 1000.0
        self._queue: SimpleQueue = SimpleQueue()
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._tick = 0

    @property
    def queue(self) -> SimpleQueue:
        return self._queue

    def start(self) -> None:
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self._thread.join(timeout=2.0)

    def _run(self) -> None:
        while not self._stop_event.is_set():
            for ctrl in _MOCK_CONTROLLERS:
                t = self._tick * self._interval
                sp = ctrl["sp"]
                pv = sp + 5.0 * math.sin(t * 0.5) + random.gauss(0, 0.5)
                co = max(0.0, min(100.0, 50.0 + 10.0 * math.sin(t * 0.3)))

                frame = {
                    "controller_id": ctrl["id"],
                    "pv": round(pv, 2),
                    "sp": round(sp, 2),
                    "co": round(co, 2),
                    "integral_val": 0.0,
                    "timestamp": datetime.now(tz=timezone.utc).isoformat(),
                    "status": "GOOD",
                }
                self._queue.put((f"STATUS.{ctrl['id']}", frame))
            self._tick += 1
            self._stop_event.wait(timeout=self._interval)


class MockAPIClient:
    """Mock REST client returning canned data. Same interface as APIClient."""

    def __init__(self) -> None:
        self._history: list[dict] = []

    def login(self, username: str, password: str) -> TokenResponse:
        # Fake JWT with long expiry
        import base64
        import json

        header = base64.urlsafe_b64encode(b'{"alg":"HS256"}').rstrip(b"=").decode()
        payload = base64.urlsafe_b64encode(json.dumps({
            "sub": "1", "username": username, "role": "operator",
            "exp": int(time.time()) + 86400,
        }).encode()).rstrip(b"=").decode()
        fake_token = f"{header}.{payload}.mocksig"
        return TokenResponse(access_token=fake_token)

    def list_controllers(self) -> list[ControllerResponse]:
        return [
            ControllerResponse(
                id=c["id"], name=c["name"], description=c["description"],
                mode="AUTO", pv=c["sp"], sp=c["sp"], co=50.0,
                sp_hi_lim=c["sp_hi_lim"], sp_lo_lim=c["sp_lo_lim"],
                out_hi_lim=c["out_hi_lim"], out_lo_lim=c["out_lo_lim"],
            )
            for c in _MOCK_CONTROLLERS
        ]

    def get_controller(self, controller_id: int) -> ControllerResponse:
        for c in _MOCK_CONTROLLERS:
            if c["id"] == controller_id:
                return ControllerResponse(
                    id=c["id"], name=c["name"], description=c["description"],
                    mode="AUTO", pv=c["sp"], sp=c["sp"], co=50.0,
                    sp_hi_lim=c["sp_hi_lim"], sp_lo_lim=c["sp_lo_lim"],
                    out_hi_lim=c["out_hi_lim"], out_lo_lim=c["out_lo_lim"],
                )
        return ControllerResponse(
            id=controller_id, name="UNKNOWN", description="",
            mode="OOS", pv=0.0, sp=0.0, co=0.0,
        )

    def set_setpoint(self, controller_id: int, value: float) -> CommandResponse:
        return CommandResponse(ok=True, controller_id=controller_id,
                               detail=f"SP set to {value}")

    def set_mode(self, controller_id: int, mode: str) -> CommandResponse:
        return CommandResponse(ok=True, controller_id=controller_id,
                               detail=f"Mode set to {mode}")

    def set_output(self, controller_id: int, value: float) -> CommandResponse:
        return CommandResponse(ok=True, controller_id=controller_id,
                               detail=f"Output set to {value}")

    def get_history(
        self, controller_id: int, start: datetime, end: datetime
    ) -> HistoryResponse:
        now = datetime.now(tz=timezone.utc)
        frames = [
            TelemetryFrameDTO(
                timestamp=now, pv=50.0, sp=50.0, co=50.0,
                mode="AUTO", status="GOOD",
            )
        ]
        return HistoryResponse(controller_id=controller_id, frames=frames, count=len(frames))
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/hmi/services/test_mock_service.py -v
```
Expected: 8 PASSED

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_hmi/src/smart_pid_hmi/services/mock_service.py \
       tests/hmi/services/test_mock_service.py
git commit -m "feat(hmi): add MockTelemetrySource + MockAPIClient for offline dev"
```

---

## Task 8: Bus Bridge (QTimer → Qt Signals)

**Files:**
- Create: `packages/smart_pid_hmi/src/smart_pid_hmi/bus_bridge.py`
- Create: `tests/hmi/conftest.py`
- Create: `tests/hmi/test_bus_bridge.py`

- [ ] **Step 1: Write conftest with shared fixtures**

```python
# tests/hmi/conftest.py
"""Shared fixtures for HMI tests."""
import pytest

from smart_pid_hmi.themes.isa101 import ISA101Theme


@pytest.fixture
def theme():
    return ISA101Theme()
```

- [ ] **Step 2: Write tests for BusBridge**

```python
# tests/hmi/test_bus_bridge.py
"""Tests for BusBridge — QTimer drains SimpleQueue → Qt signals."""
from queue import SimpleQueue

import pytest
from PySide6.QtCore import QCoreApplication

from smart_pid_hmi.bus_bridge import BusBridge


@pytest.fixture
def bridge(qtbot):
    q = SimpleQueue()
    b = BusBridge(queue=q, refresh_ms=10)
    yield b
    b.stop()


def test_emits_telemetry_signal(bridge, qtbot):
    frame = {
        "controller_id": 1, "pv": 45.0, "sp": 50.0,
        "co": 62.0, "integral_val": 0.5,
        "timestamp": "2026-04-03T10:00:00", "status": "GOOD",
    }
    bridge._queue.put(("STATUS.1", frame))
    bridge.start()

    with qtbot.waitSignal(bridge.telemetry_received, timeout=500) as sig:
        pass
    assert sig.args[0] == 1  # controller_id
    assert sig.args[1]["pv"] == 45.0


def test_batches_same_controller(bridge, qtbot):
    """Multiple frames for same controller in one tick → only last emitted."""
    for pv in [10.0, 20.0, 30.0]:
        frame = {
            "controller_id": 1, "pv": pv, "sp": 50.0,
            "co": 50.0, "integral_val": 0.0,
            "timestamp": "2026-04-03T10:00:00", "status": "GOOD",
        }
        bridge._queue.put(("STATUS.1", frame))

    received = []
    bridge.telemetry_received.connect(lambda cid, f: received.append(f["pv"]))
    bridge.start()
    qtbot.wait(100)

    # Should receive only the last value (30.0) for controller 1
    assert len(received) == 1
    assert received[0] == 30.0


def test_connection_lost_after_timeout(qtbot):
    q = SimpleQueue()
    b = BusBridge(queue=q, refresh_ms=10, heartbeat_timeout_s=0.1)
    b.start()
    # Put one frame to start heartbeat, then wait for timeout
    frame = {
        "controller_id": 1, "pv": 45.0, "sp": 50.0,
        "co": 62.0, "integral_val": 0.0,
        "timestamp": "2026-04-03T10:00:00", "status": "GOOD",
    }
    q.put(("STATUS.1", frame))
    qtbot.wait(50)

    with qtbot.waitSignal(b.connection_lost, timeout=1000):
        pass
    b.stop()


def test_latest_property(bridge, qtbot):
    frame = {
        "controller_id": 1, "pv": 45.0, "sp": 50.0,
        "co": 62.0, "integral_val": 0.5,
        "timestamp": "2026-04-03T10:00:00", "status": "GOOD",
    }
    bridge._queue.put(("STATUS.1", frame))
    bridge.start()
    qtbot.wait(100)

    latest = bridge.latest(1)
    assert latest is not None
    assert latest["pv"] == 45.0
```

- [ ] **Step 3: Run test to verify it fails**

```bash
uv run pytest tests/hmi/test_bus_bridge.py -v
```
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 4: Implement BusBridge**

```python
# packages/smart_pid_hmi/src/smart_pid_hmi/bus_bridge.py
"""Bus Bridge — QTimer on main thread drains SimpleQueue → typed Qt Signals."""
from __future__ import annotations

import time
from queue import Empty, SimpleQueue

from PySide6.QtCore import QObject, QTimer, Signal


class BusBridge(QObject):
    """Bridges network thread data into Qt signal/slot world."""

    telemetry_received = Signal(int, object)     # (controller_id, frame_dict)
    alarm_received = Signal(int, object)         # (controller_id, alarm_dict)
    system_state_changed = Signal(object)        # (state_dict)
    connection_lost = Signal()
    connection_restored = Signal()

    def __init__(
        self,
        queue: SimpleQueue,
        refresh_ms: int = 33,
        heartbeat_timeout_s: float = 5.0,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._queue = queue
        self._refresh_ms = refresh_ms
        self._heartbeat_timeout = heartbeat_timeout_s
        self._latest: dict[int, dict] = {}
        self._last_frame_time: float = 0.0
        self._connected = True
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._drain)

    def start(self) -> None:
        self._last_frame_time = time.monotonic()
        self._timer.start(self._refresh_ms)

    def stop(self) -> None:
        self._timer.stop()

    def latest(self, controller_id: int) -> dict | None:
        return self._latest.get(controller_id)

    def _drain(self) -> None:
        batch: dict[int, dict] = {}
        alarms: list[tuple[int, dict]] = []

        # Drain all available messages
        while True:
            try:
                topic, data = self._queue.get_nowait()
            except Empty:
                break

            if topic.startswith("STATUS."):
                cid = data.get("controller_id", 0)
                batch[cid] = data  # keep only latest per controller
                self._last_frame_time = time.monotonic()
            elif topic.startswith("EVENT.ALARM."):
                cid = data.get("controller_id", 0)
                alarms.append((cid, data))
                self._last_frame_time = time.monotonic()

        # Emit batched telemetry (one per controller)
        for cid, frame in batch.items():
            self._latest[cid] = frame
            self.telemetry_received.emit(cid, frame)

        # Emit all alarms (never drop)
        for cid, alarm in alarms:
            self.alarm_received.emit(cid, alarm)

        # Heartbeat check
        if self._last_frame_time > 0:
            elapsed = time.monotonic() - self._last_frame_time
            if elapsed > self._heartbeat_timeout and self._connected:
                self._connected = False
                self.connection_lost.emit()
            elif elapsed <= self._heartbeat_timeout and not self._connected:
                self._connected = True
                self.connection_restored.emit()
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/hmi/test_bus_bridge.py -v
```
Expected: 4 PASSED

- [ ] **Step 6: Commit**

```bash
git add packages/smart_pid_hmi/src/smart_pid_hmi/bus_bridge.py \
       tests/hmi/conftest.py tests/hmi/test_bus_bridge.py
git commit -m "feat(hmi): add BusBridge (QTimer 33ms → Qt signals with batching)"
```

---

## Task 9: Theme System (ThemeBase + ISA-101)

**Files:**
- Create: `packages/smart_pid_hmi/src/smart_pid_hmi/themes/__init__.py`
- Create: `packages/smart_pid_hmi/src/smart_pid_hmi/themes/base.py`
- Create: `packages/smart_pid_hmi/src/smart_pid_hmi/themes/isa101.py`
- Create: `tests/hmi/themes/__init__.py`
- Create: `tests/hmi/themes/test_isa101.py`

- [ ] **Step 1: Write tests for ISA-101 theme**

```python
# tests/hmi/themes/test_isa101.py
"""Tests for ISA-101 theme."""
import pytest

from smart_pid_hmi.themes.base import ThemeBase
from smart_pid_hmi.themes.isa101 import ISA101Theme


def test_isa101_implements_protocol():
    theme = ISA101Theme()
    # Structural check: all required attributes exist
    assert theme.name == "isa101"
    assert isinstance(theme.bg_primary, str)
    assert isinstance(theme.fg_primary, str)
    assert isinstance(theme.alarm_critical, str)
    assert isinstance(theme.alarm_warning, str)
    assert isinstance(theme.bar_pv, str)
    assert isinstance(theme.chart_pv, str)
    assert isinstance(theme.font_family, str)
    assert isinstance(theme.font_size_normal, int)


def test_isa101_color_values():
    theme = ISA101Theme()
    assert theme.bg_primary == "#808080"
    assert theme.alarm_critical == "#FF0000"
    assert theme.alarm_warning == "#FFCC00"


def test_isa101_stylesheet_not_empty():
    theme = ISA101Theme()
    qss = theme.stylesheet()
    assert len(qss) > 0
    assert "background" in qss.lower() or "background-color" in qss.lower()


def test_apply_no_crash(qtbot):
    """Verify apply() does not raise on a real QApplication."""
    from PySide6.QtWidgets import QApplication

    theme = ISA101Theme()
    app = QApplication.instance()
    assert app is not None
    theme.apply(app)
    # No crash = pass
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/hmi/themes/test_isa101.py -v
```
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement ThemeBase Protocol**

```python
# packages/smart_pid_hmi/src/smart_pid_hmi/themes/__init__.py
"""Theme system."""

# packages/smart_pid_hmi/src/smart_pid_hmi/themes/base.py
"""ThemeBase Protocol — contract for all themes."""
from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from PySide6.QtWidgets import QApplication


class ThemeBase(Protocol):
    """Protocol that all themes must satisfy."""

    name: str

    # Core palette
    bg_primary: str
    bg_secondary: str
    bg_widget: str
    fg_primary: str
    fg_secondary: str
    border: str

    # Semantic (alarms)
    alarm_critical: str
    alarm_warning: str
    alarm_text: str

    # Bars
    bar_pv: str
    bar_sp: str
    bar_co: str

    # Chart
    chart_pv: str
    chart_sp: str
    chart_co: str
    chart_grid: str
    chart_bg: str

    # Typography
    font_family: str
    font_size_normal: int
    font_size_label: int
    font_size_value: int
    font_size_title: int

    def stylesheet(self) -> str: ...
    def apply(self, app: QApplication) -> None: ...
```

- [ ] **Step 4: Implement ISA-101 theme**

```python
# packages/smart_pid_hmi/src/smart_pid_hmi/themes/isa101.py
"""ISA-101 concrete theme — gray-scale, color = alarm only."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PySide6.QtWidgets import QApplication


class ISA101Theme:
    """ISA-101 HMI theme: 100% flat, gray-scale, color only for alarms."""

    name = "isa101"

    # Core palette
    bg_primary = "#808080"
    bg_secondary = "#999999"
    bg_widget = "#B0B0B0"
    fg_primary = "#1A1A1A"
    fg_secondary = "#4D4D4D"
    border = "#666666"

    # Semantic (alarms)
    alarm_critical = "#FF0000"
    alarm_warning = "#FFCC00"
    alarm_text = "#FFFFFF"

    # Bars
    bar_pv = "#404040"
    bar_sp = "#606060"
    bar_co = "#505050"

    # Chart
    chart_pv = "#333333"
    chart_sp = "#666666"
    chart_co = "#505050"
    chart_grid = "#999999"
    chart_bg = "#B0B0B0"

    # Typography
    font_family = "Segoe UI"
    font_size_normal = 12
    font_size_label = 10
    font_size_value = 14
    font_size_title = 16

    def stylesheet(self) -> str:
        return f"""
        QMainWindow, QWidget {{
            background-color: {self.bg_primary};
            color: {self.fg_primary};
            font-family: "{self.font_family}", "Arial", sans-serif;
            font-size: {self.font_size_normal}px;
        }}
        QLabel {{
            color: {self.fg_primary};
            background: transparent;
        }}
        QPushButton {{
            background-color: {self.bg_widget};
            color: {self.fg_primary};
            border: 1px solid {self.border};
            padding: 6px 16px;
            font-size: {self.font_size_normal}px;
        }}
        QPushButton:hover {{
            background-color: {self.bg_secondary};
        }}
        QPushButton:pressed {{
            background-color: {self.border};
        }}
        QLineEdit {{
            background-color: {self.bg_widget};
            color: {self.fg_primary};
            border: 1px solid {self.border};
            padding: 4px 8px;
            font-size: {self.font_size_normal}px;
        }}
        QComboBox {{
            background-color: {self.bg_widget};
            color: {self.fg_primary};
            border: 1px solid {self.border};
            padding: 4px 8px;
        }}
        QScrollArea {{
            border: none;
            background: transparent;
        }}
        """

    def apply(self, app: QApplication) -> None:
        app.setStyleSheet(self.stylesheet())
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/hmi/themes/test_isa101.py -v
```
Expected: 4 PASSED

- [ ] **Step 6: Commit**

```bash
git add packages/smart_pid_hmi/src/smart_pid_hmi/themes/ \
       tests/hmi/themes/
git commit -m "feat(hmi): add ThemeBase protocol + ISA-101 theme (QSS)"
```

---

## Task 10: AnalogBarWidget

**Files:**
- Create: `packages/smart_pid_hmi/src/smart_pid_hmi/widgets/__init__.py`
- Create: `packages/smart_pid_hmi/src/smart_pid_hmi/widgets/analog_bar.py`
- Create: `tests/hmi/widgets/__init__.py`
- Create: `tests/hmi/widgets/test_analog_bar.py`

- [ ] **Step 1: Write tests for AnalogBarWidget**

```python
# tests/hmi/widgets/test_analog_bar.py
"""Tests for AnalogBarWidget."""
import pytest

from smart_pid_hmi.themes.isa101 import ISA101Theme
from smart_pid_hmi.widgets.analog_bar import AnalogBarWidget


@pytest.fixture
def theme():
    return ISA101Theme()


def test_creation(qtbot, theme):
    bar = AnalogBarWidget(label="PV", unit="°C", min_val=0.0, max_val=100.0, theme=theme)
    qtbot.addWidget(bar)
    assert bar.value == 0.0
    assert bar.label == "PV"


def test_set_value(qtbot, theme):
    bar = AnalogBarWidget(label="PV", unit="°C", min_val=0.0, max_val=100.0, theme=theme)
    qtbot.addWidget(bar)
    bar.set_value(45.3)
    assert bar.value == 45.3


def test_clamp_value(qtbot, theme):
    bar = AnalogBarWidget(label="PV", unit="°C", min_val=0.0, max_val=100.0, theme=theme)
    qtbot.addWidget(bar)
    bar.set_value(150.0)
    assert bar.value == 100.0
    bar.set_value(-10.0)
    assert bar.value == 0.0


def test_set_sp_marker(qtbot, theme):
    bar = AnalogBarWidget(label="PV", unit="°C", min_val=0.0, max_val=100.0, theme=theme)
    qtbot.addWidget(bar)
    bar.set_sp_marker(50.0)
    assert bar.sp_marker == 50.0


def test_alarm_state_changes_fill(qtbot, theme):
    bar = AnalogBarWidget(label="PV", unit="°C", min_val=0.0, max_val=100.0, theme=theme)
    qtbot.addWidget(bar)
    bar.set_alarm_state("CRITICAL")
    assert bar.alarm_state == "CRITICAL"
    bar.set_alarm_state(None)
    assert bar.alarm_state is None


def test_renders_without_crash(qtbot, theme):
    bar = AnalogBarWidget(label="CO", unit="%", min_val=0.0, max_val=100.0, theme=theme)
    qtbot.addWidget(bar)
    bar.set_value(62.5)
    bar.show()
    bar.repaint()
    # No crash = pass
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/hmi/widgets/test_analog_bar.py -v
```
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement AnalogBarWidget**

```python
# packages/smart_pid_hmi/src/smart_pid_hmi/widgets/__init__.py
"""HMI widgets."""

# packages/smart_pid_hmi/src/smart_pid_hmi/widgets/analog_bar.py
"""AnalogBarWidget — horizontal continuous bar with ISA-101 coloring."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import QWidget

if TYPE_CHECKING:
    from smart_pid_hmi.themes.base import ThemeBase

_BAR_HEIGHT = 20
_WIDGET_HEIGHT = 36


class AnalogBarWidget(QWidget):
    """Horizontal continuous bar with label, value, SP marker, and alarm coloring."""

    def __init__(
        self,
        label: str,
        unit: str,
        min_val: float,
        max_val: float,
        theme: ThemeBase,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._label = label
        self._unit = unit
        self._min = min_val
        self._max = max_val
        self._theme = theme
        self._value: float = 0.0
        self._sp_marker: float | None = None
        self._alarm_state: str | None = None
        self.setMinimumHeight(_WIDGET_HEIGHT)
        self.setMaximumHeight(_WIDGET_HEIGHT)

    @property
    def label(self) -> str:
        return self._label

    @property
    def value(self) -> float:
        return self._value

    @property
    def sp_marker(self) -> float | None:
        return self._sp_marker

    @property
    def alarm_state(self) -> str | None:
        return self._alarm_state

    def set_value(self, val: float) -> None:
        self._value = max(self._min, min(self._max, val))
        self.update()

    def set_sp_marker(self, val: float) -> None:
        self._sp_marker = val
        self.update()

    def set_alarm_state(self, state: str | None) -> None:
        self._alarm_state = state
        self.update()

    def _fill_color(self) -> QColor:
        if self._alarm_state == "CRITICAL":
            return QColor(self._theme.alarm_critical)
        if self._alarm_state == "WARNING":
            return QColor(self._theme.alarm_warning)
        return QColor(self._theme.bar_pv)

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)  # flat ISA-101
        w = self.width()

        # Label text (left)
        label_font = QFont(self._theme.font_family, self._theme.font_size_label)
        p.setFont(label_font)
        p.setPen(QColor(self._theme.fg_secondary))
        label_rect = QRectF(0, 0, 30, _WIDGET_HEIGHT)
        p.drawText(label_rect, Qt.AlignmentFlag.AlignVCenter, self._label)

        # Value text (right)
        value_font = QFont(self._theme.font_family, self._theme.font_size_value)
        p.setFont(value_font)
        p.setPen(QColor(self._theme.fg_primary))
        value_text = f"{self._value:.1f} {self._unit}"
        value_rect = QRectF(w - 80, 0, 80, _WIDGET_HEIGHT)
        p.drawText(value_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                   value_text)

        # Bar area
        bar_x = 34
        bar_w = w - 120
        bar_y = (_WIDGET_HEIGHT - _BAR_HEIGHT) / 2

        if bar_w <= 0:
            p.end()
            return

        # Bar background
        p.fillRect(QRectF(bar_x, bar_y, bar_w, _BAR_HEIGHT),
                    QColor(self._theme.bg_widget))

        # Bar fill
        span = self._max - self._min
        if span > 0:
            frac = (self._value - self._min) / span
            fill_w = bar_w * frac
            p.fillRect(QRectF(bar_x, bar_y, fill_w, _BAR_HEIGHT), self._fill_color())

        # SP marker (thin vertical line)
        if self._sp_marker is not None and span > 0:
            sp_frac = (self._sp_marker - self._min) / span
            sp_x = bar_x + bar_w * sp_frac
            p.setPen(QColor(self._theme.bar_sp))
            p.drawLine(int(sp_x), int(bar_y), int(sp_x), int(bar_y + _BAR_HEIGHT))

        # Border
        p.setPen(QColor(self._theme.border))
        p.drawRect(QRectF(bar_x, bar_y, bar_w, _BAR_HEIGHT))

        p.end()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/hmi/widgets/test_analog_bar.py -v
```
Expected: 6 PASSED

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_hmi/src/smart_pid_hmi/widgets/ \
       tests/hmi/widgets/
git commit -m "feat(hmi): add AnalogBarWidget with ISA-101 alarm coloring"
```

---

## Task 11: ControllerCardWidget

**Files:**
- Create: `packages/smart_pid_hmi/src/smart_pid_hmi/widgets/controller_card.py`
- Create: `tests/hmi/widgets/test_controller_card.py`

- [ ] **Step 1: Write tests for ControllerCardWidget**

```python
# tests/hmi/widgets/test_controller_card.py
"""Tests for ControllerCardWidget."""
import pytest

from smart_pid_hmi.themes.isa101 import ISA101Theme
from smart_pid_hmi.widgets.controller_card import ControllerCardWidget


@pytest.fixture
def theme():
    return ISA101Theme()


def test_creation(qtbot, theme):
    card = ControllerCardWidget(
        controller_id=1, tag_name="FIC-101",
        min_val=0.0, max_val=100.0, theme=theme,
    )
    qtbot.addWidget(card)
    assert card.controller_id == 1
    assert card.tag_name == "FIC-101"


def test_on_telemetry_updates_bars(qtbot, theme):
    card = ControllerCardWidget(
        controller_id=1, tag_name="FIC-101",
        min_val=0.0, max_val=100.0, theme=theme,
    )
    qtbot.addWidget(card)
    frame = {
        "controller_id": 1, "pv": 45.0, "sp": 50.0,
        "co": 62.0, "integral_val": 0.0,
        "timestamp": "2026-04-03T10:00:00", "status": "GOOD",
    }
    card.on_telemetry(1, frame)
    assert card._bar_pv.value == 45.0
    assert card._bar_sp.value == 50.0
    assert card._bar_co.value == 62.0


def test_ignores_other_controller(qtbot, theme):
    card = ControllerCardWidget(
        controller_id=1, tag_name="FIC-101",
        min_val=0.0, max_val=100.0, theme=theme,
    )
    qtbot.addWidget(card)
    frame = {
        "controller_id": 2, "pv": 99.0, "sp": 50.0,
        "co": 62.0, "integral_val": 0.0,
        "timestamp": "2026-04-03T10:00:00", "status": "GOOD",
    }
    card.on_telemetry(2, frame)
    assert card._bar_pv.value == 0.0  # unchanged


def test_emits_controller_selected_on_click(qtbot, theme):
    card = ControllerCardWidget(
        controller_id=1, tag_name="FIC-101",
        min_val=0.0, max_val=100.0, theme=theme,
    )
    qtbot.addWidget(card)
    with qtbot.waitSignal(card.controller_selected, timeout=500):
        qtbot.mouseClick(card, Qt.MouseButton.LeftButton)


def test_mode_badge_update(qtbot, theme):
    card = ControllerCardWidget(
        controller_id=1, tag_name="FIC-101",
        min_val=0.0, max_val=100.0, theme=theme,
    )
    qtbot.addWidget(card)
    assert card._mode_label.text() == "—"
    frame = {
        "controller_id": 1, "pv": 45.0, "sp": 50.0,
        "co": 62.0, "integral_val": 0.0,
        "timestamp": "2026-04-03T10:00:00", "status": "GOOD",
        "mode": "AUTO",
    }
    card.on_telemetry(1, frame)
    assert card._mode_label.text() == "AUTO"
```

Add at the top of the test file:

```python
from PySide6.QtCore import Qt
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/hmi/widgets/test_controller_card.py -v
```
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement ControllerCardWidget**

```python
# packages/smart_pid_hmi/src/smart_pid_hmi/widgets/controller_card.py
"""ControllerCardWidget — compact summary card per controller loop."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor, QMouseEvent
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

from smart_pid_hmi.widgets.analog_bar import AnalogBarWidget

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget

    from smart_pid_hmi.themes.base import ThemeBase

_CARD_WIDTH = 260
_CARD_MIN_HEIGHT = 160


class ControllerCardWidget(QFrame):
    """Summary card showing tag, mode, and 3 analog bars (PV, SP, CO)."""

    controller_selected = Signal(int)

    def __init__(
        self,
        controller_id: int,
        tag_name: str,
        min_val: float,
        max_val: float,
        theme: ThemeBase,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._controller_id = controller_id
        self._tag_name = tag_name
        self._theme = theme

        self.setFixedWidth(_CARD_WIDTH)
        self.setMinimumHeight(_CARD_MIN_HEIGHT)
        self.setFrameShape(QFrame.Shape.Box)
        self.setLineWidth(1)
        self.setStyleSheet(
            f"ControllerCardWidget {{ background-color: {theme.bg_widget}; "
            f"border: 1px solid {theme.border}; }}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)

        # Header: tag name + mode badge
        header = QHBoxLayout()
        tag_label = QLabel(tag_name)
        tag_label.setStyleSheet(
            f"font-size: {theme.font_size_title}px; font-weight: bold; "
            f"color: {theme.fg_primary}; background: transparent;"
        )
        self._mode_label = QLabel("—")
        self._mode_label.setStyleSheet(
            f"font-size: {theme.font_size_label}px; color: {theme.fg_secondary}; "
            f"background: transparent; padding: 2px 6px; "
            f"border: 1px solid {theme.border};"
        )
        header.addWidget(tag_label)
        header.addStretch()
        header.addWidget(self._mode_label)
        layout.addLayout(header)

        # Bars
        self._bar_pv = AnalogBarWidget("PV", "", min_val, max_val, theme)
        self._bar_sp = AnalogBarWidget("SP", "", min_val, max_val, theme)
        self._bar_co = AnalogBarWidget("CO", "%", 0.0, 100.0, theme)
        layout.addWidget(self._bar_pv)
        layout.addWidget(self._bar_sp)
        layout.addWidget(self._bar_co)
        layout.addStretch()

    @property
    def controller_id(self) -> int:
        return self._controller_id

    @property
    def tag_name(self) -> str:
        return self._tag_name

    def on_telemetry(self, controller_id: int, frame: dict) -> None:
        if controller_id != self._controller_id:
            return
        self._bar_pv.set_value(frame.get("pv", 0.0))
        self._bar_pv.set_sp_marker(frame.get("sp"))
        self._bar_sp.set_value(frame.get("sp", 0.0))
        self._bar_co.set_value(frame.get("co", 0.0))
        mode = frame.get("mode")
        if mode:
            self._mode_label.setText(str(mode))

    def on_alarm(self, controller_id: int, alarm: dict) -> None:
        if controller_id != self._controller_id:
            return
        priority = alarm.get("priority", "")
        if priority == "CRITICAL":
            self.setStyleSheet(
                f"ControllerCardWidget {{ background-color: {self._theme.bg_widget}; "
                f"border: 2px solid {self._theme.alarm_critical}; }}"
            )
            self._bar_pv.set_alarm_state("CRITICAL")
        elif priority == "WARNING":
            self.setStyleSheet(
                f"ControllerCardWidget {{ background-color: {self._theme.bg_widget}; "
                f"border: 2px solid {self._theme.alarm_warning}; }}"
            )
            self._bar_pv.set_alarm_state("WARNING")
        else:
            self.setStyleSheet(
                f"ControllerCardWidget {{ background-color: {self._theme.bg_widget}; "
                f"border: 1px solid {self._theme.border}; }}"
            )
            self._bar_pv.set_alarm_state(None)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        self.controller_selected.emit(self._controller_id)
        super().mousePressEvent(event)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/hmi/widgets/test_controller_card.py -v
```
Expected: 5 PASSED

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_hmi/src/smart_pid_hmi/widgets/controller_card.py \
       tests/hmi/widgets/test_controller_card.py
git commit -m "feat(hmi): add ControllerCardWidget with analog bars and selection"
```

---

## Task 12: FaceplateWidget

**Files:**
- Create: `packages/smart_pid_hmi/src/smart_pid_hmi/widgets/faceplate.py`
- Create: `tests/hmi/widgets/test_faceplate.py`

- [ ] **Step 1: Write tests for FaceplateWidget**

```python
# tests/hmi/widgets/test_faceplate.py
"""Tests for FaceplateWidget."""
import pytest
from PySide6.QtCore import Qt

from smart_pid_hmi.themes.isa101 import ISA101Theme
from smart_pid_hmi.widgets.faceplate import FaceplateWidget


@pytest.fixture
def theme():
    return ISA101Theme()


def test_creation(qtbot, theme):
    fp = FaceplateWidget(theme=theme)
    qtbot.addWidget(fp)
    assert fp._tag_label.text() == "—"


def test_on_controller_selected(qtbot, theme):
    fp = FaceplateWidget(theme=theme)
    qtbot.addWidget(fp)
    fp.on_controller_selected(1, "FIC-101", 0.0, 100.0)
    assert fp._tag_label.text() == "FIC-101"
    assert fp._controller_id == 1


def test_on_telemetry_updates_bars(qtbot, theme):
    fp = FaceplateWidget(theme=theme)
    qtbot.addWidget(fp)
    fp.on_controller_selected(1, "FIC-101", 0.0, 100.0)
    frame = {
        "controller_id": 1, "pv": 45.0, "sp": 50.0,
        "co": 62.0, "integral_val": 0.0,
        "timestamp": "2026-04-03T10:00:00", "status": "GOOD",
        "mode": "AUTO",
    }
    fp.on_telemetry(1, frame)
    assert fp._bar_pv.value == 45.0
    assert fp._bar_co.value == 62.0


def test_ignores_other_controller_telemetry(qtbot, theme):
    fp = FaceplateWidget(theme=theme)
    qtbot.addWidget(fp)
    fp.on_controller_selected(1, "FIC-101", 0.0, 100.0)
    frame = {"controller_id": 2, "pv": 99.0, "sp": 50.0, "co": 62.0,
             "integral_val": 0.0, "timestamp": "T", "status": "GOOD"}
    fp.on_telemetry(2, frame)
    assert fp._bar_pv.value == 0.0


def test_sp_input_emits_command(qtbot, theme):
    fp = FaceplateWidget(theme=theme)
    qtbot.addWidget(fp)
    fp.on_controller_selected(1, "FIC-101", 0.0, 100.0)

    received = []
    fp.setpoint_requested.connect(lambda cid, val: received.append((cid, val)))

    fp._sp_input.setText("55.0")
    qtbot.keyPress(fp._sp_input, Qt.Key.Key_Return)

    assert len(received) == 1
    assert received[0] == (1, 55.0)


def test_mode_button_emits_command(qtbot, theme):
    fp = FaceplateWidget(theme=theme)
    qtbot.addWidget(fp)
    fp.on_controller_selected(1, "FIC-101", 0.0, 100.0)

    received = []
    fp.mode_requested.connect(lambda cid, mode: received.append((cid, mode)))

    qtbot.mouseClick(fp._btn_man, Qt.MouseButton.LeftButton)
    assert len(received) == 1
    assert received[0] == (1, "MAN")


def test_co_input_emits_command(qtbot, theme):
    fp = FaceplateWidget(theme=theme)
    qtbot.addWidget(fp)
    fp.on_controller_selected(1, "FIC-101", 0.0, 100.0)

    received = []
    fp.output_requested.connect(lambda cid, val: received.append((cid, val)))

    fp._co_input.setText("30.0")
    qtbot.keyPress(fp._co_input, Qt.Key.Key_Return)

    assert len(received) == 1
    assert received[0] == (1, 30.0)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/hmi/widgets/test_faceplate.py -v
```
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement FaceplateWidget**

```python
# packages/smart_pid_hmi/src/smart_pid_hmi/widgets/faceplate.py
"""FaceplateWidget — detailed operation panel for selected controller."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from smart_pid_hmi.widgets.analog_bar import AnalogBarWidget

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget

    from smart_pid_hmi.themes.base import ThemeBase


class FaceplateWidget(QFrame):
    """Detailed control panel for a single controller."""

    setpoint_requested = Signal(int, float)    # (controller_id, value)
    mode_requested = Signal(int, str)          # (controller_id, mode)
    output_requested = Signal(int, float)      # (controller_id, value)

    def __init__(self, theme: ThemeBase, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._theme = theme
        self._controller_id: int | None = None

        self.setFrameShape(QFrame.Shape.Box)
        self.setStyleSheet(
            f"FaceplateWidget {{ background-color: {theme.bg_secondary}; "
            f"border: 1px solid {theme.border}; }}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        # Header
        self._tag_label = QLabel("—")
        self._tag_label.setStyleSheet(
            f"font-size: {theme.font_size_title}px; font-weight: bold; "
            f"color: {theme.fg_primary}; background: transparent;"
        )
        self._mode_label = QLabel("—")
        self._mode_label.setStyleSheet(
            f"font-size: {theme.font_size_label}px; color: {theme.fg_secondary}; "
            f"background: transparent; padding: 2px 6px; border: 1px solid {theme.border};"
        )
        header = QHBoxLayout()
        header.addWidget(self._tag_label)
        header.addStretch()
        header.addWidget(self._mode_label)
        layout.addLayout(header)

        # Bars (created with defaults, replaced on controller select)
        self._bar_pv = AnalogBarWidget("PV", "", 0.0, 100.0, theme)
        self._bar_sp = AnalogBarWidget("SP", "", 0.0, 100.0, theme)
        self._bar_co = AnalogBarWidget("CO", "%", 0.0, 100.0, theme)
        layout.addWidget(self._bar_pv)
        layout.addWidget(self._bar_sp)
        layout.addWidget(self._bar_co)

        # SP input
        sp_row = QHBoxLayout()
        sp_row.addWidget(QLabel("SP:"))
        self._sp_input = QLineEdit()
        self._sp_input.setPlaceholderText("Enter SP")
        self._sp_input.returnPressed.connect(self._on_sp_enter)
        sp_row.addWidget(self._sp_input)
        layout.addLayout(sp_row)

        # CO input
        co_row = QHBoxLayout()
        co_row.addWidget(QLabel("CO:"))
        self._co_input = QLineEdit()
        self._co_input.setPlaceholderText("Enter CO (MAN)")
        self._co_input.returnPressed.connect(self._on_co_enter)
        co_row.addWidget(self._co_input)
        layout.addLayout(co_row)

        # Mode buttons
        mode_row = QHBoxLayout()
        self._btn_auto = QPushButton("Auto")
        self._btn_man = QPushButton("Man")
        self._btn_auto.clicked.connect(lambda: self._on_mode("AUTO"))
        self._btn_man.clicked.connect(lambda: self._on_mode("MAN"))
        mode_row.addWidget(self._btn_auto)
        mode_row.addWidget(self._btn_man)
        layout.addLayout(mode_row)

        # Stats placeholder
        stats_label = QLabel("IAE: — | 2σ/Range: —")
        stats_label.setStyleSheet(
            f"font-size: {theme.font_size_label}px; color: {theme.fg_secondary}; "
            f"background: transparent;"
        )
        layout.addWidget(stats_label)
        layout.addStretch()

    def on_controller_selected(
        self, controller_id: int, tag_name: str, min_val: float, max_val: float
    ) -> None:
        self._controller_id = controller_id
        self._tag_label.setText(tag_name)
        self._mode_label.setText("—")
        # Reset bars with new range
        for bar in [self._bar_pv, self._bar_sp]:
            bar._min = min_val
            bar._max = max_val
            bar.set_value(0.0)
        self._bar_co.set_value(0.0)

    def on_telemetry(self, controller_id: int, frame: dict) -> None:
        if self._controller_id is None or controller_id != self._controller_id:
            return
        self._bar_pv.set_value(frame.get("pv", 0.0))
        self._bar_pv.set_sp_marker(frame.get("sp"))
        self._bar_sp.set_value(frame.get("sp", 0.0))
        self._bar_co.set_value(frame.get("co", 0.0))
        mode = frame.get("mode")
        if mode:
            self._mode_label.setText(str(mode))

    def _on_sp_enter(self) -> None:
        if self._controller_id is None:
            return
        try:
            val = float(self._sp_input.text())
            self.setpoint_requested.emit(self._controller_id, val)
        except ValueError:
            pass

    def _on_co_enter(self) -> None:
        if self._controller_id is None:
            return
        try:
            val = float(self._co_input.text())
            self.output_requested.emit(self._controller_id, val)
        except ValueError:
            pass

    def _on_mode(self, mode: str) -> None:
        if self._controller_id is not None:
            self.mode_requested.emit(self._controller_id, mode)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/hmi/widgets/test_faceplate.py -v
```
Expected: 7 PASSED

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_hmi/src/smart_pid_hmi/widgets/faceplate.py \
       tests/hmi/widgets/test_faceplate.py
git commit -m "feat(hmi): add FaceplateWidget with SP/CO inputs and mode buttons"
```

---

## Task 13: TrendChartWidget

**Files:**
- Create: `packages/smart_pid_hmi/src/smart_pid_hmi/widgets/trend_chart.py`
- Create: `tests/hmi/widgets/test_trend_chart.py`

- [ ] **Step 1: Write tests for TrendChartWidget**

```python
# tests/hmi/widgets/test_trend_chart.py
"""Tests for TrendChartWidget."""
import pytest

from smart_pid_hmi.themes.isa101 import ISA101Theme
from smart_pid_hmi.widgets.trend_chart import TrendChartWidget


@pytest.fixture
def theme():
    return ISA101Theme()


def test_creation(qtbot, theme):
    trend = TrendChartWidget(theme=theme)
    qtbot.addWidget(trend)
    assert trend._controller_id is None


def test_on_controller_selected_clears_data(qtbot, theme):
    trend = TrendChartWidget(theme=theme, buffer_size=100)
    qtbot.addWidget(trend)
    trend.on_controller_selected(1)
    assert trend._controller_id == 1
    assert len(trend._pv_data) == 0


def test_on_telemetry_adds_data(qtbot, theme):
    trend = TrendChartWidget(theme=theme, buffer_size=100)
    qtbot.addWidget(trend)
    trend.on_controller_selected(1)
    frame = {
        "controller_id": 1, "pv": 45.0, "sp": 50.0,
        "co": 62.0, "integral_val": 0.0,
        "timestamp": "2026-04-03T10:00:00", "status": "GOOD",
    }
    trend.on_telemetry(1, frame)
    assert len(trend._pv_data) == 1
    assert trend._pv_data[0] == 45.0


def test_ignores_other_controller(qtbot, theme):
    trend = TrendChartWidget(theme=theme, buffer_size=100)
    qtbot.addWidget(trend)
    trend.on_controller_selected(1)
    frame = {"controller_id": 2, "pv": 99.0, "sp": 50.0, "co": 62.0,
             "integral_val": 0.0, "timestamp": "T", "status": "GOOD"}
    trend.on_telemetry(2, frame)
    assert len(trend._pv_data) == 0


def test_circular_buffer(qtbot, theme):
    trend = TrendChartWidget(theme=theme, buffer_size=5)
    qtbot.addWidget(trend)
    trend.on_controller_selected(1)
    for i in range(10):
        frame = {"controller_id": 1, "pv": float(i), "sp": 50.0, "co": 50.0,
                 "integral_val": 0.0, "timestamp": "T", "status": "GOOD"}
        trend.on_telemetry(1, frame)
    assert len(trend._pv_data) == 5
    assert trend._pv_data[0] == 5.0  # oldest kept
    assert trend._pv_data[-1] == 9.0  # newest


def test_set_time_window(qtbot, theme):
    trend = TrendChartWidget(theme=theme)
    qtbot.addWidget(trend)
    trend.set_time_window("5min")
    # No crash = pass
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/hmi/widgets/test_trend_chart.py -v
```
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement TrendChartWidget**

```python
# packages/smart_pid_hmi/src/smart_pid_hmi/widgets/trend_chart.py
"""TrendChartWidget — pyqtgraph dual Y-axis real-time trend."""
from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING

import pyqtgraph as pg
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QVBoxLayout, QWidget

if TYPE_CHECKING:
    from smart_pid_hmi.themes.base import ThemeBase

_TIME_WINDOWS = {
    "1min": 60,
    "5min": 300,
    "10min": 600,
    "30min": 1800,
    "1h": 3600,
}

_DEFAULT_BUFFER = 600  # 10min at 1s scan


class TrendChartWidget(QWidget):
    """Real-time trend with PV/SP on Y1 and CO on Y2."""

    def __init__(
        self,
        theme: ThemeBase | None = None,
        buffer_size: int = _DEFAULT_BUFFER,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._controller_id: int | None = None
        self._buffer_size = buffer_size
        self._pv_data: deque[float] = deque(maxlen=buffer_size)
        self._sp_data: deque[float] = deque(maxlen=buffer_size)
        self._co_data: deque[float] = deque(maxlen=buffer_size)
        self._time_data: deque[float] = deque(maxlen=buffer_size)
        self._tick = 0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Time window selector
        ctrl_row = QHBoxLayout()
        self._combo = QComboBox()
        self._combo.addItems(list(_TIME_WINDOWS.keys()))
        self._combo.setCurrentText("10min")
        ctrl_row.addStretch()
        ctrl_row.addWidget(self._combo)
        layout.addLayout(ctrl_row)

        # Plot
        self._plot_widget = pg.PlotWidget()
        layout.addWidget(self._plot_widget)

        if theme:
            self._plot_widget.setBackground(theme.chart_bg)
            self._plot_widget.getAxis("bottom").setPen(theme.fg_primary)
            self._plot_widget.getAxis("left").setPen(theme.fg_primary)
            self._plot_widget.showGrid(x=True, y=True, alpha=0.3)

            self._pv_curve = self._plot_widget.plot(
                pen=pg.mkPen(color=theme.chart_pv, width=2, style=1),  # solid
                name="PV",
            )
            self._sp_curve = self._plot_widget.plot(
                pen=pg.mkPen(color=theme.chart_sp, width=1, style=2),  # dash
                name="SP",
            )

            # Y2 axis for CO
            self._y2 = pg.ViewBox()
            self._plot_widget.scene().addItem(self._y2)
            self._plot_widget.getAxis("right").linkToView(self._y2)
            self._y2.setXLink(self._plot_widget)
            self._plot_widget.showAxis("right")

            self._co_curve = pg.PlotCurveItem(
                pen=pg.mkPen(color=theme.chart_co, width=1),
            )
            self._y2.addItem(self._co_curve)
        else:
            self._pv_curve = self._plot_widget.plot(pen="w", name="PV")
            self._sp_curve = self._plot_widget.plot(pen="y", name="SP")
            self._y2 = None
            self._co_curve = None

    def on_controller_selected(self, controller_id: int) -> None:
        self._controller_id = controller_id
        self._pv_data.clear()
        self._sp_data.clear()
        self._co_data.clear()
        self._time_data.clear()
        self._tick = 0
        self._pv_curve.clear()
        self._sp_curve.clear()
        if self._co_curve:
            self._co_curve.clear()

    def on_telemetry(self, controller_id: int, frame: dict) -> None:
        if self._controller_id is None or controller_id != self._controller_id:
            return

        self._pv_data.append(frame.get("pv", 0.0))
        self._sp_data.append(frame.get("sp", 0.0))
        self._co_data.append(frame.get("co", 0.0))
        self._time_data.append(float(self._tick))
        self._tick += 1

        x = list(self._time_data)
        self._pv_curve.setData(x, list(self._pv_data))
        self._sp_curve.setData(x, list(self._sp_data))
        if self._co_curve:
            self._co_curve.setData(x, list(self._co_data))

    def set_time_window(self, window: str) -> None:
        self._combo.setCurrentText(window)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/hmi/widgets/test_trend_chart.py -v
```
Expected: 6 PASSED

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_hmi/src/smart_pid_hmi/widgets/trend_chart.py \
       tests/hmi/widgets/test_trend_chart.py
git commit -m "feat(hmi): add TrendChartWidget with pyqtgraph dual Y-axis"
```

---

## Task 14: AlarmBarWidget

**Files:**
- Create: `packages/smart_pid_hmi/src/smart_pid_hmi/widgets/alarm_bar.py`
- Create: `tests/hmi/widgets/test_alarm_bar.py`

- [ ] **Step 1: Write tests for AlarmBarWidget**

```python
# tests/hmi/widgets/test_alarm_bar.py
"""Tests for AlarmBarWidget — footer alarm strip."""
import pytest

from smart_pid_hmi.themes.isa101 import ISA101Theme
from smart_pid_hmi.widgets.alarm_bar import AlarmBarWidget


@pytest.fixture
def theme():
    return ISA101Theme()


def test_creation(qtbot, theme):
    bar = AlarmBarWidget(theme=theme)
    qtbot.addWidget(bar)
    assert bar.alarm_count == 0


def test_add_alarm(qtbot, theme):
    bar = AlarmBarWidget(theme=theme)
    qtbot.addWidget(bar)
    alarm = {
        "controller_name": "FIC-101",
        "alarm_type": "HIHI",
        "priority": "CRITICAL",
        "value": 95.3,
        "timestamp": "2026-04-03T10:00:00",
    }
    bar.on_alarm(1, alarm)
    assert bar.alarm_count == 1


def test_max_10_alarms(qtbot, theme):
    bar = AlarmBarWidget(theme=theme)
    qtbot.addWidget(bar)
    for i in range(15):
        alarm = {
            "controller_name": f"TAG-{i}",
            "alarm_type": "HI",
            "priority": "WARNING",
            "value": float(i),
            "timestamp": f"2026-04-03T10:{i:02d}:00",
        }
        bar.on_alarm(i, alarm)
    assert bar.alarm_count == 10


def test_newest_alarm_is_first(qtbot, theme):
    bar = AlarmBarWidget(theme=theme)
    qtbot.addWidget(bar)
    for i in range(3):
        alarm = {
            "controller_name": f"TAG-{i}",
            "alarm_type": "HI",
            "priority": "WARNING",
            "value": float(i),
            "timestamp": f"2026-04-03T10:{i:02d}:00",
        }
        bar.on_alarm(i, alarm)
    # Newest (TAG-2) should be at index 0
    assert bar._alarms[0]["controller_name"] == "TAG-2"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/hmi/widgets/test_alarm_bar.py -v
```
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement AlarmBarWidget**

```python
# packages/smart_pid_hmi/src/smart_pid_hmi/widgets/alarm_bar.py
"""AlarmBarWidget — footer strip showing last 10 alarms."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QScrollArea, QWidget

if TYPE_CHECKING:
    from smart_pid_hmi.themes.base import ThemeBase

_MAX_ALARMS = 10
_BAR_HEIGHT = 40


class AlarmBarWidget(QFrame):
    """Fixed-height footer showing recent alarms with semantic coloring."""

    def __init__(self, theme: ThemeBase, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._theme = theme
        self._alarms: list[dict] = []

        self.setFixedHeight(_BAR_HEIGHT)
        self.setStyleSheet(
            f"AlarmBarWidget {{ background-color: {theme.bg_secondary}; "
            f"border-top: 1px solid {theme.border}; }}"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(0)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet("border: none; background: transparent;")

        self._container = QWidget()
        self._container_layout = QHBoxLayout(self._container)
        self._container_layout.setContentsMargins(0, 0, 0, 0)
        self._container_layout.setSpacing(8)
        self._container_layout.addStretch()

        self._scroll.setWidget(self._container)
        layout.addWidget(self._scroll)

    @property
    def alarm_count(self) -> int:
        return len(self._alarms)

    def on_alarm(self, controller_id: int, alarm: dict) -> None:
        self._alarms.insert(0, alarm)
        if len(self._alarms) > _MAX_ALARMS:
            self._alarms = self._alarms[:_MAX_ALARMS]
        self._rebuild()

    def _rebuild(self) -> None:
        # Clear existing labels
        while self._container_layout.count() > 1:
            item = self._container_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for alarm in self._alarms:
            priority = alarm.get("priority", "")
            if priority == "CRITICAL":
                bg = self._theme.alarm_critical
            elif priority == "WARNING":
                bg = self._theme.alarm_warning
            else:
                bg = self._theme.bg_widget

            text_color = self._theme.alarm_text if priority in ("CRITICAL",) else self._theme.fg_primary
            tag = alarm.get("controller_name", "?")
            atype = alarm.get("alarm_type", "?")
            val = alarm.get("value", 0.0)
            ts = alarm.get("timestamp", "")
            # Show only time part if ISO format
            if "T" in str(ts):
                ts = str(ts).split("T")[1][:8]

            label = QLabel(f" {ts} | {tag} | {atype} | {val:.1f} ")
            label.setStyleSheet(
                f"background-color: {bg}; color: {text_color}; "
                f"font-size: {self._theme.font_size_label}px; "
                f"padding: 2px 6px; border: none;"
            )
            self._container_layout.insertWidget(self._container_layout.count() - 1, label)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/hmi/widgets/test_alarm_bar.py -v
```
Expected: 4 PASSED

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_hmi/src/smart_pid_hmi/widgets/alarm_bar.py \
       tests/hmi/widgets/test_alarm_bar.py
git commit -m "feat(hmi): add AlarmBarWidget footer with last 10 alarms"
```

---

## Task 15: ConnectionPage

**Files:**
- Create: `packages/smart_pid_hmi/src/smart_pid_hmi/pages/__init__.py`
- Create: `packages/smart_pid_hmi/src/smart_pid_hmi/pages/connection_page.py`
- Create: `tests/hmi/pages/__init__.py`
- Create: `tests/hmi/pages/test_connection_page.py`

- [ ] **Step 1: Write tests for ConnectionPage**

```python
# tests/hmi/pages/test_connection_page.py
"""Tests for ConnectionPage — login screen."""
import pytest
from PySide6.QtCore import Qt

from smart_pid_hmi.pages.connection_page import ConnectionPage
from smart_pid_hmi.themes.isa101 import ISA101Theme


@pytest.fixture
def theme():
    return ISA101Theme()


def test_creation(qtbot, theme):
    page = ConnectionPage(theme=theme, default_url="http://localhost:8000")
    qtbot.addWidget(page)
    assert page._url_input.text() == "http://localhost:8000"


def test_connect_emits_signal(qtbot, theme):
    page = ConnectionPage(theme=theme, default_url="http://test:8000")
    qtbot.addWidget(page)

    received = []
    page.login_requested.connect(lambda url, u, p: received.append((url, u, p)))

    page._url_input.setText("http://10.0.0.1:8000")
    page._user_input.setText("admin")
    page._pass_input.setText("secret")
    qtbot.mouseClick(page._connect_btn, Qt.MouseButton.LeftButton)

    assert len(received) == 1
    assert received[0] == ("http://10.0.0.1:8000", "admin", "secret")


def test_show_error(qtbot, theme):
    page = ConnectionPage(theme=theme, default_url="http://test:8000")
    qtbot.addWidget(page)
    page.show_error("Connection refused")
    assert page._status_label.text() == "Connection refused"
    assert page._status_label.isVisible()


def test_show_error_clears(qtbot, theme):
    page = ConnectionPage(theme=theme, default_url="http://test:8000")
    qtbot.addWidget(page)
    page.show_error("Error")
    page.clear_error()
    assert page._status_label.text() == ""
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/hmi/pages/test_connection_page.py -v
```
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement ConnectionPage**

```python
# packages/smart_pid_hmi/src/smart_pid_hmi/pages/__init__.py
"""HMI pages."""

# packages/smart_pid_hmi/src/smart_pid_hmi/pages/connection_page.py
"""ConnectionPage — login and server URL entry."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from smart_pid_hmi.themes.base import ThemeBase


class ConnectionPage(QWidget):
    """Initial screen for login and server URL configuration."""

    login_requested = Signal(str, str, str)  # (server_url, username, password)

    def __init__(
        self,
        theme: ThemeBase,
        default_url: str = "http://localhost:8000",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._theme = theme

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(12)

        # Title
        title = QLabel("Smart PID — Connect")
        title.setStyleSheet(
            f"font-size: {theme.font_size_title + 4}px; font-weight: bold; "
            f"color: {theme.fg_primary}; background: transparent;"
        )
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Server URL
        url_label = QLabel("Server URL")
        url_label.setStyleSheet(f"color: {theme.fg_secondary}; background: transparent;")
        layout.addWidget(url_label)
        self._url_input = QLineEdit(default_url)
        self._url_input.setFixedWidth(300)
        layout.addWidget(self._url_input)

        # Username
        user_label = QLabel("Username")
        user_label.setStyleSheet(f"color: {theme.fg_secondary}; background: transparent;")
        layout.addWidget(user_label)
        self._user_input = QLineEdit()
        self._user_input.setFixedWidth(300)
        self._user_input.setPlaceholderText("username")
        layout.addWidget(self._user_input)

        # Password
        pass_label = QLabel("Password")
        pass_label.setStyleSheet(f"color: {theme.fg_secondary}; background: transparent;")
        layout.addWidget(pass_label)
        self._pass_input = QLineEdit()
        self._pass_input.setFixedWidth(300)
        self._pass_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._pass_input.setPlaceholderText("password")
        layout.addWidget(self._pass_input)

        # Connect button
        self._connect_btn = QPushButton("Connect")
        self._connect_btn.setFixedWidth(300)
        self._connect_btn.clicked.connect(self._on_connect)
        layout.addWidget(self._connect_btn)

        # Status / error label
        self._status_label = QLabel("")
        self._status_label.setStyleSheet(
            f"color: {theme.alarm_critical}; background: transparent;"
        )
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_label.setVisible(False)
        layout.addWidget(self._status_label)

    def _on_connect(self) -> None:
        self.clear_error()
        self.login_requested.emit(
            self._url_input.text(),
            self._user_input.text(),
            self._pass_input.text(),
        )

    def show_error(self, message: str) -> None:
        self._status_label.setText(message)
        self._status_label.setVisible(True)

    def clear_error(self) -> None:
        self._status_label.setText("")
        self._status_label.setVisible(False)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/hmi/pages/test_connection_page.py -v
```
Expected: 4 PASSED

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_hmi/src/smart_pid_hmi/pages/ \
       tests/hmi/pages/
git commit -m "feat(hmi): add ConnectionPage with login form and error display"
```

---

## Task 16: DashboardPage

**Files:**
- Create: `packages/smart_pid_hmi/src/smart_pid_hmi/pages/dashboard_page.py`
- Create: `tests/hmi/pages/test_dashboard_page.py`

- [ ] **Step 1: Write tests for DashboardPage**

```python
# tests/hmi/pages/test_dashboard_page.py
"""Tests for DashboardPage layout and signal wiring."""
from queue import SimpleQueue

import pytest

from smart_pid_hmi.bus_bridge import BusBridge
from smart_pid_hmi.pages.dashboard_page import DashboardPage
from smart_pid_hmi.themes.isa101 import ISA101Theme


@pytest.fixture
def theme():
    return ISA101Theme()


@pytest.fixture
def bridge(qtbot):
    q = SimpleQueue()
    b = BusBridge(queue=q, refresh_ms=10)
    yield b
    b.stop()


def test_creation(qtbot, theme, bridge):
    page = DashboardPage(theme=theme, bus_bridge=bridge)
    qtbot.addWidget(page)
    assert page._faceplate is not None
    assert page._trend is not None
    assert page._alarm_bar is not None


def test_populate_controllers(qtbot, theme, bridge):
    page = DashboardPage(theme=theme, bus_bridge=bridge)
    qtbot.addWidget(page)
    controllers = [
        {"id": 1, "name": "FIC-101", "sp_hi_lim": 100.0, "sp_lo_lim": 0.0},
        {"id": 2, "name": "LIC-201", "sp_hi_lim": 100.0, "sp_lo_lim": 0.0},
    ]
    page.populate_controllers(controllers)
    assert len(page._cards) == 2


def test_first_controller_auto_selected(qtbot, theme, bridge):
    page = DashboardPage(theme=theme, bus_bridge=bridge)
    qtbot.addWidget(page)
    controllers = [
        {"id": 1, "name": "FIC-101", "sp_hi_lim": 100.0, "sp_lo_lim": 0.0},
    ]
    page.populate_controllers(controllers)
    assert page._faceplate._controller_id == 1
    assert page._trend._controller_id == 1
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/hmi/pages/test_dashboard_page.py -v
```
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement DashboardPage**

```python
# packages/smart_pid_hmi/src/smart_pid_hmi/pages/dashboard_page.py
"""DashboardPage — cards grid + trend/faceplate + alarm bar."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from smart_pid_hmi.widgets.alarm_bar import AlarmBarWidget
from smart_pid_hmi.widgets.controller_card import ControllerCardWidget
from smart_pid_hmi.widgets.faceplate import FaceplateWidget
from smart_pid_hmi.widgets.trend_chart import TrendChartWidget

if TYPE_CHECKING:
    from smart_pid_hmi.bus_bridge import BusBridge
    from smart_pid_hmi.themes.base import ThemeBase

_GRID_COLS = 4


class DashboardPage(QWidget):
    """Main operational dashboard with cards, trend, faceplate, and alarm bar."""

    setpoint_requested = Signal(int, float)
    mode_requested = Signal(int, str)
    output_requested = Signal(int, float)

    def __init__(
        self,
        theme: ThemeBase,
        bus_bridge: BusBridge,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._theme = theme
        self._bridge = bus_bridge
        self._cards: list[ControllerCardWidget] = []
        self._controller_meta: dict[int, dict] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 0)
        layout.setSpacing(4)

        # Top: cards grid (scrollable)
        self._cards_scroll = QScrollArea()
        self._cards_scroll.setWidgetResizable(True)
        self._cards_scroll.setMaximumHeight(200)
        self._cards_container = QWidget()
        self._cards_layout = QGridLayout(self._cards_container)
        self._cards_layout.setSpacing(6)
        self._cards_scroll.setWidget(self._cards_container)
        layout.addWidget(self._cards_scroll)

        # Middle: trend + faceplate (70/30 split)
        splitter = QSplitter()
        self._trend = TrendChartWidget(theme=theme)
        self._faceplate = FaceplateWidget(theme=theme)
        splitter.addWidget(self._trend)
        splitter.addWidget(self._faceplate)
        splitter.setStretchFactor(0, 7)
        splitter.setStretchFactor(1, 3)
        layout.addWidget(splitter, stretch=1)

        # Bottom: alarm bar
        self._alarm_bar = AlarmBarWidget(theme=theme)
        layout.addWidget(self._alarm_bar)

        # Wire faceplate command signals
        self._faceplate.setpoint_requested.connect(self.setpoint_requested)
        self._faceplate.mode_requested.connect(self.mode_requested)
        self._faceplate.output_requested.connect(self.output_requested)

        # Wire bus bridge
        bus_bridge.telemetry_received.connect(self._on_telemetry)
        bus_bridge.alarm_received.connect(self._on_alarm)

    def populate_controllers(self, controllers: list[dict]) -> None:
        """Create cards from controller list (from API response dicts)."""
        # Clear existing
        for card in self._cards:
            card.deleteLater()
        self._cards.clear()
        self._controller_meta.clear()

        for idx, ctrl in enumerate(controllers):
            cid = ctrl["id"]
            name = ctrl["name"]
            lo = ctrl.get("sp_lo_lim", 0.0)
            hi = ctrl.get("sp_hi_lim", 100.0)
            self._controller_meta[cid] = {"name": name, "lo": lo, "hi": hi}

            card = ControllerCardWidget(
                controller_id=cid, tag_name=name,
                min_val=lo, max_val=hi, theme=self._theme,
            )
            card.controller_selected.connect(self._on_card_selected)
            row = idx // _GRID_COLS
            col = idx % _GRID_COLS
            self._cards_layout.addWidget(card, row, col)
            self._cards.append(card)

        # Auto-select first
        if controllers:
            first = controllers[0]
            self._select_controller(first["id"])

    def _select_controller(self, controller_id: int) -> None:
        meta = self._controller_meta.get(controller_id)
        if meta is None:
            return
        self._faceplate.on_controller_selected(
            controller_id, meta["name"], meta["lo"], meta["hi"],
        )
        self._trend.on_controller_selected(controller_id)

    def _on_card_selected(self, controller_id: int) -> None:
        self._select_controller(controller_id)

    def _on_telemetry(self, controller_id: int, frame: dict) -> None:
        for card in self._cards:
            card.on_telemetry(controller_id, frame)
        self._faceplate.on_telemetry(controller_id, frame)
        self._trend.on_telemetry(controller_id, frame)

    def _on_alarm(self, controller_id: int, alarm: dict) -> None:
        for card in self._cards:
            card.on_alarm(controller_id, alarm)
        self._alarm_bar.on_alarm(controller_id, alarm)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/hmi/pages/test_dashboard_page.py -v
```
Expected: 3 PASSED

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_hmi/src/smart_pid_hmi/pages/dashboard_page.py \
       tests/hmi/pages/test_dashboard_page.py
git commit -m "feat(hmi): add DashboardPage with cards grid, trend, faceplate, alarms"
```

---

## Task 17: MainWindow + main.py Bootstrap

**Files:**
- Create: `packages/smart_pid_hmi/src/smart_pid_hmi/main.py`

- [ ] **Step 1: Implement main.py with MainWindow**

```python
# packages/smart_pid_hmi/src/smart_pid_hmi/main.py
"""Application bootstrap — QApplication, MainWindow, service wiring."""
from __future__ import annotations

import sys
import threading

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QStackedWidget,
    QToolBar,
    QWidget,
)

from smart_pid_hmi.bus_bridge import BusBridge
from smart_pid_hmi.config import HMISettings
from smart_pid_hmi.pages.connection_page import ConnectionPage
from smart_pid_hmi.pages.dashboard_page import DashboardPage
from smart_pid_hmi.services.session import Session
from smart_pid_hmi.themes.isa101 import ISA101Theme


class MainWindow(QMainWindow):
    """Top-level window with page stack and toolbar."""

    def __init__(
        self,
        settings: HMISettings,
        session: Session,
        api_client: object,
        telemetry_source: object,
        bus_bridge: BusBridge,
    ) -> None:
        super().__init__()
        self._settings = settings
        self._session = session
        self._api_client = api_client
        self._telemetry_source = telemetry_source
        self._bus_bridge = bus_bridge

        self.setWindowTitle("Smart PID HMI")
        self.setMinimumSize(1024, 700)

        # Theme
        theme = ISA101Theme()
        theme.apply(QApplication.instance())

        # Toolbar
        toolbar = QToolBar("Main")
        toolbar.setMovable(False)
        app_label = QLabel("  Smart PID  ")
        app_label.setStyleSheet(
            f"font-weight: bold; font-size: {theme.font_size_title}px; "
            f"color: {theme.fg_primary}; background: transparent;"
        )
        toolbar.addWidget(app_label)
        toolbar.addSeparator()

        self._conn_indicator = QLabel(" ● ")
        self._conn_indicator.setStyleSheet("color: red; background: transparent;")
        toolbar.addWidget(self._conn_indicator)

        self._user_label = QLabel("")
        self._user_label.setStyleSheet(
            f"color: {theme.fg_secondary}; background: transparent; padding-left: 8px;"
        )
        toolbar.addWidget(self._user_label)

        spacer = QWidget()
        spacer.setSizePolicy(spacer.sizePolicy().horizontalPolicy(), spacer.sizePolicy().verticalPolicy())
        toolbar.addWidget(spacer)
        self.addToolBar(toolbar)

        # Pages
        self._stack = QStackedWidget()
        self.setCentralWidget(self._stack)

        self._connection_page = ConnectionPage(theme=theme, default_url=settings.server_url)
        self._dashboard_page = DashboardPage(theme=theme, bus_bridge=bus_bridge)
        self._stack.addWidget(self._connection_page)
        self._stack.addWidget(self._dashboard_page)

        # Wire signals
        self._connection_page.login_requested.connect(self._on_login)
        self._dashboard_page.setpoint_requested.connect(self._send_setpoint)
        self._dashboard_page.mode_requested.connect(self._send_mode)
        self._dashboard_page.output_requested.connect(self._send_output)
        bus_bridge.connection_lost.connect(
            lambda: self._conn_indicator.setStyleSheet("color: red; background: transparent;")
        )
        bus_bridge.connection_restored.connect(
            lambda: self._conn_indicator.setStyleSheet("color: green; background: transparent;")
        )

    def _on_login(self, server_url: str, username: str, password: str) -> None:
        """Handle login in background thread."""
        def do_login():
            try:
                resp = self._api_client.login(username, password)
                self._session.store_token(resp.access_token)
                # Must update UI from main thread
                from PySide6.QtCore import QMetaObject, Q_ARG
                QMetaObject.invokeMethod(self, "_login_success", Qt.ConnectionType.QueuedConnection)
            except Exception as e:
                from PySide6.QtCore import QMetaObject
                self._login_error = str(e)
                QMetaObject.invokeMethod(self, "_login_failed", Qt.ConnectionType.QueuedConnection)

        threading.Thread(target=do_login, daemon=True).start()

    def _login_success(self) -> None:
        self._conn_indicator.setStyleSheet("color: green; background: transparent;")
        self._user_label.setText(self._session.username or "")
        self._telemetry_source.start()
        self._bus_bridge.start()
        self._load_dashboard()
        self._stack.setCurrentWidget(self._dashboard_page)

    def _login_failed(self) -> None:
        self._connection_page.show_error(getattr(self, "_login_error", "Login failed"))

    def _load_dashboard(self) -> None:
        """Load controllers from API and populate dashboard."""
        def do_load():
            try:
                controllers = self._api_client.list_controllers()
                ctrl_dicts = [c.model_dump() for c in controllers]
                from PySide6.QtCore import QMetaObject
                self._pending_controllers = ctrl_dicts
                QMetaObject.invokeMethod(
                    self, "_populate_dashboard", Qt.ConnectionType.QueuedConnection,
                )
            except Exception:
                pass  # Dashboard stays empty; user can retry

        threading.Thread(target=do_load, daemon=True).start()

    def _populate_dashboard(self) -> None:
        ctrl_dicts = getattr(self, "_pending_controllers", [])
        self._dashboard_page.populate_controllers(ctrl_dicts)

    def _send_setpoint(self, controller_id: int, value: float) -> None:
        threading.Thread(
            target=lambda: self._api_client.set_setpoint(controller_id, value),
            daemon=True,
        ).start()

    def _send_mode(self, controller_id: int, mode: str) -> None:
        threading.Thread(
            target=lambda: self._api_client.set_mode(controller_id, mode),
            daemon=True,
        ).start()

    def _send_output(self, controller_id: int, value: float) -> None:
        threading.Thread(
            target=lambda: self._api_client.set_output(controller_id, value),
            daemon=True,
        ).start()

    def closeEvent(self, event) -> None:  # noqa: N802
        self._bus_bridge.stop()
        self._telemetry_source.stop()
        super().closeEvent(event)


def main() -> None:
    """Entry point for the HMI application."""
    settings = HMISettings()
    session = Session()

    if settings.mock_mode:
        from smart_pid_hmi.services.mock_service import MockAPIClient, MockTelemetrySource

        api_client = MockAPIClient()
        telemetry_source = MockTelemetrySource()
    else:
        from smart_pid_hmi.services.api_client import APIClient
        from smart_pid_hmi.services.telemetry_sub import TelemetrySub

        api_client = APIClient(base_url=settings.server_url, session=session)
        telemetry_source = TelemetrySub(zmq_url=settings.zmq_url)

    bus_bridge = BusBridge(queue=telemetry_source.queue, refresh_ms=settings.refresh_ms)

    app = QApplication(sys.argv)
    window = MainWindow(
        settings=settings,
        session=session,
        api_client=api_client,
        telemetry_source=telemetry_source,
        bus_bridge=bus_bridge,
    )
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify import works**

```bash
uv run python -c "from smart_pid_hmi.main import main; print('OK')"
```
Expected: `OK` (may show Qt warnings without display — that's fine)

- [ ] **Step 3: Commit**

```bash
git add packages/smart_pid_hmi/src/smart_pid_hmi/main.py
git commit -m "feat(hmi): add MainWindow + main.py bootstrap with mock/real wiring"
```

---

## Task 18: Integration Test

**Files:**
- Create: `tests/hmi/test_integration.py`

- [ ] **Step 1: Write integration test**

```python
# tests/hmi/test_integration.py
"""Integration test: MockTelemetrySource → BusBridge → ControllerCardWidget."""
import pytest

from smart_pid_hmi.bus_bridge import BusBridge
from smart_pid_hmi.services.mock_service import MockTelemetrySource
from smart_pid_hmi.themes.isa101 import ISA101Theme
from smart_pid_hmi.widgets.controller_card import ControllerCardWidget


def test_mock_to_bridge_to_card(qtbot):
    """Full pipeline: mock generates data → bridge emits → card updates."""
    theme = ISA101Theme()

    source = MockTelemetrySource(interval_ms=50)
    bridge = BusBridge(queue=source.queue, refresh_ms=20)

    card = ControllerCardWidget(
        controller_id=1, tag_name="FIC-101",
        min_val=0.0, max_val=100.0, theme=theme,
    )
    qtbot.addWidget(card)

    bridge.telemetry_received.connect(card.on_telemetry)

    source.start()
    bridge.start()

    # Wait for at least one telemetry update to reach the card
    with qtbot.waitSignal(bridge.telemetry_received, timeout=2000):
        pass

    # Card should have updated PV
    assert card._bar_pv.value != 0.0

    bridge.stop()
    source.stop()


def test_mock_api_login_and_list(qtbot):
    """Verify mock API login + list_controllers returns valid data."""
    from smart_pid_hmi.services.mock_service import MockAPIClient
    from smart_pid_hmi.services.session import Session

    client = MockAPIClient()
    session = Session()

    resp = client.login("admin", "pass")
    session.store_token(resp.access_token)
    assert session.is_authenticated

    controllers = client.list_controllers()
    assert len(controllers) == 3
    assert all(c.id > 0 for c in controllers)
```

- [ ] **Step 2: Run integration tests**

```bash
uv run pytest tests/hmi/test_integration.py -v
```
Expected: 2 PASSED

- [ ] **Step 3: Run ALL HMI tests**

```bash
uv run pytest tests/hmi/ -v
```
Expected: All tests PASSED

- [ ] **Step 4: Run lint and type check**

```bash
uv run --with ruff ruff check packages/smart_pid_hmi/ tests/hmi/ && \
uv run mypy packages/smart_pid_hmi/
```
Fix any issues found.

- [ ] **Step 5: Commit**

```bash
git add tests/hmi/test_integration.py
git commit -m "test(hmi): add integration test (mock → bridge → card pipeline)"
```

---

## Task 19: Final Verification + Entry Point

**Files:**
- Modify: `packages/smart_pid_hmi/pyproject.toml` (add entry point)

- [ ] **Step 1: Add console entry point**

Add to `pyproject.toml`:

```toml
[project.scripts]
smart-pid-hmi = "smart_pid_hmi.main:main"
```

- [ ] **Step 2: Run full test suite**

```bash
uv sync --all-packages && uv run pytest tests/ -v
```
Expected: All tests PASSED (including existing Phase 1+2 tests)

- [ ] **Step 3: Verify app launches in mock mode**

```bash
SPID_HMI_MOCK_MODE=true uv run smart-pid-hmi
```
Expected: Window opens with gray ISA-101 theme, connection page displayed. Login with any credentials → dashboard with 3 controller cards, live trend, alarm bar.

- [ ] **Step 4: Commit**

```bash
git add packages/smart_pid_hmi/pyproject.toml
git commit -m "feat(hmi): add smart-pid-hmi console entry point"
```
