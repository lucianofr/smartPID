// Fixture: must produce NO lint error.
// Every color comes from a token utility (bridged in index.css via `@theme inline`),
// and the surface is flat (no shadow, no gradient, no bevel).
export function TokenColorClean() {
  return (
    <div className="bg-surface text-text border border-border rounded-none">
      token-only, flat surface
    </div>
  );
}
