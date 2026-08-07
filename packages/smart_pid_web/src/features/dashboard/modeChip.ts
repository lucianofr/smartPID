import type { ExecutionMode } from '@/features/loop-config/types';

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
export const RUNNING_TINT = 'color-mix(in srgb, var(--state-running) 15%, transparent)';

export interface ChipPaint {
  readonly text: string;
  readonly tint: string;
}

export const MODE_CHIP: Record<string, ChipPaint> = {
  AUTO: { text: 'text-state-running', tint: RUNNING_TINT },
  CAS: { text: 'text-state-running', tint: RUNNING_TINT },
  MAN: { text: 'text-alarm-warn', tint: 'var(--alarm-warn-bg)' },
  UNKNOWN: { text: 'text-alarm-warn', tint: 'var(--alarm-warn-bg)' },
};
export const MODE_CHIP_FALLBACK: ChipPaint = { text: 'text-text-soft', tint: 'var(--surface-sunk)' };

export const CHIP = 'border-transparent px-2 py-0.5 text-xs font-bold tracking-wide';

/** Title for a mode the loop's own mode map does not cover. */
export const UNKNOWN_MODE_TITLE = 'Mapeamento de modos não configurado';

/** Execution-mode badge tooltip — split from LoopConfigDialog's combined prose. */
export const EXEC_MODE_TITLE: Record<ExecutionMode, string> = {
  SUPERVISORY: 'SUPERVISORY: o PID roda no CLP/DCS e o SmartPID só monitora.',
  DDC: 'DDC: o PID roda dentro do SmartPID, que escreve a saída diretamente.',
};
