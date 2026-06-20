import * as React from 'react';
import { Slider as SliderPrimitive } from 'radix-ui';

import { cn } from '@/lib/utils';

const Slider = React.forwardRef<
  React.ElementRef<typeof SliderPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof SliderPrimitive.Root>
>(({ className, disabled, ...props }, ref) => {
  // Radix marks the Root disabled but does not surface aria-disabled on each
  // thumb; expose it explicitly so assistive tech and tests can read state.
  const value = props.value ?? props.defaultValue ?? [0];
  const thumbCount = Array.isArray(value) ? value.length : 1;

  return (
    <SliderPrimitive.Root
      ref={ref}
      disabled={disabled}
      className={cn(
        'relative flex w-full touch-none select-none items-center data-[disabled]:opacity-50',
        className,
      )}
      {...props}
    >
      <SliderPrimitive.Track className="relative h-1.5 w-full grow overflow-hidden rounded-none bg-bar-track">
        <SliderPrimitive.Range className="absolute h-full bg-bar-fill" />
      </SliderPrimitive.Track>
      {Array.from({ length: thumbCount }, (_, index) => (
        <SliderPrimitive.Thumb
          key={index}
          aria-disabled={disabled || undefined}
          // Responsive (Task 9.2 / §9): the thumb is a compact 16px control at >=1024; below the
          // 1024 token breakpoint it grows to the 44px touch floor so `assertMinTarget` passes.
          className="block h-4 w-4 rounded-none border border-border-strong bg-surface transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-border-strong disabled:pointer-events-none disabled:opacity-50 max-lg:h-11 max-lg:w-11"
        />
      ))}
    </SliderPrimitive.Root>
  );
});
Slider.displayName = SliderPrimitive.Root.displayName;

export { Slider };
