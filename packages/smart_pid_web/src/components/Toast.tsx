import * as React from 'react';
import { Toast as ToastPrimitive } from 'radix-ui';
import { X } from 'lucide-react';
import { cn } from '@/lib/utils';

export type ToastTone = 'default' | 'crit' | 'warn';

export interface ToastOptions {
  title: string;
  description?: string;
  tone?: ToastTone;
  durationMs?: number;
}

export interface ActiveToast extends ToastOptions {
  id: string;
}

const MAX_TOASTS = 3;
const DEFAULT_DURATION_MS = 5000;

// Module-level store so `toast()` is callable outside React (e.g. the phase-3
// apiClient 403 handler). Toaster subscribes; tests reset via clearToasts().
let counter = 0;
let toasts: readonly ActiveToast[] = [];
const listeners = new Set<(next: readonly ActiveToast[]) => void>();

function emit(): void {
  for (const listener of listeners) listener(toasts);
}

export function toast(opts: ToastOptions): string {
  const id = String(++counter);
  const next: ActiveToast = {
    tone: 'default',
    durationMs: DEFAULT_DURATION_MS,
    ...opts,
    id,
  };
  // Keep at most MAX_TOASTS — drop the oldest.
  toasts = [...toasts.slice(-(MAX_TOASTS - 1)), next];
  emit();
  return id;
}

export function dismissToast(id: string): void {
  toasts = toasts.filter((t) => t.id !== id);
  emit();
}

export function clearToasts(): void {
  toasts = [];
  emit();
}

export function useToasts(): readonly ActiveToast[] {
  const [state, setState] = React.useState(toasts);
  React.useEffect(() => {
    listeners.add(setState);
    setState(toasts);
    return () => {
      listeners.delete(setState);
    };
  }, []);
  return state;
}

const TONE_CLASS: Record<ToastTone, string> = {
  default: 'border-rule-strong bg-surface',
  crit: 'border-alarm-crit bg-alarm-crit-bg',
  warn: 'border-alarm-warn bg-alarm-warn-bg',
};

/** Mount ONCE at the app root (phase 4). */
export function Toaster() {
  const items = useToasts();
  return (
    <ToastPrimitive.Provider swipeDirection="right">
      {items.map((t) => (
        <ToastPrimitive.Root
          key={t.id}
          duration={t.durationMs}
          onOpenChange={(open) => {
            if (!open) dismissToast(t.id);
          }}
          className={cn(
            'relative flex flex-col gap-1 rounded-card border p-3 pr-12 text-text',
            TONE_CLASS[t.tone ?? 'default'],
          )}
        >
          <ToastPrimitive.Title className="text-sm font-medium">{t.title}</ToastPrimitive.Title>
          {t.description ? (
            <ToastPrimitive.Description className="text-xs text-text-soft">
              {t.description}
            </ToastPrimitive.Description>
          ) : null}
          <ToastPrimitive.Close
            aria-label="Fechar"
            className={cn(
              'absolute right-0 top-0 inline-flex min-h-11 min-w-11 items-center justify-center',
              'text-text-soft outline-none hover:text-text focus-visible:ring-2 focus-visible:ring-focus-ring',
            )}
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </ToastPrimitive.Close>
        </ToastPrimitive.Root>
      ))}
      <ToastPrimitive.Viewport
        className="fixed bottom-4 right-4 z-50 flex w-96 max-w-[calc(100vw-2rem)] flex-col gap-2 outline-none"
      />
    </ToastPrimitive.Provider>
  );
}