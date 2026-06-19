interface Props {
  running: boolean;
  onStart: () => void;
  onStop: () => void;
}

export function StartStopControl({ running, onStart, onStop }: Props): JSX.Element {
  return (
    <div role="group" aria-label="Simulator run state">
      <button type="button" disabled={running} onClick={onStart}>
        Start
      </button>
      <button type="button" disabled={!running} onClick={onStop}>
        Stop
      </button>
      <span data-testid="sim-running">{running ? 'Running' : 'Stopped'}</span>
    </div>
  );
}
