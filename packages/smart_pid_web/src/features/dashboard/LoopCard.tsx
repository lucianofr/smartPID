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

const BORDER_BY_ALARM: Record<AnalogBarAlarm, string> = {
  normal: 'border-rule',
  warn: 'border-alarm-warn',
  crit: 'border-alarm-crit',
};

const MODE_TONE: Record<string, 'neutral' | 'accent' | 'warn'> = {
  AUTO: 'accent',
  CAS: 'accent',
  MAN: 'warn',
};

/**
 * One loop in the top strip (§6.9). Fixed width, never shrinks — the strip is a
 * single horizontal scroller and wrapping would push the trend below the fold.
 * No sparkline: the trend panel is the only chart on this page.
 */
export function LoopCard({
  controller,
  status,
  onOpenConfig,
  controlsSlot,
  stale = false,
}: LoopCardProps) {
  const scale = pvScale(controller);
  const decimals = 1;
  // A frozen frame cannot certify fieldbus quality either: fall back to the
  // neutral border rather than keep asserting the pre-outage alarm level.
  const alarm = stale ? 'normal' : qualityAlarm(status?.pv);
  const mode = status?.mode ?? controller.mode;

  return (
    <div
      className={cn(
        'flex w-[280px] shrink-0 flex-col gap-2 border bg-surface p-3',
        BORDER_BY_ALARM[alarm],
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="numeric truncate text-sm font-medium text-text">{controller.name}</p>
          <p className="truncate text-2xs text-text-soft">{controller.description}</p>
        </div>
        <Badge tone={MODE_TONE[mode] ?? 'neutral'} className="numeric shrink-0">
          {mode}
        </Badge>
      </div>

      <AnalogBar
        label="PV"
        value={status?.pv.value ?? null}
        spValue={status?.sp.value}
        scale={scale}
        alarm={alarm}
        decimals={decimals}
        stale={stale}
      />
      <AnalogBar
        label="SP"
        value={status?.sp.value ?? null}
        scale={scale}
        decimals={decimals}
        stale={stale}
      />
      <AnalogBar
        label="CO"
        value={status?.co.value ?? null}
        scale={CO_SCALE}
        decimals={decimals}
        stale={stale}
      />

      {controlsSlot}

      {/* A distinct glyph from the top bar's gear: both are on screen at once
          and they configure different things (the app vs this loop). */}
      <Button
        variant="ghost"
        size="sm"
        className="self-end"
        aria-label={`Configurar ${controller.name}`}
        onClick={() => onOpenConfig(controller.id)}
      >
        <SlidersHorizontal className="h-4 w-4" aria-hidden="true" />
      </Button>
    </div>
  );
}
