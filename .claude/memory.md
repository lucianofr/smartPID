# smartPID — Project Memory

Durable facts for agent sessions. Keep short, keep true.

## Stack
- Backend: Python >= 3.13, uv workspace (`packages/smart_pid_core`, `packages/smart_pid_domain`). Root `pyproject.toml` configures ruff (line-length 100), mypy strict, pytest.
- Frontend: `packages/smart_pid_web` — React 18 + Vite 5 + Tailwind 4, vitest, playwright (e2e), npm. Excluded from uv workspace.
- Dev web: `npm run dev` (vite) on port 5173, proxies `/api` and `/ws` to the backend.

## Tests
- Backend tests: `tests/` (pytest, asyncio_mode auto; OPC-UA server spun up in-test on a free port — no external services needed).
- Frontend unit tests: `npm test` (vitest) in `packages/smart_pid_web`; e2e in `e2e/` via playwright.
- Integration marker: `integration` (external services).

## Architecture notes
- Alarm banner chain: `/alarms/active` REST + `EVENT.ALARM` WS frames → points map → severity buckets.
- RL optimizer state persisted under `models/rl_state_<id>.json`.
- Projects stored as files under `projects/` (`project.spid` at root is a sample).
- OpenAPI contract: `npm run gen:api` dumps backend schema into `src/api/generated/openapi.ts`; `gen:api:check` fails on drift.

## Conventions
- Caveman rules installed for Cursor/Windsurf/Cline/Copilot (see `.cursor/rules/caveman.mdc` etc.).
- Commits: conventional (`feat:`, `fix:`, `refactor:`, `docs:`, `test:`).
- Evidence screenshots live in `test-evidence/`; plans in `plans/`.
