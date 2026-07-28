import * as React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils';

export const badgeVariants = cva(
  'inline-flex items-center gap-1 rounded-pill border px-2 py-0.5 font-ui text-xs font-medium',
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