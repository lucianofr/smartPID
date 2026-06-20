import { NavLink } from 'react-router-dom';

interface NavItem {
  to: string;
  label: string;
  /** Exact match avoids "/" staying active on every nested route. */
  end?: boolean;
}

const ITEMS: ReadonlyArray<NavItem> = [
  { to: '/', label: 'Dashboard', end: true },
  { to: '/executive', label: 'Executive' },
  { to: '/multitrend', label: 'Multi-trend' },
  { to: '/simulator', label: 'Simulator' },
  { to: '/alarms', label: 'Alarms' },
  { to: '/settings', label: 'Settings' },
  { to: '/connection', label: 'Connection' },
  { to: '/projects', label: 'Projects' },
];

const LINK_BASE =
  'flex min-h-11 items-center rounded-none border-l-[3px] border-transparent px-3 py-2 text-sm text-text-secondary no-underline transition-colors duration-200 hover:bg-surface-container-high hover:text-text focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-[var(--focus-ring)] active:bg-surface-container';
const LINK_ACTIVE = 'border-l-text bg-surface-container-high font-semibold text-text';

export function NavRail() {
  return (
    <nav
      aria-label="Main navigation"
      className="flex w-[var(--nav-rail-w-expanded)] shrink-0 flex-col gap-1 border-r border-border bg-surface-container p-2"
    >
      {ITEMS.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.end}
          className={({ isActive }) => (isActive ? `${LINK_BASE} ${LINK_ACTIVE}` : LINK_BASE)}
        >
          {item.label}
        </NavLink>
      ))}
    </nav>
  );
}
