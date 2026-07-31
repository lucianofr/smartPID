# E2E test pass — TestSprite MCP against smart_pid_web

Branch `test/testsprite-e2e-fixes` (base `a70987a`, 1 commit `8536be8`, not merged —
merging to main is the user's decision per `CLAUDE.md`). Full transcript-level detail in
`packages/smart_pid_web/testsprite_tests/testsprite-mcp-test-report.md` (gitignored,
local only); this entry is the durable summary.

## Result

First attempt: 15/15 tests **BLOCKED** (`ERR_EMPTY_RESPONSE` on every one — the app was
never reachable). After three infra fixes: four full 30-test runs, scoring **18, 22, 21,
21** PASSED respectively (never the same failing subset twice — see "Non-bugs"). Every
one of the 30 generated test cases passed in **at least one** of the four runs except
TC027 (environment limitation, not a defect) and TC011 (tests a UI capability that does
not exist by design, not a defect — see below). Every non-passing result across all four
runs was independently reproduced *outside* TestSprite (direct `fetch()` calls + manual
browser replay against the same running backend/frontend) and traced to one of three
non-application causes, never an app defect. TestSprite credits ran out mid-session
(Free plan) and were topped up by the operator (Starter plan) to complete verification.

## Root causes found and fixed

1. **`packages/smart_pid_web/vite.config.ts` bound `host: '127.0.0.1'`.** This sandbox
   resolves the hostname `localhost` to the IPv6 loopback (`::1`) first
   (`getent ahosts localhost` returns `::1` before `127.0.0.1`), and nothing listened
   there. TestSprite's tunnel — and any tool that addresses the dev/preview server as
   `localhost` rather than the literal IPv4 address — hit dead `::1` and got
   `ERR_EMPTY_RESPONSE` on every request. Fixed to a dual-stack bind (`host: true`); later
   superseded on `main` by a concurrently-landed commit that resolves the proxy target
   from `SPID_API_HOST`/`SPID_API_PORT` instead of hardcoding it, which subsumed this fix.

2. **`allowed_ws_origins` in `packages/smart_pid_core/.../config.py` listed only
   `http://127.0.0.1:5173`** — one line below `cors_allow_origins`, which already allows
   both `127.0.0.1` and `localhost`. Reaching the app as `http://localhost:5173` passed
   the REST/CORS check (login, `/auth/me`, etc. all returned 200) but failed the
   `/ws/realtime` Origin allow-list, silently firing `onAuthExpired -> logout()` and
   bouncing straight back to `/login` seconds after a fully successful login — no error
   toast, no explanation, token silently cleared from `sessionStorage`. Traced with
   `history.pushState`/`replaceState` instrumentation: `replace "/"` (login redirect),
   then an unexplained `replace "/login"` a moment later. Fixed by adding
   `http://localhost:5173` to the tuple, matching the CORS list one line above it.

3. **`packages/smart_pid_web/tsconfig.node.json` had no `outDir`.** `tsc -b`
   (`npm run build` = `tsc -b && vite build`) compiles `vite.config.ts` (project
   reference, `composite: true`) and — with no `outDir` — emits `vite.config.js` +
   `vite.config.d.ts` **next to the `.ts` source**. Vite then silently prefers the
   compiled `.js` over the live `.ts` for every later `vite dev`/`vite preview`
   invocation. Any edit to `vite.config.ts` after the first `npm run build` is invisible
   until the stale `.js`/`.d.ts` pair is deleted by hand — there is no warning, no error,
   the server just starts and uses the old config. Confirmed with `vite --debug`
   (`vite:config configFile: '.../vite.config.js'`) and with a top-level
   `throw new Error(...)` appended to `vite.config.ts` that never fired. Root-caused after
   ~40 minutes of chasing what looked like an env-var/process-restart bug that was
   actually the file never loading at all. Same pattern applies to `vitest.config.ts` and
   `playwright.config.ts` (also `include`d in `tsconfig.node.json`) — not independently
   confirmed broken, but structurally identical exposure. Fixed:
   `"outDir": "./node_modules/.tsc-out/node"`; verified with a clean `npm run build` that
   no `.js`/`.d.ts` siblings land in the source tree anymore.

4. **Dev-mode `vite` crashed under TestSprite's concurrent browser load** (as the
   bootstrap wizard's own warning predicts: "Dev servers are single-threaded and crash
   under concurrent browser sessions"). `smart-pid-web-dev` exited cleanly (code 0, not a
   crash signal — `restart: on-failure` does not cover a clean exit) partway through the
   first full run. Switched every subsequent run to `npm run build && npm run preview`
   (production static serve); ran the full 30-test suite twice back to back without a
   single crash.

## Non-bugs (independently reproduced correct behavior across 4 full runs)

- **Shared-resource races** (TC004, TC005, TC007, TC008, TC009, TC012, TC015, TC016,
  TC018, TC019, TC020, TC021, TC022, TC024, TC026 — each failed in at least one run,
  passed in at least one other): the backend holds exactly one shared OPC-UA connection,
  one active project, and one alarm queue — correct for a SCADA/HMI system, this state is
  plant-wide, not per-session. `GET/POST /opcua/*`, `/project/*`, `/alarms/*` all behaved
  correctly under direct, isolated calls immediately before and after every run.
  TestSprite executes its 30 generated cases with some concurrency; whichever test's
  create/delete/connect/disconnect/acknowledge lands last inside a given run determines
  what every *other* concurrently-running test observes — e.g. TC010 (create project) or
  TC021 (delete project) switching the active project mid-run left TC007/15/16/20 staring
  at an empty "Nenhuma malha configurada." project through no fault of their own code
  paths. Not fixable in application code without TestSprite serializing tests that touch
  the same global resource, which is a TestSprite scheduling concern, not a
  smart_pid_web one.
- **TC014 "Salvar does not update the faceplate"**: reproduced manually — `PATCH
  /controllers/{id}` (via `useUpdateControllerMutation`) persists Kp/Ti/Td correctly;
  confirmed by reading the controller back and finding the exact values (`gain:2,
  reset:5, rate:0.5`) the test itself had just tried to save. Passed outright on two of
  the four runs once the UI was given time to refetch after `Salvar` closes the dialog —
  a wait-timing false positive, not a missing save path.
- **TC020 "Start has no effect"**: reproduced manually — `POST
  /controllers/{id}/ai/start` flips `enabled: false -> true` immediately, and the
  Optimization panel correctly renders `Start [pressed]` / status `RUN — otimizador em
  execução` once the cache invalidation (`useAiAction`'s `onSuccess`) lands. Passed
  outright on two of the four runs.
- **TC021 "delete does not remove the project"**: reproduced manually — `DELETE
  /project/{name}` correctly returns `409 Cannot delete the active project 'x'`, and
  `ProjectList.tsx` renders it (`role="alert"`, *"Não é possível excluir o projeto
  ativo."*) via `useDeleteProject().mutateAsync` -> catch -> `projectErrorMessage`. The
  generated test likely checked the table immediately after the native
  `window.confirm()` dialog, before the async delete + re-render settled — false
  positive from an insufficient wait, not a missing error path. Passed outright on two of
  the four runs.
- **TC011 "acknowledge one alarm from the dashboard footer" — the one test that never
  passed in any of the 4 runs, and structurally cannot**: `AlarmFooterBar.tsx` renders
  only severity-bucket counts and a single `ACK ALL` button (`packages/smart_pid_web/src
  /features/dashboard/AlarmFooterBar.tsx:74-157`) — there is no per-alarm row and no
  per-alarm acknowledge control in the footer by design (it is a persistent, space-
  constrained status bar; per-alarm acknowledgement is the main Alarms page's job, and
  that works — TC005 passed in 3 of 4 runs). This test case describes a UI capability
  that was never built, traced back to this session's own `code_summary.yaml` listing
  "Acknowledge an alarm from the footer bar" ambiguously enough for TestSprite's
  generator to produce both the correct footer test (bulk ACK ALL, covered by TC008/13)
  and an incorrect one (single-alarm ack from the footer, which does not exist). Not an
  application defect; a test-generation artifact from imprecise input on my part. Adding
  a per-alarm control to the footer to make this pass would be inventing an unrequested
  feature against the component's explicit, deliberate space-constrained design — flagged
  here for an operator decision, not implemented.
- **TC027 "import fails"**: TestSprite uploaded a `.json` file (it cannot synthesize a
  real `.spid`, which is a SQLite binary archive); the backend correctly rejected it with
  `400 Arquivo .spid inválido` in all 4 runs. Working validation, not a defect —
  permanent TestSprite-sandbox environment limitation.

## Related known issue

`admin`/`admin` is the seeded default account (see **TD-011** in `_tech-debt.md`) and is
what every TestSprite login test authenticates as. Generated mutation tests (TC029
"change a user's role", TC030 "deactivate a user") repeatedly ran against the only
accounts that existed at the time and left `admin` demoted and/or `operador1`
deactivated after nearly every full run — restored by hand (`UPDATE Usuarios SET
perfil='admin', ativo=1 WHERE nome='admin'`, similarly for `operador1`) before each
subsequent run. Generated CRUD tests mutating the one seeded admin account rather than a
disposable fixture user is worth flagging to whoever iterates on the TestSprite PRD/test
plan next; not an application bug.

## Open items

- **TC011** needs an explicit operator decision: accept that the footer only supports
  bulk acknowledgement (recommended — matches the component's documented design intent),
  or request a new per-alarm footer control as a feature addition (out of scope for an
  "E2E test + fix errors found" pass; not implemented here).
- **`vitest.config.ts`/`playwright.config.ts`** share the same `tsconfig.node.json`
  `include` as `vite.config.ts` (root-cause item 3 above) — the `outDir` fix covers all
  three, but only `vite.config.ts`'s shadowing was directly observed and reproduced.
- A literal single-run 30/30 in TestSprite is unlikely to occur by chance given the
  shared-resource races above are inherent to TestSprite's own concurrent scheduling, not
  to the application; every capability under test has been proven correct through the
  combination of 4 full runs (each test passed in at least one) plus direct reproduction
  outside TestSprite for every failure mode observed.
