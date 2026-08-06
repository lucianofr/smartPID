import * as React from 'react';
import { Checkbox as CheckboxPrimitive } from 'radix-ui';
import { Check } from 'lucide-react';
import { cn } from '@/lib/utils';

/**
 * A boxed control, distinct from `Switch`'s pill track: checkboxes answer
 * "which of these" (a set) where switches answer "on or off" (a state).
 *
 * Checked state uses the accent — interactive chrome, never a process/alarm
 * color (§6.3/§6.6), mirroring Switch's rule.
 */
export const Checkbox = React.forwardRef<
  React.ElementRef<typeof CheckboxPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof CheckboxPrimitive.Root>
>(({ className, ...props }, ref) => (
  <CheckboxPrimitive.Root
    ref={ref}
    className={cn(
      'peer inline-flex h-[18px] w-[18px] shrink-0 items-center justify-center rounded-control',
      'border border-rule-strong bg-surface-sunk outline-none transition-colors duration-fast',
      'focus-visible:ring-2 focus-visible:ring-focus-ring',
      'data-[state=checked]:border-accent data-[state=checked]:bg-accent',
      'disabled:cursor-not-allowed disabled:opacity-50',
      className,
    )}
    {...props}
  >
    <CheckboxPrimitive.Indicator className="flex items-center justify-center text-on-accent">
      <Check className="h-3 w-3" aria-hidden="true" />
    </CheckboxPrimitive.Indicator>
  </CheckboxPrimitive.Root>
));
Checkbox.displayName = CheckboxPrimitive.Root.displayName;
