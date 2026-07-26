// Fixture: must produce NO guard hit — every color is a §6.4 token utility.
export function TokenColorClean() {
  return (
    <div className="border border-rule bg-surface text-text">
      <span className="text-text-soft">token-only</span>
      <button
        type="button"
        className="bg-accent text-on-accent outline-none focus-visible:ring-2 focus-visible:ring-focus-ring"
      >
        ok
      </button>
    </div>
  );
}