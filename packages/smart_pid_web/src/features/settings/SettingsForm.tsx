import { useSettings } from './useSettings';
import './SettingsForm.css';

/**
 * Application preferences form (Fatia 7). Binds the localStorage-backed
 * `useSettings` hook to a two-column section layout (design-system §10).
 * No theme control (Fatia 8) and no admin/user-management controls
 * (no backend endpoint for those here).
 */
export function SettingsForm(): JSX.Element {
  const { preferences, setPreference, reset } = useSettings();

  return (
    <form className="settings-form" aria-label="Application preferences">
      <section className="settings-form__section">
        <h2 className="settings-form__section-title">Display</h2>
        <div className="settings-form__row">
          <label className="settings-form__label" htmlFor="numberDecimals">
            Number decimals
          </label>
          <input
            id="numberDecimals"
            className="settings-form__control numeric"
            type="number"
            min={0}
            max={6}
            value={preferences.numberDecimals}
            onChange={(e) => setPreference('numberDecimals', Number(e.target.value))}
          />
        </div>
        <div className="settings-form__row">
          <label className="settings-form__label" htmlFor="trendWindow">
            Trend window (seconds)
          </label>
          <input
            id="trendWindow"
            className="settings-form__control numeric"
            type="number"
            min={10}
            max={3600}
            value={preferences.trendWindowSeconds}
            onChange={(e) => setPreference('trendWindowSeconds', Number(e.target.value))}
          />
        </div>
      </section>

      <section className="settings-form__section">
        <h2 className="settings-form__section-title">Operation</h2>
        <div className="settings-form__row">
          <label className="settings-form__label" htmlFor="confirmDestructive">
            Confirm destructive actions
          </label>
          <input
            id="confirmDestructive"
            className="settings-form__control settings-form__control--checkbox"
            type="checkbox"
            checked={preferences.confirmDestructive}
            onChange={(e) => setPreference('confirmDestructive', e.target.checked)}
          />
        </div>
      </section>

      <button type="button" className="settings-form__reset" onClick={reset}>
        Reset to defaults
      </button>
    </form>
  );
}
