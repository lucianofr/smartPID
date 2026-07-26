import * as React from 'react';
import { Command as CommandPrimitive } from 'cmdk';
import { Search } from 'lucide-react';
import { Dialog, DialogContent } from '@/components/Dialog';
import { cn } from '@/lib/utils';

const Command = React.forwardRef<
  React.ElementRef<typeof CommandPrimitive>,
  React.ComponentPropsWithoutRef<typeof CommandPrimitive>
>(({ className, ...props }, ref) => (
  <CommandPrimitive
    ref={ref}
    className={cn('flex w-full flex-col overflow-hidden bg-surface text-text', className)}
    {...props}
  />
));
Command.displayName = CommandPrimitive.displayName;

const CommandInput = React.forwardRef<
  React.ElementRef<typeof CommandPrimitive.Input>,
  React.ComponentPropsWithoutRef<typeof CommandPrimitive.Input>
>(({ className, placeholder = 'Buscar comando…', ...props }, ref) => (
  <div className="flex items-center gap-2 border-b border-rule px-3">
    <Search className="h-4 w-4 shrink-0 text-text-soft" aria-hidden="true" />
    <CommandPrimitive.Input
      ref={ref}
      placeholder={placeholder}
      className={cn(
        'min-h-11 w-full bg-transparent text-sm text-text outline-none placeholder:text-text-disabled',
        className,
      )}
      {...props}
    />
  </div>
));
CommandInput.displayName = CommandPrimitive.Input.displayName;

const CommandList = React.forwardRef<
  React.ElementRef<typeof CommandPrimitive.List>,
  React.ComponentPropsWithoutRef<typeof CommandPrimitive.List>
>(({ className, ...props }, ref) => (
  <CommandPrimitive.List
    ref={ref}
    className={cn('max-h-72 overflow-y-auto p-1', className)}
    {...props}
  />
));
CommandList.displayName = CommandPrimitive.List.displayName;

const CommandEmpty = React.forwardRef<
  React.ElementRef<typeof CommandPrimitive.Empty>,
  React.ComponentPropsWithoutRef<typeof CommandPrimitive.Empty>
>(({ children = 'Nenhum resultado.', className, ...props }, ref) => (
  <CommandPrimitive.Empty
    ref={ref}
    className={cn('py-6 text-center text-sm text-text-soft', className)}
    {...props}
  >
    {children}
  </CommandPrimitive.Empty>
));
CommandEmpty.displayName = CommandPrimitive.Empty.displayName;

const CommandGroup = React.forwardRef<
  React.ElementRef<typeof CommandPrimitive.Group>,
  React.ComponentPropsWithoutRef<typeof CommandPrimitive.Group>
>(({ className, ...props }, ref) => (
  <CommandPrimitive.Group
    ref={ref}
    className={cn(
      '[&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-1.5',
      '[&_[cmdk-group-heading]]:text-2xs [&_[cmdk-group-heading]]:font-medium',
      '[&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-wider',
      '[&_[cmdk-group-heading]]:text-text-soft',
      className,
    )}
    {...props}
  />
));
CommandGroup.displayName = CommandPrimitive.Group.displayName;

const CommandItem = React.forwardRef<
  React.ElementRef<typeof CommandPrimitive.Item>,
  React.ComponentPropsWithoutRef<typeof CommandPrimitive.Item>
>(({ className, ...props }, ref) => (
  <CommandPrimitive.Item
    ref={ref}
    className={cn(
      'flex min-h-11 cursor-default select-none items-center gap-2 rounded-control px-2 text-sm outline-none',
      'data-[selected=true]:bg-selection data-[disabled=true]:pointer-events-none data-[disabled=true]:text-text-disabled',
      className,
    )}
    {...props}
  />
));
CommandItem.displayName = CommandPrimitive.Item.displayName;

export interface CommandDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  label?: string;
  children: React.ReactNode;
}

/** The `[k]` palette shell (§6.9). Phase 4 binds the shortcut and the actions. */
export function CommandDialog({ open, onOpenChange, label = 'Paleta de comandos', children }: CommandDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent aria-label={label} className="top-[20%] translate-y-0 p-0">
        <Command label={label}>{children}</Command>
      </DialogContent>
    </Dialog>
  );
}

export { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList };