// Fixture: must trip the no-raw-color guard.
//   - `bg-[#fff]` is an arbitrary hex color utility
//   - `text-red-500` is a named Tailwind palette color utility
//   - the inline `color` is a raw hex literal
// Each of these is a §6.4 violation (color must come from a token utility).
export function RawColorViolation() {
  return (
    <div className="bg-[#fff] text-red-500" style={{ color: '#00ff00' }}>
      raw color offender
    </div>
  );
}