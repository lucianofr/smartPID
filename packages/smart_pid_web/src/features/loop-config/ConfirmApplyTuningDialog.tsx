import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../../components/ui/dialog';
import type { TuningRecommendation } from './commandApi';

export interface ConfirmApplyTuningDialogProps {
  controllerId: number;
  recommendation: TuningRecommendation;
  open: boolean;
  onConfirm: () => void;
  onCancel: () => void;
  /** Surfaced when the write to the external PID is rejected; keeps the dialog open. */
  error?: string;
}

// Flat ISA-101 token utilities. The 3-column grid template + token-var spacing is
// the only genuinely-dynamic styling kept inline (no Tailwind grid-cols token for it).
const GRID_STYLE: React.CSSProperties = {
  gridTemplateColumns: 'auto 1fr 1fr',
  gap: 'var(--sp-1) var(--sp-3)',
};
const HEAD_CELL = 'uppercase tracking-wide text-text-secondary';
const REC_VALUE = 'font-semibold text-text';

function Row({ label, current, recommended }: { label: string; current: number; recommended: number }) {
  return (
    <>
      <span className={HEAD_CELL} style={{ fontSize: 'var(--text-xs)' }}>
        {label}
      </span>
      <span>{current}</span>
      <span className={REC_VALUE}>{recommended}</span>
    </>
  );
}

export function ConfirmApplyTuningDialog({
  controllerId,
  recommendation,
  open,
  onConfirm,
  onCancel,
  error,
}: ConfirmApplyTuningDialogProps) {
  const { recommended_kp, recommended_ti, recommended_td } = recommendation;

  return (
    <Dialog open={open} onOpenChange={(next) => { if (!next) onCancel(); }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Apply tuning to controller #{controllerId}</DialogTitle>
        </DialogHeader>
        <p
          className="text-alarm-warning border border-alarm-warning rounded-control px-3 py-2"
          style={{ fontSize: 'var(--text-sm)' }}
        >
          You are writing Kp={recommended_kp} Ti={recommended_ti} Td={recommended_td} to controller #
          {controllerId}.
        </p>
        <div className="grid items-baseline" style={{ ...GRID_STYLE, fontSize: 'var(--text-sm)' }}>
          <span className={HEAD_CELL} style={{ fontSize: 'var(--text-xs)' }} />
          <span className={HEAD_CELL} style={{ fontSize: 'var(--text-xs)' }}>
            Current
          </span>
          <span className={HEAD_CELL} style={{ fontSize: 'var(--text-xs)' }}>
            Recommended
          </span>
          <Row label="Kp" current={recommendation.current_kp} recommended={recommended_kp} />
          <Row label="Ti" current={recommendation.current_ti} recommended={recommended_ti} />
          <Row label="Td" current={recommendation.current_td} recommended={recommended_td} />
        </div>
        <p className="italic text-text-secondary" style={{ fontSize: 'var(--text-xs)' }}>
          {recommendation.reason}
        </p>
        {error ? (
          <p
            className="text-alarm-critical border border-alarm-critical rounded-control px-3 py-2"
            style={{ fontSize: 'var(--text-sm)' }}
            role="alert"
          >
            {error}
          </p>
        ) : null}
        <DialogFooter>
          <button type="button" onClick={onCancel}>
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            className="border-2 border-alarm-warning rounded-control bg-transparent font-semibold text-text px-4 py-1.5 cursor-pointer"
          >
            Confirm Write
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
