import type { ComponentType } from 'react';
import { DashboardPage } from '@/pages/DashboardPage';

/**
 * Single route/navigation registry (§6.9). Every later phase appends ONE
 * literal here — the top bar, the `[cfg]` menu and the `[k]` palette are all
 * projections of this array, so nothing has to be wired in three places.
 */
export interface AppRoute {
  path: string;
  element: ComponentType;
  adminOnly?: boolean;
  /** Top-bar entry (`Loops · Trends · Alarms · Sim`). */
  nav?: { label: string; order: number };
  /** `[cfg]` menu entry (Projects, Settings, Connection, Users — phase 10). */
  cfg?: { label: string; order: number };
  /** `[k]` command-palette entry. */
  command?: { label: string; keywords?: readonly string[] };
}

export const appRoutes: AppRoute[] = [
  {
    path: '/',
    element: DashboardPage,
    nav: { label: 'Loops', order: 10 },
    command: { label: 'Ir para Malhas', keywords: ['loops', 'malhas'] },
  },
];

type WithNav = AppRoute & { nav: NonNullable<AppRoute['nav']> };
type WithCfg = AppRoute & { cfg: NonNullable<AppRoute['cfg']> };
type WithCommand = AppRoute & { command: NonNullable<AppRoute['command']> };

/** Top-bar entries, ascending `nav.order`. */
export function navRoutes(routes: readonly AppRoute[] = appRoutes): WithNav[] {
  return routes.filter((r): r is WithNav => r.nav !== undefined).sort((a, b) => a.nav.order - b.nav.order);
}

/** `[cfg]` menu entries, ascending `cfg.order`. */
export function cfgRoutes(routes: readonly AppRoute[] = appRoutes): WithCfg[] {
  return routes.filter((r): r is WithCfg => r.cfg !== undefined).sort((a, b) => a.cfg.order - b.cfg.order);
}

/**
 * Palette entries: nav order first, then cfg order, then registration order —
 * the palette mirrors the visible IA instead of inventing a third ranking.
 */
export function commandRoutes(routes: readonly AppRoute[] = appRoutes): WithCommand[] {
  const rank = (r: AppRoute): number =>
    r.nav !== undefined ? r.nav.order : r.cfg !== undefined ? 1000 + r.cfg.order : Number.MAX_SAFE_INTEGER;
  return routes
    .filter((r): r is WithCommand => r.command !== undefined)
    .map((r, i) => ({ r, i }))
    .sort((a, b) => rank(a.r) - rank(b.r) || a.i - b.i)
    .map(({ r }) => r);
}
