import { useId, useState } from 'react';
import { Button } from '@/components/Button';
import { Input } from '@/components/Field';
import { Switch } from '@/components/Switch';

export interface PIDSettingsProps {
  enabled: boolean;
  kp: number;
  ti: number;
  td: number;
  onToggleEnabled: (enabled: boolean) => void;
  onApplyParams: (params: { kp: number; ti: number; td: number }) => void;
}

/**
 * The twin's internal PID: the tick loop only runs it when `pid_enabled AND
 * pid_mode==AUTO` (mode is TwinOutputModeControl's job, unrelated here).
 *
 * Kp/Ti/Td are admin-owned drafts seeded once at mount — same reasoning as
 * TwinOutputModeControl's sp/co drafts, the status snapshot republishes these
 * every tick and a field that re-syncs mid-entry eats keystrokes. Enable is a
 * plain immediate toggle, no draft.
 */
export function PIDSettings({
  enabled,
  kp,
  ti,
  td,
  onToggleEnabled,
  onApplyParams,
}: PIDSettingsProps) {
  const enabledId = useId();
  const kpId = useId();
  const tiId = useId();
  const tdId = useId();
  const [kpDraft, setKpDraft] = useState(kp);
  const [tiDraft, setTiDraft] = useState(ti);
  const [tdDraft, setTdDraft] = useState(td);

  return (
    <fieldset className="flex flex-col gap-2 border-t border-rule pt-3">
      <legend className="text-2xs font-medium uppercase tracking-wider text-text-soft">
        Internal PID
      </legend>
      <div className="flex items-center justify-between gap-3">
        <label htmlFor={enabledId} className="text-sm text-text">
          Enable PID
        </label>
        <Switch id={enabledId} checked={enabled} onCheckedChange={onToggleEnabled} />
      </div>

      <div className="flex flex-wrap items-end gap-2">
        <div className="flex min-w-16 flex-1 flex-col gap-1">
          <label htmlFor={kpId} className="text-2xs text-text-soft">
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
        <div className="flex min-w-16 flex-1 flex-col gap-1">
          <div className="flex items-baseline gap-1">
            <label htmlFor={tiId} className="text-2xs text-text-soft">
              Ti
            </label>
            <span className="text-2xs text-text-disabled">s</span>
          </div>
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
        <div className="flex min-w-16 flex-1 flex-col gap-1">
          <div className="flex items-baseline gap-1">
            <label htmlFor={tdId} className="text-2xs text-text-soft">
              Td
            </label>
            <span className="text-2xs text-text-disabled">s</span>
          </div>
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
          onClick={() => onApplyParams({ kp: kpDraft, ti: tiDraft, td: tdDraft })}
        >
          Apply PID parameters
        </Button>
      </div>
    </fieldset>
  );
}
