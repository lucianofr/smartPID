# Task 1 Report — Backend `response_model` audit for Fatia 0+1 dashboard routers

## Status
DONE

## Branch
`feat/web-fatia01-foundation-dashboard` (already checked out at start; branch creation skipped per instructions). Worktree: `/home/luciano/Documentos/ProjetosClaudeCode/smartPID/.worktrees/main-web-hmi`.

## Audit result — all four endpoints already declare the correct `response_model`

| Endpoint | Router (line) | Declared `response_model` | DTO exists | Outcome |
|---|---|---|---|---|
| `POST /auth/login` | `routers/auth.py:31` | `TokenResponse` | `dtos/auth.py:14` | already OK |
| `GET /controllers` | `routers/controllers.py:351` | `list[ControllerResponse]` | `dtos/controllers.py:203` | already OK |
| `GET /controllers/{controller_id}` | `routers/controllers.py:376` | `ControllerResponse` | `dtos/controllers.py:203` | already OK |
| `GET /opcua/status` | `routers/opcua.py:29` | `OPCUAStatusResponse` | `dtos/opcua.py:9` | already OK |

All DTO names match the contract verbatim — no name discrepancies. Per the brief, when all four already declare `response_model`, **no production code edits were made** (audit pass, no change). The routers were left untouched (`git diff` on the three router files is empty).

## What was added
TDD regression test that locks the OpenAPI contract so a future drop of any `response_model` is caught:

- `tests/core/integration/test_api_response_model_contract.py`

It mounts only the three audited routers on a bare `FastAPI()` app (no DB/ZMQ/dependency graph required), generates `app.openapi()`, and asserts each route's `200` response references its expected component schema:
- direct `$ref` ending in the model name for object responses (`TokenResponse`, `ControllerResponse`, `OPCUAStatusResponse`);
- `type: array` with `items.$ref` ending in `ControllerResponse` for `list[ControllerResponse]`.

## TDD red→green evidence
- **Red property proven:** a route mounted without `response_model` produces a `200` schema of `{}` with no `$ref`, so `_ref_name(...) == None != expected` and the assertion fails. Verified in an isolated sandbox (no edits to real routers).
- **Green:** with the existing declarations, all parametrized cases pass.

## Verification
- New contract test + auth + controllers integration tests:
  `SPID_JWT_SECRET=test-secret uv run pytest tests/core/integration/test_api_response_model_contract.py tests/core/integration/test_api_auth.py tests/core/integration/test_api_controllers.py -q` → **24 passed** (~10s).
- OPC-UA API integration tests: **3 passed**.
- Ruff (line-length 100) on the new test file: **All checks passed**.
- App import smoke (Step 3): `import ...api.app` → `ok True`.

## Scope notes
- Only the new test file and this `.sdd/` report were created. No router edits. The session "files modified" scope warnings refer to pre-existing worktree state outside this task; not touched.
- Did not run full `uv run pytest tests/` (Py3.14 aiosqlite SIGABRT) — ran targeted suites only, as instructed.

## Commit
- `51ae813` feat(web): lock response_model contract for fatia-0+1 dashboard routers
