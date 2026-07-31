import * as React from 'react';
import { Info } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Tooltip, TooltipContent, TooltipTrigger } from './Tooltip';

export interface FieldProps {
  label: string;
  htmlFor: string;
  description?: string;
  error?: string;
  required?: boolean;
  /** Description shown in a hover/focus tooltip behind an "i" icon next to the label. */
  tooltip?: string;
  children: React.ReactNode;
  className?: string;
}

/**
 * Labeled form-control wrapper. ID convention: description `${htmlFor}-desc`,
 * error `${htmlFor}-err` — callers wire aria-describedby to those ids.
 * The `*` is aria-hidden so accessible names stay verbatim (E2E binds to them).
 *
 * The tooltip trigger is a SIBLING of `<label>`, never a child of it: this
 * codebase's own accname computation folds aria-hidden descendant text back
 * into the label's accessible name (see Field.test.tsx), so anything placed
 * inside `<label>` would leak into `getByLabelText(label)` everywhere.
 */
export function Field({
  label,
  htmlFor,
  description,
  error,
  required = false,
  tooltip,
  children,
  className,
}: FieldProps) {
  return (
    <div className={cn('flex flex-col gap-1', className)}>
      <div className="flex items-center gap-1">
        <label htmlFor={htmlFor} className="text-sm font-medium text-text">
          {label}
          {required ? (
            <span aria-hidden="true" className="text-alarm-crit">
              {' '}
              *
            </span>
          ) : null}
        </label>
        {tooltip !== undefined ? (
          <Tooltip>
            <TooltipTrigger asChild>
              <button
                type="button"
                aria-label={`Mais informações sobre ${label}`}
                className={cn(
                  'inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-full',
                  'text-text-soft outline-none hover:text-text',
                  'focus-visible:ring-2 focus-visible:ring-focus-ring',
                )}
              >
                <Info className="h-3.5 w-3.5" aria-hidden="true" />
              </button>
            </TooltipTrigger>
            <TooltipContent>{tooltip}</TooltipContent>
          </Tooltip>
        ) : null}
      </div>
      {children}
      {description ? (
        <p id={`${htmlFor}-desc`} className="text-xs text-text-soft">
          {description}
        </p>
      ) : null}
      {error ? (
        <p id={`${htmlFor}-err`} role="alert" className="text-xs font-medium text-alarm-crit">
          {error}
        </p>
      ) : null}
    </div>
  );
}

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  invalid?: boolean;
}

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, invalid = false, type, ...props }, ref) => (
    <input
      ref={ref}
      type={type}
      aria-invalid={invalid || undefined}
      className={cn(
        'min-h-11 w-full rounded-control border border-rule-strong bg-surface-sunk px-2.5 py-2 text-base text-text',
        'placeholder:text-text-disabled outline-none transition-colors duration-fast',
        'focus-visible:ring-2 focus-visible:ring-focus-ring',
        'disabled:cursor-not-allowed disabled:text-text-disabled',
        // A number field is a readout the operator is allowed to edit; it reads
        // in the data face so it lines up with every other numeral on screen.
        type === 'number' && 'numeric',
        invalid && 'border-alarm-crit',
        className,
      )}
      {...props}
    />
  ),
);
Input.displayName = 'Input';