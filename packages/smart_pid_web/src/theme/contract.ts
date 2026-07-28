/**
 * §6.4 token contract (normative). All themes define ALL of these names.
 * Components consume ONLY these custom properties (guarded by token-guard.test.ts).
 */
export const THEME_IDS = ['recorder', 'phosphor', 'isa101'] as const;
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
  // Alarm (four severities — CRITICAL/WARNING/ADVISORY/LOG)
  '--alarm-crit', '--alarm-crit-bg', '--alarm-warn', '--alarm-warn-bg',
  '--alarm-adv', '--alarm-adv-bg', '--alarm-log', '--on-alarm',
  // State (gray in normal operation — green never means "ok")
  '--state-running', '--state-stopped', '--state-error', '--state-oos',
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
  // Type
  '--font-display', '--font-ui', '--font-data',
] as const;