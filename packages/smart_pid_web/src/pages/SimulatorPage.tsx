import { useId, useState } from 'react';
import { EmptyState } from '@/components/MissingState';
import { useControllers } from '@/features/dashboard/useControllers';
import { ClosedLoopDiagram } from '@/features/simulator/ClosedLoopDiagram';
import { SimulationModeBanner } from '@/features/simulator/SimulationModeBanner';
import { SimulatorControlPanel } from '@/features/simulator/SimulatorControlPanel';
import { TwinTrend } from '@/features/simulator/TwinTrend';
import { useSimulatorStatus } from '@/features/simulator/useSimulatorStatus';
import { NATIVE_SELECT_CLASS } from '@/features/simulator/PresetSelector';

/**
 * Digital-twin workspace (§6.9 `Sim`).
 *
 * NOT admin-route-guarded: twin SP/mode/CO are `loop.operate`, so an operator
 * has business here even though every configuration control is hidden from
 * them. The loop list comes from the twin snapshot when it is readable and
 * falls back to the controller roster when it is not — an operator who cannot
 * read /simulator/status can still watch the twin they are allowed to drive.
 */
export function SimulatorPage() {
  const loopSelectId = useId();
  const { data } = useSimulatorStatus();
  const controllers = useControllers();
  const [selectedId, setSelectedId] = useState<number | null>(null);

  const simIds = Object.keys(data?.controllers ?? {}).map(Number);
  const ids = (simIds.length > 0 ? simIds : (controllers.data ?? []).map((c) => c.id)).sort(
    (a, b) => a - b,
  );
  const controllerId = ids.find((id) => id === selectedId) ?? ids[0];
  const controller = data?.controllers[String(controllerId)];

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <SimulationModeBanner running={data?.running === true} />
      {controllerId === undefined ? (
        <EmptyState
          message="Nenhuma malha disponível para simulação."
          hint="Cadastre um controlador ou inicie o simulador."
        />
      ) : (
        <div className="grid min-h-0 flex-1 grid-cols-1 items-start gap-4 overflow-auto p-3 lg:grid-cols-[minmax(20rem,1fr)_2fr]">
          <div className="flex min-w-0 flex-col gap-3">
            {ids.length > 1 ? (
              <div className="flex flex-col gap-1">
                <label
                  htmlFor={loopSelectId}
                  className="text-2xs font-medium uppercase tracking-wider text-text-soft"
                >
                  Simulator loop
                </label>
                <select
                  id={loopSelectId}
                  className={NATIVE_SELECT_CLASS}
                  value={controllerId}
                  onChange={(e) => setSelectedId(Number(e.target.value))}
                >
                  {ids.map((id) => (
                    <option key={id} value={id}>
                      {id}
                    </option>
                  ))}
                </select>
              </div>
            ) : null}
            <SimulatorControlPanel controllerId={controllerId} />
          </div>
          <div className="flex min-w-0 flex-col gap-4">
            <TwinTrend key={controllerId} controllerId={controllerId} />
            <ClosedLoopDiagram controller={controller} />
          </div>
        </div>
      )}
    </div>
  );
}
