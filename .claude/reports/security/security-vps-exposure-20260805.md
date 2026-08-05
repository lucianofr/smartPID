# Security Audit — Public Exposure on `http://76.13.172.133:8032`

**Date:** 2026-08-05
**Scope:** Read-only audit of the backend's externally reachable surface as it would
sit behind `http://76.13.172.133:8032` (plaintext HTTP, public IP, port 8032, single
process, single-origin SPA served by the same daemon, seeded default admin). No code
was changed. Every finding below was traced to source, not assumed; every reachability
claim cites the exact `Depends()` (or absence of one) on the route.

**Out of scope (per assignment):** Dockerfile / deploy mechanics (owned by a peer
agent), code style, test coverage, anything not reachable through port 8032.

---

## 1. The four reachability questions

| # | Question | Answer for a caller with **zero credentials** | Answer for a caller who supplies the **seeded default credentials** (`admin`/`admin`) |
|---|---|---|---|
| a | Read process telemetry (PV/SP/CO, trend, history, stats)? | **No** | **Yes — full read** |
| b | Write a setpoint/mode/output, or apply tuning? | **No** | **Yes — full write, including OPC-UA tuning/mode writes** |
| c | Upload or download a project (`.spid`) file? | **No** | **Yes — both** |
| d | Enumerate or create users? | **No** | **Yes — including demoting/deactivating the real operator once they exist** |

**Evidence for "No" (zero-credential caller):**

- `/ws/realtime` requires a valid JWT in the very first WS frame before any
  telemetry is broadcast: `adapters/inbound/api/ws/realtime.py:217-230`
  (`receive_json()` → `resolve_token_principal()`; anything else closes the socket
  with code 4401, `realtime.py:214-215`).
- `/trend/{controller_id}` → `Depends(require_user)` (`routers/trend.py:29`).
- `/history/{controller_id}` → `Depends(require_user)` (`routers/history.py:22`).
- `/controllers` (list/get) → `Depends(require_user)` (`routers/controllers.py:433,478`).
- `/controllers/{id}/stats`, `/controllers/stats` → `Depends(require_user)`
  (`routers/stats.py:20,34`).
- `/commands/setpoint|mode|output` → `Depends(require_user)`
  (`routers/commands.py:79,110,147`); `/commands/optimization|tuning|apply-tuning`
  → `Depends(require_admin)` (`commands.py:180,251,359`).
- `/simulator/*`, `/opcua/*` → every route carries `require_admin` or `require_user`
  (grep-verified across `routers/simulator.py` and `routers/opcua.py`; no bare route).
- `/project/import` → `Depends(require_admin)` (`routers/project.py:153`);
  `/project/download` → `Depends(require_admin)` (`project.py:190`).
- `/users` GET/POST → `Depends(require_admin)` (`routers/users.py:64,72`).
- The **one** genuinely unauthenticated route is `GET /system/status`
  (`routers/system.py:39-41`, deliberately commented `"Health check — no auth
  required."`). It returns `uptime_s`, `cpu_percent`, `memory_percent`,
  `active_controllers` (a count) and `api_version` — no PV/SP/CO, no project name,
  no user data. Confirmed by reading its full body (`system.py:39-53`).

**Evidence for "Yes" (seeded-credential caller):** see Finding 1 below. The
attacker needs exactly one unauthenticated `POST /auth/login` with the literal
body `{"username":"admin","password":"admin"}` to obtain a Bearer token that
satisfies every `require_user`/`require_admin` gate listed above.

**So the honest one-line answer is:** *nothing on this API is reachable without a
token, but the only account that exists on a fresh deployment has a token anyone
can obtain in one guess, and nothing slows that guess down.* The auth boundary
is real; the credential behind it is not.

---

## 2. Findings — ranked by real exploitability against THIS deployment shape

### Tier 1 — Exploitable right now, with nothing else missing

#### F1. Default admin account (`admin`/`admin`) reseeds on every fresh `users.db`, with no forced rotation and no login throttling — CRITICAL
- **File:Line:** `packages/smart_pid_core/src/smart_pid_core/main.py:99-109`
  (`_seed_default_admin`), invoked unconditionally at `main.py:395`; consumed by
  `POST /auth/login` at `adapters/inbound/api/routers/auth.py:30-51`.
- **Verified:** `_seed_default_admin` seeds `admin`/`admin` (`hash_password("admin")`,
  `main.py:103-104`) whenever `user_repo.list_all()` is empty (`main.py:101-102`) —
  which is exactly the state of a **new** `SPID_USERS_DB_PATH=/data/users.db` on the
  fresh `smartpid-data` volume this deployment creates. This is TD-011 in the
  registry, and the code confirms it is **still unfixed**: no bootstrap-password env
  var, no forced-change-on-first-login flag, no random one-time password — the
  literal string `"admin"` is hard-coded.
- **Login has no rate limiting or lockout anywhere in the tree.** Searched the whole
  `smart_pid_core` package for `rate.?limit|slowapi|throttl|lockout|failed_attempts`
  — the only hits are unrelated logging-throttle code in `io_worker.py`. `POST
  /auth/login` (`routers/auth.py:30-51`) has zero per-IP or per-username attempt
  tracking; nothing prevents an unlimited number of login attempts per second.
- **What an internet attacker can do:** `POST http://76.13.172.133:8032/auth/login`
  with `{"username":"admin","password":"admin"}` returns a valid 8-hour admin JWT
  (`jwt_expiry_hours` default, `config.py:40`) on the first try. From there: write
  any setpoint/mode/output/tuning (`commands.py`), start/stop the simulator and
  OPC-UA links (`simulator.py`, `opcua.py`), import a poisoned `.spid` project or
  download the live one (`project.py`), and create a new admin account or
  deactivate every other user — `_reject_if_last_active_admin` (`users.py:44-58`)
  only refuses to remove the *last* admin, so the attacker can deactivate the real
  operator's account the moment it exists as long as their own stays active
  (`users.py:96-140`, `143-165`). This is a race against whoever deploys the box:
  whoever logs in with `admin`/`admin` first and changes the password locks the
  other party out.
- **Remediation (minimal):** refuse to seed a literal `"admin"` password — either
  require an explicit `SPID_BOOTSTRAP_ADMIN_PASSWORD` env var at first boot, or
  generate a random password and log it once (never store it); separately, add a
  simple per-username+IP login counter with a short lockout/backoff on
  `POST /auth/login`. Both are small, self-contained changes to `main.py` and
  `routers/auth.py`.

#### F2. Credentials and session tokens travel in plaintext (`http://`, no TLS) — CRITICAL for this exposure
- **File:Line:** deployment target itself (`http://76.13.172.133:8032`, given by
  the assignment); reflected in code by the total absence of TLS wiring in
  `main.py:562-568` (`uvicorn.Config(app=app, host=settings.api_host,
  port=settings.api_port, log_level=...)` — no `ssl_certfile`/`ssl_keyfile`) and by
  every credential/token that crosses the wire: the login body
  (`routers/auth.py:33`, username+password) and the `Authorization: Bearer <jwt>`
  header on every subsequent authenticated call.
- **What an internet attacker can do:** anyone positioned on the network path
  (shared VPS host, upstream transit, a compromised router between the operator
  and the VPS) reads the password in the login request or lifts a live Bearer
  token from any request and replays it for up to 8 hours
  (`jwt_expiry_hours=8`). This defeats even a *strong*, correctly-rotated password
  — it is independent of F1.
- **Remediation:** terminate TLS in front of port 8032 (Caddy/nginx reverse proxy
  with Let's Encrypt, or equivalent) before the box is reachable on the public
  internet. This is deploy-mechanics, explicitly out of this audit's scope to
  implement, but it is a hard precondition for calling any of the auth-boundary
  work below "defensible" — flagged here because it changes the risk rating of
  every other finding in this report from "an attacker needs a foothold" to "an
  attacker needs to be anywhere on the path."

#### F3. Full API schema and route map (`/docs`, `/redoc`, `/openapi.json`) served unauthenticated — MEDIUM (recon aid, not a direct authz bypass)
- **File:Line:** `adapters/inbound/api/app.py:107` —
  `app = FastAPI(title="Smart PID API", version="2.0.0", lifespan=_lifespan)` never
  passes `docs_url=None`, `redoc_url=None`, or `openapi_url=None`, and no other
  call site in the tree sets them (grep-verified: `docs_url|redoc_url|openapi_url`
  appears nowhere else in `smart_pid_core/src`). FastAPI's default docs routes are
  registered inside `FastAPI.__init__()`/`setup()`, i.e. before `create_app` adds
  any router or the SPA mount, so they are not shadowed by
  `app.mount("/", StaticFiles(...))` at `app.py:201-206` — an exact-path route
  registered earlier always wins the linear route scan.
- **What an internet attacker can do:** browse `http://76.13.172.133:8032/docs`
  or fetch `/openapi.json` with no credentials and get the complete route map —
  every path, method, request/response schema, and which routes exist for
  simulator control, OPC-UA connect/disconnect, tuning apply, project
  import/delete, and user management — plus Swagger's interactive "Try it out"
  UI pre-wired to call `/auth/login`. This does not grant any capability beyond
  what F1 already grants, but it removes the need to read source code first and
  hands the attacker a complete, structured target list in one request.
- **Remediation:** pass `docs_url=None, redoc_url=None, openapi_url=None` to the
  `FastAPI(...)` constructor for this deployment (or gate `/docs`/`/openapi.json`
  behind `require_admin` if interactive docs are wanted for operators).

### Tier 2 — Exploitable only if another control (above) is also missing

#### F4. Login endpoint has no length cap on `username`/`password`, unlike every other credential-bearing DTO — LOW/MEDIUM
- **File:Line:** `packages/smart_pid_domain/src/smart_pid_domain/dtos/auth.py:12-14`
  (`LoginRequest.username: str`, `.password: str` — no `Field(max_length=...)`),
  contrasted with `UserCreate` three lines below at `auth.py:23-25`
  (`Field(min_length=1, max_length=64)` / `max_length=128`).
- **Reachable without any prior control:** `/auth/login` (`routers/auth.py:30`) is
  itself unauthenticated, and neither `uvicorn.Config` (`main.py:562-566`) nor any
  middleware in `app.py` (`_security_headers`, `CORSMiddleware`,
  `TrustedHostMiddleware` — the only three registered, `app.py:151-170`) imposes a
  request body size limit.
- **What it enables:** an internet caller can POST an arbitrarily large
  `username`/`password` JSON body and force full in-memory buffering of it before
  Pydantic validation runs — a low-cost, repeatable memory-pressure vector against
  a single-process daemon with no reverse proxy in front of it. Separately, a
  large `password` against a username that **does** exist reaches
  `bcrypt.checkpw()` (`auth.py:16-17`); `bcrypt` 5.0.0 (pinned, `uv.lock`) raises
  on passwords over 72 bytes, so this path 500s per request rather than hanging,
  but it is still an unauthenticated way to generate exceptions/log noise at will.
- **Remediation:** add `Field(max_length=128)` (matching `UserCreate`) to both
  `LoginRequest` fields, and set a request body size limit at the ASGI layer
  (uvicorn `--limit-max-requests`/proxy-level `client_max_body_size`) once F2's
  reverse proxy exists.

#### F5. Username enumeration via login timing — LOW, theoretical impact given F1
- **File:Line:** `adapters/inbound/api/routers/auth.py:37-41` —
  `if user is None or not verify_password(...)`: when `user is None` the `bcrypt`
  call is skipped entirely, so a request for a non-existent username returns in
  microseconds while a request for a real username with a wrong password costs a
  full bcrypt round (tens of milliseconds). Both paths return the identical `401
  {"detail":"Invalid credentials"}` body, so this is a **timing**, not a
  **content**, side channel.
- **Impact on this deployment:** with only one account (`admin`) seeded and its
  username already public knowledge (documented in TD-011, this report, and the
  seed log line itself, `main.py:105-108`), there is nothing left to enumerate
  today. Recorded because it becomes real the moment `POST /users` creates a
  second account.
- **Remediation:** run `verify_password` against a constant dummy hash when
  `user is None`, so both branches cost the same bcrypt round.

### Tier 3 — Theoretical here (verified as not exploitable on this exposure)

#### F6. `TrustedHostMiddleware`/CORS misconfiguration risk — not a code finding, a deploy-config dependency
- `trusted_hosts` defaults to `["127.0.0.1", "localhost"]` (`config.py:30`) and
  runs outermost by design (`app.py:168-171`, comment at `app.py:146-148`
  confirms the ordering is intentional and — traced through Starlette's
  middleware-stack construction — correct: the **last** `add_middleware()` call
  ends up **outermost**, so `TrustedHostMiddleware`, added after `CORSMiddleware`
  and the security-headers middleware, does reject a bad `Host` header before
  either of the others run). If the VPS deployment's `.env` omits
  `76.13.172.133` from `SPID_TRUSTED_HOSTS`, every request 400s — a fail-**closed**
  misconfiguration, not an exposure. Not this audit's problem to fix (deploy
  mechanics, owned by the peer agent), noted only because it is the inverse risk
  of everything else in this report and is easy to conflate with a vulnerability.
- Starlette's `TrustedHostMiddleware` compares against the `Host` header with the
  port stripped (`host.split(":")[0]`), so adding the bare IP `76.13.172.133`
  (no `:8032` suffix) is sufficient — consistent with the assignment's own
  framing of this as "the #1 way this deploy silently 400s," i.e. a denial, not a
  disclosure.

#### F7. WebSocket `Origin` check is not a defense against a non-browser attacker — verified by design, not a gap
- **File:Line:** `ws/realtime.py:205-206,224` — `origin` is read from the
  handshake headers and checked with `_origin_allowed` (`realtime.py:194-195`)
  only *after* `websocket.accept()`. This looks like a TOCTOU gap but isn't one
  in practice: the `Origin` header is attacker-controlled on any non-browser
  client (`curl`, a Python `websockets` script, `wscat`) — it can be set to
  anything, so the allow-list can never stop a scripted attacker regardless of
  when it runs. Its actual job is defending a **browser-based** victim (CSWSH from
  a malicious page open in an authenticated operator's tab, where the browser —
  not the server — enforces the `Origin` header's honesty). The real control
  against an anonymous internet client is the mandatory first-frame JWT
  (`realtime.py:227-236`), already covered as reachability answer (a) = No.
  No code change indicated; recorded so the check isn't mistaken for a
  network-layer control it was never meant to be.

#### F8. `.spid` upload/download path traversal — verified closed
- **File:Line:** `packages/smart_pid_domain/src/smart_pid_domain/dtos/project.py:18-32`
  (`validate_project_name` — charset-restricted regex, explicit `.`/`..`/blank
  rejection) and `application/project_service.py:79-91`
  (`_safe_project_path` — resolves the candidate path and rejects it unless its
  parent is exactly the resolved `projects_dir`). Both the DTO layer and the
  filesystem layer independently enforce this, so a crafted `name` cannot escape
  `SPID_PROJECTS_DIR`. Size is capped at `max_upload_bytes` (2 GiB default,
  `config.py:64`) and a free-disk guard rejects an upload once it would leave the
  volume under `min_free_disk_bytes` (1 GiB default, `config.py:71`,
  enforced per-chunk in `routers/project.py:66-84`). All three checks require
  `require_admin` first (`project.py:153,190`), so this surface is Tier-1-gated
  by F1, not independently reachable.

#### F9. SQL injection — verified closed
- Every query in `adapters/outbound/user_repo.py` is parameterized
  (`?` placeholders, values passed as a tuple/list — e.g. `user_repo.py:87-90`,
  `104-108`, `176-184`); the one dynamically-built `SET` clause
  (`user_repo.py:172-184`) assembles column *names* only from a fixed literal
  tuple never influenced by caller input, with all *values* still parameterized.
  No injection surface found in the routers reviewed.

#### F10. CSRF against command endpoints — not applicable
- All authenticated writes require an `Authorization: Bearer <jwt>` header
  (`dependencies.py:108-121`, `get_current_user`), never a cookie. Browsers do
  not auto-attach `Authorization` headers cross-site, so the classic
  cookie-riding CSRF vector does not apply to this API's write surface.

---

## 3. Minimal changes to make a public-internet deployment of this defensible

Ordered by what closes the largest exposure first. Each item is a small, scoped
change — not a rewrite.

1. **Put TLS in front of port 8032** (reverse proxy with a real certificate, or
   equivalent) before the box is reachable from the public internet. Nothing
   below matters if credentials and tokens are sniffable in transit. *(deploy
   mechanics — coordinate with the peer deployment task, not fixed by this repo's
   Python code.)*
2. **Stop seeding a literal `admin`/`admin` account.** Require an explicit
   bootstrap password env var, or generate-and-log-once a random one, in
   `main.py::_seed_default_admin`.
3. **Add login rate limiting / lockout** to `POST /auth/login`
   (`routers/auth.py`) — per-username and per-IP, even a simple in-process
   counter is a large improvement over none.
4. **Disable `/docs`, `/redoc`, `/openapi.json`** for this deployment
   (`docs_url=None, redoc_url=None, openapi_url=None` on the `FastAPI(...)` call
   in `app.py:107`), or gate them behind `require_admin`.
5. **Confirm `SPID_TRUSTED_HOSTS` includes `76.13.172.133`** and
   **`SPID_ALLOWED_WS_ORIGINS` includes `http://76.13.172.133:8032`** in the
   runtime `.env` — both are deploy-config, not code, but both are load-bearing:
   without the first the API 400s on every request; without the second
   `/ws/realtime` 4401s on every browser client (telemetry silently dead in the
   HMI) even though a scripted attacker is unaffected either way (Finding F7).
6. **Cap `LoginRequest.username`/`.password` length** (`Field(max_length=128)`,
   matching `UserCreate`) and set a request body size limit at whichever layer
   terminates TLS in step 1.
7. **Neutralize the login timing side channel** (constant-time dummy-hash
   comparison when the username does not exist) — low priority until a second
   user account exists, cheap to do now.

---

## Proposed tech debt

*(For the coordinator to transcribe into `.claude/reports/_tech-debt.md`. Not
written there directly per this task's constraints.)*

- **Login brute-force has no throttle.** `POST /auth/login`
  (`routers/auth.py:30-51`) accepts unlimited attempts per second with no
  per-IP/per-username backoff. Compounds directly with TD-011 (unfixed, this
  report's Finding F1) — the two together mean the seeded default account is not
  just guessable, it is guessable at unlimited speed. Fix belongs alongside
  whatever resolves TD-011, since both touch the same login path.
- **`/docs` / `/redoc` / `/openapi.json` are public by default** (`app.py:107` —
  no `docs_url`/`redoc_url`/`openapi_url` override). Low cost, single-line fix;
  not previously tracked. Recommend a small `SPID_ENABLE_DOCS` toggle (default
  off) rather than a hardcoded `None`, so local dev / an internal-network
  deployment can still opt in.
- **`LoginRequest` has no field length limits**, unlike `UserCreate`
  (`smart_pid_domain/dtos/auth.py:12-14` vs `:23-25`). Small DTO fix, no
  behavior change for legitimate callers.
- **No request body size limit at the ASGI/ uvicorn layer.** `main.py:562-568`
  configures `uvicorn.Config` with no `--limit-max-requests`/body-size ceiling,
  and no middleware in `app.py` imposes one for JSON bodies (only the multipart
  `.spid` upload path is capped, via `max_upload_bytes`,
  `routers/project.py:66-84`). Whoever owns the reverse-proxy/TLS work in Finding
  F2 should set `client_max_body_size` there; it is the natural place for it and
  avoids a second body-buffering pass inside the Python process.
- **Login timing side channel** (Finding F5) — cosmetic today (one known
  account), becomes a real username-enumeration vector the first time `POST
  /users` creates a second account. Cheap fix, low urgency; worth bundling with
  whatever next touches `routers/auth.py`.
- **`_reject_if_last_active_admin` only protects the *last* admin, not the
  currently-logged-in operator's own account from a *different* admin.**
  (`routers/users.py:44-58`, referenced by F1.) This is arguably correct
  multi-admin behavior once the default-admin problem (TD-011) is fixed and a
  real second admin exists with a real password — flagged here only because it
  is part of why F1 is as bad as it is on a single-admin deployment. No action
  needed unless the product intentionally moves to a multi-admin trust model,
  in which case an audit-log alert on "admin deactivated another admin" would be
  the natural next step, not a code restriction.
