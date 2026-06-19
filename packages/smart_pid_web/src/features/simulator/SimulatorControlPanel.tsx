import { useCallback, useEffect, useRef } from 'react';
import { PresetSelector } from './PresetSelector';
import { DynamicsSliders, type Dynamics } from './DynamicsSliders';
import { DisturbanceControls } from './DisturbanceControls';
import { TwinOutputModeControl } from './TwinOutputModeControl';
import { AutoToggles } from './AutoToggles';
import { StartStopControl } from './StartStopControl';
import { useSimulatorStatus } from './useSimulatorStatus';
import { useSimulatorMutations } from './useSimulatorMutations';
import type { ProcessPresetName, TwinMode } from './types';
import './SimulatorControlPanel.css';

interface Props {
  controllerId: number;
}

// DynamicsSliders fires onCommit on every onChange (each slider drag tick).
// Debounce trailing so a drag collapses to a single setParameters POST.
const PARAMS_DEBOUNCE_MS = 250;

export function SimulatorControlPanel({ controllerId }: Props): JSX.Element {
  const { data } = useSimulatorStatus();
  const m = useSimulatorMutations(controllerId);
  const c = data?.controllers?.[controllerId];

  const paramsTimer = useRef<ReturnType<typeof setTimeout>>();
  const commitParams = m.params.mutate;
  const debouncedCommitParams = useCallback(
    (d: Dynamics) => {
      if (paramsTimer.current) clearTimeout(paramsTimer.current);
      paramsTimer.current = setTimeout(() => commitParams(d), PARAMS_DEBOUNCE_MS);
    },
    [commitParams],
  );
  useEffect(() => () => clearTimeout(paramsTimer.current), []);

  if (!c) return <div role="status">Loading simulator…</div>;

  const disturbanceActive = Boolean(c.step_active || c.noise_active);
  const twinMode: TwinMode = c.pid_mode === 1 ? 'AUTO' : 'MAN';

  return (
    <section aria-label="Simulator controls" className="simulator-control-panel">
      <StartStopControl
        running={Boolean(data?.running)}
        onStart={() => m.start.mutate()}
        onStop={() => m.stop.mutate()}
      />
      <PresetSelector value={c.preset as ProcessPresetName} onChange={(p) => m.preset.mutate(p)} />
      <DynamicsSliders
        value={{ gain: c.gain, dead_time: c.dead_time, tau1: c.tau1, tau2: c.tau2 }}
        onCommit={debouncedCommitParams}
      />
      <DisturbanceControls
        active={disturbanceActive}
        onInject={(type, amplitude) => m.inject.mutate({ type, amplitude })}
        onRemove={() => m.clear.mutate()}
      />
      <TwinOutputModeControl
        co={c.co}
        mode={twinMode}
        onSetCo={(co) => m.co.mutate(co)}
        onSetMode={(mode) => m.mode.mutate(mode)}
      />
      <AutoToggles
        autoSp={c.auto_sp ?? null}
        autoDisturbance={c.auto_disturbance ?? null}
        onSetAutoSp={(b) => m.autoSp.mutate(b)}
        onSetAutoDisturbance={(b) => m.autoDist.mutate(b)}
      />
    </section>
  );
}
