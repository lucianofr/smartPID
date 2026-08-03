import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react';
import { Button } from '@/components/Button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/Dialog';
import { EmptyState, LoadingState } from '@/components/MissingState';
import { useCan } from '@/auth/useCan';
import type { StatusData } from '@/lib/envelope';
import { useRealtime } from '@/realtime/useRealtime';
import { AutoToggles } from './AutoToggles';
import { DisturbanceControls } from './DisturbanceControls';
import { DynamicsSliders } from './DynamicsSliders';
import { PIDSettings } from './PIDSettings';
import { PresetSelector } from './PresetSelector';
import { StartStopControl } from './StartStopControl';
import { TwinOutputModeControl } from './TwinOutputModeControl';
import { useSimulatorMutations } from './useSimulatorMutations';
import { useSimulatorStatus } from './useSimulatorStatus';
import { PID_MODE_AUTO, type Dynamics, type ProcessPresetName, type TwinMode } from './types';

export interface SimulatorControlPanelProps {
  controllerId: number;
}

/** One PUT per drag: DynamicsSliders commits on every tick of the gesture. */
const PARAMS_DEBOUNCE_MS = 250;

/**
 * The Sim page's control column.
 *
 * Two regions with different permissions: everything that reshapes the model —
 * run state, preset, dynamics, disturbance, automation — needs
 * `simulator.configure`, while twin SP/mode/CO is `loop.operate` and therefore
 * stays available to a plain operator. That operator cannot read
 * `/simulator/status` at all, so the operate region falls back to the live
 * STATUS frame for its current values.
 */
export function SimulatorControlPanel({ controllerId }: SimulatorControlPanelProps) {
  const canConfigure = useCan('simulator.configure');
  const { data, restricted, isPending } = useSimulatorStatus();
  const live = useRealtime<StatusData>(controllerId, 'status').last?.data;
  const mutations = useSimulatorMutations(controllerId);

  const [confirmDeleteOpen, setConfirmDeleteOpen] = useState(false);
  const paramsTimer = useRef<number>();
  const commitParams = mutations.parameters.mutate;
  const debouncedCommitParams = useCallback(
    (next: Dynamics) => {
      window.clearTimeout(paramsTimer.current);
      paramsTimer.current = window.setTimeout(() => commitParams(next), PARAMS_DEBOUNCE_MS);
    },
    [commitParams],
  );
  useEffect(() => () => window.clearTimeout(paramsTimer.current), []);

  const controller = data?.controllers[String(controllerId)];

  let configRegion: ReactNode;
  if (!canConfigure || restricted) {
    configRegion = (
      <EmptyState
        message="Simulador gerenciado pelo administrador"
        hint="Você pode operar SP, modo e CO do gêmeo digital, mas não configurá-lo."
      />
    );
  } else if (isPending) {
    configRegion = <LoadingState label="Carregando simulador…" bars={3} />;
  } else if (data?.enabled === false) {
    configRegion = (
      <EmptyState
        message="Simulador desabilitado no servidor"
        hint="Defina SPID_SIMULATOR_ENABLED=true e reinicie o serviço."
      />
    );
  } else {
    configRegion = (
      <>
        <StartStopControl
          running={data?.running === true}
          onStart={() => mutations.start.mutate()}
          onStop={() => mutations.stop.mutate()}
        >
          <div
            role="group"
            aria-label="Simulator loop lifecycle"
            className="flex items-center gap-2"
          >
            <Button
              size="sm"
              disabled={mutations.createLoop.isPending}
              onClick={() => mutations.createLoop.mutate()}
            >
              Novo loop de simulação
            </Button>
            <Button
              size="sm"
              variant="destructive"
              disabled={mutations.deleteLoop.isPending || controller === undefined}
              onClick={() => setConfirmDeleteOpen(true)}
            >
              Apagar loop atual
            </Button>
          </div>
        </StartStopControl>
        {controller ? (
          <>
            <PresetSelector
              value={controller.preset as ProcessPresetName}
              onChange={(preset) => mutations.preset.mutate(preset)}
            />
            <DynamicsSliders
              value={{
                gain: controller.gain,
                dead_time: controller.dead_time,
                tau1: controller.tau1,
                tau2: controller.tau2,
              }}
              onCommit={debouncedCommitParams}
            />
            <PIDSettings
              key={controllerId}
              kp={controller.pid_kp}
              ti={controller.pid_ti}
              td={controller.pid_td}
              onApplyParams={(p) => mutations.pidParams.mutate(p)}
            />
            <DisturbanceControls
              active={controller.step_active || controller.noise_active}
              autoDisturbanceEnabled={controller.auto_disturbance?.enabled ?? false}
              onInject={(type, amplitude) => mutations.inject.mutate({ type, amplitude })}
              onRemove={() => mutations.clear.mutate()}
            />
            <AutoToggles
              autoSp={controller.auto_sp ?? null}
              autoDisturbance={controller.auto_disturbance ?? null}
              onSetAutoSp={(body) => mutations.autoSp.mutate(body)}
              onSetAutoDisturbance={(body) => mutations.autoDisturbance.mutate(body)}
            />
          </>
        ) : (
          <EmptyState
            message="Nenhuma malha no gêmeo digital."
            hint="Inicie o simulador para instanciar o modelo de processo."
          />
        )}
      </>
    );
  }

  // REST is authoritative when readable; a restricted operator still reaches
  // the twin through the realtime frame it IS allowed to receive. The wire
  // reports mode two ways: an int on the snapshot, the loop's string on a frame.
  const twin: { sp: number; co: number; mode: TwinMode } | null = controller
    ? {
        sp: controller.sp,
        co: controller.co,
        mode: controller.pid_mode === PID_MODE_AUTO ? 'AUTO' : 'MAN',
      }
    : live
      ? { sp: live.sp.value, co: live.co.value, mode: live.mode === 'AUTO' ? 'AUTO' : 'MAN' }
      : null;

  return (
    <section aria-label="Simulator controls" className="flex flex-col gap-1">
      {configRegion}
      {twin === null ? null : (
        <TwinOutputModeControl
          key={controllerId}
          sp={twin.sp}
          co={twin.co}
          mode={twin.mode}
          onSetSp={(sp) => mutations.sp.mutate(sp)}
          onSetCo={(co) => mutations.co.mutate(co)}
          onSetMode={(mode) => mutations.mode.mutate(mode)}
        />
      )}
      {canConfigure ? (
        <Dialog
          open={confirmDeleteOpen}
          onOpenChange={(next) => {
            if (!next) setConfirmDeleteOpen(false);
          }}
        >
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Apagar loop de simulação #{controllerId}</DialogTitle>
              <DialogDescription>
                O modelo de processo desta malha sai do gêmeo digital. A ação não pode ser
                desfeita.
              </DialogDescription>
            </DialogHeader>
            <DialogFooter>
              <Button variant="secondary" onClick={() => setConfirmDeleteOpen(false)}>
                Cancelar
              </Button>
              <Button
                variant="destructive"
                disabled={mutations.deleteLoop.isPending}
                onClick={() =>
                  mutations.deleteLoop.mutate(undefined, {
                    onSuccess: () => setConfirmDeleteOpen(false),
                  })
                }
              >
                Apagar
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      ) : null}
    </section>
  );
}
