import { useId } from 'react';
import { Switch } from '@/components/Switch';
import {
  AUTO_DISTURBANCE_DEFAULTS,
  AUTO_SP_DEFAULTS,
  type AutoDisturbanceRequest,
  type AutoSPRequest,
} from './types';

export interface AutoTogglesProps {
  autoSp: AutoSPRequest | null;
  autoDisturbance: AutoDisturbanceRequest | null;
  onSetAutoSp: (body: AutoSPRequest) => void;
  onSetAutoDisturbance: (body: AutoDisturbanceRequest) => void;
}

/**
 * Unattended twin exercisers. Only the enable flag is operator-editable — the
 * bands ride the server's current values (or its schema defaults on first
 * enable), which is what keeps re-enabling from silently resetting a band an
 * engineer tuned through the API.
 */
export function AutoToggles({
  autoSp,
  autoDisturbance,
  onSetAutoSp,
  onSetAutoDisturbance,
}: AutoTogglesProps) {
  const spId = useId();
  const distId = useId();

  return (
    <fieldset className="flex flex-col gap-1.5 border-t border-rule pt-1.5">
      <legend className="text-2xs font-medium uppercase tracking-wider text-text-soft">
        Automation
      </legend>
      <div className="flex items-center justify-between gap-3">
        <label htmlFor={spId} className="text-sm text-text">
          Auto-SP
        </label>
        <Switch
          id={spId}
          checked={autoSp?.enabled ?? false}
          onCheckedChange={(enabled) =>
            onSetAutoSp({
              enabled,
              sp_min_pct: autoSp?.sp_min_pct ?? AUTO_SP_DEFAULTS.sp_min_pct,
              sp_max_pct: autoSp?.sp_max_pct ?? AUTO_SP_DEFAULTS.sp_max_pct,
            })
          }
        />
      </div>
      <div className="flex items-center justify-between gap-3">
        <label htmlFor={distId} className="text-sm text-text">
          Auto-disturbance
        </label>
        <Switch
          id={distId}
          checked={autoDisturbance?.enabled ?? false}
          onCheckedChange={(enabled) =>
            onSetAutoDisturbance({
              enabled,
              max_amplitude_pct:
                autoDisturbance?.max_amplitude_pct ?? AUTO_DISTURBANCE_DEFAULTS.max_amplitude_pct,
            })
          }
        />
      </div>
    </fieldset>
  );
}
