import type { ReactNode } from 'react';
import { NavRail } from './NavRail';
import { TopBar } from './TopBar';

export function AppShell({ opcDown, children }: { opcDown: boolean; children: ReactNode }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', background: 'var(--bg)' }}>
      <TopBar opcDown={opcDown} />
      <div style={{ display: 'flex', flex: 1, minHeight: 0 }}>
        <NavRail />
        <main style={{ flex: 1, overflow: 'auto', padding: 'clamp(var(--sp-4), 2vw, var(--sp-8))' }}>{children}</main>
      </div>
    </div>
  );
}
