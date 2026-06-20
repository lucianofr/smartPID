import type { ReactNode } from 'react';
import { NavRail } from './NavRail';
import { TopBar } from './TopBar';
import { AlarmBar } from '../../features/alarms/AlarmBar';

export function AppShell({ opcDown, children }: { opcDown: boolean; children: ReactNode }) {
  return (
    <div className="flex h-screen flex-col bg-bg">
      <TopBar opcDown={opcDown} />
      <div className="flex min-h-0 flex-1">
        <NavRail />
        <main className="flex-1 overflow-auto p-[clamp(var(--sp-4),2vw,var(--sp-8))]">{children}</main>
      </div>
      <AlarmBar />
    </div>
  );
}
