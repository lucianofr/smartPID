import { useId, useState } from 'react';
import { Button } from '@/components/Button';
import { Input } from '@/components/Field';
import { clampToScale, type Scale } from '@/lib/scale';
import type { TwinMode } from './types';

export interface TwinOutputModeControlProps {
  sp: number;
  co: number;
  mode: TwinMode;
  onSetSp: (sp: number) => void;
  onSetCo: (co: number) => void;
  onSetMode: (mode: TwinMode) => void;
}

/** The twin's process is normalised percent — PV, SP and CO all live on 0–100. */
const TWIN_SCALE: Scale = { euMin: 0, euMax: 100, unit: '%' };

/**
 * Twin SP / mode / CO — the ONE region of the Sim page a plain operator may
 * drive (`loop.operate`, §9), which is why it sits outside the
 * `simulator.configure` gate.
 *
 * Both numeric fields are operator-owned drafts seeded once at mount: the twin
 * republishes SP/CO on every tick, and a field that re-syncs itself mid-entry
 * eats the digits being typed. Nothing is sent until Apply.
 */
export function TwinOutputModeControl({
  sp,
  co,
  mode,
  onSetSp,
  onSetCo,
  onSetMode,
}: TwinOutputModeControlProps) {
  const spId = useId();
  const coId = useId();
  const [spDraft, setSpDraft] = useState(sp);
  const [coDraft, setCoDraft] = useState(co);
  const auto = mode === 'AUTO';

  return (
    <fieldset className="flex flex-col gap-1.5 border-t border-rule pt-1.5">
      <legend className="text-2xs font-medium uppercase tracking-wider text-text-soft">
        Twin output / mode
      </legend>

      <div role="group" aria-label="Twin mode" className="flex gap-2">
        <Button
          size="sm"
          variant={auto ? 'secondary' : 'primary'}
          aria-pressed={!auto}
          onClick={() => onSetMode('MAN')}
        >
          MAN
        </Button>
        <Button
          size="sm"
          variant={auto ? 'primary' : 'secondary'}
          aria-pressed={auto}
          onClick={() => onSetMode('AUTO')}
        >
          AUTO
        </Button>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <label htmlFor={spId} className="shrink-0 text-2xs text-text-soft">
          Setpoint SP
        </label>
        <div className="min-w-20 max-w-28 flex-1">
          <Input
            id={spId}
            type="number"
            min={TWIN_SCALE.euMin}
            max={TWIN_SCALE.euMax}
            value={spDraft}
            onChange={(e) => setSpDraft(Number(e.target.value))}
          />
        </div>
        <Button size="sm" onClick={() => onSetSp(clampToScale(spDraft, TWIN_SCALE))}>
          Apply setpoint
        </Button>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <label htmlFor={coId} className="shrink-0 text-2xs text-text-soft">
          Output CO
        </label>
        <div className="min-w-20 max-w-28 flex-1">
          <Input
            id={coId}
            type="number"
            min={TWIN_SCALE.euMin}
            max={TWIN_SCALE.euMax}
            value={coDraft}
            disabled={auto}
            onChange={(e) => setCoDraft(Number(e.target.value))}
          />
        </div>
        {/* In AUTO the PID owns the output; writing CO there would be overwritten
            on the next tick, so the whole path is closed rather than ignored. */}
        <Button size="sm" disabled={auto} onClick={() => onSetCo(clampToScale(coDraft, TWIN_SCALE))}>
          Apply output
        </Button>
      </div>
    </fieldset>
  );
}
