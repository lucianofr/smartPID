import { cn } from '@/lib/utils';

/**
 * LFR Automação brand marks for the application shell.
 *
 * Both are presentation-only. `StepMark` is decorative — the wordmark beside it
 * already carries the product name — and `Wordmark` renders as ONE accessible
 * string so the brand link keeps a single readable accessible name.
 */
export interface BrandMarkProps {
  className?: string;
}

/**
 * The LFR "STEP" icon: a settling step response drawn as one stroked path. It
 * is the product's mark — the shape a well-tuned loop makes.
 *
 * Stroked in `currentColor` on purpose. The caller owns the ink (the shell
 * tints it `text-brand-accent`), so the mark re-resolves when [data-theme]
 * flips without this file knowing anything about the palette.
 */
export function StepMark({ className }: BrandMarkProps) {
  return (
    <svg
      viewBox="0 0 180 120"
      aria-hidden="true"
      focusable="false"
      className={cn('block h-6 w-9 shrink-0', className)}
    >
      <path
        d="M 14 100 L 50 100 C 64 100, 66 22, 78 22 S 92 64, 96 56 S 116 32, 116 38 S 132 48, 132 44 S 148 41, 148 41 L 170 41"
        fill="none"
        stroke="currentColor"
        strokeWidth={5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

/**
 * The product name as one string. The brand link labels itself with this so
 * the name cannot drift from the rendered runs below.
 */
export const WORDMARK_TEXT = 'smartPID Optimizer';

/**
 * "smartPID Optimizer", with only `PID` in the brand accent.
 *
 * The coloured run is an inline `<span>` with no surrounding whitespace nodes,
 * so `textContent` is exactly `smartPID Optimizer`. The *accessible* name is
 * pinned by the caller instead: dom-accessibility-api joins child runs with a
 * space whenever `getComputedStyle(child).display !== 'inline'`, and jsdom
 * reports `''` for an unstyled `<span>` — so an unlabelled link would be named
 * `smartPID Optimizer` in a browser and `smart PID Optimizer` under jsdom.
 *
 * The base ink is inherited (`text-text` from the shell) rather than pinned to
 * `--brand-ink`: brand-ink is a dark navy in every theme and would vanish on
 * the dark surfaces.
 */
export function Wordmark({ className }: BrandMarkProps) {
  return (
    <span className={cn('type-display text-xl font-bold tracking-tight', className)}>
      smart<span className="text-brand-accent">PID</span> Optimizer
    </span>
  );
}
