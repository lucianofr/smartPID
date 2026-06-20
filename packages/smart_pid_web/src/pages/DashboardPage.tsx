import { useQuery } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { apiGet } from '../api/client';
import { toLimitsForm, type ControllerResponse } from '../api/controllers';
import { AppShell } from '../components/shell/AppShell';
import { ControllerCard, type ControllerSummary } from '../components/ControllerCard';
import { Dialog } from '../components/ui/Dialog';
import { Faceplate } from '../components/Faceplate';
import { AiPanel } from '../features/loop-config/AiPanel';
import { CardControls } from '../features/loop-config/CardControls';
import { LoopConfigDialog } from '../features/loop-config/LoopConfigDialog';
import type { ControllerMode } from '../features/loop-config/types';
import { useRealtime } from '../realtime/useRealtime';

interface OpcuaStatus { state: string; endpoint: string | null; }

// Mode comes live from the WS status frame; until the first frame arrives the loop is
// treated as out-of-service for the controls' MAN/AUTO gating.
const DEFAULT_MODE: ControllerMode = 'OOS';

function toSummary(c: ControllerResponse): ControllerSummary {
  return {
    id: c.id,
    name: c.name,
    description: c.description,
    pv_decimals: c.pv_decimals,
    pv_unit: c.pv_unit,
  };
}

export function DashboardPage() {
  const { lastStatus, onResync } = useRealtime();
  const [configId, setConfigId] = useState<number | null>(null);
  const [faceplateId, setFaceplateId] = useState<number | null>(null);

  const controllers = useQuery({
    queryKey: ['controllers'],
    queryFn: () => apiGet<ControllerResponse[]>('/controllers'),
  });
  const opcua = useQuery({
    queryKey: ['opcua-status'],
    queryFn: () => apiGet<OpcuaStatus>('/opcua/status'),
    refetchInterval: 5_000, // OPC status is POLLED via REST, not WS
  });

  // On WS reconnect, re-sync REST state (controllers + opcua; alarms/ai added by later fatias).
  useEffect(
    () =>
      onResync(() => {
        void controllers.refetch();
        void opcua.refetch();
      }),
    [onResync, controllers.refetch, opcua.refetch],
  );

  const opcDown = opcua.data ? opcua.data.state !== 'ONLINE' : false;
  const list = controllers.data ?? [];
  const selected = list.find((c) => c.id === configId) ?? null;
  const faceplateController = list.find((c) => c.id === faceplateId) ?? null;

  return (
    <AppShell opcDown={opcDown}>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--sp-3)' }}>
        {list.map((c) => {
          const status = lastStatus.get(c.id);
          const mode = (status?.mode as ControllerMode | undefined) ?? DEFAULT_MODE;
          return (
            <ControllerCard
              key={c.id}
              controller={toSummary(c)}
              status={status}
              onOpenConfig={() => setConfigId(c.id)}
              onOpenFaceplate={() => setFaceplateId(c.id)}
              controls={
                <>
                  <CardControls
                    controllerId={c.id}
                    mode={mode}
                    optimizationEnabled={c.optimization_enabled}
                    onOpenConfig={() => setConfigId(c.id)}
                  />
                  <AiPanel controllerId={c.id} />
                </>
              }
            />
          );
        })}
      </div>

      {selected ? (
        <LoopConfigDialog
          controllerId={selected.id}
          open
          onClose={() => setConfigId(null)}
          initial={{
            pid: selected.pid_params,
            pidStructure: selected.pid_structure,
            limits: toLimitsForm(selected),
            ai: selected.ai_config,
          }}
        />
      ) : null}

      {faceplateController ? (
        <Dialog open onClose={() => setFaceplateId(null)} title={`Faceplate ${faceplateController.name}`}>
          <Faceplate
            controllerId={faceplateController.id}
            tag={faceplateController.name}
            description={faceplateController.description}
            scale={{ euMin: 0, euMax: 100, unit: faceplateController.pv_unit }}
            decimals={faceplateController.pv_decimals}
          />
        </Dialog>
      ) : null}
    </AppShell>
  );
}
