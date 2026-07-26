// Fixture: gradients built from token var()s carry no raw color. The §6.9
// card-row edge fade (phase 4) depends on this staying legal — the guard bans
// raw COLORS, not gradients (unlike the retired ISA-101 flat-surface guard).
export function GradientTokenAllowed() {
  return (
    <div
      aria-hidden="true"
      className="pointer-events-none absolute inset-y-0 right-0 w-8"
      style={{ backgroundImage: 'linear-gradient(to right, transparent, var(--bg))' }}
    />
  );
}