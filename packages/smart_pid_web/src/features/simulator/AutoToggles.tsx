import type { AutoSPRequest, AutoDisturbanceRequest } from './types';

interface Props {
  autoSp: AutoSPRequest | null;
  autoDisturbance: AutoDisturbanceRequest | null;
  onSetAutoSp: (b: AutoSPRequest) => void;
  onSetAutoDisturbance: (b: AutoDisturbanceRequest) => void;
}

export function AutoToggles({
  autoSp,
  autoDisturbance,
  onSetAutoSp,
  onSetAutoDisturbance,
}: Props): JSX.Element {
  const spOn = autoSp?.enabled ?? false;
  const distOn = autoDisturbance?.enabled ?? false;
  return (
    <fieldset>
      <legend>Automation</legend>
      <label>
        <span>Auto-SP</span>
        <input
          type="checkbox"
          role="switch"
          aria-label="Auto-SP"
          checked={spOn}
          onChange={(e) =>
            onSetAutoSp({
              enabled: e.target.checked,
              sp_min_pct: autoSp?.sp_min_pct ?? 30,
              sp_max_pct: autoSp?.sp_max_pct ?? 70,
            })
          }
        />
      </label>
      <label>
        <span>Auto-disturbance</span>
        <input
          type="checkbox"
          role="switch"
          aria-label="Auto-disturbance"
          checked={distOn}
          onChange={(e) =>
            onSetAutoDisturbance({
              enabled: e.target.checked,
              max_amplitude_pct: autoDisturbance?.max_amplitude_pct ?? 10,
            })
          }
        />
      </label>
    </fieldset>
  );
}
