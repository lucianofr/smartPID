import type { StatusData } from '../realtime/envelope';
import { AnalogBar } from './AnalogBar';

export interface ControllerSummary {
  id: number;
  name: string;
  description: string;
  pv_decimals: number;
  pv_unit: string;
}

/**
 * Flat ISA-101 card. All static styling is expressed as token utilities
 * (`bg-surface`, `border-border`, `rounded-card`, `--sp-*` spacing). Card width
 * is the `--card-w` contract token. Hierarchy is scale + weight + gray only — no
 * color-coded emphasis. Hover on the icon buttons is a single tonal surface step
 * (no shadow/lift, per §design-quality flat policy); active steps back down with
 * `translateY(0)`; focus ring is always visible.
 *
 * Font sizes stay inline as `var(--text-*)` — the type scale has no Tailwind
 * utility mapping in the `@theme inline` bridge (same precedent as AnalogBar).
 */
const ICON_BUTTON =
  'flex items-center justify-center cursor-pointer border-none bg-transparent p-0 leading-none text-text-secondary ' +
  'transition-colors duration-fast hover:text-text hover:bg-surface-container-high ' +
  'active:bg-surface-container active:translate-y-0 ' +
  'focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-[var(--focus-ring)]';

export function ControllerCard({
  controller,
  status,
  onOpenConfig,
  onOpenFaceplate,
  controls,
}: {
  controller: ControllerSummary;
  status: StatusData | undefined;
  onOpenConfig?: () => void;
  onOpenFaceplate?: () => void;
  controls?: React.ReactNode;
}) {
  return (
    <div className="flex w-[var(--card-w)] flex-col border border-border bg-surface rounded-card">
      <div className="h-[var(--alarmstrip-h)]" />
      <div className="flex flex-col gap-2 p-4">
        <div className="flex items-baseline justify-between gap-2">
          <span
            className="numeric font-bold text-text"
            style={{ fontSize: 'var(--text-base)' }}
          >
            {controller.name}
          </span>
          <div className="flex items-baseline gap-2">
            {controller.description && (
              <span className="text-text-secondary" style={{ fontSize: 'var(--text-xs)' }}>
                {controller.description}
              </span>
            )}
            {onOpenFaceplate && (
              <button
                type="button"
                aria-label="Open faceplate"
                title="Open faceplate"
                onClick={onOpenFaceplate}
                className={ICON_BUTTON}
                style={{ fontSize: 'var(--text-base)' }}
              >
                ⤢
              </button>
            )}
            {onOpenConfig && (
              <button
                type="button"
                aria-label="Open loop config"
                title="Configure loop"
                onClick={onOpenConfig}
                className={ICON_BUTTON}
                style={{ fontSize: 'var(--text-base)' }}
              >
                ⚙
              </button>
            )}
          </div>
        </div>
        <AnalogBar label="PV" value={status?.pv?.value} scale={{ euMin: 0, euMax: 100, unit: controller.pv_unit }} decimals={controller.pv_decimals} />
        <AnalogBar label="SP" value={status?.sp?.value} scale={{ euMin: 0, euMax: 100, unit: controller.pv_unit }} decimals={controller.pv_decimals} />
        <AnalogBar label="CO" value={status?.co?.value} scale={{ euMin: 0, euMax: 100, unit: '%' }} decimals={1} />
        <div className="flex gap-2 text-text-secondary" style={{ fontSize: 'var(--text-xs)' }}>
          <span className="numeric">{status?.mode ?? '—'}</span>
        </div>
      </div>
      {controls}
    </div>
  );
}
