import { useId, useState } from 'react';
import { Input } from '@/components/Field';
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
 * Unattended twin exercisers. The enable switch and the band/period fields
 * ride the same request: the switch flips `enabled`, the number fields carry
 * the excitation shape (SP band + period, disturbance amplitude + period). The
 * loop reads `auto_sp_period_s`/`auto_dist_period_s` directly — a short period
 * is what makes the automation observably fire on the trend.
 *
 * Drafts are seeded once at mount (same reasoning as PIDSettings): the status
 * snapshot republishes these every tick and a field that re-syncs mid-entry
 * eats keystrokes. Committing on blur (or on enable) is what persists an edit.
 */
export function AutoToggles({
  autoSp,
  autoDisturbance,
  onSetAutoSp,
  onSetAutoDisturbance,
}: AutoTogglesProps) {
  const spId = useId();
  const spMinId = useId();
  const spMaxId = useId();
  const spPeriodId = useId();
  const distId = useId();
  const distAmpId = useId();
  const distPeriodId = useId();

  const [spMin, setSpMin] = useState(autoSp?.sp_min_pct ?? AUTO_SP_DEFAULTS.sp_min_pct);
  const [spMax, setSpMax] = useState(autoSp?.sp_max_pct ?? AUTO_SP_DEFAULTS.sp_max_pct);
  const [spPeriod, setSpPeriod] = useState(autoSp?.period_s ?? AUTO_SP_DEFAULTS.period_s);
  const [distAmp, setDistAmp] = useState(
    autoDisturbance?.max_amplitude_pct ?? AUTO_DISTURBANCE_DEFAULTS.max_amplitude_pct,
  );
  const [distPeriod, setDistPeriod] = useState(
    autoDisturbance?.period_s ?? AUTO_DISTURBANCE_DEFAULTS.period_s,
  );

  const commitSp = (enabled: boolean) =>
    onSetAutoSp({ enabled, sp_min_pct: spMin, sp_max_pct: spMax, period_s: spPeriod });
  const commitDist = (enabled: boolean) =>
    onSetAutoDisturbance({ enabled, max_amplitude_pct: distAmp, period_s: distPeriod });

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
          onCheckedChange={(enabled) => commitSp(enabled)}
        />
      </div>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
        <div className="flex min-w-24 flex-1 items-center gap-1.5">
          <label htmlFor={spMinId} className="shrink-0 text-2xs text-text-soft">
            SP mín (%)
          </label>
          <div className="min-w-0 flex-1">
            <Input
              id={spMinId}
              type="number"
              value={spMin}
              onChange={(e) => setSpMin(Number(e.target.value))}
              onBlur={() => commitSp(autoSp?.enabled ?? false)}
            />
          </div>
        </div>
        <div className="flex min-w-24 flex-1 items-center gap-1.5">
          <label htmlFor={spMaxId} className="shrink-0 text-2xs text-text-soft">
            SP máx (%)
          </label>
          <div className="min-w-0 flex-1">
            <Input
              id={spMaxId}
              type="number"
              value={spMax}
              onChange={(e) => setSpMax(Number(e.target.value))}
              onBlur={() => commitSp(autoSp?.enabled ?? false)}
            />
          </div>
        </div>
        <div className="flex min-w-24 flex-1 items-center gap-1.5">
          <label htmlFor={spPeriodId} className="shrink-0 text-2xs text-text-soft">
            Período (s)
          </label>
          <div className="min-w-0 flex-1">
            <Input
              id={spPeriodId}
              type="number"
              value={spPeriod}
              onChange={(e) => setSpPeriod(Number(e.target.value))}
              onBlur={() => commitSp(autoSp?.enabled ?? false)}
            />
          </div>
        </div>
      </div>

      <div className="flex items-center justify-between gap-3">
        <label htmlFor={distId} className="text-sm text-text">
          Auto-disturbance
        </label>
        <Switch
          id={distId}
          checked={autoDisturbance?.enabled ?? false}
          onCheckedChange={(enabled) => commitDist(enabled)}
        />
      </div>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
        <div className="flex min-w-24 flex-1 items-center gap-1.5">
          <label htmlFor={distAmpId} className="shrink-0 text-2xs text-text-soft">
            Amplitude (%)
          </label>
          <div className="min-w-0 flex-1">
            <Input
              id={distAmpId}
              type="number"
              value={distAmp}
              onChange={(e) => setDistAmp(Number(e.target.value))}
              onBlur={() => commitDist(autoDisturbance?.enabled ?? false)}
            />
          </div>
        </div>
        <div className="flex min-w-24 flex-1 items-center gap-1.5">
          <label htmlFor={distPeriodId} className="shrink-0 text-2xs text-text-soft">
            Período (s)
          </label>
          <div className="min-w-0 flex-1">
            <Input
              id={distPeriodId}
              type="number"
              value={distPeriod}
              onChange={(e) => setDistPeriod(Number(e.target.value))}
              onBlur={() => commitDist(autoDisturbance?.enabled ?? false)}
            />
          </div>
        </div>
      </div>
    </fieldset>
  );
}
