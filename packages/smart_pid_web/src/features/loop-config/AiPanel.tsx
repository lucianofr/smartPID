import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import type { ApiError } from '../../api/client';
import { useRealtime } from '../../realtime/useRealtime';
import type { AiData, RealtimeEnvelope } from '../../realtime/envelope';
import { ConfirmApplyTuningDialog } from './ConfirmApplyTuningDialog';
import { applyTuning } from './commandApi';
import { useAiAction, useAiStatus, useTuningRecommendation } from './useAiControls';
import type { AiAction } from './commandApi';

export interface AiPanelProps {
  controllerId: number;
}

/**
 * Flat ISA-101 AI optimization panel. Inline-style blocks migrated to token
 * utilities (Task 8.2). The frozen `data-testid="ai-panel"` and the
 * `getByRole('button', { name: /apply tuning/i })` disabled state are preserved.
 * Numeric readouts carry `numeric` (tabular numerals, §6). Font sizes stay inline
 * as `var(--text-*)` (no Tailwind type-scale mapping in the `@theme inline` bridge).
 */
const ACTION_BUTTON =
  'cursor-pointer bg-surface-container-high text-text border border-border rounded-control px-2 py-0.5 ' +
  'transition-colors duration-fast hover:bg-surface-container active:bg-field-bg ' +
  'focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-[var(--focus-ring)] ' +
  'disabled:text-text-disabled disabled:cursor-not-allowed disabled:hover:bg-surface-container-high';

const APPLY_BUTTON =
  'cursor-pointer bg-transparent text-text border-2 border-border-strong rounded-control px-3 py-0.5 font-semibold ' +
  'transition-colors duration-fast hover:bg-surface-container-high active:bg-field-bg ' +
  'focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-[var(--focus-ring)] ' +
  'disabled:text-text-disabled disabled:border-border disabled:cursor-not-allowed disabled:hover:bg-transparent';

const AI_ACTIONS: AiAction[] = ['start', 'stop', 'pause'];

export function AiPanel({ controllerId }: AiPanelProps) {
  const status = useAiStatus(controllerId);
  const recommendation = useTuningRecommendation(controllerId);
  const aiAction = useAiAction();
  const { subscribe } = useRealtime();
  const queryClient = useQueryClient();

  const [live, setLive] = useState<AiData | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);

  // Writing a recommendation to the external PID can fail (e.g. 409 if the loop is
  // not in AUTO, 404 if the recommendation was consumed). Run it through a mutation so
  // the rejection surfaces to the operator instead of being swallowed.
  const applyMut = useMutation<unknown, ApiError, void>({
    mutationFn: () => applyTuning(controllerId),
    onSuccess: () => {
      setConfirmOpen(false);
      void queryClient.invalidateQueries({ queryKey: ['tuning', 'rec', controllerId] });
      void queryClient.invalidateQueries({ queryKey: ['ai', 'status', controllerId] });
    },
  });

  useEffect(() => {
    const unsubscribe = subscribe<AiData>('ai', (env: RealtimeEnvelope<AiData>) => {
      if (env.loop_id !== controllerId) return;
      setLive(env.data);
    });
    return unsubscribe;
  }, [subscribe, controllerId]);

  const ai = status.data;
  const strategy = live?.strategy ?? ai?.engine ?? '-';
  const gamma = live?.gamma ?? ai?.last_gamma ?? null;
  const ki = live?.ki ?? ai?.current_ki ?? null;

  const rec = recommendation.data;
  const canApply = rec?.status === 'pending';

  const handleConfirm = () => {
    applyMut.mutate();
  };

  const handleCancel = () => {
    applyMut.reset();
    setConfirmOpen(false);
  };

  return (
    <div data-testid="ai-panel" className="flex flex-col gap-3">
      <div
        className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1"
        style={{ fontSize: 'var(--text-sm)' }}
      >
        <span className="text-text-secondary" style={{ fontSize: 'var(--text-xs)' }}>
          Engine
        </span>
        <span>{ai?.engine ?? '-'}</span>
        <span className="text-text-secondary" style={{ fontSize: 'var(--text-xs)' }}>
          Objective
        </span>
        <span>{ai?.objective ?? '-'}</span>
        <span className="text-text-secondary" style={{ fontSize: 'var(--text-xs)' }}>
          Enabled
        </span>
        <span>{ai ? (ai.enabled ? 'yes' : 'no') : '-'}</span>
        <span className="text-text-secondary" style={{ fontSize: 'var(--text-xs)' }}>
          Strategy
        </span>
        <span>{strategy}</span>
        <span className="text-text-secondary" style={{ fontSize: 'var(--text-xs)' }}>
          Current Ki
        </span>
        <span className="numeric">{ki ?? '-'}</span>
        <span className="text-text-secondary" style={{ fontSize: 'var(--text-xs)' }}>
          Last gamma
        </span>
        <span className="numeric">{gamma ?? '-'}</span>
      </div>

      <div className="flex flex-wrap gap-2">
        {AI_ACTIONS.map((action) => (
          <button
            key={action}
            type="button"
            onClick={() => aiAction.mutate({ id: controllerId, action })}
            className={ACTION_BUTTON}
          >
            {action.charAt(0).toUpperCase() + action.slice(1)}
          </button>
        ))}
        <button
          type="button"
          className={APPLY_BUTTON}
          disabled={!canApply}
          onClick={() => setConfirmOpen(true)}
        >
          Apply tuning
        </button>
      </div>

      {aiAction.error ? (
        <span className="text-alarm-warning" style={{ fontSize: 'var(--text-2xs)' }}>
          {aiAction.error.detail}
        </span>
      ) : null}

      {rec ? (
        <ConfirmApplyTuningDialog
          controllerId={controllerId}
          recommendation={rec}
          open={confirmOpen}
          onConfirm={handleConfirm}
          onCancel={handleCancel}
          error={applyMut.error?.detail}
        />
      ) : null}
    </div>
  );
}
