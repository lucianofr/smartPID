import type { StatusData } from '../realtime/envelope';
import { AnalogBar } from './AnalogBar';

export interface ControllerSummary {
  id: number;
  name: string;
  description: string;
  pv_decimals: number;
  pv_unit: string;
}

export function ControllerCard({
  controller,
  status,
}: {
  controller: ControllerSummary;
  status: StatusData | undefined;
}) {
  return (
    <div
      style={{
        width: 'var(--card-w)', background: 'var(--surface)',
        border: '1px solid var(--border)', display: 'flex', flexDirection: 'column',
      }}
    >
      <div style={{ height: 'var(--alarmstrip-h)', background: 'transparent' }} />
      <div style={{ padding: 'var(--sp-4)', display: 'flex', flexDirection: 'column', gap: 'var(--sp-2)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
          <span className="numeric" style={{ fontSize: 'var(--text-base)', fontWeight: 700, color: 'var(--text)' }}>
            {controller.name}
          </span>
          {controller.description && (
            <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>{controller.description}</span>
          )}
        </div>
        <AnalogBar label="PV" value={status?.pv} min={0} max={100} unit={controller.pv_unit} decimals={controller.pv_decimals} />
        <AnalogBar label="SP" value={status?.sp} min={0} max={100} unit={controller.pv_unit} decimals={controller.pv_decimals} />
        <AnalogBar label="CO" value={status?.co} min={0} max={100} unit="%" decimals={1} />
        <div style={{ display: 'flex', gap: 'var(--sp-2)', fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>
          <span className="numeric">{status?.mode ?? '—'}</span>
        </div>
      </div>
    </div>
  );
}
