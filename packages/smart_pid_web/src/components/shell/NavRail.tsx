import {
  LayoutDashboard,
  BarChart3,
  LineChart,
  FlaskConical,
  Bell,
  Settings,
  PlugZap,
  FolderOpen,
  type LucideIcon,
} from 'lucide-react';
import { NavLink } from 'react-router-dom';

interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  /** Exact match avoids "/" staying active on every nested route. */
  end?: boolean;
}

const ITEMS: ReadonlyArray<NavItem> = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/executive', label: 'Executive', icon: BarChart3 },
  { to: '/multitrend', label: 'Multi-trend', icon: LineChart },
  { to: '/simulator', label: 'Simulator', icon: FlaskConical },
  { to: '/alarms', label: 'Alarms', icon: Bell },
  { to: '/settings', label: 'Settings', icon: Settings },
  { to: '/connection', label: 'Connection', icon: PlugZap },
  { to: '/projects', label: 'Projects', icon: FolderOpen },
];

// Responsive (Task 9.2 / §9): >=1024 the rail is the 224px expanded label list; below 1024 it
// collapses to the 64px icon-only rail. The collapse is CSS-driven (`max-lg:` variants over the
// 1024 token breakpoint) — no toggle/state, so the shell DOM stays stable and every link keeps its
// accessible name. The label `<span>` is hidden (`max-lg:hidden`) and the icon shown only when
// collapsed (`hidden max-lg:block`); each link carries `aria-label` so the name survives the
// collapse and `assertMinTarget` sees a >=44x44 target (min-h-11 + the 64px rail width).
const LINK_BASE =
  'flex min-h-11 items-center gap-3 rounded-none border-l-[3px] border-transparent px-3 py-2 text-sm text-text-secondary no-underline transition-colors duration-200 hover:bg-surface-container-high hover:text-text focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-[var(--focus-ring)] active:bg-surface-container max-lg:justify-center max-lg:gap-0 max-lg:px-0';
const LINK_ACTIVE = 'border-l-text bg-surface-container-high font-semibold text-text';

export function NavRail() {
  return (
    <nav
      aria-label="Main navigation"
      className="flex w-[var(--nav-rail-w-expanded)] shrink-0 flex-col gap-1 border-r border-border bg-surface-container p-2 max-lg:w-[var(--nav-rail-w)] max-lg:p-1"
    >
      {ITEMS.map((item) => {
        const Icon = item.icon;
        return (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            aria-label={item.label}
            className={({ isActive }) => (isActive ? `${LINK_BASE} ${LINK_ACTIVE}` : LINK_BASE)}
          >
            <Icon className="hidden h-5 w-5 shrink-0 max-lg:block" aria-hidden="true" />
            <span className="max-lg:hidden">{item.label}</span>
          </NavLink>
        );
      })}
    </nav>
  );
}
