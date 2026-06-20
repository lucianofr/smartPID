import { StatusIndicator } from './StatusIndicator';
import { ThemeSwitcher } from './ThemeSwitcher';

export function TopBar({ opcDown }: { opcDown: boolean }) {
  return (
    <header
      style={{
        height: 'var(--appbar-h)', background: 'var(--surface-container)',
        borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center',
        padding: '0 var(--sp-4)', gap: 'var(--sp-4)', color: 'var(--text)',
      }}
    >
      <strong style={{ fontSize: 'var(--text-lg)' }}>Smart PID</strong>
      <span style={{ flex: 1 }} />
      <ThemeSwitcher />
      <StatusIndicator state={opcDown ? 'down' : 'normal'} label="OPC" />
    </header>
  );
}
