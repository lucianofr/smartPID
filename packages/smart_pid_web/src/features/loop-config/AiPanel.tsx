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

const panelStyle: React.CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  gap: 'var(--sp-3)',
};

const fieldRowStyle: React.CSSProperties = {
  display: 'grid',
  gridTemplateColumns: 'auto 1fr',
  gap: 'var(--sp-1) var(--sp-3)',
  fontSize: 'var(--text-sm)',
};

const labelStyle: React.CSSProperties = {
  color: 'var(--text-secondary)',
  fontSize: 'var(--text-xs)',
};

const buttonRowStyle: React.CSSProperties = {
  display: 'flex',
  gap: 'var(--sp-2)',
  flexWrap: 'wrap',
};

const applyButtonStyle: React.CSSProperties = {
  border: '2px solid var(--accent, var(--border-strong, var(--border)))',
  borderRadius: 'var(--radius-control)',
  background: 'transparent',
  color: 'var(--text)',
  fontWeight: 'var(--fw-semibold)' as unknown as number,
  padding: '0.25rem 0.75rem',
  cursor: 'pointer',
};

const errorStyle: React.CSSProperties = {
  fontSize: 'var(--text-2xs)',
  color: 'var(--alarm-warning, #d08a3a)',
};

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
    <div data-testid="ai-panel" style={panelStyle}>
      <div style={fieldRowStyle}>
        <span style={labelStyle}>Engine</span>
        <span>{ai?.engine ?? '-'}</span>
        <span style={labelStyle}>Objective</span>
        <span>{ai?.objective ?? '-'}</span>
        <span style={labelStyle}>Enabled</span>
        <span>{ai ? (ai.enabled ? 'yes' : 'no') : '-'}</span>
        <span style={labelStyle}>Strategy</span>
        <span>{strategy}</span>
        <span style={labelStyle}>Current Ki</span>
        <span>{ki ?? '-'}</span>
        <span style={labelStyle}>Last gamma</span>
        <span>{gamma ?? '-'}</span>
      </div>

      <div style={buttonRowStyle}>
        {AI_ACTIONS.map((action) => (
          <button
            key={action}
            type="button"
            onClick={() => aiAction.mutate({ id: controllerId, action })}
          >
            {action.charAt(0).toUpperCase() + action.slice(1)}
          </button>
        ))}
        <button
          type="button"
          style={applyButtonStyle}
          disabled={!canApply}
          onClick={() => setConfirmOpen(true)}
        >
          Apply tuning
        </button>
      </div>

      {aiAction.error ? <span style={errorStyle}>{aiAction.error.detail}</span> : null}

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
