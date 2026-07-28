# SDD ledger — Web Frontend Rewrite (Recorder/Phosphor)

Strategy: one implementer per phase; plan tasks are steps inside the dispatch.
Phase gate: backend pytest (0–1) / frontend test+typecheck+lint+E2E (2–11).
Terminal gate: TEST_E2E.md 50/50 via real Chrome + real backend + simulator.

## Phases 0–10 — DONE (independently re-verified, not taken on report)

| Phase | Evidence I ran myself |
|---|---|
| 0 two-role RBAC | `test_role_contract.py` 180/180 |
| 1 SQLAlchemy async | 3 engines; see bootstrap defect below |
| 2 foundation | 17 primitives; bundle in budget |
| 3 realtime + pure modules | frameCache replay added later |
| 4 shell/login/dashboard | first E2E re-green |
| 5 loop-config/commands/AI | 337/50 at close |
| 6 alarms | 398/57 at close |
| 7 multitrend/stats/export | re-verified on my client fix, no drift |
| 8 simulator | 490/72 at close |
| 9 executive | route-level React.lazy split 193.7 → 184.0 KB |
| 10 settings/connection/projects/users | 592/81 |

Current frontend: **592 unit / 81 files**, `tsc -b` 0, eslint 0, **Playwright 53/53**.
Current backend: **655 unit + 32 api + 162 domain = 849 pass**, role contract 180/180, zero exclusions.

## Genuine product bugs found and fixed (NOT test drift)

Found by `BackendFixtureFix`:
1. `commands.py` called `controller_label()` unimported — NameError on every SP/mode/CO/tune write.
2. `asyncua>=1.1` resolved to 1.1.8, which does `issubclass()` on a str annotation and cannot open a
   secure channel on Python 3.14. Reproduced against vanilla asyncua. Bumped to `>=2.0` (2.0.1).
3. `ai.py` used `AuditAction.{START,STOP,PAUSE}_AI_OPTIMIZATION`, which never existed → 500.
4. `ai.py` did `await pub.send(...)` on a sync method → 500 in all three handlers.
5. `stop_ai`/`pause_ai` referenced `bus` without declaring it → NameError/500.
6. Project import never enforced `max_upload_bytes` — the TD-004 upload guard was dead code.

Found by me, booting the real daemon (commit `47e5bb8`):
7. **The daemon could not start at all.** `main.py` passed the deleted `repo.db` to
   `_load_alarm_configs` and `_retention_cleanup`.
8. **`/auth/login` returned 500.** `AIRepository`/`AlarmRepository`/`AuditRepository` were constructed
   with the repository object instead of its session factory.

Both of 7–8 survived every suite because **no test imports `__main__`**. 849 backend tests were green
while the product was unbootable. Fixed, then verified over real HTTP: login 200 (164-char token),
`/auth/me` → admin claims, `/controllers` 200, `/alarms/active` 200.

Also fixed by me (`820f312`, `6f7da80`):
9. Spurious "Sem permissão" toast on every user-role reconnect — `run()` fired `onForbidden` at
   transport level before throwing, so `resync.ts` catching the 403 was too late. Added an additive
   `RequestOptions { silentForbidden }`; only the admin-only simulator probe passes it. 401 is never
   silenced. Mutation-checked: reverting the guard fails the new test.
10. `CLAUDE.md` documented `SPID_API_HOST` as `0.0.0.0` while `config.py` hardens it to `127.0.0.1`
    (TD-004) — docs contradicted the security default.
11. `test_process_speed_speed_factor` still asserted the pre-`c39158c` table. That commit
    ("improve RL learning speed") shifted every tier up one notch. Production is normative;
    `tests/domain` is now 162/162 with no exclusions.
12. ISA-101 never rendered the solid blue SP its own §6.3 rules require: `buildUplotTheme` baked
    `dash: [6, 4]` for every theme, in v1 and in the phase-2 rewrite alike. The dash is now the
    `--trend-sp-dash` token (`6 4` recorder/phosphor, `none` isa101).
13. The phase-2 interim ISA-101 block collapsed `--border` (65 class uses) and `--divider` (10)
    onto `--rule` and kept the *minority* hex, so 60 boundaries rendered a step too dark. Also
    `--selection` had been given an arbitrary value instead of the old hover/selected raise.
    Both corrected against the pre-rewrite palette at `ca0a6f6`; see
    `packages/smart_pid_web/docs/isa101-token-mapping.md`.

## Open risks (not blockers, but real)
- **Intermittent zmq deadlock** in `EventBus.stop()` → `ctx.destroy()` under suite-wide pressure.
  Reproduced: `tests/core/unit` stalls at ~21% on one run, then passes 655 in 38.84s with `-v`.
  Pre-existing (present in the pre-change baseline). Deserves its own ticket.
- A **running daemon holds zmq 5555 and will abort a concurrent pytest run.** Stop it before testing.
- `ai.py` has 6 ruff F821 for `Annotated[dict[int, "AIWorker"], ...]`; `AIWorker` is never imported.
  Harmless today but the same class as bugs 1/3/5.
- asyncua 1.x→2.x is a major bump; all 40 opcua tests pass and the adapter needed no change, but it
  warrants a real-hardware smoke before release.
- `tests/hmi` has 18 pre-existing PySide6 failures — out of scope, no HMI file touched.
- **The trend well paints no trace.** With 24 rows confirmed in the plotted data (the panel's own
  CSV export), a patched `CanvasRenderingContext2D.prototype.stroke` shows uPlot issuing the
  PV/SP/CO strokes with the right colours and widths (`#1b4f87 w=2`, `#7c8894 w=1.5`,
  `#bc7211 w=1.5`), yet the canvas ends up holding only `--trend-grid` and `--trend-axis` pixels.
  The pen tip's filled circle does not land either — a degenerate series path, not a colour
  problem. The product's signature element (§6.7) therefore renders empty under the mocked
  socket. Found in phase 11 while freezing the visual baselines; deliberately NOT fixed there
  (out of scope, and it needs live telemetry to confirm). Confirm against a real backend in the
  terminal gate; if it reproduces, it needs its own fix phase.

## Phase 11 — COMPLETE (`f0d9736`, `2ff767b`, `688cadf`, `ace5edb`)
ISA-101 finalised on the shared §6.4 vocabulary — all three themes declare the identical 41 tokens,
every ISA hex traced to `ca0a6f6` and pinned by `src/theme/isa101Mapping.test.ts`. Task 2 was
already satisfied by `7603b80` (exactly the 21 obsolete PNGs deleted); said so with evidence rather
than inventing work. 13 terminal visual baselines recorded and reproduced byte for byte over two
full runs. `bundle-baseline.json` retightened 174.9 → 184.0 KB gzip — the measured feature-complete
size, not a hidden regression; budget constants untouched at 300/50/160 KB.
Gate: unit 681/82, typecheck 0, lint 0, build 0, check:bundle 0, playwright **66/66** (the 53
retained specs plus the 13 new baselines). Report: `.superpowers/sdd/phase11-report.md`.

## Terminal gate — TEST_E2E.md 50/50, not yet attempted
Boot contract verified: all 8 `SPID_` env vars map to real settings; Vite proxy 5173 → 8000 with
`/api` stripped and `/ws` upgraded. Daemon boots ready in ~4 s with the simulator on 4849.
