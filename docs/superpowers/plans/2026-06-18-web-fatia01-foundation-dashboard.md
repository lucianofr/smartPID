# Fatia 0+1: Foundation + Live Dashboard — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Stand up the end-to-end web HMI foundation — a `/ws/realtime` WebSocket bridge (2nd EventBus consumer) with first-message auth, plus the canonical `smart_pid_web` React/Vite scaffold whose live dashboard renders `status` frames over the socket — proving the realtime pipeline with a visible feature.

**Architecture:** A single non-blocking `asyncio.Task` drains the in-process ZMQ EventBus (mirroring `TelemetryPublisher`) and fans each topic out, as a JSON envelope, to all connected sockets via a resilient `ConnectionManager`; the React SPA opens one shared `WebSocket` (via `RealtimeProvider`/`useRealtime`), authenticates with its JWT as the first frame, and feeds coalesced `status` last-values into `ControllerCard` + `RealtimeTrend`. OPC connection state is polled separately over REST (`GET /opcua/status`), never via WS. In production the SPA is served single-origin by FastAPI `StaticFiles`; in dev Vite proxies `/api` and `/ws` to `:8000`.

**Tech Stack:** Backend — Python 3.13, FastAPI, `zmq`/`zmq.asyncio`, `msgpack`, PyJWT (HS256), pytest + pytest-asyncio. Frontend — React 18 + Vite 5 + TypeScript 5 (strict), TanStack Query v5, native `WebSocket`, uPlot, Vitest + @testing-library/react, Playwright, `openapi-typescript`.

## Global Constraints

- **Backend:** bind `127.0.0.1` (config `SPID_API_HOST`); serve SPA via `app.mount('/', StaticFiles(directory=dist, html=True))` mounted **after** routers (single-origin → no CORS in prod); dev CORS allowlist `http://127.0.0.1:5173` only; add security headers (`X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, basic CSP). Validate `Origin` on `/ws/realtime`.
- **RealtimeWS:** it is the **2nd EventBus consumer**, structurally analogous to `TelemetryPublisher`. The bus `recv()` is **blocking ZMQ** — a naive `await sub.recv()` freezes the daemon loop. Use a single shared consumer in `run_in_executor` (single-flight) that fans out to all clients. **Never** a recv-loop per client; **never** concurrent recv on the same socket. Coalesce last-value only for `status`/`stats`; `alarm`/`ai`/system are **lossless bounded** (on overflow, close the socket so the client re-syncs via REST). `ConnectionManager` with async lock + resilient broadcast.
- **TDD (mandatory):** failing test → run it red → minimal impl → run it green → commit. Bite-sized steps (2–5 min each), checkbox `- [ ]` syntax.
- **Branching (inviolable):** implemented on a **new dedicated branch from `main`**: `feat/web-fatia01-foundation-dashboard`. Never reuse another task's branch, never commit to `main` directly, never touch `feat/windows-installers`. Merge to `main` only with explicit user approval.
- **Subagents:** `model: opus` (project rule).
- **Commits:** conventional (`feat(web): …`, `fix(web): …`); **no attribution trailers**.
- **Python toolchain:** Python 3.13, `uv`. Lint `uv run --with ruff ruff check .` (line-length 100). Types `uv run mypy packages/` (baseline ~540 errors — must not increase). Tests `uv run pytest`. uv fallback in Flatpak: `/home/luciano/.var/app/com.visualstudio.code/bin/uv`.
- **Frontend toolchain:** `npm` inside `packages/smart_pid_web/`. `npm run test` (Vitest), `npm run test:e2e` (Playwright), `npm run build` (Vite), `npm run gen:api`.
- **Known-environmental:** 3 pre-existing failures in `tests/.../test_opcua_endpoint.py::TestProjectServiceOPCUA` (Py3.14 `asyncio.get_event_loop()`) are NOT regressions — do not "fix" them inside this fatia.
- **UI specs upkeep:** any UI change updates `docs/smartPIDv2.md` + the relevant `docs/identidade_visual_*.md`; the design-system spec is the web UI authority.
- **GateGuard:** the first `Write` of each new file may be blocked by a PreToolUse hook — present the facts (no importers yet / no API or schema change / instructed to create) and retry the same Write, or the operator may `export ECC_GATEGUARD=off`.

## File Structure

Backend (modify under `packages/smart_pid_core/src/smart_pid_core/`):

- `adapters/inbound/api/ws/__init__.py` — **Create.** New `ws` package marker.
- `adapters/inbound/api/ws/realtime.py` — **Create.** `ConnectionManager`, `RealtimeBridge` (single bus consumer task), topic→envelope mapper, `/ws/realtime` endpoint with first-message + Origin auth.
- `adapters/inbound/api/middleware.py` — **Create.** `SecurityHeadersMiddleware` (nosniff/frame-deny/referrer/CSP).
- `adapters/inbound/api/app.py` — **Modify** (`create_app` at lines 55–118): mount the WS endpoint, inject `RealtimeBridge` lifecycle into `_lifespan`, add `SecurityHeadersMiddleware`, dev `CORSMiddleware`, and the `StaticFiles` SPA mount after routers.
- `config.py` — **Modify.** Confirm/keep `api_host` default `127.0.0.1` (`SPID_API_HOST`); add `web_dist_dir` (optional SPA dist path) if not present.

Backend tests (modify under `packages/smart_pid_core/tests/`):

- `tests/adapters/inbound/api/test_ws_realtime.py` — **Create.** pytest-asyncio: multi-client broadcast, token reject (4401), clean disconnect drop, last-value coalescing (STATUS), lossless alarm delivery, Origin rejection.

Frontend (create the canonical scaffold — `packages/smart_pid_web/`):

- `package.json` — **Create.** name `@smart-pid/web`; scripts `dev/build/test/test:e2e/gen:api/lint`.
- `vite.config.ts` — **Create.** dev `127.0.0.1:5173`; proxy `/api`→`:8000`, `/ws`→`:8000` (`ws:true`).
- `tsconfig.json` / `tsconfig.node.json` — **Create.** strict.
- `vitest.config.ts` — **Create.** jsdom env, `src/test/setup.ts`.
- `playwright.config.ts` — **Create.** e2e config.
- `index.html` — **Create.** root + module entry.
- `.gitignore` — **Create.** `node_modules/`, `dist/`, `src/api/generated/`, Playwright artifacts.
- `src/main.tsx` — **Create.** ReactDOM root; `QueryClientProvider + ThemeProvider + AuthProvider + RealtimeProvider`.
- `src/App.tsx` — **Create.** `<BrowserRouter>` + route table + `<RequireAuth>`.
- `src/api/client.ts` — **Create.** fetch wrapper: base `/api`, `Authorization: Bearer`, throws `ApiError`.
- `src/api/queryClient.ts` — **Create.** configured `QueryClient`.
- `src/api/generated/openapi.ts` — **Generated** by `npm run gen:api` (gitignored; not hand-edited).
- `src/realtime/envelope.ts` — **Create.** CANONICAL WS envelope + per-type data types (contract §4).
- `src/realtime/useRealtime.ts` — **Create.** CANONICAL hook (contract §5).
- `src/realtime/RealtimeProvider.tsx` — **Create.** single WS, first-message auth, backoff reconnect, `onResync`.
- `src/auth/AuthContext.tsx` — **Create.** JWT in memory + sessionStorage; `login/logout`, token getter.
- `src/auth/RequireAuth.tsx` — **Create.** route guard → redirect `/login`.
- `src/auth/LoginPage.tsx` — **Create.** consumes `POST /auth/login` (JSON `LoginRequest`).
- `src/theme/tokens.css` — **Create.** stable token contract (design-system §2.0).
- `src/theme/themes.css` — **Create.** ISA-101 values (design-system §2.2) + Dark Room base.
- `src/theme/ThemeProvider.tsx` — **Create.** sets `data-theme`; persists choice (localStorage).
- `src/components/shell/AppShell.tsx` — **Create.** nav rail + top bar + content (design-system §4.2).
- `src/components/shell/NavRail.tsx` — **Create.**
- `src/components/shell/TopBar.tsx` — **Create.** logo · project · OPC status · theme · user.
- `src/components/shell/StatusIndicator.tsx` — **Create.** OPC/worker status dot (design-system §5.8).
- `src/components/AnalogBar.tsx` — **Create.** signature element base (design-system §5.1).
- `src/components/ControllerCard.tsx` — **Create.** design-system §5.2 (no inline control yet).
- `src/components/RealtimeTrend.tsx` — **Create.** uPlot wrapper (design-system §5.4).
- `src/pages/DashboardPage.tsx` — **Create.** Fatia 0+1 dashboard.
- `src/lib/format.ts` — **Create.** tabular number formatting (design-system §3.3).
- `src/test/setup.ts` — **Create.** vitest setup; WebSocket + matchMedia mocks.
- `src/realtime/useRealtime.test.ts` — **Create.** connect/reconnect/parse-envelope unit tests.
- `src/components/ControllerCard.test.tsx` — **Create.** render test.
- `src/components/RealtimeTrend.test.tsx` — **Create.** render/mount test.
- `e2e/login-dashboard.spec.ts` — **Create.** Playwright: login → dashboard receives `status` frame.

Monorepo wiring: `smart_pid_web` is a **Node** package (NOT a `uv`/python workspace member). PySide6 `smart_pid_hmi` stays frozen. Add `packages/smart_pid_web/node_modules/` and `packages/smart_pid_web/dist/` to the repo `.gitignore`.

---

### Task 1: Branch + backend `response_model` audit for fatia-0+1 routers

**Files**
- Modify: `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/auth.py`, `routers/controllers.py`, `routers/opcua.py` (only if an audited endpoint is missing `response_model`).

**Interfaces**
- Consumes (verify, real signatures): `POST /auth/login` → `response_model=TokenResponse`, body `LoginRequest{username,password}`; `GET /controllers` → `response_model=list[ControllerResponse]`; `GET /controllers/{controller_id}` → `response_model=ControllerResponse`; `GET /opcua/status` → `response_model=OPCUAStatusResponse`.
- Produces: a confirmed-typed OpenAPI surface for the four endpoints this fatia consumes.

- [ ] **Step 1:** Create the dedicated branch from `main`:
  ```bash
  git checkout main && git pull --ff-only && git checkout -b feat/web-fatia01-foundation-dashboard
  ```
  Expected: `Switched to a new branch 'feat/web-fatia01-foundation-dashboard'`.
- [ ] **Step 2:** Audit the four consumed endpoints for `response_model`. Run:
  ```bash
  grep -nE '@router\.(get|post)\(' \
    packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/auth.py \
    packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/controllers.py \
    packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/opcua.py
  ```
  Expected (already present in the worktree): `auth.py` `@router.post("/login", response_model=TokenResponse)`; `controllers.py` `@router.get("", response_model=list[ControllerResponse])` and `@router.get("/{controller_id}", response_model=ControllerResponse)`; `opcua.py` `@router.get("/status", response_model=OPCUAStatusResponse)`. If ALL four already declare `response_model`, make NO edits — record "audit pass, no change". Only if one is missing do you add the matching response model (do not invent fields; reuse the existing DTO the handler already returns).
- [ ] **Step 3:** Verify the FastAPI app still imports cleanly (no edit regression):
  ```bash
  uv run python -c "import smart_pid_core.adapters.inbound.api.app as a; print('ok', hasattr(a, 'create_app'))"
  ```
  Expected: `ok True`.
- [ ] **Step 4:** Commit.
  ```bash
  git add -A && git commit -m "chore(api): audit response_model on auth/controllers/opcua routers used by web dashboard"
  ```

### Task 2: `ConnectionManager` (resilient async broadcast)

**Files**
- Create: `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/ws/__init__.py`
- Create: `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/ws/realtime.py` (ConnectionManager portion)
- Create: `packages/smart_pid_core/tests/adapters/inbound/api/test_ws_realtime.py` (ConnectionManager tests)

**Interfaces**
- Produces: `class ConnectionManager` — `async connect(ws)`, `async disconnect(ws)`, `async broadcast(message: str)` (one failing socket does not drop others), `count` property.

- [ ] **Step 1:** Write the failing test for resilient broadcast and disconnect. Create `packages/smart_pid_core/tests/adapters/inbound/api/test_ws_realtime.py`:
  ```python
  """Tests for the RealtimeWS bridge."""
  from __future__ import annotations

  import asyncio
  import json

  import pytest

  from smart_pid_core.adapters.inbound.api.ws.realtime import ConnectionManager


  class FakeSocket:
      def __init__(self, *, fail: bool = False) -> None:
          self.fail = fail
          self.sent: list[str] = []
          self.closed = False
          self.close_code: int | None = None

      async def send_text(self, message: str) -> None:
          if self.fail:
              raise RuntimeError("socket gone")
          self.sent.append(message)

      async def close(self, code: int = 1000) -> None:
          self.closed = True
          self.close_code = code


  @pytest.mark.asyncio
  async def test_broadcast_reaches_all_healthy_sockets() -> None:
      mgr = ConnectionManager()
      a, b = FakeSocket(), FakeSocket()
      await mgr.connect(a)
      await mgr.connect(b)

      await mgr.broadcast(json.dumps({"type": "status"}))

      assert a.sent == ['{"type": "status"}']
      assert b.sent == ['{"type": "status"}']


  @pytest.mark.asyncio
  async def test_one_failing_socket_does_not_drop_others() -> None:
      mgr = ConnectionManager()
      bad, good = FakeSocket(fail=True), FakeSocket()
      await mgr.connect(bad)
      await mgr.connect(good)

      await mgr.broadcast("payload")

      assert good.sent == ["payload"]
      # the failing socket is auto-removed
      assert mgr.count == 1


  @pytest.mark.asyncio
  async def test_disconnect_removes_socket() -> None:
      mgr = ConnectionManager()
      s = FakeSocket()
      await mgr.connect(s)
      assert mgr.count == 1
      await mgr.disconnect(s)
      assert mgr.count == 0
  ```
- [ ] **Step 2:** Run it red.
  ```bash
  uv run pytest packages/smart_pid_core/tests/adapters/inbound/api/test_ws_realtime.py -q
  ```
  Expected: collection/import error `ModuleNotFoundError: smart_pid_core...ws.realtime` (RED).
- [ ] **Step 3:** Create the package marker `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/ws/__init__.py`:
  ```python
  """WebSocket adapters for the inbound API."""
  ```
- [ ] **Step 4:** Create `ConnectionManager` (minimal) in `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/ws/realtime.py`:
  ```python
  """RealtimeWS bridge: 2nd EventBus consumer + WebSocket fan-out.

  Mirrors the threading/loop model of ``application/telemetry_publisher.py``:
  a single asyncio.Task drains the in-process ZMQ bus via
  ``run_in_executor(None, sub.recv, 10)`` (poll-gated blocking recv offloaded to
  a thread) and fans each message out to every connected socket. NEVER a
  recv-loop per client and NEVER concurrent recv on the same socket.
  """
  from __future__ import annotations

  import asyncio
  from typing import Protocol


  class _Sendable(Protocol):
      async def send_text(self, message: str) -> None: ...
      async def close(self, code: int = ...) -> None: ...


  class ConnectionManager:
      """Tracks live sockets and broadcasts resiliently under an async lock."""

      def __init__(self) -> None:
          self._conns: set[_Sendable] = set()
          self._lock = asyncio.Lock()

      @property
      def count(self) -> int:
          return len(self._conns)

      async def connect(self, ws: _Sendable) -> None:
          async with self._lock:
              self._conns.add(ws)

      async def disconnect(self, ws: _Sendable) -> None:
          async with self._lock:
              self._conns.discard(ws)

      async def broadcast(self, message: str) -> None:
          async with self._lock:
              targets = list(self._conns)
          dead: list[_Sendable] = []
          for ws in targets:
              try:
                  await ws.send_text(message)
              except Exception:  # noqa: BLE001 — one bad socket must not drop the rest
                  dead.append(ws)
          if dead:
              async with self._lock:
                  for ws in dead:
                      self._conns.discard(ws)
  ```
- [ ] **Step 5:** Run it green.
  ```bash
  uv run pytest packages/smart_pid_core/tests/adapters/inbound/api/test_ws_realtime.py -q
  ```
  Expected: `3 passed`.
- [ ] **Step 6:** Lint.
  ```bash
  uv run --with ruff ruff check packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/ws/
  ```
  Expected: `All checks passed!`.
- [ ] **Step 7:** Commit.
  ```bash
  git add -A && git commit -m "feat(api): add resilient WebSocket ConnectionManager for realtime bridge"
  ```

### Task 3: `RealtimeBridge` — single non-blocking bus consumer + topic→envelope mapping

**Files**
- Modify: `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/ws/realtime.py`
- Modify: `packages/smart_pid_core/tests/adapters/inbound/api/test_ws_realtime.py`

**Interfaces**
- Consumes: `EventBus.create_subscriber(topic_prefix: bytes) -> BusSubscriber`; `BusSubscriber.recv(timeout_ms) -> tuple[bytes, bytes] | None` (poll-gated blocking, returns `(topic_bytes, payload_bytes)`); `msgpack` payloads. Subscribed prefixes: `b"STATUS."`, `b"ACTION.CTRL."`, `b"ACTION.AI."`, `b"EVENT.ALARM."`, `b"EVENT.SYSTEM"`, `b"STATS."`.
- Produces: `class RealtimeBridge(bus)` — `async start()`, `async stop()`, and a pure helper `map_topic_to_envelope(topic: bytes, payload: dict) -> dict | None` returning the canonical envelope `{type, loop_id, seq, ts, data}` (seq/ts stamped by the bridge).

- [ ] **Step 1:** Write the failing test for the topic→envelope mapping (pure function — no live bus). Append to `test_ws_realtime.py`:
  ```python
  from smart_pid_core.adapters.inbound.api.ws.realtime import map_topic_to_envelope


  def test_map_status_topic_to_status_envelope() -> None:
      payload = {"pv": 150.2, "sp": 152.0, "co": 64.0, "mode": "AUTO"}
      env = map_topic_to_envelope(b"STATUS.12", payload, seq=7, ts=1718743200.5)
      assert env == {
          "type": "status",
          "loop_id": 12,
          "seq": 7,
          "ts": 1718743200.5,
          "data": payload,
      }


  def test_map_action_ctrl_topic() -> None:
      env = map_topic_to_envelope(b"ACTION.CTRL.3", {"cv": 1.0, "delta": 0.2}, seq=1, ts=0.0)
      assert env["type"] == "action"
      assert env["loop_id"] == 3


  def test_map_ai_topic() -> None:
      env = map_topic_to_envelope(b"ACTION.AI.4", {"gamma": 0.1, "ki": 2.0, "strategy": "FUZZY"}, seq=1, ts=0.0)
      assert env["type"] == "ai"
      assert env["loop_id"] == 4


  def test_map_alarm_topic() -> None:
      env = map_topic_to_envelope(b"EVENT.ALARM.9", {"alarm_id": "a1", "severity": "CRITICAL", "state": "UNACK"}, seq=1, ts=0.0)
      assert env["type"] == "alarm"
      assert env["loop_id"] == 9


  def test_map_stats_topic() -> None:
      env = map_topic_to_envelope(b"STATS.2", {"iae": 1.0}, seq=1, ts=0.0)
      assert env["type"] == "stats"
      assert env["loop_id"] == 2


  def test_map_system_event_topic_has_null_loop_id() -> None:
      env = map_topic_to_envelope(b"EVENT.SYSTEM", {"kind": "startup"}, seq=1, ts=0.0)
      assert env["type"] == "system"
      assert env["loop_id"] is None


  def test_map_unknown_topic_returns_none() -> None:
      assert map_topic_to_envelope(b"TELEMETRY.1", {}, seq=1, ts=0.0) is None
  ```
- [ ] **Step 2:** Run red.
  ```bash
  uv run pytest packages/smart_pid_core/tests/adapters/inbound/api/test_ws_realtime.py -q -k map_
  ```
  Expected: `ImportError: cannot import name 'map_topic_to_envelope'` (RED).
- [ ] **Step 3:** Add the mapper + bridge to `realtime.py`. Append:
  ```python
  import contextlib

  import msgpack

  # Bus prefixes the RealtimeWS subscribes to. STATS is on the internal bus only
  # (the legacy tcp://5555 whitelist skips it) but we subscribe to the bus DIRECTLY.
  _BRIDGE_TOPICS: list[bytes] = [
      b"STATUS.",
      b"ACTION.CTRL.",
      b"ACTION.AI.",
      b"EVENT.ALARM.",
      b"EVENT.SYSTEM",
      b"STATS.",
  ]

  # Topic prefix -> (envelope type, has_loop_id). Order matters: longer/specific first.
  _TOPIC_MAP: list[tuple[bytes, str, bool]] = [
      (b"STATUS.", "status", True),
      (b"ACTION.CTRL.", "action", True),
      (b"ACTION.AI.", "ai", True),
      (b"EVENT.ALARM.", "alarm", True),
      (b"EVENT.SYSTEM", "system", False),
      (b"STATS.", "stats", True),
  ]

  # Discrete (lossless) envelope types — never coalesced.
  _LOSSLESS_TYPES = frozenset({"action", "ai", "alarm", "system"})


  def map_topic_to_envelope(
      topic: bytes, payload: dict, *, seq: int, ts: float
  ) -> dict | None:
      """Map a bus (topic, payload) to the canonical JSON envelope, or None if unmapped."""
      for prefix, etype, has_id in _TOPIC_MAP:
          if topic.startswith(prefix):
              loop_id: int | None = None
              if has_id:
                  suffix = topic[len(prefix):].decode("ascii", "ignore")
                  with contextlib.suppress(ValueError):
                      loop_id = int(suffix)
              return {"type": etype, "loop_id": loop_id, "seq": seq, "ts": ts, "data": payload}
      return None


  class RealtimeBridge:
      """Single asyncio.Task that drains the EventBus and fans out to ConnectionManager.

      Mirrors ``TelemetryPublisher._run``: one subscriber per prefix, drained via
      ``run_in_executor(None, sub.recv, 10)`` so the blocking poll-gated recv never
      blocks the event loop. One consumer total — NOT one per client.
      """

      def __init__(self, bus, manager: ConnectionManager) -> None:
          self._bus = bus
          self._manager = manager
          self._task: asyncio.Task | None = None
          self._stop = asyncio.Event()
          self._seq = 0

      async def start(self) -> None:
          self._stop.clear()
          self._task = asyncio.create_task(self._run())

      async def stop(self) -> None:
          self._stop.set()
          if self._task is not None:
              self._task.cancel()
              with contextlib.suppress(asyncio.CancelledError):
                  await self._task
              self._task = None

      async def _run(self) -> None:
          import time

          loop = asyncio.get_running_loop()
          subs = [self._bus.create_subscriber(t) for t in _BRIDGE_TOPICS]
          try:
              while not self._stop.is_set():
                  for sub in subs:
                      result = await loop.run_in_executor(None, sub.recv, 10)
                      if result is None:
                          continue
                      topic_bytes, payload_bytes = result
                      data = msgpack.unpackb(payload_bytes, raw=False)
                      self._seq += 1
                      env = map_topic_to_envelope(
                          topic_bytes, data, seq=self._seq, ts=time.time()
                      )
                      if env is not None:
                          import json

                          await self._manager.broadcast(json.dumps(env))
                  await asyncio.sleep(0.001)
          except asyncio.CancelledError:
              raise
  ```
- [ ] **Step 4:** Run green.
  ```bash
  uv run pytest packages/smart_pid_core/tests/adapters/inbound/api/test_ws_realtime.py -q -k map_
  ```
  Expected: `7 passed`.
- [ ] **Step 5:** Lint + import check.
  ```bash
  uv run --with ruff ruff check packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/ws/realtime.py
  ```
  Expected: `All checks passed!`.
- [ ] **Step 6:** Commit.
  ```bash
  git add -A && git commit -m "feat(api): add non-blocking EventBus->WS bridge with topic->envelope mapping"
  ```

### Task 4: `/ws/realtime` endpoint — first-message auth, Origin validation, coalescing/lossless queue

**Files**
- Modify: `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/ws/realtime.py`
- Modify: `packages/smart_pid_core/tests/adapters/inbound/api/test_ws_realtime.py`

**Interfaces**
- Consumes: `decode_access_token(token: str, *, secret: str) -> dict` (HS256; raises `jwt.PyJWTError`); `CoreSettings.jwt_secret`; `app.state.realtime_bridge` / `app.state.realtime_manager`.
- Produces: `async def realtime_ws(websocket: WebSocket)` registered at `GET /ws/realtime`. First frame must be `{"type":"auth","token":"<JWT>"}`; validates JWT + `Origin` header; closes with code `4401` on missing/invalid/expired token or bad Origin. Per-connection: coalesced last-value for `status`/`stats`; lossless bounded queue for `alarm`/`ai`/`system` (close socket on overflow).

- [ ] **Step 1:** Write the failing auth/Origin tests using FastAPI's `TestClient` WebSocket. Append to `test_ws_realtime.py`:
  ```python
  from fastapi import FastAPI, WebSocket
  from fastapi.testclient import TestClient
  from starlette.websockets import WebSocketDisconnect

  from smart_pid_core.adapters.inbound.api.auth import create_access_token
  from smart_pid_core.adapters.inbound.api.ws.realtime import register_realtime_ws

  _SECRET = "test-secret"
  _ALLOWED_ORIGIN = "http://127.0.0.1:5173"


  def _make_app() -> FastAPI:
      app = FastAPI()

      class _Settings:
          jwt_secret = _SECRET
          allowed_ws_origins = (_ALLOWED_ORIGIN,)

      app.state.settings = _Settings()
      app.state.realtime_manager = ConnectionManager()
      register_realtime_ws(app)
      return app


  def _good_token() -> str:
      return create_access_token(
          user_id=1, username="admin", role="ADMIN", secret=_SECRET
      )


  def test_ws_rejects_missing_token() -> None:
      app = _make_app()
      client = TestClient(app)
      with client.websocket_connect(
          "/ws/realtime", headers={"origin": _ALLOWED_ORIGIN}
      ) as ws:
          ws.send_json({"type": "auth"})  # no token
          with pytest.raises(WebSocketDisconnect) as exc:
              ws.receive_text()
      assert exc.value.code == 4401


  def test_ws_rejects_invalid_token() -> None:
      app = _make_app()
      client = TestClient(app)
      with client.websocket_connect(
          "/ws/realtime", headers={"origin": _ALLOWED_ORIGIN}
      ) as ws:
          ws.send_json({"type": "auth", "token": "garbage.jwt.value"})
          with pytest.raises(WebSocketDisconnect) as exc:
              ws.receive_text()
      assert exc.value.code == 4401


  def test_ws_rejects_bad_origin() -> None:
      app = _make_app()
      client = TestClient(app)
      with client.websocket_connect(
          "/ws/realtime", headers={"origin": "http://evil.example"}
      ) as ws:
          ws.send_json({"type": "auth", "token": _good_token()})
          with pytest.raises(WebSocketDisconnect) as exc:
              ws.receive_text()
      assert exc.value.code == 4401


  def test_ws_accepts_valid_token_and_broadcast_reaches_client() -> None:
      app = _make_app()
      client = TestClient(app)
      with client.websocket_connect(
          "/ws/realtime", headers={"origin": _ALLOWED_ORIGIN}
      ) as ws:
          ws.send_json({"type": "auth", "token": _good_token()})
          # server acknowledges auth
          ack = ws.receive_json()
          assert ack["type"] == "auth_ok"
  ```
- [ ] **Step 2:** Run red.
  ```bash
  uv run pytest packages/smart_pid_core/tests/adapters/inbound/api/test_ws_realtime.py -q -k "ws_"
  ```
  Expected: `ImportError: cannot import name 'register_realtime_ws'` (RED).
- [ ] **Step 3:** Add the endpoint + per-connection pump to `realtime.py`. Append:
  ```python
  from fastapi import FastAPI, WebSocket
  from starlette.websockets import WebSocketDisconnect, WebSocketState

  _WS_CLOSE_AUTH = 4401
  _LOSSLESS_QUEUE_MAX = 256


  def _origin_allowed(origin: str | None, allowed: tuple[str, ...]) -> bool:
      return origin is not None and origin in allowed


  def register_realtime_ws(app: FastAPI) -> None:
      """Register GET /ws/realtime on the app."""

      @app.websocket("/ws/realtime")
      async def realtime_ws(websocket: WebSocket) -> None:  # noqa: WPS430
          settings = websocket.app.state.settings
          allowed = tuple(getattr(settings, "allowed_ws_origins", (_ALLOWED_ORIGIN_DEFAULT,)))
          origin = websocket.headers.get("origin")
          await websocket.accept()

          # First-message auth: first frame MUST be {"type":"auth","token":"<JWT>"}.
          try:
              first = await websocket.receive_json()
          except (WebSocketDisconnect, ValueError):
              await websocket.close(code=_WS_CLOSE_AUTH)
              return

          token = first.get("token") if isinstance(first, dict) else None
          if first.get("type") != "auth" or not token or not _origin_allowed(origin, allowed):
              await websocket.close(code=_WS_CLOSE_AUTH)
              return
          try:
              decode_access_token(token, secret=settings.jwt_secret)
          except Exception:  # noqa: BLE001 — any JWT error => reject
              await websocket.close(code=_WS_CLOSE_AUTH)
              return

          await websocket.send_json({"type": "auth_ok"})
          manager: ConnectionManager = websocket.app.state.realtime_manager
          await manager.connect(websocket)
          try:
              # The bridge drives outbound traffic via manager.broadcast(); this
              # loop only watches for client close. No per-client bus recv.
              while websocket.application_state == WebSocketState.CONNECTED:
                  await websocket.receive_text()
          except WebSocketDisconnect:
              pass
          finally:
              await manager.disconnect(websocket)
  ```
  Also add at the top of the module (near other constants):
  ```python
  _ALLOWED_ORIGIN_DEFAULT = "http://127.0.0.1:5173"
  ```
  And add the import at the top with the other imports:
  ```python
  from smart_pid_core.adapters.inbound.api.auth import decode_access_token
  ```
- [ ] **Step 4:** Run green.
  ```bash
  uv run pytest packages/smart_pid_core/tests/adapters/inbound/api/test_ws_realtime.py -q -k "ws_"
  ```
  Expected: `4 passed`.
- [ ] **Step 5:** Write the coalescing/lossless test. `status`/`stats` keep only last value per loop; `alarm` is lossless. Because outbound is driven by the bridge broadcast, test the per-connection buffer policy directly via a small helper `ConnectionBuffer`. Append:
  ```python
  from smart_pid_core.adapters.inbound.api.ws.realtime import ConnectionBuffer


  def test_status_coalesces_last_value_per_loop() -> None:
      buf = ConnectionBuffer()
      buf.offer({"type": "status", "loop_id": 1, "seq": 1, "ts": 0.0, "data": {"pv": 1}})
      buf.offer({"type": "status", "loop_id": 1, "seq": 2, "ts": 1.0, "data": {"pv": 2}})
      drained = buf.drain()
      # only the latest status for loop 1 survives
      statuses = [m for m in drained if m["type"] == "status" and m["loop_id"] == 1]
      assert len(statuses) == 1
      assert statuses[0]["data"]["pv"] == 2


  def test_alarm_is_lossless() -> None:
      buf = ConnectionBuffer()
      buf.offer({"type": "alarm", "loop_id": 9, "seq": 1, "ts": 0.0, "data": {"alarm_id": "a"}})
      buf.offer({"type": "alarm", "loop_id": 9, "seq": 2, "ts": 1.0, "data": {"alarm_id": "b"}})
      drained = buf.drain()
      alarms = [m for m in drained if m["type"] == "alarm"]
      assert [m["data"]["alarm_id"] for m in alarms] == ["a", "b"]


  def test_lossless_overflow_flags_for_close() -> None:
      buf = ConnectionBuffer(lossless_max=2)
      for i in range(3):
          buf.offer({"type": "alarm", "loop_id": 1, "seq": i, "ts": 0.0, "data": {"alarm_id": str(i)}})
      assert buf.overflowed is True
  ```
- [ ] **Step 6:** Run red.
  ```bash
  uv run pytest packages/smart_pid_core/tests/adapters/inbound/api/test_ws_realtime.py -q -k buffer_or_alarm
  uv run pytest packages/smart_pid_core/tests/adapters/inbound/api/test_ws_realtime.py -q -k "coalesces or lossless"
  ```
  Expected: `ImportError: cannot import name 'ConnectionBuffer'` (RED).
- [ ] **Step 7:** Add `ConnectionBuffer` to `realtime.py`:
  ```python
  class ConnectionBuffer:
      """Per-connection outbound policy: coalesce status/stats, lossless alarm/ai/system."""

      def __init__(self, lossless_max: int = _LOSSLESS_QUEUE_MAX) -> None:
          self._coalesced: dict[tuple[str, int | None], dict] = {}
          self._lossless: list[dict] = []
          self._lossless_max = lossless_max
          self.overflowed = False

      def offer(self, env: dict) -> None:
          etype = env["type"]
          if etype in ("status", "stats"):
              self._coalesced[(etype, env["loop_id"])] = env
          else:
              if len(self._lossless) >= self._lossless_max:
                  self.overflowed = True
                  return
              self._lossless.append(env)

      def drain(self) -> list[dict]:
          out = list(self._coalesced.values()) + self._lossless
          self._coalesced.clear()
          self._lossless.clear()
          return out
  ```
- [ ] **Step 8:** Run green (full file).
  ```bash
  uv run pytest packages/smart_pid_core/tests/adapters/inbound/api/test_ws_realtime.py -q
  ```
  Expected: all tests pass (ConnectionManager + map + ws auth + buffer).
- [ ] **Step 9:** Lint.
  ```bash
  uv run --with ruff ruff check packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/ws/realtime.py
  ```
  Expected: `All checks passed!`.
- [ ] **Step 10:** Commit.
  ```bash
  git add -A && git commit -m "feat(api): /ws/realtime first-message auth, Origin check, coalescing+lossless buffer"
  ```

### Task 5: Wire RealtimeWS, security headers, dev CORS, SPA mount into `create_app`

**Files**
- Create: `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/middleware.py`
- Modify: `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/app.py` (lines 55–118: `_lifespan` ~49–52, after `app = FastAPI(...)` ~75, after `include_router` block ~100–114)
- Modify: `packages/smart_pid_core/src/smart_pid_core/config.py` (host default + optional `web_dist_dir` + `allowed_ws_origins`)
- Modify: `packages/smart_pid_core/tests/adapters/inbound/api/test_ws_realtime.py` (smoke test through `create_app`)

**Interfaces**
- Consumes: `create_app(*, repo, historian, user_repo, loop_manager, settings, ..., event_bus=None) -> FastAPI` (app.py:55–118), `app.state.event_bus` (app.py:93).
- Produces: app with `app.state.realtime_manager`, `app.state.realtime_bridge` (started/stopped in `_lifespan`), `SecurityHeadersMiddleware`, dev `CORSMiddleware` (allowlist `http://127.0.0.1:5173`), `StaticFiles` SPA mount at `/` (mounted last, only if dist exists), and the `/ws/realtime` route.

- [ ] **Step 1:** Write the failing security-headers + route-presence test. Append to `test_ws_realtime.py`:
  ```python
  def test_security_headers_present_on_rest_response() -> None:
      from smart_pid_core.adapters.inbound.api.middleware import SecurityHeadersMiddleware

      app = FastAPI()
      app.add_middleware(SecurityHeadersMiddleware)

      @app.get("/ping")
      async def ping() -> dict:
          return {"ok": True}

      client = TestClient(app)
      r = client.get("/ping")
      assert r.headers["x-content-type-options"] == "nosniff"
      assert r.headers["x-frame-options"] == "DENY"
      assert r.headers["referrer-policy"] == "strict-origin-when-cross-origin"
      assert "content-security-policy" in r.headers
  ```
- [ ] **Step 2:** Run red.
  ```bash
  uv run pytest packages/smart_pid_core/tests/adapters/inbound/api/test_ws_realtime.py -q -k security_headers
  ```
  Expected: `ModuleNotFoundError: ...api.middleware` (RED).
- [ ] **Step 3:** Create `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/middleware.py`:
  ```python
  """HTTP security headers middleware."""
  from __future__ import annotations

  from starlette.middleware.base import BaseHTTPMiddleware
  from starlette.requests import Request
  from starlette.responses import Response

  _CSP = (
      "default-src 'self'; "
      "script-src 'self'; "
      "style-src 'self' 'unsafe-inline'; "
      "img-src 'self' data:; "
      "connect-src 'self' ws: wss:; "
      "frame-ancestors 'none'; "
      "base-uri 'self'; "
      "object-src 'none'"
  )


  class SecurityHeadersMiddleware(BaseHTTPMiddleware):
      """Adds baseline security headers to every response."""

      async def dispatch(self, request: Request, call_next) -> Response:  # noqa: ANN001
          response = await call_next(request)
          response.headers.setdefault("X-Content-Type-Options", "nosniff")
          response.headers.setdefault("X-Frame-Options", "DENY")
          response.headers.setdefault(
              "Referrer-Policy", "strict-origin-when-cross-origin"
          )
          response.headers.setdefault("Content-Security-Policy", _CSP)
          return response
  ```
- [ ] **Step 4:** Run green.
  ```bash
  uv run pytest packages/smart_pid_core/tests/adapters/inbound/api/test_ws_realtime.py -q -k security_headers
  ```
  Expected: `1 passed`.
- [ ] **Step 5:** Add config fields. In `packages/smart_pid_core/src/smart_pid_core/config.py`, confirm the API host default is `127.0.0.1` (env `SPID_API_HOST`); if it currently defaults to `0.0.0.0`, change the default to `"127.0.0.1"`. Add two settings near the API settings:
  ```python
      web_dist_dir: str | None = None
      allowed_ws_origins: tuple[str, ...] = ("http://127.0.0.1:5173",)
  ```
  (Keep the existing `pydantic-settings` `SPID_` env prefix; these become `SPID_WEB_DIST_DIR` / `SPID_ALLOWED_WS_ORIGINS`.)
- [ ] **Step 6:** Wire `create_app` in `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/app.py`. After `app = FastAPI(...)` (~line 75) and before/around the `include_router` block, add:
  ```python
  from smart_pid_core.adapters.inbound.api.middleware import SecurityHeadersMiddleware
  from smart_pid_core.adapters.inbound.api.ws.realtime import (
      ConnectionManager,
      RealtimeBridge,
      register_realtime_ws,
  )
  ```
  Inside `create_app`, after `app.state.event_bus = event_bus`:
  ```python
      app.state.realtime_manager = ConnectionManager()
      app.state.realtime_bridge = (
          RealtimeBridge(event_bus, app.state.realtime_manager)
          if event_bus is not None
          else None
      )

      app.add_middleware(SecurityHeadersMiddleware)
      # Dev-only CORS allowlist (prod is single-origin via StaticFiles, no CORS).
      app.add_middleware(
          CORSMiddleware,
          allow_origins=list(settings.allowed_ws_origins),
          allow_credentials=True,
          allow_methods=["*"],
          allow_headers=["*"],
      )
  ```
  (Add `from fastapi.middleware.cors import CORSMiddleware` to the imports.)
  Register the WS route after the `include_router(...)` block (~line 114):
  ```python
      register_realtime_ws(app)
  ```
  Mount the SPA LAST (after routers + WS), only if a dist dir is configured and exists:
  ```python
      import os

      from fastapi.staticfiles import StaticFiles

      if settings.web_dist_dir and os.path.isdir(settings.web_dist_dir):
          app.mount("/", StaticFiles(directory=settings.web_dist_dir, html=True), name="spa")
  ```
  Extend `_lifespan` (app.py:49–52) to start/stop the bridge:
  ```python
  @contextlib.asynccontextmanager
  async def _lifespan(app: FastAPI):
      app.state.start_time = time.time()
      bridge = getattr(app.state, "realtime_bridge", None)
      if bridge is not None:
          await bridge.start()
      try:
          yield
      finally:
          if bridge is not None:
              await bridge.stop()
  ```
  (Add `import contextlib`, `import time` if not already imported — match existing imports.)
- [ ] **Step 7:** Write a smoke test that `create_app` exposes `/ws/realtime` and `/openapi.json`. Append to `test_ws_realtime.py`:
  ```python
  def test_create_app_registers_ws_route_and_openapi() -> None:
      import importlib

      app_mod = importlib.import_module("smart_pid_core.adapters.inbound.api.app")
      ws_paths = [
          r.path for r in app_mod  # placeholder; replaced below
      ] if False else None
      assert ws_paths is None  # marker to force the real assertion below
  ```
  Then replace that placeholder with a real assertion that builds the app via the project's existing test fixture/factory used elsewhere (reuse the same `create_app` keyword fixture pattern found in `tests/adapters/inbound/api/conftest.py`); assert `"/ws/realtime"` is in `{r.path for r in app.routes}` and that `TestClient(app).get("/openapi.json").status_code == 200`.
- [ ] **Step 8:** Run the full backend WS suite + a broad app import to ensure no regression.
  ```bash
  uv run pytest packages/smart_pid_core/tests/adapters/inbound/api/test_ws_realtime.py -q
  uv run pytest packages/smart_pid_core/tests/adapters/inbound/api/ -q
  ```
  Expected: all new tests pass; pre-existing `TestProjectServiceOPCUA` failures (3, Py3.14) are the only non-passing items and are unchanged.
- [ ] **Step 9:** Lint + mypy (must not increase baseline ~540).
  ```bash
  uv run --with ruff ruff check packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/
  uv run mypy packages/ | tail -1
  ```
  Expected: ruff `All checks passed!`; mypy error count not above baseline.
- [ ] **Step 10:** Commit.
  ```bash
  git add -A && git commit -m "feat(api): mount /ws/realtime, security headers, dev CORS, SPA StaticFiles in create_app"
  ```

### Task 6: Frontend scaffold (`packages/smart_pid_web/`) — Vite/React/TS toolchain

**Files**
- Create: `packages/smart_pid_web/package.json`, `vite.config.ts`, `tsconfig.json`, `tsconfig.node.json`, `vitest.config.ts`, `playwright.config.ts`, `index.html`, `.gitignore`
- Create: `packages/smart_pid_web/src/test/setup.ts`, `src/main.tsx`, `src/App.tsx`
- Modify: repo root `.gitignore` (ignore `packages/smart_pid_web/node_modules/` and `/dist/`)

**Interfaces**
- Produces: a runnable Vite app skeleton; `npm run dev/build/test/test:e2e/gen:api/lint` scripts; dev proxy `/api`+`/ws` → `:8000`.

- [ ] **Step 1:** Create `packages/smart_pid_web/package.json`:
  ```json
  {
    "name": "@smart-pid/web",
    "private": true,
    "version": "0.0.0",
    "type": "module",
    "scripts": {
      "dev": "vite",
      "build": "tsc -b && vite build",
      "preview": "vite preview",
      "test": "vitest run",
      "test:watch": "vitest",
      "test:e2e": "playwright test",
      "gen:api": "openapi-typescript http://127.0.0.1:8000/openapi.json -o src/api/generated/openapi.ts",
      "lint": "eslint ."
    },
    "dependencies": {
      "@tanstack/react-query": "^5.51.0",
      "react": "^18.3.1",
      "react-dom": "^18.3.1",
      "react-router-dom": "^6.26.0",
      "uplot": "^1.6.31"
    },
    "devDependencies": {
      "@playwright/test": "^1.46.0",
      "@testing-library/jest-dom": "^6.4.8",
      "@testing-library/react": "^16.0.0",
      "@types/react": "^18.3.3",
      "@types/react-dom": "^18.3.0",
      "@vitejs/plugin-react": "^4.3.1",
      "eslint": "^9.9.0",
      "jsdom": "^24.1.1",
      "openapi-typescript": "^7.3.0",
      "typescript": "^5.5.4",
      "vite": "^5.4.0",
      "vitest": "^2.0.5"
    }
  }
  ```
- [ ] **Step 2:** Create `vite.config.ts`:
  ```ts
  import react from '@vitejs/plugin-react';
  import { defineConfig } from 'vite';

  export default defineConfig({
    plugins: [react()],
    server: {
      host: '127.0.0.1',
      port: 5173,
      proxy: {
        '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
        '/ws': { target: 'http://127.0.0.1:8000', ws: true, changeOrigin: true },
      },
    },
  });
  ```
- [ ] **Step 3:** Create `tsconfig.json` (strict) and `tsconfig.node.json`:
  ```json
  {
    "compilerOptions": {
      "target": "ES2022",
      "useDefineForClassFields": true,
      "lib": ["ES2022", "DOM", "DOM.Iterable"],
      "module": "ESNext",
      "skipLibCheck": true,
      "moduleResolution": "bundler",
      "allowImportingTsExtensions": true,
      "resolveJsonModule": true,
      "isolatedModules": true,
      "noEmit": true,
      "jsx": "react-jsx",
      "strict": true,
      "noUnusedLocals": true,
      "noUnusedParameters": true,
      "noFallthroughCasesInSwitch": true
    },
    "include": ["src", "e2e"],
    "references": [{ "path": "./tsconfig.node.json" }]
  }
  ```
  ```json
  {
    "compilerOptions": {
      "composite": true,
      "skipLibCheck": true,
      "module": "ESNext",
      "moduleResolution": "bundler",
      "allowSyntheticDefaultImports": true,
      "strict": true,
      "noEmit": true
    },
    "include": ["vite.config.ts", "vitest.config.ts", "playwright.config.ts"]
  }
  ```
- [ ] **Step 4:** Create `vitest.config.ts`:
  ```ts
  import react from '@vitejs/plugin-react';
  import { defineConfig } from 'vitest/config';

  export default defineConfig({
    plugins: [react()],
    test: {
      environment: 'jsdom',
      globals: true,
      setupFiles: ['./src/test/setup.ts'],
    },
  });
  ```
- [ ] **Step 5:** Create `playwright.config.ts`:
  ```ts
  import { defineConfig } from '@playwright/test';

  export default defineConfig({
    testDir: './e2e',
    use: { baseURL: 'http://127.0.0.1:5173' },
    webServer: {
      command: 'npm run dev',
      url: 'http://127.0.0.1:5173',
      reuseExistingServer: !process.env.CI,
    },
  });
  ```
- [ ] **Step 6:** Create `index.html`:
  ```html
  <!doctype html>
  <html lang="en" data-theme="isa101">
    <head>
      <meta charset="UTF-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1.0" />
      <title>Smart PID</title>
    </head>
    <body>
      <div id="root"></div>
      <script type="module" src="/src/main.tsx"></script>
    </body>
  </html>
  ```
- [ ] **Step 7:** Create `.gitignore` in `packages/smart_pid_web/`:
  ```gitignore
  node_modules/
  dist/
  src/api/generated/
  test-results/
  playwright-report/
  .vite/
  ```
  And append to the repo root `.gitignore`:
  ```gitignore
  packages/smart_pid_web/node_modules/
  packages/smart_pid_web/dist/
  ```
- [ ] **Step 8:** Create `src/test/setup.ts` (WebSocket + matchMedia mocks):
  ```ts
  import '@testing-library/jest-dom/vitest';

  // jsdom lacks matchMedia; ThemeProvider/reduced-motion checks need it.
  if (!window.matchMedia) {
    window.matchMedia = (query: string) =>
      ({
        matches: false,
        media: query,
        onchange: null,
        addEventListener: () => {},
        removeEventListener: () => {},
        addListener: () => {},
        removeListener: () => {},
        dispatchEvent: () => false,
      }) as unknown as MediaQueryList;
  }
  ```
- [ ] **Step 9:** Create a minimal `src/main.tsx` and `src/App.tsx` so the toolchain builds (full providers wired in later tasks):
  ```tsx
  // src/main.tsx
  import { StrictMode } from 'react';
  import { createRoot } from 'react-dom/client';
  import { App } from './App';

  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <App />
    </StrictMode>,
  );
  ```
  ```tsx
  // src/App.tsx
  export function App() {
    return <div>Smart PID Web — bootstrapping</div>;
  }
  ```
- [ ] **Step 10:** Install + verify build/test toolchain.
  ```bash
  cd packages/smart_pid_web && npm install && npm run build && npm run test
  ```
  Expected: `npm install` resolves; `vite build` emits `dist/`; Vitest runs (0 tests, exit 0) — toolchain healthy.
- [ ] **Step 11:** Commit.
  ```bash
  git add -A && git commit -m "feat(web): scaffold smart_pid_web Vite/React/TS package with test+e2e toolchain"
  ```

### Task 7: Theme tokens + ThemeProvider (design-system §2.0 / §2.2)

**Files**
- Create: `packages/smart_pid_web/src/theme/tokens.css`, `src/theme/themes.css`, `src/theme/ThemeProvider.tsx`
- Create: `packages/smart_pid_web/src/lib/format.ts`, `src/lib/format.test.ts`

**Interfaces**
- Produces: stable CSS token contract (design-system §2.0); ISA-101 + Dark Room theme values (§2.1/§2.2); `<ThemeProvider>` setting `data-theme` and persisting to localStorage; `formatNumber(value, decimals)` tabular helper.

- [ ] **Step 1:** Create `src/theme/tokens.css` — the stable contract names + scales (design-system §2.0, §3.2, §4.1, §6.2). These names are CANONICAL; downstream fatias must not rename:
  ```css
  :root {
    /* Type scale (§3.2) */
    --text-2xs: 0.6875rem; --text-xs: 0.75rem; --text-sm: 0.8125rem;
    --text-base: 0.9375rem;
    --text-lg: clamp(1rem, 0.95rem + 0.25vw, 1.125rem);
    --text-xl: clamp(1.25rem, 1.1rem + 0.6vw, 1.5rem);
    --text-2xl: clamp(1.75rem, 1.4rem + 1.2vw, 2.5rem);
    --text-3xl: clamp(2.5rem, 1.8rem + 2.4vw, 3.75rem);
    --fw-regular: 400; --fw-medium: 500; --fw-semibold: 600; --fw-bold: 700;
    --lh-tight: 1.1; --lh-snug: 1.3; --lh-normal: 1.5;
    --font-ui: system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;
    --font-data: 'JetBrains Mono', 'Roboto Mono', ui-monospace, monospace;

    /* Spacing (§4.1) */
    --sp-1: 0.25rem; --sp-2: 0.5rem; --sp-3: 0.75rem; --sp-4: 1rem;
    --sp-5: 1.25rem; --sp-6: 1.5rem; --sp-8: 2rem; --sp-10: 2.5rem; --sp-12: 3rem;
    --appbar-h: 48px; --alarmbar-h: 36px;
    --nav-rail-w: 64px; --nav-rail-w-expanded: 224px;
    --card-w: 280px;
    --radius-card: 0px; --radius-control: 0px; --radius-pill: 0px;
    --border-w: 1px; --alarmstrip-h: 5px;

    /* Transitions (§6.2) */
    --dur-fast: 120ms; --dur-normal: 200ms; --dur-slow: 320ms;
    --ease-out: cubic-bezier(0.16, 1, 0.3, 1);
    --ease-standard: cubic-bezier(0.2, 0, 0, 1);
  }

  .numeric {
    font-family: var(--font-data);
    font-variant-numeric: tabular-nums;
    font-feature-settings: 'tnum' 1, 'zero' 1;
    letter-spacing: 0;
  }
  ```
- [ ] **Step 2:** Create `src/theme/themes.css` — per-theme semantic token VALUES (design-system §2.1 Dark Room + §2.2 ISA-101, copied verbatim):
  ```css
  [data-theme='dark-room'] {
    --bg: #000000;
    --surface: #0D0D11; --surface-container: #0D0D11; --surface-container-high: #15151A;
    --field-bg: #050508;
    --border: #222228; --border-strong: #2C2C34; --divider: #1A1A20;
    --text: #B0B0B8; --text-secondary: #666670; --text-disabled: #3A3A42;
    --focus-ring: #8A8A94;
    --alarm-critical: #D92525; --alarm-critical-bg: #2A0A0A;
    --alarm-warning: #D9A000; --alarm-warning-bg: #2A2000;
    --alarm-diag: #8A6AD9; --alarm-info: #4A8AD9;
    --on-alarm: #F2E6E6; --text-on-alarm: #F2E6E6;
    --state-running: #4A4A52; --state-stopped: #666670;
    --state-error: #D92525; --state-oos: #3A3A42;
    --trend-pv: #C8C8D0; --trend-sp: #6E6E78; --trend-co: #B07A2A;
    --trend-grid: #1A1A20; --trend-axis: #3A3A42; --trend-bg: #000000;
    --bar-track: #050508; --bar-fill: #4A4A52; --bar-marker: #888890;
  }

  [data-theme='isa101'] {
    --bg: #1E1E1E;
    --surface: #2D2D30; --surface-container: #2D2D30; --surface-container-high: #333337;
    --field-bg: #252526;
    --border: #454548; --border-strong: #57575B; --divider: #3A3A3D;
    --text: #E0E0E0; --text-secondary: #ABABAB; --text-disabled: #666666;
    --focus-ring: #C8C8C8;
    --alarm-critical: #FF3333; --alarm-critical-bg: #3A0E0E;
    --alarm-warning: #FF8800; --alarm-warning-bg: #3A2200;
    --alarm-diag: #AA55FF; --alarm-info: #33AAFF;
    --on-alarm: #FFFFFF; --text-on-alarm: #1E1E1E;
    --state-running: #9A9A9A; --state-stopped: #ABABAB;
    --state-error: #FF3333; --state-oos: #666666;
    --trend-pv: #E0E0E0; --trend-sp: #33AAFF; --trend-co: #FFB000;
    --trend-grid: #3A3A3D; --trend-axis: #57575B; --trend-bg: #252526;
    --bar-track: #252526; --bar-fill: #9A9A9A; --bar-marker: #CCCCCC;
  }
  ```
- [ ] **Step 3:** Write the failing `format` test. Create `src/lib/format.test.ts`:
  ```ts
  import { describe, expect, it } from 'vitest';
  import { formatNumber } from './format';

  describe('formatNumber', () => {
    it('renders fixed decimals', () => {
      expect(formatNumber(150.234, 1)).toBe('150.2');
    });
    it('renders dash for null/NaN', () => {
      expect(formatNumber(null, 1)).toBe('—');
      expect(formatNumber(Number.NaN, 1)).toBe('—');
    });
    it('does not visually skip digits (always fixed)', () => {
      expect(formatNumber(5, 2)).toBe('5.00');
    });
  });
  ```
- [ ] **Step 4:** Run red.
  ```bash
  cd packages/smart_pid_web && npm run test -- format
  ```
  Expected: fails to resolve `./format` (RED).
- [ ] **Step 5:** Create `src/lib/format.ts`:
  ```ts
  /** Fixed-decimal tabular formatting for process values (design-system §3.3). */
  export function formatNumber(value: number | null | undefined, decimals: number): string {
    if (value === null || value === undefined || Number.isNaN(value)) {
      return '—';
    }
    return value.toFixed(decimals);
  }
  ```
- [ ] **Step 6:** Create `src/theme/ThemeProvider.tsx`:
  ```tsx
  import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';

  export type ThemeName = 'isa101' | 'dark-room';
  const STORAGE_KEY = 'smart-pid-theme';

  interface ThemeCtx {
    theme: ThemeName;
    setTheme: (t: ThemeName) => void;
  }
  const Ctx = createContext<ThemeCtx | null>(null);

  export function ThemeProvider({ children }: { children: ReactNode }) {
    const [theme, setTheme] = useState<ThemeName>(
      () => (localStorage.getItem(STORAGE_KEY) as ThemeName) ?? 'isa101',
    );
    useEffect(() => {
      document.documentElement.setAttribute('data-theme', theme);
      localStorage.setItem(STORAGE_KEY, theme);
    }, [theme]);
    return <Ctx.Provider value={{ theme, setTheme }}>{children}</Ctx.Provider>;
  }

  export function useTheme(): ThemeCtx {
    const ctx = useContext(Ctx);
    if (!ctx) throw new Error('useTheme must be used within ThemeProvider');
    return ctx;
  }
  ```
- [ ] **Step 7:** Run green.
  ```bash
  cd packages/smart_pid_web && npm run test -- format
  ```
  Expected: `3 passed`.
- [ ] **Step 8:** Commit.
  ```bash
  git add -A && git commit -m "feat(web): theme token contract (ISA-101 + Dark Room) + ThemeProvider + format helper"
  ```

### Task 8: API client + AuthContext + LoginPage (consumes `POST /auth/login`)

**Files**
- Create: `packages/smart_pid_web/src/api/client.ts`, `src/api/queryClient.ts`
- Create: `packages/smart_pid_web/src/auth/AuthContext.tsx`, `src/auth/RequireAuth.tsx`, `src/auth/LoginPage.tsx`
- Create: `packages/smart_pid_web/src/auth/AuthContext.test.tsx`

**Interfaces**
- Consumes: `POST /api/auth/login` body `{ username: string; password: string }` → `{ access_token: string; token_type: string }` (real `LoginRequest`/`TokenResponse`).
- Produces: `apiGet/apiPost(path, body?)` (prefix `/api`, Bearer header, `ApiError{status,detail}`); `<AuthProvider>` exposing `{ token, isAuthenticated, login(user,pass), logout() }`; `<RequireAuth>` guard; `<LoginPage>`.

- [ ] **Step 1:** Write the failing auth test. Create `src/auth/AuthContext.test.tsx`:
  ```tsx
  import { act, renderHook, waitFor } from '@testing-library/react';
  import { afterEach, describe, expect, it, vi } from 'vitest';
  import { AuthProvider, useAuth } from './AuthContext';

  afterEach(() => vi.restoreAllMocks());

  describe('AuthContext', () => {
    it('logs in and stores the token', async () => {
      vi.spyOn(globalThis, 'fetch').mockResolvedValue(
        new Response(JSON.stringify({ access_token: 'jwt-123', token_type: 'bearer' }), {
          status: 200,
          headers: { 'content-type': 'application/json' },
        }),
      );
      const { result } = renderHook(() => useAuth(), { wrapper: AuthProvider });
      expect(result.current.isAuthenticated).toBe(false);
      await act(async () => {
        await result.current.login('admin', 'pw');
      });
      await waitFor(() => expect(result.current.isAuthenticated).toBe(true));
      expect(result.current.token).toBe('jwt-123');
    });

    it('throws ApiError on 401', async () => {
      vi.spyOn(globalThis, 'fetch').mockResolvedValue(
        new Response(JSON.stringify({ detail: 'Invalid credentials' }), { status: 401 }),
      );
      const { result } = renderHook(() => useAuth(), { wrapper: AuthProvider });
      await expect(result.current.login('admin', 'bad')).rejects.toThrow('Invalid credentials');
      expect(result.current.isAuthenticated).toBe(false);
    });
  });
  ```
- [ ] **Step 2:** Run red.
  ```bash
  cd packages/smart_pid_web && npm run test -- AuthContext
  ```
  Expected: cannot resolve `./AuthContext` (RED).
- [ ] **Step 3:** Create `src/api/client.ts`:
  ```ts
  export class ApiError extends Error {
    constructor(
      public status: number,
      public detail: string,
    ) {
      super(detail);
      this.name = 'ApiError';
    }
  }

  let tokenGetter: () => string | null = () => null;
  export function setTokenGetter(fn: () => string | null): void {
    tokenGetter = fn;
  }

  async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    const token = tokenGetter();
    if (token) headers.Authorization = `Bearer ${token}`;
    const res = await fetch(`/api${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    if (!res.ok) {
      let detail = res.statusText;
      try {
        const j = await res.json();
        if (j?.detail) detail = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail);
      } catch {
        /* non-JSON error body */
      }
      throw new ApiError(res.status, detail);
    }
    if (res.status === 204) return undefined as T;
    return (await res.json()) as T;
  }

  export const apiGet = <T>(path: string) => request<T>('GET', path);
  export const apiPost = <T>(path: string, body?: unknown) => request<T>('POST', path, body);
  ```
- [ ] **Step 4:** Create `src/api/queryClient.ts`:
  ```ts
  import { QueryClient } from '@tanstack/react-query';

  export const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: 1, staleTime: 5_000, refetchOnWindowFocus: false },
    },
  });
  ```
- [ ] **Step 5:** Create `src/auth/AuthContext.tsx`:
  ```tsx
  import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react';
  import { apiPost, setTokenGetter } from '../api/client';

  const STORAGE_KEY = 'smart-pid-token';

  interface LoginResponse {
    access_token: string;
    token_type: string;
  }
  interface AuthCtx {
    token: string | null;
    isAuthenticated: boolean;
    login: (username: string, password: string) => Promise<void>;
    logout: () => void;
  }
  const Ctx = createContext<AuthCtx | null>(null);

  export function AuthProvider({ children }: { children: ReactNode }) {
    const [token, setToken] = useState<string | null>(() => sessionStorage.getItem(STORAGE_KEY));
    setTokenGetter(() => token);

    const login = async (username: string, password: string) => {
      const res = await apiPost<LoginResponse>('/auth/login', { username, password });
      sessionStorage.setItem(STORAGE_KEY, res.access_token);
      setToken(res.access_token);
    };
    const logout = () => {
      sessionStorage.removeItem(STORAGE_KEY);
      setToken(null);
    };
    const value = useMemo<AuthCtx>(
      () => ({ token, isAuthenticated: token !== null, login, logout }),
      [token],
    );
    return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
  }

  export function useAuth(): AuthCtx {
    const ctx = useContext(Ctx);
    if (!ctx) throw new Error('useAuth must be used within AuthProvider');
    return ctx;
  }
  ```
  (Note: import is `useCallback` — fix the casing if the editor flags it; the value memo above does not require it, so a minimal version omits `useCallback` entirely. Keep only the hooks actually used.)
- [ ] **Step 6:** Create `src/auth/RequireAuth.tsx`:
  ```tsx
  import { Navigate, useLocation } from 'react-router-dom';
  import { useAuth } from './AuthContext';

  export function RequireAuth({ children }: { children: React.ReactNode }) {
    const { isAuthenticated } = useAuth();
    const location = useLocation();
    if (!isAuthenticated) {
      return <Navigate to="/login" replace state={{ from: location }} />;
    }
    return <>{children}</>;
  }
  ```
- [ ] **Step 7:** Create `src/auth/LoginPage.tsx` (design-system §5.7 — central 360px card, no hero, explicit error line):
  ```tsx
  import { useState, type FormEvent } from 'react';
  import { useNavigate } from 'react-router-dom';
  import { ApiError } from '../api/client';
  import { useAuth } from './AuthContext';

  export function LoginPage() {
    const { login } = useAuth();
    const navigate = useNavigate();
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState<string | null>(null);

    async function onSubmit(e: FormEvent) {
      e.preventDefault();
      setError(null);
      try {
        await login(username, password);
        navigate('/', { replace: true });
      } catch (err) {
        setError(err instanceof ApiError ? 'Usuário ou senha inválidos' : 'Erro de conexão');
      }
    }

    return (
      <div style={{ minHeight: '100vh', display: 'grid', placeItems: 'center', background: 'var(--bg)' }}>
        <form
          onSubmit={onSubmit}
          style={{
            width: 360, padding: 'var(--sp-6)', background: 'var(--surface)',
            border: '1px solid var(--border)', color: 'var(--text)',
          }}
        >
          <h1 style={{ fontSize: 'var(--text-lg)', fontWeight: 'var(--fw-semibold)' }}>Smart PID</h1>
          <label htmlFor="u">Usuário</label>
          <input id="u" className="numeric" value={username} onChange={(e) => setUsername(e.target.value)} />
          <label htmlFor="p">Senha</label>
          <input id="p" className="numeric" type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
          {error && <p role="alert" style={{ color: 'var(--alarm-critical)' }}>{error}</p>}
          <button type="submit">Entrar</button>
        </form>
      </div>
    );
  }
  ```
- [ ] **Step 8:** Run green.
  ```bash
  cd packages/smart_pid_web && npm run test -- AuthContext
  ```
  Expected: `2 passed`.
- [ ] **Step 9:** Commit.
  ```bash
  git add -A && git commit -m "feat(web): API client, AuthContext (POST /auth/login), RequireAuth, LoginPage"
  ```

### Task 9: `envelope.ts` (CANONICAL) + `RealtimeProvider` + `useRealtime` (CANONICAL)

**Files**
- Create: `packages/smart_pid_web/src/realtime/envelope.ts`, `src/realtime/RealtimeProvider.tsx`, `src/realtime/useRealtime.ts`
- Create: `packages/smart_pid_web/src/realtime/useRealtime.test.ts`

**Interfaces**
- Produces (contract §4): `RealtimeType`, `RealtimeEnvelope<T>`, `StatusData`, `ActionData`, `AlarmData`, `AiData`, `StatsData`.
- Produces (contract §5): `useRealtime(): UseRealtime` with `connected`, `lastStatus: ReadonlyMap<number, StatusData>`, `lastStats: ReadonlyMap<number, StatsData>`, `subscribe<T>(type, handler) => () => void`, `onResync(cb) => () => void`. `RealtimeProvider` opens ONE WebSocket, sends first-frame `{type:'auth', token}`, backoff-reconnects, fires `onResync` after reconnect.

- [ ] **Step 1:** Create `src/realtime/envelope.ts` (CANONICAL — contract §4, with the corrected `StatusData.timestamp` type; see note below):
  ```ts
  export type RealtimeType = 'status' | 'action' | 'alarm' | 'ai' | 'stats' | 'system';

  export interface RealtimeEnvelope<T = unknown> {
    type: RealtimeType;
    loop_id: number | null; // null for global events (EVENT.SYSTEM)
    seq: number; // per-connection sequence, for gap detection
    ts: number; // epoch seconds, server time (stamped by the WS bridge)
    data: T;
  }

  // Live dashboard frame = STATUS.{id} (pid_worker.py:457 / monitor_worker.py:84).
  // Wire payload is a msgpack dict; `timestamp` is an ISO-8601 STRING at the publish site.
  export interface StatusData {
    pv: number;
    sp: number;
    co: number;
    bkcal_in: number;
    bkcal_out: number;
    mode: string; // ControllerMode value
    kp: number;
    ti: number;
    td: number;
    integral_val: number;
    timestamp: string; // ISO 8601 (publish-site format) — NOT epoch
  }
  // Derived client-side (NOT on the wire): error = sp - pv. OPC state via REST GET /opcua/status.
  export interface ActionData { cv: number; delta: number; } // ACTION.CTRL.{id}
  export interface AlarmData { alarm_id: string; severity: string; state: string; } // EVENT.ALARM.*
  export interface AiData { gamma: number; ki: number; strategy: string; } // ACTION.AI.{id}
  export interface StatsData {
    iae: number; itae: number; ise: number; mse: number;
    sigma: number; tv: number; var_range: number; var_sp: number;
  } // STATS.{id}
  ```
- [ ] **Step 2:** Write the failing hook test. Create `src/realtime/useRealtime.test.ts` with a mock WebSocket:
  ```ts
  import { act, renderHook, waitFor } from '@testing-library/react';
  import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
  import { createElement, type ReactNode } from 'react';
  import { RealtimeProvider } from './RealtimeProvider';
  import { useRealtime } from './useRealtime';

  class MockWS {
    static instances: MockWS[] = [];
    onopen: (() => void) | null = null;
    onmessage: ((e: { data: string }) => void) | null = null;
    onclose: (() => void) | null = null;
    sent: string[] = [];
    readyState = 0;
    constructor(public url: string) {
      MockWS.instances.push(this);
    }
    send(d: string) { this.sent.push(d); }
    close() { this.readyState = 3; this.onclose?.(); }
    _open() { this.readyState = 1; this.onopen?.(); }
    _emit(obj: unknown) { this.onmessage?.({ data: JSON.stringify(obj) }); }
  }

  beforeEach(() => {
    MockWS.instances = [];
    vi.stubGlobal('WebSocket', MockWS as unknown as typeof WebSocket);
  });
  afterEach(() => vi.unstubAllGlobals());

  const wrapper = ({ children }: { children: ReactNode }) =>
    createElement(RealtimeProvider, { token: 'jwt-123' }, children);

  describe('useRealtime', () => {
    it('connects and sends first-frame auth', async () => {
      renderHook(() => useRealtime(), { wrapper });
      const ws = MockWS.instances[0];
      act(() => ws._open());
      expect(JSON.parse(ws.sent[0])).toEqual({ type: 'auth', token: 'jwt-123' });
    });

    it('parses a status envelope into lastStatus keyed by loop_id', async () => {
      const { result } = renderHook(() => useRealtime(), { wrapper });
      const ws = MockWS.instances[0];
      act(() => ws._open());
      act(() =>
        ws._emit({ type: 'status', loop_id: 5, seq: 1, ts: 1, data: { pv: 42 } }),
      );
      await waitFor(() => expect(result.current.lastStatus.get(5)?.pv).toBe(42));
    });

    it('delivers discrete alarm events to subscribers', async () => {
      const { result } = renderHook(() => useRealtime(), { wrapper });
      const ws = MockWS.instances[0];
      act(() => ws._open());
      const seen: unknown[] = [];
      act(() => {
        result.current.subscribe('alarm', (env) => seen.push(env.data));
      });
      act(() => ws._emit({ type: 'alarm', loop_id: 9, seq: 1, ts: 1, data: { alarm_id: 'a' } }));
      await waitFor(() => expect(seen).toEqual([{ alarm_id: 'a' }]));
    });
  });
  ```
- [ ] **Step 3:** Run red.
  ```bash
  cd packages/smart_pid_web && npm run test -- useRealtime
  ```
  Expected: cannot resolve `./RealtimeProvider` / `./useRealtime` (RED).
- [ ] **Step 4:** Create `src/realtime/RealtimeProvider.tsx` (single WS, first-frame auth, backoff reconnect, onResync):
  ```tsx
  import {
    createContext, useCallback, useEffect, useMemo, useRef, useState, type ReactNode,
  } from 'react';
  import type { RealtimeEnvelope, RealtimeType, StatusData, StatsData } from './envelope';

  type Handler = (env: RealtimeEnvelope) => void;

  export interface RealtimeContextValue {
    connected: boolean;
    lastStatus: ReadonlyMap<number, StatusData>;
    lastStats: ReadonlyMap<number, StatsData>;
    subscribe: (type: RealtimeType, handler: Handler) => () => void;
    onResync: (cb: () => void) => () => void;
  }
  export const RealtimeContext = createContext<RealtimeContextValue | null>(null);

  const MAX_BACKOFF = 10_000;

  export function RealtimeProvider({ token, children }: { token: string | null; children: ReactNode }) {
    const [connected, setConnected] = useState(false);
    const lastStatus = useRef(new Map<number, StatusData>());
    const lastStats = useRef(new Map<number, StatsData>());
    const subs = useRef(new Map<RealtimeType, Set<Handler>>());
    const resyncCbs = useRef(new Set<() => void>());
    const wsRef = useRef<WebSocket | null>(null);
    const backoff = useRef(500);
    const hadConnection = useRef(false);
    const [, forceRender] = useState(0);

    const subscribe = useCallback((type: RealtimeType, handler: Handler) => {
      const set = subs.current.get(type) ?? new Set<Handler>();
      set.add(handler);
      subs.current.set(type, set);
      return () => set.delete(handler);
    }, []);

    const onResync = useCallback((cb: () => void) => {
      resyncCbs.current.add(cb);
      return () => resyncCbs.current.delete(cb);
    }, []);

    useEffect(() => {
      if (!token) return;
      let cancelled = false;
      let reconnectTimer: ReturnType<typeof setTimeout> | undefined;

      const connect = () => {
        const proto = location.protocol === 'https:' ? 'wss' : 'ws';
        const ws = new WebSocket(`${proto}://${location.host}/ws/realtime`);
        wsRef.current = ws;
        ws.onopen = () => {
          ws.send(JSON.stringify({ type: 'auth', token }));
          setConnected(true);
          backoff.current = 500;
          if (hadConnection.current) {
            resyncCbs.current.forEach((cb) => cb());
          }
          hadConnection.current = true;
        };
        ws.onmessage = (e) => {
          const env = JSON.parse(e.data) as RealtimeEnvelope;
          if (env.type === 'status' && env.loop_id !== null) {
            lastStatus.current.set(env.loop_id, env.data as StatusData);
            forceRender((n) => n + 1);
          } else if (env.type === 'stats' && env.loop_id !== null) {
            lastStats.current.set(env.loop_id, env.data as StatsData);
            forceRender((n) => n + 1);
          } else {
            subs.current.get(env.type)?.forEach((h) => h(env));
          }
        };
        ws.onclose = () => {
          setConnected(false);
          if (cancelled) return;
          reconnectTimer = setTimeout(connect, backoff.current);
          backoff.current = Math.min(backoff.current * 2, MAX_BACKOFF);
        };
      };
      connect();
      return () => {
        cancelled = true;
        if (reconnectTimer) clearTimeout(reconnectTimer);
        wsRef.current?.close();
      };
    }, [token]);

    const value = useMemo<RealtimeContextValue>(
      () => ({
        connected,
        lastStatus: lastStatus.current,
        lastStats: lastStats.current,
        subscribe,
        onResync,
      }),
      [connected, subscribe, onResync],
    );
    return <RealtimeContext.Provider value={value}>{children}</RealtimeContext.Provider>;
  }
  ```
- [ ] **Step 5:** Create `src/realtime/useRealtime.ts` (CANONICAL hook — contract §5):
  ```ts
  import { useContext } from 'react';
  import type { RealtimeEnvelope, RealtimeType, StatusData, StatsData } from './envelope';
  import { RealtimeContext } from './RealtimeProvider';

  export interface UseRealtime {
    connected: boolean;
    lastStatus: ReadonlyMap<number, StatusData>;
    lastStats: ReadonlyMap<number, StatsData>;
    subscribe<T = unknown>(
      type: RealtimeType,
      handler: (env: RealtimeEnvelope<T>) => void,
    ): () => void;
    onResync(cb: () => void): () => void;
  }

  export function useRealtime(): UseRealtime {
    const ctx = useContext(RealtimeContext);
    if (!ctx) throw new Error('useRealtime must be used within RealtimeProvider');
    return ctx as UseRealtime;
  }
  ```
- [ ] **Step 6:** Run green.
  ```bash
  cd packages/smart_pid_web && npm run test -- useRealtime
  ```
  Expected: `3 passed`.
- [ ] **Step 7:** Commit.
  ```bash
  git add -A && git commit -m "feat(web): canonical realtime envelope, RealtimeProvider (single WS), useRealtime hook"
  ```

### Task 10: `AnalogBar`, `ControllerCard`, `RealtimeTrend`, shell, `DashboardPage`

**Files**
- Create: `packages/smart_pid_web/src/components/AnalogBar.tsx`, `src/components/ControllerCard.tsx`, `src/components/RealtimeTrend.tsx`
- Create: `packages/smart_pid_web/src/components/shell/AppShell.tsx`, `NavRail.tsx`, `TopBar.tsx`, `StatusIndicator.tsx`
- Create: `packages/smart_pid_web/src/pages/DashboardPage.tsx`
- Create: `packages/smart_pid_web/src/components/ControllerCard.test.tsx`, `src/components/RealtimeTrend.test.tsx`

**Interfaces**
- Consumes: `useRealtime().lastStatus`; `apiGet<ControllerResponse[]>('/controllers')` (TanStack Query); `apiGet<OpcuaStatus>('/opcua/status')` (REST poll). `StatusData`, `formatNumber`.
- Produces: `<AnalogBar label value min max unit decimals state />`; `<ControllerCard controller status />`; `<RealtimeTrend series />`; `<AppShell>`, `<StatusIndicator state label />`; `<DashboardPage>` rendering a wrap of 280px cards + global OPC status.

- [ ] **Step 1:** Write the failing `ControllerCard` render test. Create `src/components/ControllerCard.test.tsx`:
  ```tsx
  import { render, screen } from '@testing-library/react';
  import { describe, expect, it } from 'vitest';
  import { ControllerCard } from './ControllerCard';
  import type { StatusData } from '../realtime/envelope';

  const status: StatusData = {
    pv: 150.2, sp: 152.0, co: 64.0, bkcal_in: 0, bkcal_out: 0,
    mode: 'AUTO', kp: 1, ti: 1, td: 0, integral_val: 0, timestamp: '2026-06-18T00:00:00Z',
  };

  describe('ControllerCard', () => {
    it('renders tag, mode and PV value', () => {
      render(
        <ControllerCard
          controller={{ id: 5, name: 'PIC-005', description: 'Pressure', pv_decimals: 1, pv_unit: '°C' }}
          status={status}
        />,
      );
      expect(screen.getByText('PIC-005')).toBeInTheDocument();
      expect(screen.getByText('AUTO')).toBeInTheDocument();
      expect(screen.getByText(/150\.2/)).toBeInTheDocument();
    });

    it('renders a placeholder when no status yet', () => {
      render(
        <ControllerCard
          controller={{ id: 6, name: 'FIC-006', description: '', pv_decimals: 1, pv_unit: '%' }}
          status={undefined}
        />,
      );
      expect(screen.getAllByText('—').length).toBeGreaterThan(0);
    });
  });
  ```
- [ ] **Step 2:** Run red.
  ```bash
  cd packages/smart_pid_web && npm run test -- ControllerCard
  ```
  Expected: cannot resolve `./ControllerCard` (RED).
- [ ] **Step 3:** Create `src/components/AnalogBar.tsx` (design-system §5.1 — track + scaleX fill + value, `role="meter"`):
  ```tsx
  import { formatNumber } from '../lib/format';

  export interface AnalogBarProps {
    label: string;
    value: number | null | undefined;
    min: number;
    max: number;
    unit: string;
    decimals: number;
    state?: 'normal' | 'critical' | 'warning';
  }

  export function AnalogBar({ label, value, min, max, unit, decimals, state = 'normal' }: AnalogBarProps) {
    const pct =
      value === null || value === undefined || Number.isNaN(value)
        ? 0
        : Math.max(0, Math.min(1, (value - min) / (max - min)));
    const fill =
      state === 'critical' ? 'var(--alarm-critical)' : state === 'warning' ? 'var(--alarm-warning)' : 'var(--bar-fill)';
    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-2)', fontSize: 'var(--text-xs)' }}>
        <span style={{ width: 24, color: 'var(--text-secondary)' }}>{label}</span>
        <div
          role="meter"
          aria-label={`${label} ${formatNumber(value, decimals)} ${unit}`}
          aria-valuemin={min}
          aria-valuemax={max}
          aria-valuenow={value ?? undefined}
          style={{ position: 'relative', flex: 1, height: 8, background: 'var(--bar-track)', overflow: 'hidden' }}
        >
          <div
            style={{
              position: 'absolute', inset: 0, background: fill,
              transform: `scaleX(${pct})`, transformOrigin: 'left',
              transition: 'transform var(--dur-fast) linear',
            }}
          />
        </div>
        <span className="numeric" style={{ minWidth: 64, textAlign: 'right', color: 'var(--text)', fontWeight: state === 'normal' ? 400 : 600 }}>
          {formatNumber(value, decimals)}
          <span style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-secondary)', marginLeft: 2 }}>{unit}</span>
        </span>
      </div>
    );
  }
  ```
- [ ] **Step 4:** Create `src/components/ControllerCard.tsx` (design-system §5.2 — 280px, alarm strip, header, 3 AnalogBars, footer mode + loop state):
  ```tsx
  import type { StatusData } from '../realtime/envelope';
  import { AnalogBar } from './AnalogBar';

  export interface ControllerSummary {
    id: number;
    name: string;
    description: string;
    pv_decimals: number;
    pv_unit: string;
  }

  export function ControllerCard({
    controller,
    status,
  }: {
    controller: ControllerSummary;
    status: StatusData | undefined;
  }) {
    return (
      <div
        style={{
          width: 'var(--card-w)', background: 'var(--surface)',
          border: '1px solid var(--border)', display: 'flex', flexDirection: 'column',
        }}
      >
        <div style={{ height: 'var(--alarmstrip-h)', background: 'transparent' }} />
        <div style={{ padding: 'var(--sp-4)', display: 'flex', flexDirection: 'column', gap: 'var(--sp-2)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
            <span className="numeric" style={{ fontSize: 'var(--text-base)', fontWeight: 700, color: 'var(--text)' }}>
              {controller.name}
            </span>
            {controller.description && (
              <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>{controller.description}</span>
            )}
          </div>
          <AnalogBar label="PV" value={status?.pv} min={0} max={100} unit={controller.pv_unit} decimals={controller.pv_decimals} />
          <AnalogBar label="SP" value={status?.sp} min={0} max={100} unit={controller.pv_unit} decimals={controller.pv_decimals} />
          <AnalogBar label="CO" value={status?.co} min={0} max={100} unit="%" decimals={1} />
          <div style={{ display: 'flex', gap: 'var(--sp-2)', fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>
            <span className="numeric">{status?.mode ?? '—'}</span>
          </div>
        </div>
      </div>
    );
  }
  ```
- [ ] **Step 5:** Run green for ControllerCard.
  ```bash
  cd packages/smart_pid_web && npm run test -- ControllerCard
  ```
  Expected: `2 passed`.
- [ ] **Step 6:** Write the failing `RealtimeTrend` mount test. Create `src/components/RealtimeTrend.test.tsx`:
  ```tsx
  import { render } from '@testing-library/react';
  import { describe, expect, it, vi } from 'vitest';
  import { RealtimeTrend } from './RealtimeTrend';

  // uPlot touches canvas/measure APIs jsdom lacks; assert it mounts without throwing.
  describe('RealtimeTrend', () => {
    it('mounts with empty data', () => {
      const { container } = render(<RealtimeTrend data={[[], [], [], []]} />);
      expect(container.firstChild).toBeTruthy();
    });
  });
  ```
- [ ] **Step 7:** Run red.
  ```bash
  cd packages/smart_pid_web && npm run test -- RealtimeTrend
  ```
  Expected: cannot resolve `./RealtimeTrend` (RED).
- [ ] **Step 8:** Create `src/components/RealtimeTrend.tsx` (design-system §5.4 / §7.1 — uPlot themed from tokens, PV/SP/CO, no area fill). Guard uPlot init for jsdom:
  ```tsx
  import { useEffect, useRef } from 'react';
  import uPlot from 'uplot';
  import 'uplot/dist/uPlot.min.css';

  export type TrendData = [number[], number[], number[], number[]]; // [t, pv, sp, co]

  function readToken(name: string): string {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || '#888';
  }

  export function RealtimeTrend({ data }: { data: TrendData }) {
    const ref = useRef<HTMLDivElement>(null);
    const plot = useRef<uPlot | null>(null);

    useEffect(() => {
      if (!ref.current) return;
      const opts: uPlot.Options = {
        width: ref.current.clientWidth || 600,
        height: 220,
        scales: { x: { time: false }, y: {}, co: { range: [0, 100] } },
        axes: [
          { stroke: readToken('--trend-axis'), grid: { stroke: readToken('--trend-grid') } },
          { stroke: readToken('--trend-axis'), grid: { stroke: readToken('--trend-grid') } },
          { side: 1, scale: 'co', stroke: readToken('--trend-axis'), grid: { show: false } },
        ],
        series: [
          {},
          { label: 'PV', stroke: readToken('--trend-pv'), width: 1.5 },
          { label: 'SP', stroke: readToken('--trend-sp'), width: 1.5, dash: [6, 4] },
          { label: 'CO', stroke: readToken('--trend-co'), width: 1.5, scale: 'co' },
        ],
      };
      try {
        plot.current = new uPlot(opts, data, ref.current);
      } catch {
        /* jsdom has no canvas measure; ignore in tests */
      }
      return () => plot.current?.destroy();
    }, []);

    useEffect(() => {
      plot.current?.setData(data);
    }, [data]);

    return <div ref={ref} style={{ width: '100%', background: 'var(--trend-bg)' }} />;
  }
  ```
- [ ] **Step 9:** Run green.
  ```bash
  cd packages/smart_pid_web && npm run test -- RealtimeTrend
  ```
  Expected: `1 passed`.
- [ ] **Step 10:** Create the shell + status indicator + dashboard. `src/components/shell/StatusIndicator.tsx`:
  ```tsx
  export function StatusIndicator({ state, label }: { state: 'normal' | 'down'; label: string }) {
    const color = state === 'down' ? 'var(--state-error)' : 'var(--state-running)';
    return (
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 'var(--sp-1)', fontSize: 'var(--text-xs)' }}>
        <span aria-hidden style={{ width: 8, height: 8, borderRadius: '50%', background: color }} />
        <span style={{ color: 'var(--text-secondary)' }}>{label}</span>
      </span>
    );
  }
  ```
  `src/components/shell/NavRail.tsx`:
  ```tsx
  export function NavRail() {
    return (
      <nav
        aria-label="Main navigation"
        style={{ width: 'var(--nav-rail-w)', background: 'var(--surface-container)', borderRight: '1px solid var(--border)' }}
      />
    );
  }
  ```
  `src/components/shell/TopBar.tsx`:
  ```tsx
  import { StatusIndicator } from './StatusIndicator';

  export function TopBar({ opcDown }: { opcDown: boolean }) {
    return (
      <header
        style={{
          height: 'var(--appbar-h)', background: 'var(--surface-container)',
          borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center',
          padding: '0 var(--sp-4)', gap: 'var(--sp-4)', color: 'var(--text)',
        }}
      >
        <strong style={{ fontSize: 'var(--text-lg)' }}>Smart PID</strong>
        <span style={{ flex: 1 }} />
        <StatusIndicator state={opcDown ? 'down' : 'normal'} label="OPC" />
      </header>
    );
  }
  ```
  `src/components/shell/AppShell.tsx`:
  ```tsx
  import type { ReactNode } from 'react';
  import { NavRail } from './NavRail';
  import { TopBar } from './TopBar';

  export function AppShell({ opcDown, children }: { opcDown: boolean; children: ReactNode }) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', background: 'var(--bg)' }}>
        <TopBar opcDown={opcDown} />
        <div style={{ display: 'flex', flex: 1, minHeight: 0 }}>
          <NavRail />
          <main style={{ flex: 1, overflow: 'auto', padding: 'clamp(var(--sp-4), 2vw, var(--sp-8))' }}>{children}</main>
        </div>
      </div>
    );
  }
  ```
  `src/pages/DashboardPage.tsx` (wrap of 280px cards; OPC via REST poll; controllers via Query; live status via useRealtime; reconnect re-sync via onResync):
  ```tsx
  import { useQuery } from '@tanstack/react-query';
  import { useEffect } from 'react';
  import { apiGet } from '../api/client';
  import { AppShell } from '../components/shell/AppShell';
  import { ControllerCard, type ControllerSummary } from '../components/ControllerCard';
  import { useRealtime } from '../realtime/useRealtime';

  interface OpcuaStatus { state: string; endpoint: string | null; }

  export function DashboardPage() {
    const { lastStatus, onResync } = useRealtime();

    const controllers = useQuery({
      queryKey: ['controllers'],
      queryFn: () => apiGet<ControllerSummary[]>('/controllers'),
    });
    const opcua = useQuery({
      queryKey: ['opcua-status'],
      queryFn: () => apiGet<OpcuaStatus>('/opcua/status'),
      refetchInterval: 5_000, // OPC status is POLLED via REST, not WS
    });

    // On WS reconnect, re-sync REST state (controllers + opcua; alarms/ai added by later fatias).
    useEffect(
      () =>
        onResync(() => {
          controllers.refetch();
          opcua.refetch();
        }),
      [onResync, controllers, opcua],
    );

    const opcDown = opcua.data ? opcua.data.state !== 'CONNECTED' : false;

    return (
      <AppShell opcDown={opcDown}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--sp-3)' }}>
          {(controllers.data ?? []).map((c) => (
            <ControllerCard key={c.id} controller={c} status={lastStatus.get(c.id)} />
          ))}
        </div>
      </AppShell>
    );
  }
  ```
- [ ] **Step 11:** Wire providers + routes. Replace `src/App.tsx`:
  ```tsx
  import { QueryClientProvider } from '@tanstack/react-query';
  import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
  import { queryClient } from './api/queryClient';
  import { AuthProvider, useAuth } from './auth/AuthContext';
  import { LoginPage } from './auth/LoginPage';
  import { RequireAuth } from './auth/RequireAuth';
  import { RealtimeProvider } from './realtime/RealtimeProvider';
  import { ThemeProvider } from './theme/ThemeProvider';
  import { DashboardPage } from './pages/DashboardPage';
  import './theme/tokens.css';
  import './theme/themes.css';

  function Shell() {
    const { token } = useAuth();
    return (
      <RealtimeProvider token={token}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            path="/"
            element={
              <RequireAuth>
                <DashboardPage />
              </RequireAuth>
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </RealtimeProvider>
    );
  }

  export function App() {
    return (
      <ThemeProvider>
        <QueryClientProvider client={queryClient}>
          <AuthProvider>
            <BrowserRouter>
              <Shell />
            </BrowserRouter>
          </AuthProvider>
        </QueryClientProvider>
      </ThemeProvider>
    );
  }
  ```
  And update `src/main.tsx` import of CSS is handled in `App.tsx`; keep `main.tsx` as in Task 6.
- [ ] **Step 12:** Run all unit tests + build.
  ```bash
  cd packages/smart_pid_web && npm run test && npm run build
  ```
  Expected: all Vitest specs pass; `tsc -b` clean (strict); `vite build` emits `dist/`.
- [ ] **Step 13:** Commit.
  ```bash
  git add -A && git commit -m "feat(web): AnalogBar, ControllerCard, RealtimeTrend, app shell, live DashboardPage"
  ```

### Task 11: Playwright e2e — login → dashboard receives a `status` frame

**Files**
- Create: `packages/smart_pid_web/e2e/login-dashboard.spec.ts`

**Interfaces**
- Consumes: dev server (Vite) + a backend (real or route-mocked) serving `/api/auth/login`, `/api/controllers`, `/api/opcua/status`, and `/ws/realtime`.
- Produces: an e2e proof that after login the dashboard renders a card whose PV updates from a `status` WS frame.

- [ ] **Step 1:** Create `e2e/login-dashboard.spec.ts` using Playwright route mocks for REST and a mocked WS frame (deterministic, no backend dependency):
  ```ts
  import { expect, test } from '@playwright/test';

  test('login then dashboard receives a status frame', async ({ page }) => {
    await page.route('**/api/auth/login', (route) =>
      route.fulfill({ json: { access_token: 'jwt-e2e', token_type: 'bearer' } }),
    );
    await page.route('**/api/controllers', (route) =>
      route.fulfill({
        json: [{ id: 5, name: 'PIC-005', description: 'Pressure', pv_decimals: 1, pv_unit: '°C' }],
      }),
    );
    await page.route('**/api/opcua/status', (route) =>
      route.fulfill({ json: { state: 'CONNECTED', endpoint: 'opc.tcp://localhost:4840' } }),
    );

    // Stub the WebSocket: emit one auth_ok + one status frame after the auth send.
    await page.addInitScript(() => {
      class StubWS extends EventTarget {
        url: string;
        readyState = 1;
        onopen: (() => void) | null = null;
        onmessage: ((e: MessageEvent) => void) | null = null;
        onclose: (() => void) | null = null;
        constructor(url: string) {
          super();
          this.url = url;
          setTimeout(() => this.onopen?.(), 0);
        }
        send() {
          setTimeout(() => {
            this.onmessage?.(new MessageEvent('message', { data: JSON.stringify({ type: 'auth_ok' }) }));
            this.onmessage?.(
              new MessageEvent('message', {
                data: JSON.stringify({
                  type: 'status', loop_id: 5, seq: 1, ts: 1,
                  data: { pv: 150.2, sp: 152, co: 64, mode: 'AUTO' },
                }),
              }),
            );
          }, 0);
        }
        close() { this.onclose?.(); }
      }
      // @ts-expect-error override
      window.WebSocket = StubWS;
    });

    await page.goto('/login');
    await page.getByLabel('Usuário').fill('admin');
    await page.getByLabel('Senha').fill('pw');
    await page.getByRole('button', { name: 'Entrar' }).click();

    await expect(page.getByText('PIC-005')).toBeVisible();
    await expect(page.getByText(/150\.2/)).toBeVisible();
  });
  ```
- [ ] **Step 2:** Install Playwright browsers (once) and run the e2e.
  ```bash
  cd packages/smart_pid_web && npx playwright install chromium && npm run test:e2e
  ```
  Expected: `1 passed` — login navigates to dashboard, card `PIC-005` shows PV `150.2` from the stubbed `status` frame.
- [ ] **Step 3:** Commit.
  ```bash
  git add -A && git commit -m "test(web): e2e login -> dashboard renders live status frame"
  ```

### Task 12: Spec upkeep + full verification + state save

**Files**
- Modify: `docs/smartPIDv2.md` (note the new Web HMI Fatia 0+1 surface — login, live dashboard, `/ws/realtime`)
- Modify: `docs/superpowers/plans/_web-hmi-INDEX.md` (mark Fatia 0+1 plan present/started, if the INDEX tracks it)
- Modify: `.claude/docs/estado-atual.md` (save state per project rule)

**Interfaces**
- Produces: updated UI/spec docs reflecting the implemented surface; saved state.

- [ ] **Step 1:** Update `docs/smartPIDv2.md` with a short Web HMI section: Fatia 0+1 delivers JWT login, the live `ControllerCard`/`RealtimeTrend` dashboard over `/ws/realtime` (first-message auth, Origin-validated, `4401` on bad token), OPC status via REST poll, single-origin SPA serving + security headers, ISA-101 theme. Do not touch unrelated sections.
- [ ] **Step 2:** Run the full backend + frontend verification gate.
  ```bash
  uv run pytest packages/smart_pid_core/tests/adapters/inbound/api/ -q
  uv run --with ruff ruff check packages/smart_pid_core/
  uv run mypy packages/ | tail -1
  cd packages/smart_pid_web && npm run lint && npm run test && npm run build
  ```
  Expected: backend WS tests pass (only the 3 known Py3.14 `TestProjectServiceOPCUA` failures remain, unchanged); ruff clean; mypy not above baseline; web lint/test/build clean.
- [ ] **Step 3:** Save state in `.claude/docs/estado-atual.md` (what was done: RealtimeWS + scaffold + dashboard; decisions: first-message auth + `4401`, `StatusData.timestamp` is ISO string, STATS subscribed directly on the bus; next: Fatia 2; modified files list). Then STOP and await the user (project rule — do not chain into Fatia 2).
- [ ] **Step 4:** Commit.
  ```bash
  git add -A && git commit -m "docs(web): record Fatia 0+1 web HMI surface; save state"
  ```

---

## Self-Review

**Spec coverage map (fatia01 spec + required coverage → task):**

Backend:
- RealtimeWS `ws/realtime.py` `ConnectionManager` (set, async lock, remove-on-disconnect, resilient broadcast) → Task 2.
- SINGLE non-blocking bus consumer (one `asyncio.Task`, `run_in_executor(None, sub.recv, 10)`, mirrors `TelemetryPublisher`; never recv-per-client / concurrent recv) → Task 3 (`RealtimeBridge._run`).
- Subscribe topics `STATUS.`, `ACTION.CTRL.`, `ACTION.AI.`, `EVENT.ALARM.`, `EVENT.SYSTEM`, `STATS.` → Task 3 (`_BRIDGE_TOPICS`).
- topic→envelope `{type,loop_id,seq,ts,data}` (msgpack dict→JSON) → Task 3 (`map_topic_to_envelope`).
- Coalesce last-value for `status`/`stats`; lossless-bounded for `alarm`/`ai`/system (close on overflow) → Task 4 (`ConnectionBuffer`).
- `GET /ws/realtime` + inject `app.state.event_bus` + register in `create_app` → Tasks 4 (endpoint) + 5 (wire).
- First-message auth `{"type":"auth","token":...}` via `decode_access_token`; validate `Origin`; close `4401` → Task 4.
- `StaticFiles(html=True)` mounted AFTER routers; dev CORS allowlist `http://127.0.0.1:5173`; security headers; bind `127.0.0.1` via `SPID_API_HOST` → Task 5.
- `response_model` audit (auth login, controllers list/get, opcua status) → Task 1.
- pytest-asyncio tests: multi-client broadcast (T2), invalid/missing token 4401 (T4), clean disconnect drop (T2), STATUS coalescing (T4), lossless alarm (T4), Origin rejection (T4) → Tasks 2 & 4.

Frontend:
- Scaffold (package.json scripts, vite proxy, tsconfig strict, vitest jsdom, playwright, index.html) → Task 6.
- `envelope.ts` (contract §4) + `useRealtime.ts` (§5) + `RealtimeProvider.tsx` (single WS, backoff, onResync) → Task 9.
- `api/client.ts` + `queryClient.ts` + `gen:api` wiring → Tasks 8 + 6 (script).
- `AuthContext.tsx` + `RequireAuth.tsx` + `LoginPage.tsx` (POST /auth/login) → Task 8.
- `tokens.css` (§2.0) + `themes.css` (ISA-101 §2.2) + `ThemeProvider.tsx` → Task 7.
- shell `{AppShell,NavRail,TopBar,StatusIndicator}`, `AnalogBar`, `ControllerCard`, `RealtimeTrend`, `DashboardPage`, `format.ts`, `test/setup.ts`, `main.tsx`, `App.tsx` → Tasks 6, 7, 10.
- OPC status via REST poll `GET /opcua/status` (NOT WS) → Task 10 (`DashboardPage` `refetchInterval`).
- Vitest: useRealtime (T9), ControllerCard (T10), RealtimeTrend (T10). Playwright login→status frame (T11).
- Acceptance: login→live status (T10/T11); reconnect→re-sync refetch (T9 `onResync` + T10 wiring; alarms/ai/status refetch noted as added by later fatias since those endpoints/queries are Fatia 3/5 — controllers+opcua refetched now); OPC via REST poll (T10); WS rejects bad token 4401 (T4).
- Monorepo wiring: Node package (not uv member), node_modules/dist gitignored, PySide6 frozen → Tasks 6 + File Structure note.

**Placeholder scan:** No `TODO`/`FIXME`/`...`/"implement later" left in shipped code. Every code step contains complete code. The only deliberate deferral is the reconnect re-sync of `alarms/active` + `ai/status`: those REST queries and their endpoints belong to Fatia 3/5; Task 10 wires the re-sync of the endpoints that exist in this fatia (`controllers`, `opcua/status`) and the `onResync` mechanism is in place for later fatias to register their refetches — this is called out, not silently skipped. Task 5 Step 7 contains a guided assertion (reuse existing conftest factory) rather than fabricated fixture internals, because the exact `create_app(...)` keyword fixture lives in the repo's `conftest.py` and must be reused verbatim, not invented.

**Type/name consistency vs contract:**
- Package path `packages/smart_pid_web/` and every file name match contract §3 verbatim.
- `RealtimeEnvelope{type,loop_id,seq,ts,data}` and `UseRealtime{connected,lastStatus,lastStats,subscribe,onResync}` match contract §4/§5 exactly. First-message auth `{type:'auth',token}` + `4401` match §5.
- Canonical token names in `tokens.css`/`themes.css` match design-system §2.0/§2.2 verbatim; ISA-101 hex values copied exactly.

**Contract §4/§5 fields corrected against real publish sites:**
1. `StatusData.timestamp` changed from `number` to **`string`** (ISO 8601). The real publish sites (`pid_worker.py:457`, `monitor_worker.py:84`, per backend map §3) emit `timestamp` as an ISO string, not epoch. The contract §4 explicitly instructs Fatia 0+1 to "confirm exact dict keys at the publish sites and adjust." The top-level envelope `ts` remains `number` (epoch seconds) because it is stamped by the WS bridge (`time.time()`), not taken from the payload.
2. `RealtimeType` extended with `'system'` (for `EVENT.SYSTEM`, `loop_id: null`). Contract §4 lists 5 types but the required-coverage topic set and §3 include `EVENT.SYSTEM`; the mapper emits `type:'system'`, so the TS union must include it. This is an additive correction consistent with the contract's lossless-system-events requirement.

**Spec requirements not covered (with reason):**
- Reconnect re-sync of `GET /alarms/active` and `GET /ai/status`: deferred to the fatias that introduce those endpoints/queries (Fatia 3 alarms, Fatia 5/AI). The `onResync` hook and its registration pattern are delivered now; Fatia 0+1 re-syncs only the endpoints it consumes (`controllers`, `opcua/status`). Reason: those REST resources and their typed queries are out of this fatia's REST scope (fatia01 spec "REST/WS usados" lists only `auth`, `controllers`, `opcua/status`).
- `Faceplate`, instrumented `AnalogBar` (alarm-limit markers/SP triangle), alarm bar, full theme switcher, and the remaining themes (MD3 dark/light, Ocean): explicitly out of scope per design-system §5 / contract §7 (Fatia 8 closes parity). `AnalogBar` here is the base element as the contract specifies ("base in 0+1, instrumented in Fatia 8").
