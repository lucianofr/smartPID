import type { ReactNode } from 'react';
import { SlidersHorizontal } from 'lucide-react';
import { AnalogBar, type AnalogBarAlarm } from '@/components/AnalogBar';
import { Badge } from '@/components/Badge';
import { Button } from '@/components/Button';
import type { ControllerResponse } from '@/api/types';
import type { FFSignal, StatusData } from '@/lib/envelope';
import { cn } from '@/lib/utils';
import { CO_SCALE, pvScale } from './useControllers';

export interface LoopCardProps {
  controller: ControllerResponse;
  status: StatusData | null;
  onOpenConfig(id: number): void;
  /** Phase 5 mounts `CardControls` here. */
  controlsSlot?: ReactNode;
  /** The realtime bus went quiet — mark every reading as not current (E2E-047). */
  stale?: boolean;
  /** This loop drives the trend and the faceplate: lift it out of the strip. */
  selected?: boolean;
}

/**
 * Fieldbus quality → card alarm level. The card has no alarm-row feed (that is
 * the footer's job, §6.9); what it owns is the quality of the values it is
 * showing, so a BAD signal must not read as a healthy number.
 */
function qualityAlarm(signal: FFSignal | undefined): AnalogBarAlarm {
  const severity = signal?.severity ?? '';
  if (severity.startsWith('BAD')) return 'crit';
  if (severity.startsWith('UNCERTAIN')) return 'warn';
  return 'normal';
}

/**
 * The AI strategy the loop is actually running, or null.
 *
 * Roster-level truth, same rule the executive dashboard applies: an engine is
 * only "on" when optimization is switched on AND an engine is selected (`NONE`
 * is the opted-out default). A card that advertised `FUZZY` for a loop with the
 * optimizer disabled would be lying to the operator.
 */
export function activeAiStrategy(controller: ControllerResponse): string | null {
  if (controller.optimization_enabled !== true) return null;
  const engine = controller.ai_config?.engine ?? 'NONE';
  return engine === 'NONE' ? null : engine;
}

const BORDER_BY_ALARM: Record<AnalogBarAlarm, string> = {
  normal: 'border-rule',
  warn: 'border-alarm-warn',
  crit: 'border-alarm-crit',
};

const DOT_BY_ALARM: Record<AnalogBarAlarm, string> = {
  normal: '',
  warn: 'bg-alarm-warn',
  crit: 'bg-alarm-crit',
};

/** Modes in which the loop is closing on its own — everything else is attention. */
const CLOSED_LOOP_MODES: ReadonlySet<string> = new Set(['AUTO', 'CAS']);

/**
 * Mode chip paint. Not a `Badge` tone: the severity tones carry `badge-glow`
 * (§10.5 is severity-only) and a mode is not an alarm, so `neutral` is the tone
 * and the colour comes from the state tokens here.
 *
 * The tint is an inline `color-mix` (same pattern as `KpiBand`) rather than a
 * `bg-state-running/15` utility. There is no soft variant of `--state-running`
 * in the §6.4 contract, and Tailwind's opacity modifier emits a FULL-opacity
 * fallback outside `@supports color-mix` — which would put green text on solid
 * green. An unsupported inline `color-mix` just drops to no background instead.
 */
const RUNNING_TINT = 'color-mix(in srgb, var(--state-running) 15%, transparent)';

interface ChipPaint {
  readonly text: string;
  readonly tint: string;
}

const MODE_CHIP: Record<string, ChipPaint> = {
  AUTO: { text: 'text-state-running', tint: RUNNING_TINT },
  CAS: { text: 'text-state-running', tint: RUNNING_TINT },
  MAN: { text: 'text-alarm-warn', tint: 'var(--alarm-warn-bg)' },
};
const MODE_CHIP_FALLBACK: ChipPaint = { text: 'text-text-soft', tint: 'var(--surface-sunk)' };

const CHIP = 'border-transparent px-2 py-0.5 text-xs font-bold tracking-wide';

/**
 * One loop in the top strip (§6.9). Fixed 206 px width, never shrinks — the
 * strip is a single horizontal scroller and wrapping would push the trend below
 * the fold. No sparkline: the trend panel is the only chart on this page.
 *
 * Border precedence is deliberate: a bad fieldbus signal outranks selection.
 * The operator can always see which card is open (shadow + the pressed `Abrir`
 * button), but a card whose numbers cannot be trusted must say so first.
 */
export function LoopCard({
  controller,
  status,
  onOpenConfig,
  controlsSlot,
  stale = false,
  selected = false,
}: LoopCardProps) {
  const scale = pvScale(controller);
  const decimals = 1;
  // A frozen frame cannot certify fieldbus quality either: fall back to the
  // neutral border rather than keep asserting the pre-outage alarm level.
  const alarm = stale ? 'normal' : qualityAlarm(status?.pv);
  const mode = status?.mode ?? controller.mode;
  const closedLoop = CLOSED_LOOP_MODES.has(mode);
  const modeChip = MODE_CHIP[mode] ?? MODE_CHIP_FALLBACK;
  const strategy = activeAiStrategy(controller);

  const border =
    alarm !== 'normal' ? BORDER_BY_ALARM[alarm] : selected ? 'border-accent' : 'border-rule';

  return (
    <div
      className={cn(
        'relative flex w-[206px] shrink-0 cursor-pointer flex-col gap-2.5 overflow-hidden',
        'rounded-card border-2 bg-surface p-3.5',
        'transition-transform hover:-translate-y-0.5',
        border,
      )}
      style={{ boxShadow: selected ? 'var(--shadow-lifted)' : 'var(--shadow-card)' }}
    >
      {/* Mode ribbon: the one thing readable from across the control room. */}
      <span
        aria-hidden="true"
        className={cn(
          'absolute inset-x-0 top-0 h-[3px]',
          closedLoop ? 'bg-state-running' : 'bg-alarm-warn',
        )}
      />
      {alarm !== 'normal' ? (
        <span
          aria-hidden="true"
          data-testid="loop-card-quality-dot"
          className={cn('absolute right-2.5 top-2.5 h-2 w-2 rounded-pill', DOT_BY_ALARM[alarm])}
        />
      ) : null}

      <div className="min-w-0 pr-3">
        <p className="numeric truncate text-md font-bold text-text">{controller.name}</p>
        <p className="truncate text-sm text-text-soft">{controller.description}</p>
      </div>

      <div className="flex flex-col gap-1.5">
        <AnalogBar
          label="PV"
          value={status?.pv.value ?? null}
          spValue={status?.sp.value}
          scale={scale}
          alarm={alarm}
          decimals={decimals}
          size="card"
          stale={stale}
        />
        <AnalogBar
          label="SP"
          value={status?.sp.value ?? null}
          scale={scale}
          decimals={decimals}
          size="card"
          stale={stale}
        />
        <AnalogBar
          label="CO"
          value={status?.co.value ?? null}
          scale={CO_SCALE}
          decimals={decimals}
          size="card"
          stale={stale}
        />
      </div>

      <div className="flex items-center gap-1.5">
        <div className="flex flex-wrap gap-1.5">
          <Badge
            tone="neutral"
            style={{ backgroundColor: modeChip.tint }}
            className={cn('numeric', CHIP, modeChip.text)}
          >
            {mode}
          </Badge>
          {/* The optimizer is the product's reason to exist: it gets a permanent
              slot, and an em dash when the loop opted out — not a missing chip. */}
          <Badge
            tone="neutral"
            title={strategy !== null ? `Otimização por IA: ${strategy}` : 'Sem otimização por IA'}
            className={cn(CHIP, strategy !== null ? 'bg-state-ai-soft text-state-ai' : 'text-text-soft')}
          >
            {strategy ?? '—'}
          </Badge>
        </div>

        {/* A distinct glyph from the top bar's gear: both are on screen at once
            and they configure different things (the app vs this loop). */}
        <Button
          variant="ghost"
          size="sm"
          className="ml-auto shrink-0"
          aria-label={`Configurar ${controller.name}`}
          onClick={() => onOpenConfig(controller.id)}
        >
          <SlidersHorizontal className="h-4 w-4" aria-hidden="true" />
        </Button>
      </div>

      {/* Pushed to the floor so every card in the row lines its actions up, even
          though only the selected one carries the mode switch. */}
      {controlsSlot !== undefined ? <div className="mt-auto">{controlsSlot}</div> : null}
    </div>
  );
}
