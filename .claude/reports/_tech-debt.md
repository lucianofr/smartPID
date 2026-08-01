# Tech Debt

Tracked improvements to address later. Items here need a decision or a window
that a single bugfix pass cannot take unilaterally.

- [ ] **TD-010**: Rotate `SPID_JWT_SECRET` — the key in active use is the one that
      was committed to `.env.example`
  - **Impact:** Critical
  - **Detail:** `.env.example` shipped a real generated signing key, not a
    placeholder. Verified by hashing: the value in the repo's `.env.example` at
    commit `ca5739c` and the value in the operator's live `.env` are identical
    (SHA-256 prefix `ed7dc1495f6e`). Anyone with read access to the repository —
    including its history, where the value survives in 1 commit — can forge a
    valid auth token for this deployment.
  - **Done in this pass:** `.env.example` now carries a placeholder plus the
    generation command, and documents that the file is read by both the daemon
    and the Vite dev proxy.
  - **Still needed (operator decision):** generate a new secret, replace it in
    the live `.env`, restart the daemon (this invalidates every issued token, so
    it wants a maintenance window). Separately decide whether to purge the value
    from git history — a rewrite is disruptive and only worth it if the
    repository is, or will become, shared.
  - **Source:** bugfix pass 2026-07-30
  - **Created:** 2026-07-30

- [ ] **TD-011**: Default admin account ships with password `admin`
  - **Impact:** High
  - **Detail:** `smart_pid_core/main.py::_seed_default_admin` creates the `admin`
    user with the password `admin` and logs
    `SECURITY: Default admin account created with password 'admin'`. The warning
    is deliberate and correct, but nothing forces a change: the account stays
    usable with the default indefinitely. Confirmed live — `admin`/`admin`
    authenticates against the running daemon today.
  - **Options to weigh:** force a password change on first login; refuse to seed
    unless an explicit bootstrap env var is set; or generate a random password
    and print it once at seed time.
  - **Source:** bugfix pass 2026-07-30
  - **Created:** 2026-07-30

- [ ] **TD-012**: Trend column starves below 1024x768 — the loop-card strip is
      ~413px tall at every viewport
  - **Impact:** Medium
  - **Detail:** The card strip does not compact with viewport height, so at
    1024x768 it takes the height the trend and faceplate need. The faceplate
    no-scroll gate currently passes with roughly 25px of slack, and that slack
    exists only because the KPI band collapses to <=46px below 820px of height.
    Any growth in the band or the strip breaks the rail first.
  - **Source:** design-system rewrite 2026-07-28, confirmed in bugfix pass
  - **Created:** 2026-07-30

- [ ] **TD-014**: `POST /controllers` wires up almost nothing; `DELETE` tears down
      almost nothing
  - **Impact:** High
  - **Detail:** The simulator-registration bug fixed on 2026-07-30 was one
    instance of a wider pattern. Creating a controller through the REST API
    persists the row and stops: it does **not** start a control loop, and delete
    does not stop one, nor update `IOWorker.controller_ids`, nor refresh
    `AlarmWorker` metadata, nor register/deregister with the OPC-UA adapter. All
    of that still happens only on daemon startup or project open. So a loop
    created at runtime is inert until a restart, and a deleted one keeps being
    serviced.
  - **Why deferred:** wider blast radius than the simulator fix — it touches
    `LoopManager`, `IOWorker`, `AlarmWorker` and the OPC-UA adapter, and needs a
    deliberate decision about which component owns controller lifecycle. Wants
    its own task with its own tests.
  - **Source:** `.claude/reports/bugs/bugs-simulator-registration-20260730.md`
  - **Created:** 2026-07-30

- [ ] **TD-015**: `set_output` is accepted for SUPERVISORY controllers
  - **Impact:** Medium
  - **Detail:** `loop_manager.py:243` already forbids a manual output write when
    the daemon is in global monitor mode, but a per-controller
    `execution_mode=SUPERVISORY` loop still accepts one. Letting an operator
    write CO through a supervisor that does not own CO is the same category of
    lie as the fabricated GOOD zero fixed in the same pass.
  - **Why deferred:** the gate breaks
    `test_api_commands.py::TestOutputCommand::test_set_output_in_man_mode`, which
    needs re-deciding rather than re-editing; keep it out of the read-through fix.
  - **Source:** `.claude/reports/bugs/bugs-co-telemetry-mapping-20260730.md`
  - **Created:** 2026-07-30

- [ ] **TD-013**: The two executive KPIs render an em dash — no data source wired
  - **Impact:** Low
  - **Detail:** `KpiBand` receives `variability` and `savings` as em dashes
    because their only sources are `GET /controllers/stats` and the AI tuning
    log, both of which would be new polls on the dashboard route. Wiring them is
    a product call about network cost per operator screen.
  - **Source:** design-system rewrite 2026-07-28
  - **Created:** 2026-07-30

- [ ] **TD-016**: No worker-liveness signal — a stuck worker is indistinguishable
      from a healthy steady loop
  - **Impact:** High
  - **Detail:** The 2026-07-31 diff added catch-all guards so a bad frame can no
    longer kill `MonitorWorker`/`StatsWorker`. L4's verdict is that this
    *relocates* the observability gap rather than closing it: a worker that
    survives but retries forever still serves a frozen
    `/controllers/{id}/stats` snapshot that looks exactly like a perfectly
    steady loop. Nothing — `/system/status`, `LoopManager.is_loop_running`,
    `get_stats_workers`, `AlarmWorker` — reads worker liveness or a
    consecutive-failure count. Closing it means a heartbeat or failure counter
    surfaced on the health endpoint; larger than any one bugfix.
  - **Source:** `.claude/reports/sre/L4-reliability-20260731.md`
  - **Created:** 2026-07-31

- [ ] **TD-017**: Unbounded paced retry is now the shape in 3 of 5 worker loops
  - **Impact:** Medium
  - **Detail:** `monitor_worker.py:96-104` and `stats_worker.py:191-202` were
    deliberately modelled on `pid_worker.py:552-565`. The comment is accurate —
    which is the problem: the pattern carries no retry budget, no circuit
    breaker, and no escalation, so a permanent fault (e.g. `self._last_pv=None`
    never reset at `stats_worker.py:150-151`) re-raises every tick forever.
    Fixing two of five loops in isolation entrenches the divergence; do all five
    together with a shared consecutive-error counter.
  - **Source:** `.claude/reports/sre/L4-reliability-20260731.md`
  - **Created:** 2026-07-31

- [ ] **TD-018**: "Simulator owns the OPC-UA endpoint" invariant has no owner
  - **Impact:** High
  - **Detail:** `project_service.py:326-331` now abstains from applying a saved
    endpoint in simulator mode, but three other paths can still break the
    invariant: `AdapterFactory.__init__` sets it once, and `PUT
    /opcua/endpoint` (`opcua.py:85-86`) plus `POST /opcua/connect`
    (`opcua.py:96-99`) call `set_endpoint()` with no simulator guard. Worse,
    `_resync_simulator_link` restarts the client without re-asserting the
    endpoint, so after an admin points it at a real DCS every later project
    switch re-arms the wrong endpoint while binding twin node ids. Needs one
    enforcing owner at the boundary.
  - **Source:** `.claude/reports/review/L2-arch-20260731.md`
  - **Created:** 2026-07-31

- [ ] **TD-019**: `register_controller` names two unrelated contracts
  - **Impact:** Medium
  - **Detail:** `SimulatorAdapter.register_controller(id, pv_min, pv_max)`
    (`simulator_adapter.py:323`) creates simulation state;
    `OPCUAAdapter.register_controller(id, node_id_*, mode_int_map)`
    (`opcua_adapter.py:212`) records a tag address map. Same name, unrelated
    contracts, in the two modules `bind_opcua_client` exists to bridge. Already
    load-bearing: `project_service.py:262` probes the name with `hasattr`, a
    check that passes for either adapter. Rename the outbound one to
    `bind_tags`; three call sites.
  - **Source:** `.claude/reports/review/L2-arch-20260731.md`
  - **Created:** 2026-07-31

- [ ] **TD-020**: `application/` imports concrete adapters instead of ports
  - **Impact:** Medium
  - **Detail:** Pre-existing and systemic, not introduced by any one change:
    `application/workers/db_worker.py:16-17` imports
    `adapters.outbound.db_engine` and `adapters.outbound.historian` at module
    level, and `ProjectService` types its adapter slots as `object | None`
    (`project_service.py:50`), forcing `hasattr` probes and `# type: ignore`
    throughout. `domain/ports/` already holds the right pattern
    (`TelemetrySource`, `ControlWriter`, `ControllerRepository`). Remediation is
    a ports-and-injection program across the worker layer — deliberately out of
    scope for bugfix PRs. Note: protocol-specific contracts such as OPC-UA tag
    binding must be declared in the adapter layer, NOT in the dependency-free
    domain package.
  - **Source:** `.claude/reports/review/L2-arch-20260731.md`
  - **Created:** 2026-07-31

- [ ] **TD-021**: No request body size or JSON nesting-depth limit
  - **Impact:** Low
  - **Detail:** `fastapi.encoders.jsonable_encoder` raises an uncaught
    `RecursionError` on a ~990-level-deep wrong-typed body (~12 KB payload),
    turning a would-be 422 into a 500. Pre-existing FastAPI framework
    behaviour — the stock handler calls the same function — and bounded: the
    route requires an authenticated admin token, and Starlette's
    `ServerErrorMiddleware` sends the 500 before re-raising, so it is not a
    daemon-wide DoS. `app.py` has no body-size or depth middleware. Add a
    nesting guard, or wrap the handler in `except RecursionError -> generic 422`.
  - **Source:** `.claude/reports/security/L3-security-20260731.md`
  - **Created:** 2026-07-31
