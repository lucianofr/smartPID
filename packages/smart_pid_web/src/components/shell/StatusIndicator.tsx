export function StatusIndicator({ state, label }: { state: 'normal' | 'down'; label: string }) {
  const color = state === 'down' ? 'var(--state-error)' : 'var(--state-running)';
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 'var(--sp-1)', fontSize: 'var(--text-xs)' }}>
      <span aria-hidden style={{ width: 8, height: 8, borderRadius: '50%', background: color }} />
      <span style={{ color: 'var(--text-secondary)' }}>{label}</span>
    </span>
  );
}
