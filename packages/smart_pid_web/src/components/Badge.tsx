import * as React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils';

/**
 * The Optimizer chip: pill, caps-ish tracking, bold, and small enough that a
 * row of them reads as metadata rather than as buttons. Severity tones stay
 * outline + bloom (§6.4 — severity is text + shape + color, never a fill that
 * competes with an alarm row); the state tones below are fills, because a
 * strategy or run-state chip is a label, not a severity.
 */
export const badgeVariants = cva(
  'inline-flex items-center gap-1 rounded-pill border px-2 py-0.5 font-ui text-xs font-bold tracking-wide',
  {
    variants: {
      tone: {
        neutral: 'border-rule text-text-soft',
        accent: 'border-accent bg-accent-soft text-accent',
        // `badge-glow` is the §10.5 bloom hook (src/index.css). Severity only —
        // `neutral` and `log` are chrome and must never bloom.
        crit: 'badge-glow border-alarm-crit text-alarm-crit',
        warn: 'badge-glow border-alarm-warn text-alarm-warn',
        adv: 'badge-glow border-alarm-adv text-alarm-adv',
        log: 'border-rule text-alarm-log',
        // The FUZZY/RL strategy chip. --state-ai is the optimizer's own hue and
        // is not in the alarm ramp, so this fill can never be misread as state.
        ai: 'border-transparent bg-state-ai-soft text-state-ai',
        // Solid run-state chip; --on-alarm is the contrast-checked foreground
        // for every solid state/alarm fill in all six palettes.
        running: 'border-transparent bg-state-running text-on-alarm',
      },
    },
    defaultVariants: { tone: 'neutral' },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, tone, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ tone }), className)} {...props} />;
}