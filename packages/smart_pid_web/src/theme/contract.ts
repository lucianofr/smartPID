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
  '--trend-pv-width', '--trend-sp-width', '--trend-co-width',
  // Bar
  '--bar-track', '--bar-fill', '--bar-marker',
  // Type
  '--font-display', '--font-ui', '--font-data',
] as const;