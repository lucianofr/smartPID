import { Button } from '@/components/Button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/Dialog';
import type { TuningRecommendation } from './commandApi';

export interface ConfirmApplyTuningDialogProps {
  controllerId: number;
  tag: string;
  recommendation: TuningRecommendation;
  open: boolean;
  pending?: boolean;
  /** Kept open on rejection (409 = loop not in AUTO, 404 = already consumed). */
  error?: string;
  onConfirm(): void;
  onCancel(): void;
}

function Row({
  label,
  current,
  recommended,
}: {
  label: string;
  current: number;
  recommended: number;
}) {
  return (
    <>
      <span className="text-2xs font-medium uppercase tracking-wider text-text-soft">{label}</span>
      <span className="numeric text-sm text-text-soft">{current}</span>
      <span className="numeric text-sm font-semibold text-text">{recommended}</span>
    </>
  );
}

/**
 * The one gate between an AI recommendation and a live PID write. Nothing is
 * posted until `Confirm Write`; the before/after table is the whole point of
 * the stop (§11 "every destructive write requires confirmation").
 */
export function ConfirmApplyTuningDialog({
  controllerId,
  tag,
  recommendation,
  open,
  pending = false,
  error,
  onConfirm,
  onCancel,
}: ConfirmApplyTuningDialogProps) {
  const { recommended_kp, recommended_ti, recommended_td } = recommendation;

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) onCancel();
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Aplicar sintonia — {tag}</DialogTitle>
          <DialogDescription>
            Escrita direta no PID da malha #{controllerId}. Kp={recommended_kp} Ti={recommended_ti}{' '}
            Td={recommended_td}.
          </DialogDescription>
        </DialogHeader>

        <div className="grid grid-cols-[auto_1fr_1fr] items-baseline gap-x-4 gap-y-1">
          <span />
          <span className="text-2xs font-medium uppercase tracking-wider text-text-soft">Atual</span>
          <span className="text-2xs font-medium uppercase tracking-wider text-text-soft">
            Recomendado
          </span>
          <Row label="Kp" current={recommendation.current_kp} recommended={recommended_kp} />
          <Row label="Ti" current={recommendation.current_ti} recommended={recommended_ti} />
          <Row label="Td" current={recommendation.current_td} recommended={recommended_td} />
        </div>

        <p className="text-xs italic text-text-soft">{recommendation.reason}</p>

        {error !== undefined ? (
          <p role="alert" className="text-sm font-medium text-alarm-crit">
            {error}
          </p>
        ) : null}

        <DialogFooter>
          <Button variant="secondary" onClick={onCancel}>
            Cancelar
          </Button>
          <Button variant="destructive" disabled={pending} onClick={onConfirm}>
            Confirm Write
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
