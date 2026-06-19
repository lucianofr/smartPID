import { Dialog } from '../../components/ui/Dialog';
import type { TuningRecommendation } from './commandApi';

export interface ConfirmApplyTuningDialogProps {
  controllerId: number;
  recommendation: TuningRecommendation;
  open: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

const gridStyle: React.CSSProperties = {
  display: 'grid',
  gridTemplateColumns: 'auto 1fr 1fr',
  gap: 'var(--sp-1) var(--sp-3)',
  alignItems: 'baseline',
  fontSize: 'var(--text-sm)',
};

const headCellStyle: React.CSSProperties = {
  fontSize: 'var(--text-xs)',
  color: 'var(--text-secondary)',
  textTransform: 'uppercase',
  letterSpacing: '0.05em',
};

const recValueStyle: React.CSSProperties = {
  fontWeight: 'var(--fw-semibold)' as unknown as number,
  color: 'var(--text)',
};

const reasonStyle: React.CSSProperties = {
  fontSize: 'var(--text-xs)',
  color: 'var(--text-secondary)',
  fontStyle: 'italic',
};

const warningStyle: React.CSSProperties = {
  fontSize: 'var(--text-sm)',
  color: 'var(--alarm-warning, #d08a3a)',
  border: '1px solid var(--alarm-warning, #d08a3a)',
  borderRadius: 'var(--radius-control)',
  padding: 'var(--sp-2) var(--sp-3)',
};

const confirmButtonStyle: React.CSSProperties = {
  border: '2px solid var(--alarm-warning, #d08a3a)',
  borderRadius: 'var(--radius-control)',
  background: 'transparent',
  color: 'var(--text)',
  fontWeight: 'var(--fw-semibold)' as unknown as number,
  padding: '0.35rem 0.9rem',
  cursor: 'pointer',
};

function Row({ label, current, recommended }: { label: string; current: number; recommended: number }) {
  return (
    <>
      <span style={headCellStyle}>{label}</span>
      <span>{current}</span>
      <span style={recValueStyle}>{recommended}</span>
    </>
  );
}

export function ConfirmApplyTuningDialog({
  controllerId,
  recommendation,
  open,
  onConfirm,
  onCancel,
}: ConfirmApplyTuningDialogProps) {
  const { recommended_kp, recommended_ti, recommended_td } = recommendation;

  const footer = (
    <>
      <button type="button" onClick={onCancel}>
        Cancel
      </button>
      <button type="button" onClick={onConfirm} style={confirmButtonStyle}>
        Confirm Write
      </button>
    </>
  );

  return (
    <Dialog open={open} onClose={onCancel} title={`Apply tuning to controller #${controllerId}`} footer={footer}>
      <p style={warningStyle}>
        You are writing Kp={recommended_kp} Ti={recommended_ti} Td={recommended_td} to controller #
        {controllerId}.
      </p>
      <div style={gridStyle}>
        <span style={headCellStyle} />
        <span style={headCellStyle}>Current</span>
        <span style={headCellStyle}>Recommended</span>
        <Row label="Kp" current={recommendation.current_kp} recommended={recommended_kp} />
        <Row label="Ti" current={recommendation.current_ti} recommended={recommended_ti} />
        <Row label="Td" current={recommendation.current_td} recommended={recommended_td} />
      </div>
      <p style={reasonStyle}>{recommendation.reason}</p>
    </Dialog>
  );
}
