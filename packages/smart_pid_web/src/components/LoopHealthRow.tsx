export type LoopHealth = 'running' | 'stopped' | 'error';
export interface LoopHealthRowProps {
  name: string;
  health: LoopHealth;
  opc: 'OFFLINE' | 'CONNECTING' | 'ONLINE' | 'RECONNECTING';
  mode: string;
}

export function LoopHealthRow({ name, health, opc, mode }: LoopHealthRowProps) {
  return (
    <div data-testid={`health-${name}`} data-health={health} data-opc={opc}>
      <span>{name}</span>
      <span>{mode}</span>
      <span data-testid={`health-${name}-state`}>{health}</span>
      <span data-testid={`health-${name}-opc`}>{opc}</span>
    </div>
  );
}
