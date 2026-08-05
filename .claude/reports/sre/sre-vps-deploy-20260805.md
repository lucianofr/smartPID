# smartPID VPS deployment — 2026-08-05

Final. smartPID is live at `http://76.13.172.133:8032/` in a single Docker
container, verified end to end from this workstation (never from inside the
VPS).

## What was built

Files authored in the repo working tree (`/home/luciano/Documentos/ProjetosClaudeCode/smartPID`):

- **`Dockerfile`** (repo root) — multi-stage: Node 20 builds the SPA
  (`packages/smart_pid_web`), Python 3.13 + `uv` installs the backend
  daemon (`packages/smart_pid_core`, workspace-aware via
  `packages/smart_pid_domain`) and serves as the runtime image.
- **`.dockerignore`** (repo root) — trims the build context to source +
  lockfiles; excludes VCS metadata, caches, docs/plans, test evidence,
  runtime data (`*.spid`, `models/`, `projects/`, `exports/`), and local
  secrets (`.env`).
- **`docker-compose.yml`** (repo root) — the single deployment mechanism
  (rationale below).
- **`deploy/README.md`** — exact first-deploy / redeploy / rollback /
  secret-rotation procedure.

### Compose vs. a deploy script — which one, and why

Chose **`docker-compose.yml`**, not a `deploy/*.sh` wrapper around
`docker run`. The full contract (image tag, container name, restart policy,
port mapping, named volume, env-file) is entirely declarative with no
conditional logic, retries, or multi-step orchestration that would benefit
from a script. Compose expresses it in ~15 lines, is idempotent
(`docker compose up -d` no-ops on an unchanged spec and recreates only what
changed), and is the tool an operator reaches for first on a Docker host. A
`docker run` script would duplicate the same information with more room for
drift (a forgotten flag on a manual rerun) and no idempotency for free.
`deploy/README.md` documents the procedure against this one mechanism — it
does not duplicate a second one.

## Image / container / volume / env layout

| Item | Value |
|---|---|
| Image tag | `smartpid:latest` (1.32 GB) |
| Container name | `smartpid` |
| Restart policy | `unless-stopped` |
| Port mapping | `0.0.0.0:8032->8000/tcp`, `[::]:8032->8000/tcp` (only 8032 published; ZMQ 5555, simulator 4849, OPC-UA client stay unpublished) |
| Volume | named volume `smartpid-data` → `/data` in-container |
| Volume physical path (VPS host) | `/var/lib/docker/volumes/smartpid-data/_data` |
| Runtime env file | `/opt/smartpid/.env`, mode `0600`, passed via compose `env_file:` (the compose equivalent of `docker run --env-file`) |
| Source on VPS | `/opt/smartpid` (rsynced working tree; image built there — no registry, no `git clone`, no deploy key on the VPS) |
| Runs as | **non-root**, `appuser` uid/gid 1000 — confirmed below |

### Runs as root or non-root, and where data physically lives (as required)

**Non-root.** `docker exec smartpid id` → `uid=1000(appuser) gid=1000(appuser) groups=1000(appuser)`.
`/data` is pre-created and `chown`ed to `appuser` in the image *before* the
volume is mounted, so Docker's first-run volume population (which copies
the image's existing mount-point content, ownership included, into a fresh
empty named volume) lands the volume already owned by `appuser` — no
entrypoint chown script was needed, and none was added.

**Persisted data physically lives** at
`/var/lib/docker/volumes/smartpid-data/_data` on the VPS host filesystem,
containing `project.spid` (+ `-wal`/`-shm`), `users.db` (+ sidecars),
`projects/`, and `exports/`, all owned by `appuser:appuser`. Confirmed
present, correctly owned, and unchanged in ownership after a `docker
restart smartpid`.

### Dockerfile stages

1. **`web-builder`** (`node:20-slim`, matching `.github/workflows/ci.yml`'s
   pinned Node 20): `npm ci`, then `VITE_API_BASE="" npm run build`. The
   empty `VITE_API_BASE` is what makes single-origin serving work at all —
   see defect #2 below. Output: `dist/`.
2. **`runtime`** (`python:3.13-slim`, final image): `uv` installed via
   `COPY --from=ghcr.io/astral-sh/uv:latest`. Copies only the workspace
   root manifest/lock plus `packages/smart_pid_domain` and
   `packages/smart_pid_core` — never `smart_pid_web`'s source, which is
   excluded from the uv workspace and is npm-managed.
   `uv sync --frozen --no-dev --package smart-pid-core` installs the daemon
   and its workspace dependency, skipping the `dev` dependency-group
   (pytest, ruff, mypy, httpx) and the `pyinstaller`/test tooling in
   `smart-pid-core`'s own `dev` extra (never requested, never installed).
   `--package smart-pid-core` was required because the root `pyproject.toml`
   is a virtual workspace root with no dependencies of its own — a plain
   `uv sync` resolved and installed nothing (confirmed: first attempt
   produced an empty `.venv` and the container failed to start with
   `exec: "smart-pid-core": executable file not found in $PATH`; fixed by
   naming the package explicitly). Copies the built SPA from stage 1 to
   `/app/web/dist`. Creates non-root `appuser`, `EXPOSE 8000`,
   `CMD ["smart-pid-core"]`.

## Runtime `.env` (`/opt/smartpid/.env`, mode 0600)

Generated with `openssl rand -hex 32` (64 hex chars, value redacted here and
never pasted into any report or log) and written directly to the VPS —
never staged in the local repo, never rsynced. Contents (secret redacted):

```
SPID_JWT_SECRET=<redacted — 64 hex chars>
SPID_API_HOST=0.0.0.0
SPID_API_PORT=8000
SPID_TRUSTED_HOSTS=["76.13.172.133","localhost","127.0.0.1"]
SPID_ALLOWED_WS_ORIGINS=["http://76.13.172.133:8032"]
SPID_CORS_ALLOW_ORIGINS=["http://76.13.172.133:8032"]
SPID_DB_PATH=/data/project.spid
SPID_USERS_DB_PATH=/data/users.db
SPID_PROJECTS_DIR=/data/projects
SPID_WEB_DIST_DIR=/app/web/dist
SPID_LOG_LEVEL=INFO
```

`SPID_BOOTSTRAP_ADMIN_PASSWORD` was deliberately **not** set: leaving it
unset makes the daemon generate a fresh `secrets.token_urlsafe(12)` password
per empty-`users.db` deploy, logged once at WARNING
(`docker logs smartpid | grep bootstrap_admin_password`) rather than pinning
a memorable value in a file — the whole point of fixing the old
`admin`/`admin` default was to stop shipping a guessable credential, and a
static env-var password chosen by whoever writes `.env` reintroduces the
same class of problem.

## Timeline of app-source defects found during this deploy

The task's non-goals explicitly exclude changing anything under `packages/`,
with instructions to stop and report rather than patch it myself. Four
pre-existing defects surfaced while wiring the container — none introduced
by this deploy work, all confirmed by reading actual source, not assumed.
Coordinator (`Main`) fixed three of the four directly in `packages/`
(verified: core suite 1470/1470 green after the combined change); I
implemented nothing under `packages/` myself.

1. **No `/health` endpoint.** The acceptance criteria (and
   `packaging/windows/README.md`, now fixed) assumed `GET /health` exists.
   It never did — the only health-check route is `GET /system/status`
   (unauthenticated, same purpose). `curl http://76.13.172.133:8032/health`
   correctly returns `404` (see Verification); `/system/status` is the
   acceptance-equivalent check, per explicit agreement with Main.

2. **Frontend/backend `/api` prefix mismatch (fixed by Main).**
   `packages/smart_pid_web/src/api/client.ts` hardcoded
   `const BASE = '/api'`; the backend mounts every router at root
   (`/auth`, `/controllers`, ...) with no `/api` prefix anywhere.
   `vite.config.ts`'s dev proxy strips `/api` before forwarding, hiding the
   bug in development. In the production single-origin build (the entire
   point of this deployment) nothing strips it, so every `/api/*` call from
   the browser hit the StaticFiles catch-all mount and got `404` — the
   shipped SPA could not log in or fetch anything, even though the
   container itself was healthy. Fixed in `client.ts`
   (`const BASE = import.meta.env.VITE_API_BASE ?? '/api'`, default
   unchanged so dev/`vite preview` keep working) plus the missing
   `packages/smart_pid_web/src/vite-env.d.ts`. My Dockerfile builds with
   `VITE_API_BASE=""` so the single-origin bundle calls unprefixed paths.
   Verified: the bundle served over the wire contains zero `/api/`
   occurrences and the literal string `/auth/login`.

3. **`npm run build` failed on a clean `npm ci` (fixed by Main).**
   `tsc -b` (part of `npm run build`) errored on every file touching
   `process`/`node:*` (`vite.config.ts`, `playwright.config.ts`, every test
   file pulled in by `tsconfig.json`'s `include`) because `@types/node` was
   not a declared devDependency and wasn't resolvable transitively
   (confirmed by grepping `package-lock.json` — the only hits were unrelated
   packages' *optional* peerDependencies on it, never actually installed).
   Invisible until now because `ci.yml`'s `web` job runs only `npm test`,
   never `npm run build`. `tsconfig.json` sets `noEmit: true` for this
   project, so as a deploy-scoped stopgap while waiting for the upstream
   fix I briefly ran `vite build` directly (bypassing the broken
   type-check; byte-identical `dist/`). Main independently reproduced the
   failure from a clean-room `rm -rf node_modules && npm ci` and landed
   `@types/node` (`^20.13.0`) as a proper devDependency with a relocked
   `package-lock.json`; my Dockerfile now runs the canonical
   `npm run build` again (`tsc -b` passes).

4. **Seeded `admin`/`admin` account (fixed by Main).**
   `main.py::_seed_default_admin` used to create `admin`/`admin` on any
   fresh `users.db` — exactly what a fresh `smartpid-data` volume produces.
   Fixed to generate a random `secrets.token_urlsafe(12)` password (or
   accept `SPID_BOOTSTRAP_ADMIN_PASSWORD` if an operator sets one
   explicitly), logged once at WARNING. Verified below: the old
   `admin`/`admin` credential now returns `401`, and the real generated
   password returns a valid token.

Also landed by Main alongside the above (not requested by me, discovered by
the parallel security-reviewer peer and worth recording since they change
what "working" means for this deployment): `GET /docs`, `/redoc`, and
`/openapi.json` are now gated behind `SPID_EXPOSE_OPENAPI` (default
`false`, so they 404 in this deployment — confirmed below); `POST
/auth/login` now has a 5-attempts/60s per-IP rate limiter; `LoginRequest`
now bounds username/password length.

## Verification

All commands below were run **directly from this workstation** (the same
machine `Main` operates from), never over SSH into the VPS.

### `curl .../health` → 404 (documented gap, not a passing acceptance item)

```
$ curl -sS -o /dev/null -w '%{http_code}\n' http://76.13.172.133:8032/health
404
```

### `curl .../system/status` → 200 (functional health-check equivalent)

```
$ curl -sS -o /dev/null -w '%{http_code}\n' http://76.13.172.133:8032/system/status
200
$ curl -sS http://76.13.172.133:8032/system/status
{"status":"running","uptime_s":67.1,"active_controllers":0,"bus_active":true,"api_version":"2.0.0","cpu_percent":17.5,"memory_percent":22.6}
```

### `curl .../` → 200, real SPA HTML

```
$ curl -sS -o /dev/null -w '%{http_code}\n' http://76.13.172.133:8032/
200
$ curl -sS http://76.13.172.133:8032/ | tail -c 250
    <script type="module" crossorigin src="/assets/index-fjuuNKoj.js"></script>
    <link rel="stylesheet" crossorigin href="/assets/index-Cw_vUGhv.css">
  </head>
  <body>
    <div id="root"></div>
  </body>
</html>
```

### Built JS/CSS asset → 200

```
$ curl -sS -o /dev/null -w 'js_status=%{http_code}\n' http://76.13.172.133:8032/assets/index-fjuuNKoj.js
js_status=200
$ curl -sS -o /dev/null -w 'css_status=%{http_code}\n' http://76.13.172.133:8032/assets/index-Cw_vUGhv.css
css_status=200
```

### Bundle served over the wire has no `/api/` prefix

```
$ curl -sS http://76.13.172.133:8032/assets/index-fjuuNKoj.js -o /tmp/bundle.js
$ grep -c '/api/' /tmp/bundle.js
0
$ grep -o '"/auth/login"' /tmp/bundle.js
"/auth/login"
```

### `/docs` and `/openapi.json` disabled by default (new hardening, not requested but verified)

```
$ curl -sS -o /dev/null -w 'docs=%{http_code}\n' http://76.13.172.133:8032/docs
docs=404
$ curl -sS -o /dev/null -w 'openapi=%{http_code}\n' http://76.13.172.133:8032/openapi.json
openapi=404
```

### Login end to end, against the public IP

Old default credential — must now fail:

```
$ curl -sS -o /dev/null -w 'old_default_login_status=%{http_code}\n' \
    -X POST http://76.13.172.133:8032/auth/login -H 'Content-Type: application/json' \
    -d '{"username":"admin","password":"admin"}'
old_default_login_status=401
```

Real generated bootstrap password, retrieved from `docker logs smartpid |
grep bootstrap_admin_password` on the VPS (value not reproduced here):

```
$ curl -sS -o /tmp/login.json -w 'login_status=%{http_code}\n' \
    -X POST http://76.13.172.133:8032/auth/login -H 'Content-Type: application/json' \
    -d '{"username":"admin","password":"<redacted>"}'
login_status=200
$ python3 -c "import json; d=json.load(open('/tmp/login.json')); print('has_access_token:', 'access_token' in d); print('token_type:', d.get('token_type')); print('token_len:', len(d.get('access_token','')))"
has_access_token: True
token_type: bearer
token_len: 164
```

### `docker ps` — container `Up`, correct port mapping

```
$ docker ps --filter name=smartpid --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
NAMES      STATUS          PORTS
smartpid   Up About a minute   0.0.0.0:8032->8000/tcp, [::]:8032->8000/tcp
```

### `docker restart smartpid` → second successful `/health`-equivalent 200, data and login survive

```
$ docker restart smartpid
smartpid
$ sleep 10 && docker ps --filter name=smartpid --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
NAMES      STATUS          PORTS
smartpid   Up 10 seconds   0.0.0.0:8032->8000/tcp, [::]:8032->8000/tcp
$ docker exec smartpid id
uid=1000(appuser) gid=1000(appuser) groups=1000(appuser)
```

Post-restart, from this workstation:

```
$ curl -sS -o /dev/null -w 'post_restart_status=%{http_code}\n' http://76.13.172.133:8032/system/status
post_restart_status=200
$ curl -sS http://76.13.172.133:8032/system/status
{"status":"running","uptime_s":18.7,"active_controllers":0,"bus_active":true,"api_version":"2.0.0","cpu_percent":35.3,"memory_percent":22.0}
$ curl -sS -o /dev/null -w 'post_restart_login_status=%{http_code}\n' \
    -X POST http://76.13.172.133:8032/auth/login -H 'Content-Type: application/json' \
    -d '{"username":"admin","password":"<redacted, same generated password>"}'
post_restart_login_status=200
```

The generated admin password still logging in after a restart proves
`users.db` (and the JWT secret used to validate/issue tokens) persisted
through the container recreation via the `smartpid-data` volume and `.env`
file — not just first boot.

### No dev port leaked into the container environment

Main flagged that a stray rsync of the local dev `.env`
(`SPID_API_PORT=8537`) would silently break the deployment. My rsync
commands only ever transferred an explicit file list or used
`--exclude=.env --exclude=.env.*`, so it was never copied — confirmed:

```
$ grep 8537 /proc/$(docker inspect -f '{{.State.Pid}}' smartpid)/environ
(no output — not present)
```

## Anything worked around

- The uv virtual workspace root has no dependencies of its own, so a bare
  `uv sync --frozen --no-dev` installs nothing; fixed with
  `--package smart-pid-core` (see Dockerfile stage notes above).
- Interim `vite build`-only workaround for the missing-`@types/node` build
  failure, reverted to canonical `npm run build` once Main landed the fix
  (defect #3 above) — the interim state was never left in the final
  Dockerfile.
- The `smartpid-data` volume was recreated once, deliberately, after Main's
  bootstrap-admin fix landed: the volume from my earlier interim deploy
  already contained a `users.db` row for the old `admin`/`admin` account
  (seeding only fires on an empty table), which would have masked the new
  random-password behavior. Recreating gives a genuinely fresh first-boot
  for the credential verification above; no real project data existed to
  lose (the `.spid` file at that point held only the daemon's own
  first-boot empty project).

## Proposed tech debt

(Coordinator owns `.claude/reports/_registry.md` / `_tech-debt.md` — these
are handed off, not filed directly.)

1. **`/health` route referenced by docs/ops tooling but absent from the
   API.** `packaging/windows/README.md`'s check has been corrected to
   `/system/status`, but any external monitoring, uptime checks, or load
   balancer health probes configured against `/health` for this or future
   deployments will 404. Either add a trivial `GET /health` alias (same
   body as `/system/status`, or a bare `200 OK`) or standardize all
   documentation/tooling on `/system/status` going forward — right now both
   names are "the health endpoint" depending which doc you read.
2. **Bootstrap admin is still a single shared `admin` account with no
   forced password rotation.** The random-password fix stops the
   credential from being guessable, but the password is a plaintext line in
   `docker logs` indefinitely (container log retention, `docker logs`
   history, any log-shipping pipeline) until an operator changes it. There
   is no "must change password on first login" flow and no expiry.
3. **No TLS.** `http://76.13.172.133:8032/` serves the login form and JWT
   over plaintext — the password and the issued bearer token are visible to
   anyone on-path between a browser and the VPS. Explicitly a non-goal for
   this task; flagging because it compounds directly with #2 (a
   network-sniffable admin credential immediately after being sniffable
   only via log access).
4. **The 611 KB `index-*.js` chunk** (`vite build`'s own warning: "Some
   chunks are larger than 500 kB after minification") is unrelated to this
   deploy but was visible in every build log — a candidate for
   `manualChunks`/dynamic `import()` code-splitting if initial load time on
   the VPS's link ever matters.
5. **Login rate limiter is in-process, single-worker state**
   (`ponytail`-flagged by its own author in `auth.py`): resets on every
   daemon restart and would need a shared store if this ever scales past
   one process. Not a problem at the current single-container scale, noted
   for whenever that changes.
