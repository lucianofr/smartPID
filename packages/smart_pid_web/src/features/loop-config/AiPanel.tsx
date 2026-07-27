import { useCallback, useEffect, useId, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/api/queryKeys';
import { useCan } from '@/auth/useCan';
import { Badge } from '@/components/Badge';
import { Button } from '@/components/Button';
import { Field, Input } from '@/components/Field';
import { toast } from '@/components/Toast';
import type { AiConfigDto, AiStatus } from '@/api/types';
import type { AiData } from '@/lib/envelope';
import { cn } from '@/lib/utils';
import { useRealtime } from '@/realtime/useRealtime';
import { useControllers } from '@/features/dashboard/useControllers';
import { ConfirmApplyTuningDialog } from './ConfirmApplyTuningDialog';
import { applyTuning, type AiAction } from './commandApi';
import { tuningRecommendationKey, useAiAction, useAiStatus, useTuningRecommendation } from './useAiControls';
import {
  AI_ENGINES,
  OBJECTIVES,
  PROCESS_SPEEDS,
  type AiConfigForm,
  type AiEngine,
  type ControlObjective,
  type ProcessSpeed,
} from './types';
import { useUpdateControllerMutation } from './useCommands';
import { hasErrors, validateAiConfig } from './validation';

export interface AiPanelProps {
  controllerId: number;
  tag: string;
}

type AiForm = AiConfigForm & { objective: ControlObjective; speed: ProcessSpeed };

/** Ring buffer for the terminal box — an unbounded log would grow all shift. */
const MAX_LOG_LINES = 100;

const AI_ACTIONS: readonly { action: AiAction; label: string }[] = [
  { action: 'start', label: 'Start' },
  { action: 'pause', label: 'Pause' },
  { action: 'stop', label: 'Stop' },
];

/**
 * The optimizer has THREE states but the DTO carries two booleans, so a naive
 * `enabled ? RUN : STOP` reports a paused engine as running. `paused` is only
 * meaningful while `enabled`; a status we cannot read at all is not a running
 * optimizer, so it reads STOP.
 *
 * Tone is the second channel, never the first: the code itself is the state
 * (§8.2 — colour never alone), mirrored on `data-state` for the e2e gate.
 */
export type AiLifecycle = 'RUN' | 'PAUSE' | 'STOP';

const AI_LIFECYCLE: Record<AiLifecycle, { tone: 'accent' | 'warn' | 'neutral'; label: string }> = {
  RUN: { tone: 'accent', label: 'otimizador em execução' },
  PAUSE: { tone: 'warn', label: 'otimizador pausado' },
  STOP: { tone: 'neutral', label: 'otimizador parado' },
};

export function aiLifecycle(status: AiStatus | undefined): AiLifecycle {
  if (status === undefined || !status.enabled) return 'STOP';
  return status.paused ? 'PAUSE' : 'RUN';
}

const SELECT_CLASS = cn(
  'numeric min-h-11 w-full rounded-control border border-rule-strong bg-surface-sunk px-2 py-1',
  'text-sm text-text outline-none focus-visible:ring-2 focus-visible:ring-focus-ring',
  'disabled:cursor-not-allowed disabled:text-text-disabled',
);

function logLine(env: AiData): string {
  const stamp = env.timestamp.length > 0 ? env.timestamp : '—';
  return `${stamp}  ${env.engine}  γ=${env.gamma}  Ki=${env.new_ki}  ${env.reasoning}`;
}

/**
 * Optimizer surface for one loop (§6.7). The optimizer lifecycle is independent
 * from AUTO/MAN: a loop can run in AUTO with the engine stopped and vice versa,
 * so `Start`/`Pause`/`Stop` never touch the block mode.
 *
 * Admin-only in full: `ai.control` gates the lifecycle, `tuning.edit` gates the
 * engine configuration and the guarded `Apply tuning` write. Backend re-enforces.
 */
export function AiPanel({ controllerId, tag }: AiPanelProps) {
  const canControl = useCan('ai.control');
  const canTune = useCan('tuning.edit');

  const visible = canControl || canTune;

  const controllers = useControllers();
  const status = useAiStatus(controllerId, visible);
  const recommendation = useTuningRecommendation(controllerId, canTune);
  const aiAction = useAiAction();
  const updateController = useUpdateControllerMutation();
  const queryClient = useQueryClient();
  const ai = useRealtime<AiData>(controllerId, 'ai');

  const engineId = useId();
  const objectiveId = useId();
  const speedId = useId();
  const deadTimeId = useId();
  const limitMinId = useId();
  const limitMaxId = useId();

  // Persisted config is the baseline; `draft` is only what the operator has
  // touched, so a save (or a resync) shows through without stomping an edit.
  const [draft, setDraft] = useState<Partial<AiForm>>({});
  const [lines, setLines] = useState<readonly string[]>([]);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [applyError, setApplyError] = useState<string | undefined>(undefined);
  const [applying, setApplying] = useState(false);
  const logRef = useRef<HTMLDivElement>(null);

  const { subscribe } = ai;
  useEffect(
    () =>
      subscribe((env) => {
        setLines((prev) => [...prev, logLine(env.data)].slice(-MAX_LOG_LINES));
      }),
    [subscribe],
  );

  // A terminal that does not follow its own tail is a scrollback, not a log.
  useEffect(() => {
    const box = logRef.current;
    if (box !== null) box.scrollTop = box.scrollHeight;
  }, [lines]);

  // Schema defaults, not assumptions: a roster row may predate `ai_config`.
  const controller = controllers.data?.find((c) => c.id === controllerId);
  const persisted = controller?.ai_config as Partial<AiConfigDto> | undefined;
  const form: AiForm = {
    engine: (persisted?.engine as AiEngine | undefined) ?? 'NONE',
    objective: (persisted?.objective as ControlObjective | undefined) ?? 'DISTURBANCE_REJECTION',
    speed: (controller?.process_speed as ProcessSpeed | undefined) ?? 'MEDIUM',
    dead_time_l: persisted?.dead_time_l ?? 1,
    limit_min: persisted?.limit_min ?? 0.1,
    limit_max: persisted?.limit_max ?? 100,
    ...draft,
  };
  const errors = validateAiConfig(form);
  const rec = recommendation.data;
  const pendingRecommendation = rec !== undefined && rec.status === 'pending';

  const confirmApply = useCallback(() => {
    setApplying(true);
    setApplyError(undefined);
    applyTuning(controllerId)
      .then(() => {
        setConfirmOpen(false);
        toast({ title: 'Sintonia aplicada', description: `Malha ${tag}` });
        void queryClient.invalidateQueries({ queryKey: tuningRecommendationKey(controllerId) });
        void queryClient.invalidateQueries({ queryKey: queryKeys.aiStatus(controllerId) });
        void queryClient.invalidateQueries({ queryKey: queryKeys.controllers });
      })
      .catch((error: unknown) => {
        setApplyError(error instanceof Error ? error.message : 'Falha ao escrever a sintonia');
      })
      .finally(() => setApplying(false));
  }, [controllerId, queryClient, tag]);

  if (!visible) return null;

  const live = ai.last?.data;
  const engine = live?.engine ?? status.data?.engine ?? '—';
  const ki = live?.new_ki ?? status.data?.current_ki ?? null;
  const gamma = live?.gamma ?? status.data?.last_gamma ?? null;
  // Lifecycle comes from /ai/status only: LOG.AI events carry no run state, so
  // a stale event must never keep the badge reading RUN after a Stop.
  const lifecycle = aiLifecycle(status.data);

  return (
    <section
      aria-label="Otimização IA"
      data-testid="ai-panel"
      className="flex flex-col gap-2 border-t border-rule pt-3"
    >
      <header className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-2xs font-medium uppercase tracking-wider text-text-soft">
          Otimização IA
        </h3>
        <div className="flex items-baseline gap-2">
          <Badge
            tone={AI_LIFECYCLE[lifecycle].tone}
            role="status"
            aria-live="polite"
            data-testid="ai-lifecycle"
            data-state={lifecycle}
          >
            {lifecycle}
            <span className="sr-only">{` — ${AI_LIFECYCLE[lifecycle].label}`}</span>
          </Badge>
          <span className="numeric text-2xs text-text-soft">
            {engine} · Ki {ki ?? '—'} · γ {gamma ?? '—'}
          </span>
        </div>
      </header>

      {canTune ? (
        <div className="flex flex-col gap-2">
          <Field label="Motor" htmlFor={engineId}>
            <select
              id={engineId}
              className={SELECT_CLASS}
              value={form.engine}
              onChange={(e) => setDraft((p) => ({ ...p, engine: e.target.value as AiEngine }))}
            >
              {AI_ENGINES.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </Field>

          <Field label="Objetivo" htmlFor={objectiveId}>
            <select
              id={objectiveId}
              className={SELECT_CLASS}
              value={form.objective}
              onChange={(e) =>
                setDraft((p) => ({ ...p, objective: e.target.value as ControlObjective }))
              }
            >
              {OBJECTIVES.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </Field>

          <Field label="Velocidade do processo" htmlFor={speedId}>
            <select
              id={speedId}
              className={SELECT_CLASS}
              value={form.speed}
              onChange={(e) => setDraft((p) => ({ ...p, speed: e.target.value as ProcessSpeed }))}
            >
              {PROCESS_SPEEDS.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </Field>

          <Field label="Tempo morto L" htmlFor={deadTimeId} error={errors.dead_time_l}>
            <Input
              id={deadTimeId}
              type="number"
              inputMode="decimal"
              className="numeric px-2 py-1"
              value={form.dead_time_l}
              invalid={errors.dead_time_l !== undefined}
              onChange={(e) => setDraft((p) => ({ ...p, dead_time_l: Number(e.target.value) }))}
            />
          </Field>

          <div className="flex gap-2">
            <Field
              label="Limite mín."
              htmlFor={limitMinId}
              error={errors.limit_min}
              className="min-w-0 flex-1"
            >
              <Input
                id={limitMinId}
                type="number"
                inputMode="decimal"
                className="numeric px-2 py-1"
                value={form.limit_min}
                invalid={errors.limit_min !== undefined}
                onChange={(e) => setDraft((p) => ({ ...p, limit_min: Number(e.target.value) }))}
              />
            </Field>
            <Field
              label="Limite máx."
              htmlFor={limitMaxId}
              error={errors.limit_max}
              className="min-w-0 flex-1"
            >
              <Input
                id={limitMaxId}
                type="number"
                inputMode="decimal"
                className="numeric px-2 py-1"
                value={form.limit_max}
                invalid={errors.limit_max !== undefined}
                onChange={(e) => setDraft((p) => ({ ...p, limit_max: Number(e.target.value) }))}
              />
            </Field>
          </div>

          <Button
            variant="secondary"
            disabled={hasErrors(errors) || updateController.isPending}
            onClick={() =>
              updateController.mutate(
                {
                  id: controllerId,
                  patch: {
                    process_speed: form.speed,
                    ai_config: {
                      engine: form.engine,
                      objective: form.objective,
                      dead_time_l: form.dead_time_l,
                      limit_min: form.limit_min,
                      limit_max: form.limit_max,
                    },
                  },
                },
                // Saved values now come back through the roster query.
                { onSuccess: () => setDraft({}) },
              )
            }
          >
            Salvar IA
          </Button>
          {updateController.error !== null ? (
            <p role="alert" className="text-xs font-medium text-alarm-crit">
              {updateController.error.detail}
            </p>
          ) : null}
        </div>
      ) : null}

      {canControl ? (
        <div role="group" aria-label="Ciclo do otimizador" className="flex gap-2">
          {AI_ACTIONS.map(({ action, label }) => (
            <Button
              key={action}
              size="sm"
              className="flex-1"
              disabled={aiAction.isPending}
              onClick={() =>
                aiAction.mutate(
                  { id: controllerId, action },
                  {
                    onError: () =>
                      toast({
                        title: 'Comando de IA recusado',
                        description: `Malha ${tag}`,
                        tone: 'crit',
                      }),
                  },
                )
              }
            >
              {label}
            </Button>
          ))}
        </div>
      ) : null}

      <div
        ref={logRef}
        role="log"
        aria-label="LOG.AI"
        aria-live="polite"
        className="numeric max-h-32 overflow-y-auto rounded-control bg-surface-sunk p-2 text-2xs text-text-soft"
      >
        {lines.length === 0 ? (
          <p>Sem eventos de IA.</p>
        ) : (
          lines.map((line, index) => (
            <p key={`${index}-${line}`} className="whitespace-pre-wrap">
              {line}
            </p>
          ))
        )}
      </div>

      {canTune ? (
        <Button
          variant="secondary"
          disabled={!pendingRecommendation}
          onClick={() => {
            setApplyError(undefined);
            setConfirmOpen(true);
          }}
        >
          Apply tuning
        </Button>
      ) : null}

      {canTune && rec !== undefined ? (
        <ConfirmApplyTuningDialog
          controllerId={controllerId}
          tag={tag}
          recommendation={rec}
          open={confirmOpen}
          pending={applying}
          error={applyError}
          onConfirm={confirmApply}
          onCancel={() => {
            setApplyError(undefined);
            setConfirmOpen(false);
          }}
        />
      ) : null}
    </section>
  );
}
