# Fatia 2 digest — Commands + Loop Config (merged main 3a77ae5, 2026-06-19)

Web command/config surface on the Live Dashboard. Backend reused intact except one additive
field. Forked main `427b670`; merged `--no-ff` → `3a77ae5`.

## Delivered
- `src/features/loop-config/`: types.ts, validation.ts, commandApi.ts, useCommands.ts,
  useAiControls.ts, CardControls.tsx, LoopConfigDialog.tsx, AiPanel.tsx, ConfirmApplyTuningDialog.tsx.
- `src/components/ui/Dialog.tsx` — NEW canonical accessible modal primitive (reused by both dialogs).
- `src/components/ControllerCard.tsx` — EXTENDED (⚙ button + `controls` slot); not redefined.
- `src/api/client.ts` — added apiPut/apiDelete. `src/api/controllers.ts` — FE ControllerResponse type.
- `src/pages/DashboardPage.tsx` — fetches full ControllerResponse[]; mounts CardControls+AiPanel per
  card; ⚙ opens LoopConfigDialog with full ai_config initial.
- Backend: `optimization_enabled` on ControllerResponse DTO + _to_response (+5 tests). ONLY backend change.
- e2e/fatia2-commands.spec.ts (network-mocked + WS stub). specs: smartPIDv2 §13, identidade_visual_ISA101 §4.3.

## Contract facts (for downstream fatias)
- Commands: setpoint/output key=`value`; mode=`mode`; optimization={controller_id,enabled};
  tuning={controller_id,kp,ti,td}; apply-tuning POST path no-body; AI start/stop/pause POST path no-body.
- All routes `require_authenticated_admin` (Bearer via client.ts). Errors → ApiError{status,detail}.
- ai_config persisted via PUT /controllers/{id}; MUST send all 9 fields (update_controller rebuilds whole AIConfig).
- Canonical to reuse: ui/Dialog, loop-config/types, commandApi types (AiStatus/TuningRecommendation/CommandResponse),
  useCommands/useAiControls hooks, api/controllers ControllerResponse.
- AiStatus.engine/objective/speed are UPPERCASE StrEnum on the wire (minor M1: FE typed string).

## Minors deferred (sdd/fatia2-minor-findings.md): M1 AiStatus typing/fixture casing; M2 dead onOpenConfig
prop; M3 sp_rate_* not edited; M4 fontWeight casts/hex fallbacks; M5 mode cast; M6 AiPanel density.
