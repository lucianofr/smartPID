import type { Role } from '../api/types';
import { useAuth } from './AuthContext';

/**
 * Capability actions — the spec §9 permission table (12 rows) plus the phase-8
 * additive row `simulator.configure`: starting, presetting, retuning or
 * disturbing the digital twin is a CONFIGURATION act, while driving the twin's
 * SP/mode/CO stays `loop.operate`.
 * Frontend gating is PRESENTATION ONLY: the backend enforces on every route
 * (require_user / require_admin, phase 0).
 */
export const CAPABILITY_ACTIONS = [
  'view', // View dashboards, trends, alarms, stats
  'alarms.ack', // Acknowledge alarms
  'loop.operate', // Set SP, mode, manual CO
  'export.data', // Export data (create + download)
  'tuning.edit', // Edit PID / fuzzy / RL parameters, apply tuning
  'ai.control', // Start, pause, stop AI workers; optimization toggle
  'controllers.manage', // Create, edit, delete controllers
  'alarms.configure', // Configure alarm limits
  'opcua.configure', // OPC-UA connection and tag mapping
  'projects.manage', // .spid project management
  'users.manage', // Manage users
  'settings.manage', // Change application settings
  'simulator.configure', // Start/stop the twin, presets, dynamics, disturbances
] as const;

export type CapabilityAction = (typeof CAPABILITY_ACTIONS)[number];

const USER_ACTIONS: ReadonlySet<CapabilityAction> = new Set<CapabilityAction>([
  'view',
  'alarms.ack',
  'loop.operate',
  'export.data',
]);

/** Deny-by-default: null/undefined role (me not resolved) can do nothing. */
export function can(role: Role | null | undefined, action: CapabilityAction): boolean {
  if (role === 'admin') return true;
  if (role === 'user') return USER_ACTIONS.has(action);
  return false;
}

export function useCan(action: CapabilityAction): boolean {
  const { user } = useAuth();
  return can(user?.role ?? null, action);
}