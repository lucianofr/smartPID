import * as React from 'react';
import { Switch as SwitchPrimitive } from 'radix-ui';
import { cn } from '@/lib/utils';

/**
 * The Optimizer toggle: an 18x32 borderless track with a 14px raised thumb —
 * the same compact switch the mock uses for "Auto-escala". The visual control
 * is deliberately smaller than the pointer target; the ::after inset extends
 * the hit area to 44x46 (compact-control rule / design-system §9).
 *
 * Those insets are derived from the track, not decorative: 32 + 2*6 = 44 wide,
 * 18 + 2*14 = 46 tall. Resize the track and they must be recomputed.
 *
 * Checked state uses the accent — interactive chrome, never a process/alarm
 * color (§6.3/§6.6).
 */
export const Switch = React.forwardRef<
  React.ElementRef<typeof SwitchPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof SwitchPrimitive.Root>
>(({ className, ...props }, ref) => (
  <SwitchPrimitive.Root
    ref={ref}
    className={cn(
      'peer relative inline-flex h-[18px] w-8 shrink-0 cursor-pointer items-center rounded-pill',
      'bg-rule-strong outline-none transition-colors duration-fast',
      "after:absolute after:-inset-x-1.5 after:-inset-y-3.5 after:content-['']",
      'focus-visible:ring-2 focus-visible:ring-focus-ring',
      'data-[state=checked]:bg-accent',
      'disabled:cursor-not-allowed disabled:opacity-50',
      className,
    )}
    {...props}
  >
    <SwitchPrimitive.Thumb
      className={cn(
        'pointer-events-none block h-3.5 w-3.5 translate-x-0.5 rounded-pill bg-surface shadow-card',
        'transition-transform duration-fast data-[state=checked]:translate-x-4',
      )}
    />
  </SwitchPrimitive.Root>
));
Switch.displayName = SwitchPrimitive.Root.displayName;