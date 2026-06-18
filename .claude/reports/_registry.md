# Report Registry

**Last Updated:** 2026-06-18

> Central index of agent work. Check here before starting new work.

---

## 2026-06-18

<!-- Format: - report-name | Status | One-line summary -->
<!-- Example: - review-auth-timeout-20251228 | Completed | Root cause and fix plan -->

- arch/arch-web-hmi-20260618 | Completed | RealtimeWS bridge: CRITICAL naive `await recv` blocks daemon; STATUS.{id} is the live frame (not TELEMETRY); discrete events must not coalesce; StaticFiles/CORS + OPC-via-REST; zmq.asyncio + ConnectionManager.
- review/review-web-hmi-contract-20260618 | Completed | Contract-accuracy audit of fatia specs vs backend — wrong routes/topics, missing endpoints, GAPs (enable PID, OPC start/stop, export list).
- security/security-web-hmi-20260618 | Completed | CRITICAL: project router unauth + path traversal; HIGH: /commands/tuning guardrail bypass, no CORS/TrustedHost (0.0.0.0), no upload size limit; MEDIUM: WS `?token=`.
- tests/tests-web-hmi-20260618 | Completed | Test-plan & acceptance-criteria review — replace non-verifiable prose (≈60 fps, "paridade visual") with objective asserts; RBAC negative tests; ack≠clear.
- design/design-web-hmi-system-20260618 | Completed | Design review of the web HMI design system (tokens/components/themes), authority for all fatias.
- spec: docs/superpowers/specs/2026-06-18-web-frontend-design-system-design.md | Created | Web frontend design-system spec — single source of UI tokens, components and themes for the 8 fatias.

---

## Archive

Older entries are moved to: `reports/archive/_registry-archive.md`

