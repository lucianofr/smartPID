# Architecture Review — Web HMI (React/Vite) RealtimeWS bridge

**Date:** 2026-06-18
**Scope:** `2026-06-18-web-hmi-react-migration-design.md` + the 8 fatia specs — the WebSocket
bridge (RealtimeWS) and packaging of the new `smart_pid_web` frontend over the existing
Smart PID v2 backend.
**Status:** Completed (persisted manually — the architect agent could not write to disk).

---

## Summary

The overall approach is sound: add a single second EventBus consumer (RealtimeWS) and a
React/Vite frontend, with no changes to engine/workers/OPC/fuzzy/RL/persistence. Several
specifics in the original design were wrong or risky and must be corrected before
implementing Fatia 0+1. Findings below, by severity.

---

## CRITICAL

- **Naive `await sub.recv()` blocks the daemon loop.** `BusSubscriber.recv()` is a blocking
  ZMQ call. Awaiting it directly on the asyncio loop freezes the whole daemon (PID engine,
  workers, publisher all stall). Fix: use `zmq.asyncio` (preferred) OR a single shared
  `run_in_executor` single-flight consumer that fans out to all WS clients. Never a per-client
  recv loop; never concurrent recv on one socket.

## HIGH

- **Wrong WS source topic.** The live dashboard frame is the ENRICHED `STATUS.{id}` produced
  by MonitorWorker (pv/sp/co/mode/error/saturated/kp/ti/td), NOT `TELEMETRY.{id}` (which is
  internal to the backend and not bridged). The real bridged topics are `STATUS.{id}`,
  `ACTION.CTRL.{id}`, `ACTION.AI.{id}`, `EVENT.ALARM.*`, `EVENT.SYSTEM`, `STATS.{id}`. The
  original `ALARM` / `TELEMETRY.{id}` mapping is invalid. `EVENT.SYSTEM` was omitted.
- **Last-value coalescing must not be applied to discrete events.** Coalescing is fine for
  `STATUS`/`STATS` but coalescing `EVENT.ALARM`/`ACTION.AI`/`EVENT.SYSTEM` drops alarm
  transitions — a safety regression. Use a lossless bounded per-client queue for discrete
  events; on overflow close the socket so the client reconnects and re-syncs via REST.
- **Packaging gaps.** The app currently mounts no `StaticFiles` and has no CORS. To serve the
  SPA: `app.mount("/", StaticFiles(directory=dist, html=True))` AFTER the routers
  (single-origin SPA fallback → no CORS needed); alternatively an explicit CORS allow-list.
  OPC status is REST-polled (`GET /opcua/status`), NOT a WS topic — the dashboard spec was
  wrong to source it from WS.
- **Thread/loop safety.** Use `zmq.asyncio` for the consumer and a `ConnectionManager` guarded
  by an `asyncio.Lock` for the active-connection set and resilient broadcast.

## Confirmations (design choices that are correct)

- RealtimeWS as a 2nd EventBus consumer in the same asyncio loop — CORRECT (direct analog of
  the existing `TelemetryPublisher`).
- Handshake token auth — CORRECT and necessary; reject with close `4401`.
- The 8-fatia ordering is SOUND (Fatia 0+1 is the end-to-end foundation; others depend on it).
- Freezing PySide6 during transition is safe — REST/event contracts do not change.

## MEDIUM / LOW

- Add `stats` to the WS envelope `type` enum.
- Add a per-connection `seq` for client-side gap detection.
- Single msgpack unpack → broadcast (decode once, fan out) instead of per-client decode.
- Audit routers for Pydantic `response_model` so the frontend can generate OpenAPI-typed
  clients.
- Define a reconnect re-sync contract: on WS reconnect, refetch controllers, active alarms,
  and ai/status via REST.
- Recommend binding the API to `127.0.0.1`.
- WS auth via `?token=` leaks through logs/history — prefer a short-lived ws-ticket or
  first-message auth (tracked as TD-006).

---

## Related reports / debt

- security/security-web-hmi-20260618.md (CRITICAL project router auth + path traversal; CORS;
  upload size; `/commands/tuning` guardrails)
- Tech debt: TD-001..TD-006 in `_tech-debt.md`.
