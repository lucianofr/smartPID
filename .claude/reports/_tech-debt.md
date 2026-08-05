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

- [x] **TD-011**: Default admin account ships with password `admin` — **RESOLVED 2026-08-05**
  - **Impact:** High
  - **Resolution:** `_seed_default_admin` no longer hard-codes `admin`. When
    users.db is empty at boot it uses `SPID_BOOTSTRAP_ADMIN_PASSWORD` if set
    (never logged), otherwise generates `secrets.token_urlsafe(12)` and logs it
    once at WARNING as event `bootstrap_admin_password`. Covered by
    `tests/core/integration/test_user_role_migration.py::TestSeedDefaultAdmin`.
  - **Source:** bugfix pass 2026-07-30; resolved by
    `.claude/reports/security/security-bootstrap-admin-20260805.md`
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

- [ ] **TD-022**: Login rate limiter is in-memory and per-process
  - **Impact:** Low
  - **Detail:** `LoginRateLimiter` (routers/auth.py) keeps its budget in a
    dict. A daemon restart resets every IP's budget, and a future multi-worker
    uvicorn deploy would keep N independent budgets. Acceptable for this
    single-process control-plane daemon; move to a shared store (Redis) only
    if the deployment ever scales past one process.
  - **Source:** `.claude/reports/security/security-login-hardening-20260805.md`
  - **Created:** 2026-08-05

- [ ] **TD-023**: No per-username login lockout (intentional)
  - **Impact:** Low
  - **Detail:** The rate limit is keyed by client IP, deliberately not by
    username — per-username lockouts let a caller enumerate which usernames
    exist. Consequence: a single-IP credential spray is the only brute-force
    coverage this layer provides; a rotating-IP attacker gets 5 tries per IP.
  - **Source:** `.claude/reports/security/security-login-hardening-20260805.md`
  - **Created:** 2026-08-05

- [ ] **TD-024**: Login timing side channel still open (audit finding F5)
  - **Impact:** Low
  - **Detail:** `GET /auth/login` short-circuits when the user is not found,
    so a caller can time-distinguish "no such user" from "wrong password"
    and enumerate usernames. bcrypt's per-hash cost makes the signal small
    but nonzero. Fix: run a dummy bcrypt against a stored hash in the
    user-not-found branch to equalize the path. Touches a file outside this
    round's ownership, deferred deliberately.
  - **Source:** `.claude/reports/security/security-vps-exposure-20260805.md` (F5)
  - **Created:** 2026-08-05

- [ ] **TD-025**: Explicit weak bootstrap password is still honoured
  - **Impact:** Low
  - **Detail:** Setting `SPID_BOOTSTRAP_ADMIN_PASSWORD=admin` (or any weak
    value) seeds a weak admin by operator choice. The env-var path never logs
    the value and cannot tell a generated secret from a typed one. Optional
    defense-in-depth: deny-list common weak values or enforce a minimum
    length on the explicit path.
  - **Source:** `.claude/reports/security/security-bootstrap-admin-20260805.md`
  - **Created:** 2026-08-05

- [ ] **TD-026**: OpenAPI exposure is one global knob, no per-route policy
  - **Impact:** Low
  - **Detail:** `SPID_API_EXPOSE_OPENAPI` toggles /docs, /redoc and
    /openapi.json together and globally. There is no way to publish a
    curated, auth-gated subset (e.g. hide /docs but keep a documented
    openapi.json behind admin auth). Single boolean is enough today.
  - **Source:** `.claude/reports/security/security-openapi-shadow-20260805.md`
  - **Created:** 2026-08-05


- [ ] **TD-027**: `/health` referenced by ops tooling but absent from the API
  - **Impact:** Low
  - **Detail:** `packaging/windows/README.md` was corrected to
    `GET /system/status`, but external monitoring, uptime checks, or LB
    probes configured against `/health` will 404. Either add a trivial
    `GET /health` alias or standardize all documentation on `/system/status`.
  - **Source:** `.claude/reports/sre/sre-vps-deploy-20260805.md`
  - **Created:** 2026-08-05

- [ ] **TD-028**: Bootstrap admin has no forced password rotation
  - **Impact:** Medium
  - **Detail:** The random-password fix makes the credential unguessable, but
    it stays a plaintext line in `docker logs` (log retention, history, any
    log-shipping pipeline) until an operator changes it. No "must change on
    first login" flow, no expiry. Single shared `admin` account.
  - **Source:** `.claude/reports/sre/sre-vps-deploy-20260805.md`
  - **Created:** 2026-08-05

- [ ] **TD-029**: No TLS on the public deployment
  - **Impact:** High
  - **Detail:** `http://76.13.172.133:8032/` serves the login form and JWT
    over plaintext — password and bearer token visible to anyone on-path.
    Explicitly a non-goal of the deploy task; compounds TD-028 (a
    network-sniffable admin credential, not just a log-sniffable one).
    Fix: terminate TLS (Caddy/nginx + ACME) in front of 8032, or an
    origin certificate.
  - **Source:** `.claude/reports/security/security-vps-exposure-20260805.md` (F2),
    `.claude/reports/sre/sre-vps-deploy-20260805.md`
  - **Created:** 2026-08-05

- [ ] **TD-030**: Oversized SPA entry chunk (~600 KB)
  - **Impact:** Low
  - **Detail:** `vite build` warns "Some chunks are larger than 500 kB" —
    the 600+ KB `index-*.js` entry chunk. Candidate for
    `manualChunks`/dynamic `import()` code-splitting once initial load time
    on the VPS link matters.
  - **Source:** `.claude/reports/sre/sre-vps-deploy-20260805.md`
  - **Created:** 2026-08-05

- [ ] **TD-031**: Simulator page keeps a stale loop selection after the last loop is deleted
  - **Impact:** Low
  - **Detail:** Deleting every loop via the UI, the watchdog reseeds loop 0 in
    the twin within one tick, but the page's selected-loop state (chip
    header, telemetry readouts) does not re-sync until the next status poll
    lands on an existing id — transient blank header observed in E2E.
    Cosmetic; data path is correct. Fix: SimulatorPage re-selects the first
    available loop when its selection disappears from /simulator/status.
  - **Source:** browser E2E, simulator independence work 2026-08-05
  - **Created:** 2026-08-05
---

# Histórico — registro anterior (TD-000..TD-007, web HMI 2026-06)

## Tech Debt Registry (2026-06)

Track technical debt explicitly like bugs. Review weekly.

---

## Critical (Blocks Feature Work)

_Debt that prevents or significantly slows new development._

_No open Critical items. TD-001 and TD-002 resolved on 2026-06-18 (see Resolved)._

<!-- Example:
- [ ] **TD-001**: Legacy auth system needs migration
  - **Impact:** High - blocks SSO integration
  - **Effort:** 2 weeks
  - **Owner:** @unassigned
  - **Created:** 2025-01-01
-->

## High (Causes Frequent Issues)

_Debt that causes recurring problems or bugs._

- [ ] **TD-004**: Sem CORS/TrustedHost; API binda `0.0.0.0`
  - **Impact:** High - exposição a DNS-rebinding; recomenda-se bind `127.0.0.1` + allow-list/TrustedHost ou SPA single-origin
  - **Source:** security/security-web-hmi-20260618.md
  - **Effort:** TBD
  - **Owner:** @unassigned
  - **Created:** 2026-06-18

- [ ] **TD-007**: Converter backend para single-admin / remover RBAC + users router
  - **Impact:** High - decisão de produto (2026-06-18): o sistema passa a ser
    **single-user (um administrador), sem RBAC (mono-usuário)**. Os gates por tier de papel
    do security fix (operator/supervisor/admin) devem colapsar para uma única dependência
    "exige administrador autenticado". A exigência de **auth permanece** (401 sem auth);
    apenas os tiers de papel (403 por papel) são removidos. Concretamente: `routers/users`
    (CRUD) deve ser descontinuado; `POST /commands/optimization` hoje usa `require_operator`
    e deve passar a usar o gate de admin único; idem para os demais comandos/projetos que
    hoje exigem operator/supervisor/admin.
  - **Source:** reconciliação dos web specs / decisão de produto 2026-06-18
  - **Effort:** TBD
  - **Owner:** @unassigned
  - **Created:** 2026-06-18

<!-- Example:
- [ ] **TD-002**: N+1 queries in user dashboard
  - **Impact:** Medium - page load > 5s
  - **Effort:** 3 days
  - **Owner:** @unassigned
  - **Created:** 2025-01-01
-->

## Medium (Slows Development)

_Debt that makes development harder but doesn't block._

- [ ] **TD-006**: WS auth via `?token=` (ponte WS futura)
  - **Impact:** Medium - token em query param vaza em log/history; usar ws-ticket de curta duração ou auth na primeira mensagem quando a ponte WS for criada
  - **Source:** arch/arch-web-hmi-20260618.md + security/security-web-hmi-20260618.md
  - **Effort:** TBD
  - **Owner:** @unassigned
  - **Created:** 2026-06-18

<!-- Example:
- [ ] **TD-003**: Test fixtures are brittle
  - **Impact:** Low - flaky CI
  - **Effort:** 1 week
  - **Owner:** @unassigned
  - **Created:** 2025-01-01
-->

## Low (Track for Later)

_Known issues not currently prioritized._

<!-- Example:
- [ ] **TD-004**: Could use newer React patterns
  - **Impact:** None - works fine
  - **Effort:** 2 weeks
  - **Owner:** @unassigned
  - **Created:** 2025-01-01
-->

---

## Resolved

_Completed tech debt items. Keep for 90 days then archive._

- [x] **TD-001**: `routers/project.py` sem auth/authz
  - **Resolved:** 2026-06-18 — branch `fix/backend-security-hardening`
  - **Resolution:** Added role dependencies to every `/project` route
    (current/list → operator; new/open/import/download → supervisor; delete →
    admin). Unauthenticated → 401, wrong role → 403. Tests in
    `tests/core/integration/test_api_project.py`.
    _Nota: com a decisão single-admin (TD-007), estes tiers de papel colapsam para um único
    gate "exige administrador autenticado"; a exigência de auth (401) permanece._

- [x] **TD-002**: Path traversal via `name` em `project_service`
  - **Resolved:** 2026-06-18 — branch `fix/backend-security-hardening`
  - **Resolution:** Added `ProjectService._safe_project_path()` — strict name
    allow-list (`[A-Za-z0-9._\- ]`, ≤128 chars, no `..`/separators/absolute/NUL)
    plus a resolved-path-inside-`projects_dir` assertion. Applied to
    new/open/import/delete; import also re-validates the derived name from
    `UploadFile.filename`. Router maps `ValueError` → 400. Tests in
    `tests/core/unit/test_project_service.py` and `test_api_project.py`.

- [x] **TD-003**: `/commands/tuning` fura guardrails
  - **Resolved:** 2026-06-18 — branch `fix/backend-security-hardening`
  - **Resolution:** Brought raw `/commands/tuning` to the `apply-tuning` bar:
    typed `TuningCommand` Pydantic body, each supplied Kp/Ti/Td clamped to the
    controller's `max_tuning_change_pct` via `clamp_tuning_change`, and gate
    raised from `require_operator` to `require_supervisor`. Tests in
    `tests/core/integration/test_api_commands.py::TestWriteTuningCommand`.
    _Nota: com a decisão single-admin (TD-007), o gate `require_supervisor` colapsa para o
    gate de admin único; o clamp e a tipagem permanecem._

- [x] **TD-005**: Sem limite de tamanho no upload `.spid` (import)
  - **Resolved:** 2026-06-18 — branch `fix/backend-security-hardening`
  - **Resolution:** `/project/import` now reads the upload in 1 MB chunks with a
    running byte cap (`CoreSettings.max_upload_bytes`, default 50 MB) and rejects
    oversized uploads with HTTP 413 before buffering/writing. Tests in
    `tests/core/integration/test_api_project.py::TestImportProject`.

<!-- Example:
- [x] **TD-000**: Migrated from callbacks to async/await
  - **Resolved:** 2025-01-15
  - **Resolution:** Refactored auth module
-->

---

## Metrics

| Category | Count | Oldest |
|----------|-------|--------|
| Critical | 0 | - |
| High | 2 | 2026-06-18 |
| Medium | 1 | 2026-06-18 |
| Low | 0 | - |
| **Total Open** | **3** | 2026-06-18 |

_Open remaining: TD-004 (CORS/bind, High), TD-007 (single-admin/no-RBAC backend migration,
High), TD-006 (WS token, Medium). TD-004/TD-006 deferidos ao trabalho de packaging
WS/StaticFiles (Fatia 0+1); TD-007 é a migração de produto para single-admin._

_Last updated: 2026-06-18_

---

## Guidelines

### When to Add Debt

Add to registry when you:
- Skip tests to meet deadline
- Use workaround instead of proper fix
- Copy-paste instead of abstract
- Ignore deprecation warnings
- Hard-code instead of configure
- Disable linter rules

### Debt Item Format

```markdown
- [ ] **TD-NNN**: Brief description
  - **Impact:** Critical | High | Medium | Low
  - **Source:** [report-name.md] or [postmortem-name.md] (what identified this debt)
  - **Effort:** Time estimate
  - **Owner:** @username or @unassigned
  - **Created:** YYYY-MM-DD
```

### Priority Guidelines

| Priority | Criteria | Action |
|----------|----------|--------|
| Critical | Blocks features, security risk | Address immediately |
| High | Causes incidents, slows team | Next sprint |
| Medium | Annoying but manageable | Quarterly review |
| Low | Nice to fix someday | Opportunistic |

### Review Cadence

- **Weekly:** Review Critical/High items
- **Sprint planning:** Consider Medium items
- **Quarterly:** Audit full registry, archive resolved

### Commands

```bash
# View debt summary
/debt

# Add new debt item
/debt add "Description" --priority high

# Mark resolved
/debt resolve TD-001
```
