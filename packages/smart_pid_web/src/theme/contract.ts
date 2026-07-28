/**
 * §6.4 token contract (normative). All themes define ALL of these names.
 * Components consume ONLY these custom properties (guarded by token-guard.test.ts).
 *
 * `optimizer` / `optimizer-dark` are the smartPID Optimizer design system —
 * directions 1a ("Painel Executivo", light) and 1b ("Comando IA", dark) of
 * docs/design/claude-design/smartPID-Optimizer-Dashboard.dc.html. They are the
 * first themes to carry a BRAND layer: the four legacy palettes are instrument
 * chrome with no brand voice, so they answer the brand tokens with their own
 * accent rather than with LFR navy/amber.
 */
export const THEME_IDS = [
  'optimizer',
  'optimizer-dark',
  'recorder',
  'phosphor',
  'isa101',
  'neon',
] as const;
export type ContractThemeId = (typeof THEME_IDS)[number];

export const CONTRACT_TOKENS = [
  // Surfaces
  '--bg', '--surface', '--surface-sunk',
  // Lines
  '--rule', '--rule-strong',
  // Text
  '--text', '--text-soft', '--text-disabled',
  // Focus / selection / overlay
  '--focus-ring', '--selection', '--scrim',
  // Accent
  '--accent', '--accent-hover', '--accent-sunk', '--accent-soft', '--on-accent',
  // Brand (design-system layer). The interactive accent above answers "what can
  // I click"; these answer "whose product is this" — wordmark, active nav rule,
  // the KPI band and the AI call-to-action. Never used for process indication.
  '--brand-ink', '--brand-ink-deep',
  '--brand-accent', '--brand-accent-hover', '--brand-accent-soft', '--on-brand-accent',
  '--kpi-band',
  // Alarm (four severities — CRITICAL/WARNING/ADVISORY/LOG)
  '--alarm-crit', '--alarm-crit-bg', '--alarm-warn', '--alarm-warn-bg',
  '--alarm-adv', '--alarm-adv-bg', '--alarm-log', '--on-alarm',
  // State (gray in normal operation — green never means "ok")
  '--state-running', '--state-stopped', '--state-error', '--state-oos',
  // The optimiser strategy chip (FUZZY / RL) and the OPC-UA link dot. `--live`
  // is the one green the ISA-101 doctrine permits: it reports a COMMS link, not
  // a process state.
  '--state-ai', '--state-ai-soft', '--live',
  // Trend
  '--trace-pv', '--trace-sp', '--trace-co',
  '--trend-grid', '--trend-axis', '--trend-bg',
  '--trend-pv-width', '--trend-sp-width', '--trend-co-width', '--trend-sp-dash',
  // Bar
  '--bar-track', '--bar-fill', '--bar-marker',
  // Glow (§10.5) — the salience channel. Bloom is reserved for alarms, focus,
  // the PV trace and primary-button hover; steady state never blooms. The three
  // shadow tokens are `0 0 #0000` (a valid no-op <shadow>) outside neon, NOT
  // `none`: `none` cannot appear inside a comma-separated box-shadow list and
  // would invalidate Tailwind's composed ring.
  '--glow-alarm', '--glow-focus', '--glow-accent', '--glow-trace',
  // Elevation. The design system lifts the selected loop card and rests every
  // other card on a hairline; `0 0 #0000` keeps the flat themes flat.
  '--shadow-card', '--shadow-lifted',
  // Type
  '--font-display', '--font-ui', '--font-data',
] as const;
