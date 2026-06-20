// Fixture: the sanctioned dialog scrim/backdrop — must produce NO lint error.
// `bg-black/60` is the ONE allowed translucent overlay (ISA-101 spec, Task 0.3):
// it is a Tailwind opacity utility on `black`, NOT a shadow/gradient/bevel and NOT
// an arbitrary hex or named-palette color. The flat + no-raw-color rules are written
// so this passes naturally; the real scrim lives in `ui/dialog-primitive.tsx`.
export function ScrimAllowed() {
  return <div data-testid="dialog-backdrop" className="fixed inset-0 z-50 bg-black/60" />;
}
