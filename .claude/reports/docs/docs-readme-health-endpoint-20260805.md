# Docs fix: Windows installer README health-check reference

`packaging/windows/README.md` (merged today from `feat/windows-installers`) told
operators to verify a fresh install with `curl http://localhost:8000/health` —
that route does not exist in the backend. The only unauthenticated status
endpoint is `GET /system/status` (mounted via `system.router` at prefix
`/system` in `app.py`, handler in `routers/system.py` explicitly documented as
"Health check — no auth required", returning `{"status": "running", ...}`
with no process values). Updated the single verification-checklist line
(line 58) from `curl http://localhost:8000/health` returns HTTP 200 to
`curl http://localhost:8000/system/status` returns HTTP 200 (JSON body).
Grepped the whole file for `/health` afterward — no other occurrences, so no
further lines needed changing. No code was touched.

## Proposed tech debt

No e2e or smoke test exercises the Windows installer verification checklist
itself (it's a manual VM-based doc, not driven by CI), so this class of drift
— checklist referencing a route that was renamed/removed in the API — can
recur silently whenever backend routes change without someone cross-checking
`packaging/windows/README.md`. Consider either a lightweight CI check that
greps installer/README docs for `curl .../<path>` patterns and asserts the
referenced routes exist in the FastAPI route table, or a note in the PR
template asking authors of API route changes to grep `packaging/` for stale
references.
