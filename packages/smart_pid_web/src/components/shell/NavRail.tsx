import { NavLink } from 'react-router-dom';
import './NavRail.css';

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

export function NavRail() {
  return (
    <nav aria-label="Main navigation" className="nav-rail">
      {ITEMS.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.end}
          className={({ isActive }) =>
            isActive ? 'nav-rail__link nav-rail__link--active' : 'nav-rail__link'
          }
        >
          {item.label}
        </NavLink>
      ))}
    </nav>
  );
}
