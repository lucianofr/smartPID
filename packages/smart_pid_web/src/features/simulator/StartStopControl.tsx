import { Badge } from '@/components/Badge';
import { Button } from '@/components/Button';

export interface StartStopControlProps {
  running: boolean;
  onStart: () => void;
  onStop: () => void;
}

/**
 * Twin run state. The `Start` / `Stop` names and the `sim-running` readout are
 * frozen by e2e/simulator.spec.ts. Run state travels on two channels — the
 * badge text and the disabled buttons — never colour alone (§6.4).
 */
export function StartStopControl({ running, onStart, onStop }: StartStopControlProps) {
  return (
    <div role="group" aria-label="Simulator run state" className="flex items-center gap-2">
      <Button size="sm" variant="primary" disabled={running} onClick={onStart}>
        Start
      </Button>
      <Button size="sm" disabled={!running} onClick={onStop}>
        Stop
      </Button>
      <Badge tone={running ? 'accent' : 'neutral'} data-testid="sim-running" className="ml-auto">
        {running ? 'Running' : 'Stopped'}
      </Badge>
    </div>
  );
}
