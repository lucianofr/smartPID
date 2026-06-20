import { useSettings } from './useSettings';

/**
 * Application preferences form (Fatia 7; Task 8.3 — CSS migrated to flat ISA-101
 * token utilities). Two-column rows (label left, control right-aligned) under a
 * section header with a hairline rule. No theme control (Fatia 8) and no
 * admin/user-management controls (no backend endpoint for those here).
 */
const SECTION_TITLE =
  'm-0 mb-2 pb-1 border-b border-border text-text-secondary font-semibold uppercase tracking-[0.04em]';

const ROW = 'grid grid-cols-[1fr_auto] items-center gap-4 min-h-8';

const CONTROL =
  'numeric w-28 justify-self-end text-right bg-surface text-text border border-border-strong rounded-control px-2 py-1 ' +
  'focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-[var(--border-strong)]';

const CHECKBOX =
  'w-auto h-4 p-0 justify-self-end bg-surface text-text border border-border-strong rounded-control ' +
  'focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-[var(--border-strong)]';

const RESET =
  'self-start cursor-pointer bg-surface-container text-text border border-border-strong rounded-control px-4 py-2 ' +
  'transition-colors duration-fast hover:bg-surface-container-high ' +
  'focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-[var(--border-strong)]';

export function SettingsForm(): JSX.Element {
  const { preferences, setPreference, reset } = useSettings();

  return (
    <form
      className="flex flex-col gap-6 max-w-[32rem]"
      style={{ fontSize: 'var(--text-sm)' }}
      aria-label="Application preferences"
    >
      <section className="flex flex-col gap-2">
        <h2 className={SECTION_TITLE} style={{ fontSize: 'var(--text-sm)' }}>
          Display
        </h2>
        <div className={ROW}>
          <label className="text-text" htmlFor="numberDecimals">
            Number decimals
          </label>
          <input
            id="numberDecimals"
            className={CONTROL}
            type="number"
            min={0}
            max={6}
            value={preferences.numberDecimals}
            onChange={(e) => setPreference('numberDecimals', Number(e.target.value))}
          />
        </div>
        <div className={ROW}>
          <label className="text-text" htmlFor="trendWindow">
            Trend window (seconds)
          </label>
          <input
            id="trendWindow"
            className={CONTROL}
            type="number"
            min={10}
            max={3600}
            value={preferences.trendWindowSeconds}
            onChange={(e) => setPreference('trendWindowSeconds', Number(e.target.value))}
          />
        </div>
      </section>

      <section className="flex flex-col gap-2">
        <h2 className={SECTION_TITLE} style={{ fontSize: 'var(--text-sm)' }}>
          Operation
        </h2>
        <div className={ROW}>
          <label className="text-text" htmlFor="confirmDestructive">
            Confirm destructive actions
          </label>
          <input
            id="confirmDestructive"
            className={CHECKBOX}
            type="checkbox"
            checked={preferences.confirmDestructive}
            onChange={(e) => setPreference('confirmDestructive', e.target.checked)}
          />
        </div>
      </section>

      <button type="button" className={RESET} onClick={reset}>
        Reset to defaults
      </button>
    </form>
  );
}
