import * as React from 'react';
import { Switch as SwitchPrimitive } from 'radix-ui';
import { cn } from '@/lib/utils';

/**
 * 24px visual track; the ::after inset extends the pointer target to ≥44px
 * (compact-control rule). Checked state uses the accent — interactive chrome,
 * never a process/alarm color (§6.3/§6.6).
 */
export const Switch = React.forwardRef<
  React.ElementRef<typeof SwitchPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof SwitchPrimitive.Root>
>(({ className, ...props }, ref) => (
  <SwitchPrimitive.Root
    ref={ref}
    className={cn(
      'peer relative inline-flex h-6 w-10 shrink-0 cursor-pointer items-center rounded-pill',
      'border border-rule-strong bg-bar-track outline-none transition-colors',
      "after:absolute after:-inset-x-1 after:-inset-y-2.5 after:content-['']",
      'focus-visible:ring-2 focus-visible:ring-focus-ring',
      'data-[state=checked]:border-accent data-[state=checked]:bg-accent',
      'disabled:cursor-not-allowed disabled:opacity-50',
      className,
    )}
    {...props}
  >
    <SwitchPrimitive.Thumb
      className={cn(
        'pointer-events-none block h-4 w-4 translate-x-1 rounded-pill bg-surface transition-transform',
        'data-[state=checked]:translate-x-[1.125rem]',
      )}
    />
  </SwitchPrimitive.Root>
));
Switch.displayName = SwitchPrimitive.Root.displayName;