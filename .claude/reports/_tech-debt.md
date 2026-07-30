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
