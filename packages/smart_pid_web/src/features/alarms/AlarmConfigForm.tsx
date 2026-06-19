import { useEffect, useState } from 'react';
import { useAlarmConfig, useUpdateAlarmConfig } from './useAlarmConfig';
import type { AlarmThreshold, AlarmType, AlarmPriority } from './types';
import './AlarmConfigForm.css';

const ALARM_TYPES: AlarmType[] = ['HIHI', 'HI', 'LO', 'LOLO', 'DV_HI', 'DV_LO'];
const PRIORITIES: AlarmPriority[] = ['CRITICAL', 'WARNING', 'ADVISORY', 'LOG'];

function blank(t: AlarmType): AlarmThreshold {
  return { alarm_type: t, priority: 'WARNING', limit: 0, enabled: false, deadband: 0, delay_on_s: 0, delay_off_s: 0 };
}

export function AlarmConfigForm({ controllerId }: { controllerId: number }): JSX.Element {
  const { data, isLoading, isError } = useAlarmConfig(controllerId);
  const update = useUpdateAlarmConfig(controllerId);
  const [draft, setDraft] = useState<AlarmThreshold[]>([]);

  useEffect(() => {
    if (!data) return;
    const byType = new Map(data.thresholds.map((t) => [t.alarm_type, t]));
    setDraft(ALARM_TYPES.map((t) => byType.get(t) ?? blank(t)));
  }, [data]);

  if (isLoading) return <p>Loading alarm config…</p>;
  if (isError) return <p role="alert">Failed to load alarm config.</p>;

  const patch = (t: AlarmType, p: Partial<AlarmThreshold>): void =>
    setDraft((d) => d.map((row) => (row.alarm_type === t ? { ...row, ...p } : row)));

  return (
    <form
      className="alarm-config"
      onSubmit={(e) => { e.preventDefault(); update.mutate(draft); }}
      aria-label={`Alarm configuration for controller ${controllerId}`}
    >
      {draft.map((row) => (
        <fieldset key={row.alarm_type} data-testid={`threshold-${row.alarm_type}`} className="alarm-config__row">
          <legend>{row.alarm_type}</legend>
          <label>
            Enabled
            <input type="checkbox" checked={row.enabled}
              onChange={(e) => patch(row.alarm_type, { enabled: e.target.checked })} />
          </label>
          <label>
            Limit
            <input type="number" value={row.limit}
              onChange={(e) => patch(row.alarm_type, { limit: Number(e.target.value) })} />
          </label>
          <label>
            Priority
            <select value={row.priority}
              onChange={(e) => patch(row.alarm_type, { priority: e.target.value as AlarmPriority })}>
              {PRIORITIES.map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
          </label>
        </fieldset>
      ))}
      <button type="submit" disabled={update.isPending}>Save</button>
      {update.isError && <p role="alert">Save failed.</p>}
      {update.isSuccess && <p role="status">Saved.</p>}
    </form>
  );
}
