// Fixture: must trip the flat (no-box-shadow) rule.
//   - the inline `boxShadow` is a raised/bevel effect
//   - `shadow-lg` is a Tailwind elevation utility
//   - `bg-gradient-to-r` would introduce a gradient
// ISA-101 mandates flat surfaces — no shadows, no gradients, no bevels.
export function BoxShadowViolation() {
  return (
    <div
      className="shadow-lg bg-gradient-to-r from-zinc-100 to-zinc-300"
      style={{ boxShadow: '0 1px 2px #000' }}
    >
      flat-violation offender
    </div>
  );
}
