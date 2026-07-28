import { useCallback, useEffect, useRef, useState } from 'react';
import { BrainCircuit, Check } from 'lucide-react';
import { useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/api/queryKeys';
import { useCan } from '@/auth/useCan';
import { Badge } from '@/components/Badge';
import { Button } from '@/components/Button';
import { toast } from '@/components/Toast';
import type { AiStatus } from '@/api/types';
import type { AiData } from '@/lib/envelope';
import { formatNumber, formatTimestamp } from '@/lib/format';
import { useRealtime } from '@/realtime/useRealtime';
import { cn } from '@/lib/utils';
import { ConfirmApplyTuningDialog } from './ConfirmApplyTuningDialog';
import { applyTuning, type AiAction } from './commandApi';
import { tuningRecommendationKey, useAiAction, useAiStatus, useTuningRecommendation } from './useAiControls';

export interface AiPanelProps {
  controllerId: number;
  tag: string;
}

/** Ring buffer for the tuning log — an unbounded log would grow all shift. */
const MAX_LOG_LINES = 100;

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

/**
 * `Start`/`Pause`/`Stop` are the accessible names the retained e2e binds to, so
 * the 1a RUN/STOP segment is a VISUAL treatment laid over them — the label text
 * never changes. `state` is the lifecycle each action lands on, which is what
 * paints the segment as selected.
 */
const AI_ACTIONS: readonly { action: AiAction; label: string; state: AiLifecycle }[] = [
  { action: 'start', label: 'Start', state: 'RUN' },
  { action: 'pause', label: 'Pause', state: 'PAUSE' },
  { action: 'stop', label: 'Stop', state: 'STOP' },
];

const SEGMENT_BASE = 'min-h-11 flex-1 rounded-control border border-rule px-1 py-2 text-base font-bold';
const SEGMENT_IDLE = 'bg-transparent text-text-soft hover:bg-surface-sunk hover:text-text';

/**
 * Selected-segment fills. Every pair is a gated on-* token: `on-alarm` is
 * documented ≥5.10:1 on every fill in every theme (themes.css), which
 * `text-on-accent` is NOT — under optimizer-dark `--on-accent` is the same navy
 * as `--brand-ink`.
 */
const SEGMENT_ACTIVE: Record<AiLifecycle, string> = {
  RUN: 'bg-state-running text-on-alarm hover:bg-state-running',
  PAUSE: 'bg-alarm-warn text-on-alarm hover:bg-alarm-warn',
  STOP: 'bg-state-stopped text-on-alarm hover:bg-state-stopped',
};

/**
 * Body copy for the box when there is nothing pending — state, not invention.
 * Kept to one rendered line at 320px: a second line is 17px the rail does not
 * have at 1024x768.
 */
const LIFECYCLE_BODY: Record<AiLifecycle, string> = {
  RUN: 'Em execução — sem ajuste pendente.',
  PAUSE: 'Pausado — sintonia atual mantida.',
  STOP: 'Parado — sem otimização contínua.',
};

export function aiLifecycle(status: AiStatus | undefined): AiLifecycle {
  if (status === undefined || !status.enabled) return 'STOP';
  return status.paused ? 'PAUSE' : 'RUN';
}

/** One tuning-log row: wall clock left, what the engine did right. */
interface AiLogEntry {
  readonly time: string;
  readonly text: string;
}

function logEntry(env: AiData): AiLogEntry {
  return {
    time: formatTimestamp(env.timestamp),
    text: `${env.engine} γ=${env.gamma} Ki=${env.new_ki} — ${env.reasoning}`,
  };
}

/**
 * Optimizer surface for one loop (§6.7), rebuilt to the 1a faceplate rail: a
 * `Otimizador IA` segment over the lifecycle buttons, then the amber AI box —
 * header, one-sentence proposal, the guarded write, and the tuning log.
 *
 * The optimizer lifecycle is independent from AUTO/MAN: a loop can run in AUTO
 * with the engine stopped and vice versa, so `Start`/`Pause`/`Stop` never touch
 * the block mode.
 *
 * Admin-only in full: `ai.control` gates the lifecycle, `tuning.edit` gates the
 * guarded `Apply tuning` write. Backend re-enforces.
 */
export function AiPanel({ controllerId, tag }: AiPanelProps) {
  const canControl = useCan('ai.control');
  const canTune = useCan('tuning.edit');

  const visible = canControl || canTune;

  const status = useAiStatus(controllerId, visible);
  const recommendation = useTuningRecommendation(controllerId, canTune);
  const aiAction = useAiAction();
  const queryClient = useQueryClient();
  const ai = useRealtime<AiData>(controllerId, 'ai');

  const [entries, setEntries] = useState<readonly AiLogEntry[]>([]);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [applyError, setApplyError] = useState<string | undefined>(undefined);
  const [applying, setApplying] = useState(false);
  const logRef = useRef<HTMLDivElement>(null);

  const { subscribe } = ai;
  useEffect(
    () =>
      subscribe((env) => {
        setEntries((prev) => [...prev, logEntry(env.data)].slice(-MAX_LOG_LINES));
      }),
    [subscribe],
  );

  // A log that does not follow its own tail is a scrollback, not a log.
  useEffect(() => {
    const box = logRef.current;
    if (box !== null) box.scrollTop = box.scrollHeight;
  }, [entries]);

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

  // Lifecycle comes from /ai/status only: LOG.AI events carry no run state, so
  // a stale event must never keep the badge reading RUN after a Stop.
  const lifecycle = aiLifecycle(status.data);

  // Amber is the §6.3 call-to-action, not decoration: the box only lights up
  // when there is a write to authorise. Otherwise it is neutral chrome.
  const proposing = pendingRecommendation && rec !== undefined;
  const body = proposing
    ? `Kp ${formatNumber(rec.current_kp, 2)}→${formatNumber(rec.recommended_kp, 2)} · Ti ${formatNumber(rec.current_ti, 2)}→${formatNumber(rec.recommended_ti, 2)}`
    : LIFECYCLE_BODY[lifecycle];

  return (
    <section
      aria-label="Otimização IA"
      data-testid="ai-panel"
      className="flex min-h-0 flex-1 flex-col gap-2"
    >
      {/* The 1a `Otimizador IA` caption is carried by the box header two rows
          down instead of repeated here: at 1024x768 the rail cannot afford the
          same word twice (see the header comment). */}
      {canControl ? (
        <div role="group" aria-label="Ciclo do otimizador" className="flex gap-1.5">
          {AI_ACTIONS.map(({ action, label, state }) => (
            <Button
              key={action}
              aria-pressed={lifecycle === state}
              className={cn(SEGMENT_BASE, lifecycle === state ? SEGMENT_ACTIVE[state] : SEGMENT_IDLE)}
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

      {/* color-mix over the brand token keeps the 1a amber wash theme-reactive
          without a literal — a fixed rgba() would not survive a theme flip. */}
      <div
        className={cn(
          'flex min-h-0 flex-1 flex-col gap-2 rounded-card border p-2.5',
          // Same height-aware density as the rail that hosts it (Faceplate).
          '[@media(max-height:820px)]:gap-1.5 [@media(max-height:820px)]:p-2',
          proposing ? 'border-transparent' : 'border-rule',
        )}
        style={
          proposing
            ? {
                backgroundColor: 'color-mix(in srgb, var(--brand-accent) 9%, transparent)',
                borderColor: 'color-mix(in srgb, var(--brand-accent) 40%, transparent)',
              }
            : undefined
        }
      >
        <header className="flex items-center justify-between gap-2">
          <span className="flex min-w-0 items-center gap-2">
            <BrainCircuit
              aria-hidden="true"
              className={cn(
                'h-[15px] w-[15px] shrink-0',
                proposing ? 'text-brand-accent' : 'text-text-soft',
              )}
            />
            <span
              className={cn(
                'truncate text-2xs font-bold uppercase tracking-caps',
                proposing ? 'text-brand-accent' : 'text-text-soft',
              )}
            >
              {proposing ? 'IA sugere ajuste' : 'Otimização IA'}
            </span>
          </span>
          <Badge
            tone={AI_LIFECYCLE[lifecycle].tone}
            role="status"
            aria-live="polite"
            data-testid="ai-lifecycle"
            data-state={lifecycle}
            className="shrink-0"
          >
            {lifecycle}
            <span className="sr-only">{` — ${AI_LIFECYCLE[lifecycle].label}`}</span>
          </Badge>
        </header>

        <p className="text-sm leading-snug text-text-soft">{body}</p>

        {canTune ? (
          <Button
            className={cn(
              'w-full gap-1.5 text-base font-bold',
              proposing
                ? 'border-transparent bg-brand-accent text-on-brand-accent hover:bg-brand-accent-hover'
                : 'border-rule-strong bg-transparent text-text-soft',
            )}
            disabled={!pendingRecommendation}
            onClick={() => {
              setApplyError(undefined);
              setConfirmOpen(true);
            }}
          >
            <Check aria-hidden="true" className="h-[13px] w-[13px] shrink-0" strokeWidth={3} />
            Apply tuning
          </Button>
        ) : null}

        {/* Always mounted, never faked: the rows are LOG.AI events off the bus,
            and an empty bus says so rather than borrowing yesterday's tuning. */}
        <div
          ref={logRef}
          role="log"
          aria-label="LOG.AI"
          aria-live="polite"
          className="flex min-h-0 flex-1 flex-col gap-1.5 overflow-y-auto border-t pt-1.5 max-lg:max-h-24"
          style={{
            borderTopColor: proposing
              ? 'color-mix(in srgb, var(--brand-accent) 22%, transparent)'
              : 'var(--rule)',
          }}
        >
          {entries.length === 0 ? (
            <p className="text-2xs text-text-soft">Sem eventos de IA.</p>
          ) : (
            entries.map((entry, index) => (
              <p key={`${index}-${entry.time}`} className="flex gap-2 text-2xs text-text-soft">
                <span className="numeric shrink-0">{entry.time}</span>
                <span className="min-w-0 flex-1 break-words">{entry.text}</span>
              </p>
            ))
          )}
        </div>
      </div>

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
