import { StatusIndicator } from './StatusIndicator';
import { ThemeSwitcher } from './ThemeSwitcher';

export function TopBar({ opcDown }: { opcDown: boolean }) {
  return (
    <header className="flex h-[var(--appbar-h)] items-center gap-4 border-b border-border bg-surface-container px-4 text-text">
      <strong className="text-lg">Smart PID</strong>
      <span className="flex-1" />
      <ThemeSwitcher />
      <StatusIndicator state={opcDown ? 'down' : 'normal'} label="OPC" />
    </header>
  );
}
