import { lazy, type ComponentType } from 'react';
import { AlarmsPage } from '@/pages/AlarmsPage';
import { DashboardPage } from '@/pages/DashboardPage';
import { MultiTrendPage } from '@/pages/MultiTrendPage';

/**
 * `React.lazy` over a NAMED export — every page in this app exports by name,
 * and `lazy` insists on a default. One place to do the unwrapping.
 */
function lazyPage<T>(load: () => Promise<T>, pick: (module: T) => ComponentType): ComponentType {
  return lazy(async () => ({ default: pick(await load()) }));
}

/**
 * Secondary surfaces are code-split (§12 perf budget). Loops, Trends and
 * Alarms stay in the entry chunk — they are the operator's first paint. The
 * commissioning twin, the buyer dashboard and the admin group all load on
 * demand behind App's Suspense boundary.
 */
const SimulatorPage = lazyPage(() => import('@/pages/SimulatorPage'), (m) => m.SimulatorPage);
const ExecutiveDashboardPage = lazyPage(
  () => import('@/pages/ExecutiveDashboardPage'),
  (m) => m.ExecutiveDashboardPage,
);
const ProjectsPage = lazyPage(() => import('@/pages/ProjectsPage'), (m) => m.ProjectsPage);
const SettingsPage = lazyPage(() => import('@/pages/SettingsPage'), (m) => m.SettingsPage);
const ConnectionPage = lazyPage(() => import('@/pages/ConnectionPage'), (m) => m.ConnectionPage);
const UsersPage = lazyPage(() => import('@/pages/UsersPage'), (m) => m.UsersPage);

/**
 * Single route/navigation registry (§6.9). Every later phase appends ONE
 * literal here — the top bar and the configuration menu are both projections of
 * this array, so nothing has to be wired in two places.
 */
export interface AppRoute {
  path: string;
  element: ComponentType;
  adminOnly?: boolean;
  /** Top-bar entry (`Loops · Trends · Alarms · Sim · Executivo`). */
  nav?: { label: string; order: number };
  /** Configuration-menu entry (Projects, Settings, Connection, Users). */
  cfg?: { label: string; order: number };
}

export const appRoutes: AppRoute[] = [
  {
    path: '/',
    element: DashboardPage,
    nav: { label: 'Loops', order: 10 },
  },
  {
    path: '/multitrend',
    element: MultiTrendPage,
    nav: { label: 'Trends', order: 20 },
  },
  {
    path: '/alarms',
    element: AlarmsPage,
    nav: { label: 'Alarms', order: 30 },
  },
  {
    path: '/simulator',
    element: SimulatorPage,
    nav: { label: 'Sim', order: 40 },
  },
  {
    path: '/executive',
    element: ExecutiveDashboardPage,
  },
  // The configuration-menu administration group. Every entry is `adminOnly`:
  // the routers behind them are `require_admin`, so a `user` who reached one
  // would only collect 403s. RouteGuard sends them back to the dashboard and
  // AppShell drops the menu entries entirely.
  {
    path: '/projects',
    element: ProjectsPage,
    adminOnly: true,
    cfg: { label: 'Projects', order: 10 },
  },
  {
    path: '/settings',
    element: SettingsPage,
    adminOnly: true,
    cfg: { label: 'Settings', order: 20 },
  },
  {
    path: '/connection',
    element: ConnectionPage,
    adminOnly: true,
    cfg: { label: 'Connection', order: 30 },
  },
  {
    path: '/users',
    element: UsersPage,
    adminOnly: true,
    cfg: { label: 'Users', order: 40 },
  },
];

type WithNav = AppRoute & { nav: NonNullable<AppRoute['nav']> };
type WithCfg = AppRoute & { cfg: NonNullable<AppRoute['cfg']> };

/** Top-bar entries, ascending `nav.order`. */
export function navRoutes(routes: readonly AppRoute[] = appRoutes): WithNav[] {
  return routes.filter((r): r is WithNav => r.nav !== undefined).sort((a, b) => a.nav.order - b.nav.order);
}

/** Configuration-menu entries, ascending `cfg.order`. */
export function cfgRoutes(routes: readonly AppRoute[] = appRoutes): WithCfg[] {
  return routes.filter((r): r is WithCfg => r.cfg !== undefined).sort((a, b) => a.cfg.order - b.cfg.order);
}
