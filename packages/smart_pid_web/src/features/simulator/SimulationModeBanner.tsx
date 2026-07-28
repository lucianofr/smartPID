import { cn } from '@/lib/utils';

export interface SimulationModeBannerProps {
  /** The twin is actually stepping — the values on screen are model output. */
  running: boolean;
  className?: string;
}

/**
 * Persistent simulation-mode banner.
 *
 * `role="status"` makes it a live region: the operator is TOLD when the plant
 * they are watching turns into a model, instead of having to notice a colour.
 * The accessible name `Simulation mode` is frozen (e2e/simulator.spec.ts).
 * Advisory tokens, never `--alarm-crit`: simulation is a mode, not an alarm.
 */
export function SimulationModeBanner({ running, className }: SimulationModeBannerProps) {
  return (
    <div
      role="status"
      aria-label="Simulation mode"
      className={cn(
        'flex shrink-0 flex-wrap items-baseline justify-center gap-x-2 border-b',
        'border-alarm-adv bg-alarm-adv-bg px-3 py-2 text-center',
        className,
      )}
    >
      <span className="text-xs font-semibold uppercase tracking-widest text-alarm-adv">
        {running ? 'SIMULAÇÃO ATIVA' : 'MODO SIMULAÇÃO'}
      </span>
      <span className="text-xs text-text-soft">
        {running
          ? 'os valores exibidos vêm do gêmeo digital, não da planta'
          : 'gêmeo digital parado — nenhum valor simulado em circulação'}
      </span>
    </div>
  );
}
