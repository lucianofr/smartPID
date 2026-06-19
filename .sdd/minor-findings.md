## T4 minor findings (final-review triage)
- [auth_ok] realtime.py:119 — auth_ok control frame is outside canonical {type,loop_id,seq,ts,data} envelope; brief-mandated. FE realtime contract (T9) must treat auth_ok as control, not data.
- [buffer-unwired] realtime.py:62-85 — ConnectionBuffer built+unit-tested but NOT wired into bridge broadcast; close-on-overflow requirement (contract: overflow→close→REST resync) unimplemented in Fatia 0+1 (T5 trimmed). CROSS-FATIA GAP — needs explicit deferral decision or a follow-up task.
- [dict-annot] realtime.py:65-81 — bare dict annotations; prefer dict[str,Any] for mypy-strict consistency.
## T5 minor findings (final-review triage)
- [smoke-heavy] test_ws_realtime.py:204+ — route-existence smoke test spins real SQLite/EventBus/LoopManager; could use light stub. Matches house style. Optional.
- [fn-local-import] test_ws_realtime.py:206-213 — function-local imports; hoist to module top if consistent. Optional.
- [spa-untested] app.py:183-188 — SPA mount branch (web_dist_dir set + dir exists) exercised by no test; add when built bundle exists (relevant to T11/T12).
## T6 minor/tech-debt (final-review triage)
- [npm-audit] smart_pid_web: 7 vulns (1 critical, 1 high) in transitive DEV deps at pinned majors; not in shipped bundle. Revisit when version pins relax (post-Fatia 0+1).
- [brief-amend] T6 brief: tsconfig.node.json noEmit triggers TS6310 under tsc -b — implementer correctly removed noEmit + gitignored tsbuildinfo/config.{js,d.ts}. Amend plan brief.
## T8 minor findings (final-review triage)
- [render-side-effect] AuthContext.tsx:141 — setTokenGetter(()=>token) called in render body (impure but functionally correct live token); prefer useEffect([token]) or ref. Optional.
- [autocomplete] LoginPage.tsx:204,206 — inputs lack autoComplete=username/current-password; password-manager+a11y nicety. Cosmetic.
## T9 minor findings (final-review triage)
- [json-parse-guard] RealtimeProvider onmessage now try/catches JSON.parse (applied in fix 3a894fc). Resolved.
- [contract] StatusData.timestamp is ISO-8601 string (not epoch) — brief corrected digest 'num'; ensure contract §4 + T12 spec upkeep reflect string.
