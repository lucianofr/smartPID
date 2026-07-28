import * as React from 'react';
import { Slider as SliderPrimitive } from 'radix-ui';
import { cn } from '@/lib/utils';

export interface SliderProps extends React.ComponentPropsWithoutRef<typeof SliderPrimitive.Root> {
  /** aria-label applied to every thumb (Radix does not inherit it from the root). */
  thumbLabel?: string;
}

/**
 * The thumb is a compact 16px control at ≥1024; below the 1024 breakpoint it
 * grows to the literal 44px touch floor — the pattern the retained
 * e2e/target-size.spec.ts asserts on the CO slider (assertMinTarget <1024).
 */
export const Slider = React.forwardRef<
  React.ElementRef<typeof SliderPrimitive.Root>,
  SliderProps
>(({ className, disabled, thumbLabel, ...props }, ref) => {
  const value = props.value ?? props.defaultValue ?? [0];
  const thumbCount = Array.isArray(value) ? value.length : 1;

  return (
    <SliderPrimitive.Root
      ref={ref}
      disabled={disabled}
      className={cn(
        'relative flex min-h-11 w-full touch-none select-none items-center data-[disabled]:opacity-50',
        className,
      )}
      {...props}
    >
      <SliderPrimitive.Track className="relative h-1.5 w-full grow overflow-hidden rounded-pill bg-bar-track">
        <SliderPrimitive.Range className="absolute h-full rounded-pill bg-accent" />
      </SliderPrimitive.Track>
      {Array.from({ length: thumbCount }, (_, index) => (
        <SliderPrimitive.Thumb
          key={index}
          aria-label={thumbLabel}
          aria-disabled={disabled || undefined}
          className={cn(
            'block h-4 w-4 rounded-pill border border-rule-strong bg-surface shadow-card outline-none',
            'transition-colors duration-fast hover:border-accent',
            'focus-visible:ring-2 focus-visible:ring-focus-ring disabled:pointer-events-none',
            'max-lg:h-11 max-lg:w-11',
          )}
        />
      ))}
    </SliderPrimitive.Root>
  );
});
Slider.displayName = SliderPrimitive.Root.displayName;