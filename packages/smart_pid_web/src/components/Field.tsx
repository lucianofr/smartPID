import * as React from 'react';
import { cn } from '@/lib/utils';

export interface FieldProps {
  label: string;
  htmlFor: string;
  description?: string;
  error?: string;
  required?: boolean;
  children: React.ReactNode;
  className?: string;
}

/**
 * Labeled form-control wrapper. ID convention: description `${htmlFor}-desc`,
 * error `${htmlFor}-err` — callers wire aria-describedby to those ids.
 * The `*` is aria-hidden so accessible names stay verbatim (E2E binds to them).
 */
export function Field({ label, htmlFor, description, error, required = false, children, className }: FieldProps) {
  return (
    <div className={cn('flex flex-col gap-1', className)}>
      <label htmlFor={htmlFor} className="text-sm font-medium text-text">
        {label}
        {required ? (
          <span aria-hidden="true" className="text-alarm-crit">
            {' '}
            *
          </span>
        ) : null}
      </label>
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
  ({ className, invalid = false, ...props }, ref) => (
    <input
      ref={ref}
      aria-invalid={invalid || undefined}
      className={cn(
        'min-h-11 w-full rounded-control border border-rule-strong bg-surface-sunk px-3 py-2 text-sm text-text',
        'placeholder:text-text-disabled outline-none focus-visible:ring-2 focus-visible:ring-focus-ring',
        'disabled:cursor-not-allowed disabled:text-text-disabled',
        invalid && 'border-alarm-crit',
        className,
      )}
      {...props}
    />
  ),
);
Input.displayName = 'Input';