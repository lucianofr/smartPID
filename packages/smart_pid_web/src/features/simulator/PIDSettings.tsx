import { useId, useState } from 'react';
import { Button } from '@/components/Button';
import { Input } from '@/components/Field';

export interface PIDSettingsProps {
  kp: number;
  ti: number;
  td: number;
  onApplyParams: (params: { kp: number; ti: number; td: number }) => void;
}

/**
 * The twin's internal PID. It is always running — `pid_mode` (AUTO/MAN, owned
 * by TwinOutputModeControl) is the only thing that decides whether it drives
 * CO, so there is no enable switch to get out of sync with the mode.
 *
 * Kp/Ti/Td are admin-owned drafts seeded once at mount — same reasoning as
 * TwinOutputModeControl's sp/co drafts, the status snapshot republishes these
 * every tick and a field that re-syncs mid-entry eats keystrokes.
 */
export function PIDSettings({ kp, ti, td, onApplyParams }: PIDSettingsProps) {
  const kpId = useId();
  const tiId = useId();
  const tdId = useId();
  const [kpDraft, setKpDraft] = useState(kp);
  const [tiDraft, setTiDraft] = useState(ti);
  const [tdDraft, setTdDraft] = useState(td);

  return (
    <fieldset className="flex flex-col gap-1.5 border-t border-rule pt-1.5">
      <legend className="text-2xs font-medium uppercase tracking-wider text-text-soft">
        Internal PID
      </legend>
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex min-w-20 flex-1 items-center gap-1">
          <label htmlFor={kpId} className="shrink-0 text-2xs text-text-soft">
            Kp
          </label>
          <Input
            id={kpId}
            type="number"
            min={0.01}
            max={50}
            step={0.01}
            value={kpDraft}
            onChange={(e) => setKpDraft(Number(e.target.value))}
          />
        </div>
        <div className="flex min-w-20 flex-1 items-center gap-1">
          <label htmlFor={tiId} className="shrink-0 text-2xs text-text-soft">
            Ti
          </label>
          <span className="shrink-0 text-2xs text-text-disabled">s</span>
          <Input
            id={tiId}
            type="number"
            min={0.1}
            max={999}
            step={0.1}
            value={tiDraft}
            onChange={(e) => setTiDraft(Number(e.target.value))}
          />
        </div>
        <div className="flex min-w-20 flex-1 items-center gap-1">
          <label htmlFor={tdId} className="shrink-0 text-2xs text-text-soft">
            Td
          </label>
          <span className="shrink-0 text-2xs text-text-disabled">s</span>
          <Input
            id={tdId}
            type="number"
            min={0}
            max={999}
            step={0.1}
            value={tdDraft}
            onChange={(e) => setTdDraft(Number(e.target.value))}
          />
        </div>
        <Button
          size="sm"
          className="shrink-0"
          onClick={() => onApplyParams({ kp: kpDraft, ti: tiDraft, td: tdDraft })}
        >
          Apply PID parameters
        </Button>
      </div>
    </fieldset>
  );
}
