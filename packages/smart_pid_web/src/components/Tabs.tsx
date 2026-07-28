import * as React from 'react';
import { Tabs as TabsPrimitive } from 'radix-ui';
import { cn } from '@/lib/utils';

const Tabs = TabsPrimitive.Root;

const TabsList = React.forwardRef<
  React.ElementRef<typeof TabsPrimitive.List>,
  React.ComponentPropsWithoutRef<typeof TabsPrimitive.List>
>(({ className, ...props }, ref) => (
  <TabsPrimitive.List
    ref={ref}
    className={cn('inline-flex items-center gap-0.5 border-b border-rule', className)}
    {...props}
  />
));
TabsList.displayName = TabsPrimitive.List.displayName;

const TabsTrigger = React.forwardRef<
  React.ElementRef<typeof TabsPrimitive.Trigger>,
  React.ComponentPropsWithoutRef<typeof TabsPrimitive.Trigger>
>(({ className, ...props }, ref) => (
  <TabsPrimitive.Trigger
    ref={ref}
    className={cn(
      '-mb-px inline-flex min-h-11 items-center justify-center rounded-t-control border-b-2 border-transparent px-3.5',
      'text-base font-medium text-text-soft outline-none transition-colors duration-fast',
      'hover:text-text focus-visible:ring-2 focus-visible:ring-focus-ring',
      // The active rule is brand amber, matching the shell's primary nav
      // (AppShell NAV_LINK_ACTIVE). `border-b-*` is the bottom-edge longhand
      // and is emitted after the `border-*` shorthand, so it wins on the only
      // edge that has width — the other three sit at 0 and never paint.
      'data-[state=active]:border-accent data-[state=active]:border-b-brand-accent',
      'data-[state=active]:font-semibold data-[state=active]:text-text',
      'disabled:pointer-events-none disabled:text-text-disabled',
      className,
    )}
    {...props}
  />
));
TabsTrigger.displayName = TabsPrimitive.Trigger.displayName;

const TabsContent = React.forwardRef<
  React.ElementRef<typeof TabsPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof TabsPrimitive.Content>
>(({ className, ...props }, ref) => (
  <TabsPrimitive.Content
    ref={ref}
    className={cn('pt-3 outline-none focus-visible:ring-2 focus-visible:ring-focus-ring', className)}
    {...props}
  />
));
TabsContent.displayName = TabsPrimitive.Content.displayName;

export { Tabs, TabsContent, TabsList, TabsTrigger };