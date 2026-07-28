import * as React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils';

/**
 * Quiet instrument chrome (§6.1): secondary (outline) is the default; primary
 * (accent) is opt-in; destructive uses --alarm-crit — the ONE sanctioned
 * process-color exception for confirm affordances (§6.3). `brand` is the
 * Optimizer amber call-to-action: it is the ONE affordance allowed to shout,
 * reserved for the AI panel's apply/optimize action, and it is deliberately
 * NOT a process color (§6.3) — brand-accent never encodes plant state.
 */
export const buttonVariants = cva(
  cn(
    'inline-flex min-h-11 min-w-11 select-none items-center justify-center gap-2 whitespace-nowrap',
    'rounded-control font-ui text-base font-semibold outline-none',
    'transition-colors duration-fast',
    'focus-visible:ring-2 focus-visible:ring-focus-ring',
    'disabled:pointer-events-none disabled:opacity-50',
  ),
  {
    variants: {
      variant: {
        // `btn-primary` is the §10.5 hover/active bloom hook (src/index.css).
        primary: 'btn-primary bg-accent text-on-accent hover:bg-accent-hover active:bg-accent-sunk',
        secondary: 'border border-rule-strong bg-surface text-text hover:bg-surface-sunk',
        ghost: 'text-text-soft hover:bg-surface-sunk hover:text-text',
        destructive: 'bg-alarm-crit text-on-alarm hover:opacity-90',
        brand: 'bg-brand-accent font-bold text-on-brand-accent hover:bg-brand-accent-hover',
      },
      size: {
        md: 'px-3.5 py-2 text-base',
        sm: 'px-3 py-1.5 text-sm',
      },
    },
    defaultVariants: { variant: 'secondary', size: 'md' },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, type = 'button', ...props }, ref) => (
    <button ref={ref} type={type} className={cn(buttonVariants({ variant, size }), className)} {...props} />
  ),
);
Button.displayName = 'Button';