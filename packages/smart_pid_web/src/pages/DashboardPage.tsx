import { useQuery } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { apiGet } from '../api/client';
import { toLimitsForm, type ControllerResponse } from '../api/controllers';
import { AppShell } from '../components/shell/AppShell';
import { ControllerCard, type ControllerSummary } from '../components/ControllerCard';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '../components/ui/dialog';
import { Faceplate } from '../components/Faceplate';
import { AiPanel } from '../features/loop-config/AiPanel';
import { CardControls } from '../features/loop-config/CardControls';
import { LoopConfigDialog } from '../features/loop-config/LoopConfigDialog';
import type { ControllerMode } from '../features/loop-config/types';
import { useRealtime } from '../realtime/useRealtime';
import { EmptyState, ErrorState, LoadingState } from '../components/MissingState';

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

  // §6a missing states: loading (static bars + aria-busy), error (diag + retry),
  // empty (explicit "no loops"). The loaded grid is unchanged below.
  let body: JSX.Element;
  if (controllers.isLoading) {
    body = <LoadingState testId="dashboard-loading" label="Loading loops…" />;
  } else if (controllers.isError) {
    body = (
      <ErrorState
        testId="dashboard-error"
        message="Failed to load loops."
        actionLabel="Retry"
        onAction={() => void controllers.refetch()}
      />
    );
  } else if (list.length === 0) {
    body = (
      <EmptyState
        testId="dashboard-empty"
        message="No loops configured."
        hint="Open or import a project to add control loops."
      />
    );
  } else {
    body = (
      // Responsive (Task 9.2 / §9): the card strip wraps at >=1024; below the 1024 token
      // breakpoint it reflows to a single column (`max-lg:flex-col`) so each card spans the row.
      <div className="flex flex-wrap gap-3 max-lg:flex-col">
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
    );
  }

  return (
    <AppShell opcDown={opcDown}>
      {body}

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
        <Dialog open onOpenChange={(next) => { if (!next) setFaceplateId(null); }}>
          {/* Responsive (Task 9.2 / §9): >=1024 the faceplate is the centered side-sheet dialog;
              below the 1024 token breakpoint it goes full-screen — pinned to all insets, no centering
              transform, full width/height, internal scroll. Only the faceplate dialog opts in; other
              dialogs keep the centered layout. */}
          <DialogContent className="max-lg:inset-0 max-lg:left-0 max-lg:top-0 max-lg:h-full max-lg:max-w-none max-lg:translate-x-0 max-lg:translate-y-0 max-lg:overflow-auto max-lg:rounded-none">
            <DialogHeader>
              <DialogTitle>Faceplate {faceplateController.name}</DialogTitle>
            </DialogHeader>
            <Faceplate
              controllerId={faceplateController.id}
              tag={faceplateController.name}
              description={faceplateController.description}
              scale={{ euMin: 0, euMax: 100, unit: faceplateController.pv_unit }}
              decimals={faceplateController.pv_decimals}
            />
          </DialogContent>
        </Dialog>
      ) : null}
    </AppShell>
  );
}
