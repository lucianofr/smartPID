# Fatia 7 digest — Settings + OPC Connection + Projects (web HMI)

**Merged:** main `2a17c78` (--no-ff), 2026-06-20. Branch `feat/web-fatia7-settings-connection-projects`
(forked main `0961c7c`, 13 commits). Frontend + tests-only (zero `packages/` production change).
Final review (code-reviewer opus): **MERGE** — 0 Crit/0 High/0 Med; 1 Low fixed.

## Shipped (all `packages/smart_pid_web/src/` unless noted)
- `features/settings/` — `settingsTypes.ts` (AppPreferences{trendWindowSeconds=120,numberDecimals=2,confirmDestructive=true}, key `spid.preferences`), `useSettings.ts` (localStorage, immutable, merges partial over defaults), `SettingsForm.tsx`+`.css`. `pages/SettingsPage.tsx`.
- `features/connection/` — `opcuaApi.ts` (getStatus/saveEndpoint(PUT /opcua/endpoint)/connect(POST optional)/disconnect/browse(GET /opcua/browse/{enc})/search(GET /opcua/search?q=)), `useOpcua.ts` (useSaveEndpoint/useConnect/useDisconnect → all `setQueryData(['opcua-status'])`; useBrowse enabled nodeId!=null; useSearch enabled q nonempty), `ConnectionPanel.tsx` (endpoint field + Connect/Disconnect, Disconnect disabled unless ONLINE, NO acquisition controls), `TagBrowser.tsx` (searchbox; browse vs search; icon by node_class), `pages/ConnectionPage.tsx` (inline-polls ['opcua-status'] refetchInterval 5000).
- `features/projects/` — `projectApi.ts` (list/create(POST /project/new {name})/open(POST /project/open {name})/import(apiUpload multipart file+optional name)/download(apiDownload ACTIVE only)/remove(apiDelete /project/{enc})), `useProjects.ts` (useProjectList key ['projects','list']; 4 mutations invalidate list), `ProjectList.tsx` (Open/Download/Delete; confirmDestructive→window.confirm; error regions), `ProjectImportDropzone.tsx` (file input→useImportProject, progress, role=alert, input reset on finally), `WelcomeDialog.tsx` (post-login modal; hooks-before-early-return; New/Import navigate /projects), `pages/ProjectsPage.tsx` (New-project form).
- `api/client.ts` — NEW `apiUpload<T>(path, FormData)` (Bearer header, NO Content-Type so browser sets boundary, ApiError map, 204→undefined). `api/client.upload.test.ts`.
- `App.tsx` — 3 routes (RequireAuth, named imports, no lazy) + WelcomeDialog mount in Shell (guard `sessionStorage['spid.welcome-seen']`, `showWelcome = token!=null && !seen`). `components/shell/NavRail.tsx` — Settings/Connection/Projects items.
- Backend `tests/core/integration/` — `test_project_auth_required.py` (param sweep 6 routes→401, POSTs send {name:x}), `test_project_export_no_credentials.py` (new_project→download_path→sqlite_master has no cred tables).
- Docs: `docs/smartPIDv2.md` §17, `docs/identidade_visual_ISA101.md`.

## Reusable canon (REUSE in Fatia 8 — do not recreate)
- `apiUpload` (`api/client.ts`) — authed multipart for any future upload.
- Single OPC-status source: `useOpcuaStatus()` (`api/executive.ts`, key `['opcua-status']`); never duplicate. Connection mutations keep it fresh via setQueryData.
- Feature layout = `src/features/<domain>/` (settings/connection/projects), domain-named (NOT fatia-numbered). Pages = `src/pages/<Name>Page.tsx`, NAMED export, self-shell `<AppShell opcDown>`, root `<div>`.
- Project DTOs (hand-typed from live Pydantic): ProjectListItem{name,controller_count,size_bytes}; ProjectResponse{name,path,controller_count}. OPC: OpcuaStatus{state,endpoint|null} (executive.ts), OpcuaNode{node_id,display_name,node_class}, ConnectionState OFFLINE/CONNECTING/ONLINE/RECONNECTING.
- Mono-user contract: no users/roles UI; unauth→401 (single gate require_authenticated_admin). Credentials in users.db, never in .spid.
- **Fatia 8 caveat:** WelcomeDialog modal now mounts post-login — any NEW e2e that seeds a token must also seed `sessionStorage['spid.welcome-seen']='1'` (else the overlay intercepts clicks). The 9 existing fatia-using specs already do.

## SDD ledger (archived)
T0 investigation (no commit; verified project-auth GATED, settings client-only, opcua/project/auth DTOs).
T1 `5866bba` useSettings. T2 `36fb403` SettingsForm/Page. T3 `b44097e` opcuaApi/useOpcua. T4 `42c7b49`(+fix `a0f973c` font-mono→.numeric) ConnectionPanel/TagBrowser/Page. T5 `98617ef` projectApi/useProjects+apiUpload. T6 `9b0a2b3` pytest contracts. T7 `3a1ba77`(+fix `f6cd598` error surfaces+input reset) ProjectList/Dropzone/Page. T8 `1389846` WelcomeDialog+mount. T9 `3c90f76` e2e+fixture. T10 `00347cd` docs+legacy-e2e welcome-seen regression fix. Final-review Low `a1176a2` drop dead useCurrentProject.

## Deferred minors (non-blocking; full list in sdd/fatia7-minor-findings.md)
numberDecimals no clamp on empty input · credential-boundary denylist (consider allowlist of 7 project tables) · auth-sweep omits POST /import · per-row Download = active only (backend GAP, no per-name endpoint) · WelcomeDialog no focus-trap/Escape.

## Recurring STALE-brief corrections (apply every fatia)
generated/ gitignored → hand-type DTOs (no gen:api) · briefs use src/components|features/fatiaN → real domain folders · briefs use api.get/post object → real named apiGet/apiPost/apiPut/apiDelete/apiUpload/apiDownload · briefs use default export+lazy → named export+RequireAuth · `tnum`/`--space-N`/`--font-mono` → `.numeric`/`--sp-N`/`--font-data` · tests colocated src/** · /tmp cd paths → real worktree.
