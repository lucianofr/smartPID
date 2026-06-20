export function StatusIndicator({ state, label }: { state: 'normal' | 'down'; label: string }) {
  const dotColor = state === 'down' ? 'bg-[var(--state-error)]' : 'bg-[var(--state-running)]';
  return (
    <span className="inline-flex items-center gap-1 text-xs">
      <span aria-hidden className={`size-2 rounded-full ${dotColor}`} />
      <span className="text-text-secondary">{label}</span>
    </span>
  );
}
