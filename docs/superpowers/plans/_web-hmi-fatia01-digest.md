# Fatia 0+1 — Orchestrator Digest (controller working memory)

Branch `feat/web-fatia01-foundation-dashboard` off main `cb7f16c` (in `.worktrees/main-web-hmi`).
Subagents opus, TDD, conventional `feat(web):`/`fix(web):` no attribution. 12 tasks.

## GLOBAL CONSTRAINTS (binding)
**Dir `packages/smart_pid_web/`:** package.json(@smart-pid/web; scripts dev,build,test,test:e2e,gen:api,lint) ·
vite.config.ts(dev 127.0.0.1:5173; proxy /api→:8000, /ws→:8000 ws:true) · tsconfig(strict) ·
index.html(`<html data-theme="isa101">`) · playwright.config.ts(testDir ./e2e, baseURL http://127.0.0.1:5173) ·
src/api/{client.ts,queryClient.ts,generated/openapi.ts(gen:api openapi-typescript, gitignored)} ·
src/realtime/{envelope.ts,useRealtime.ts,RealtimeProvider.tsx} (CANONICAL) ·
src/auth/{AuthContext.tsx,RequireAuth.tsx,LoginPage.tsx} · src/theme/{tokens.css,themes.css,ThemeProvider.tsx} ·
src/components/shell/AppShell.tsx. gitignore: node_modules,dist,src/api/generated,test-results,playwright-report,.vite

**WS envelope `{type,loop_id,seq,ts,data}`:** type='status'|'action'|'alarm'|'ai'|'stats'|'system' (6; plan superset, contract §4 had 5);
loop_id:number|null(null EVENT.SYSTEM); seq:number(per-conn, gap-detect); ts:number(epoch sec, bridge-stamped); data:T.
**map_topic_to_envelope(topic:bytes,payload:dict,*,seq,ts)->dict|None:** STATUS.→status(id) · ACTION.CTRL.→action(id) ·
ACTION.AI.→ai(id) · EVENT.ALARM.→alarm · EVENT.SYSTEM→system(no id) · STATS.→stats(id). Bus payloads msgpack.

**Wire data:** StatusData{pv,sp,co,bkcal_in,bkcal_out:num; mode:str(8+BYPASS); kp,ti,td,integral_val,timestamp:num}
(error=sp-pv client-side; OPC state from REST GET /opcua/status NOT STATUS) · ActionData{cv,delta} ·
AlarmData{alarm_id,severity,state} · AiData{gamma,ki,strategy} · StatsData{iae,itae,ise,mse,sigma,tv,var_range,var_sp}.

**useRealtime():** {connected:bool; lastStatus:ReadonlyMap<number,StatusData>; lastStats:ReadonlyMap<number,StatsData>;
subscribe<T>(type,handler)=>()=>void; onResync(cb)=>()=>void}. RealtimeProvider: ONE
`new WebSocket(${proto}://${location.host}/ws/realtime)` (wss if https); first frame JSON `{type:'auth',token}` on open;
backoff 500ms→min(x*2,MAX); onResync on reconnect (hadConnection guard); status/stats→maps+forceRender, others→subscribers.

**Theme:** stable token names tokens.css (design-system §2.0); per-theme values themes.css via [data-theme]; ThemeProvider
sets data-theme + localStorage. Fatia 0+1 ships token contract + ISA-101. Gates WCAG AA ≥4.5:1; ISA-101 saturated=abnormal only.
**Auth:** POST /api/auth/login {username,password}→{access_token,token_type}. AuthContext: token useState+sessionStorage
key 'smart-pid-token'; {token,isAuthenticated,login,logout}. apiGet/apiPost prefix /api, Bearer, ApiError{status,detail}.
RequireAuth→/login. JWT HS256 decode_access_token(token,*,secret) / CoreSettings.jwt_secret. Single-admin no RBAC.
**Magic:** WS close 4401; config web_dist_dir:str|None=None (SPID_WEB_DIST_DIR), allowed_ws_origins tuple=("http://127.0.0.1:5173",)
(SPID_ALLOWED_WS_ORIGINS); SPA mount app.mount('/',StaticFiles(dir=dist,html=True)) AFTER routers.

## TASKS (deps)
1[BE] response_model audit: routers/{auth,controllers,opcua} — /auth/login→TokenResponse, /controllers→list[ControllerResponse],
  /controllers/{id}→ControllerResponse, /opcua/status→OPCUAStatusResponse (none)
2[BE] ConnectionManager async broadcast — ws/realtime.py+test (1)
3[BE] RealtimeBridge + map_topic_to_envelope, one asyncio.Task run_in_executor(None,sub.recv,10) (2)
4[BE] /ws/realtime endpoint: first-msg auth {type:auth,token} + Origin validation + ConnectionBuffer
  (coalesce status/stats, lossless bounded alarm/ai/system, close 4401 on overflow) (3)
5[BE] Wire into create_app — **TRIMMED (P4 did CORS+headers):** lifespan start/stop realtime_manager+realtime_bridge,
  SPA StaticFiles mount last, add config web_dist_dir+allowed_ws_origins. **Do NOT re-add CORS/SecurityHeaders** (4)
6[FE] scaffold Vite/React/TS toolchain + test/setup.ts(WS+matchMedia mocks) (none)
7[FE] theme tokens+themes+ThemeProvider (6)
8[FE] api client+AuthContext+RequireAuth+LoginPage+test (6)
9[FE] envelope.ts+RealtimeProvider+useRealtime+test (6,8 token)
10[FE] AnalogBar,ControllerCard,RealtimeTrend(uPlot),shell,DashboardPage (7,9)
11[E2E] Playwright login→dashboard status frame; route-mock /api/auth/login,/controllers,/opcua/status + mocked WS (PIC-005, PV 150.2) (10)
12[VERIFY] spec upkeep docs/smartPIDv2.md + full verify + state save (all)

## SEQUENCING
BE strict linear 1→2→3→4→5. FE 6 gates 7,8,9; 9 needs 8 token; 10 needs 7+9; 11 needs 10; 12 needs all.
Interfaces: ConnectionManager(2→3,4,5); RealtimeBridge/map_topic_to_envelope(3→4,5); /ws/realtime+app.state.realtime_*(4,5→9,11);
apiPost/AuthContext.token(8→9); useRealtime/lastStatus(9→10).

## RESOLUTIONS
- Task 5: trimmed (CORS+security-headers already on main via P4 cb7f16c). Only lifespan wiring + SPA mount + 2 config fields.
- 'system' type: accept plan's 6-value union (envelope.ts), note to align contract §4.
- Verification: full pytest SIGABRTs (Py3.14 aiosqlite) — targeted paths only. Frontend: npm test / playwright in packages/smart_pid_web.

## STATUS: starting Task 1.
