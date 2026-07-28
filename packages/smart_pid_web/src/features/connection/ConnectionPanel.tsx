import { useState } from 'react';
import type { ApiError } from '@/api/client';
import type { ConnectionState } from '@/api/types';
import { useCan } from '@/auth/useCan';
import { Badge } from '@/components/Badge';
import { Button } from '@/components/Button';
import { Field, Input } from '@/components/Field';
import { useConnect, useDisconnect, useOpcuaStatus, useSaveEndpoint } from './useOpcua';

/**
 * OPC-UA session control (§9 `opcua.configure`, admin-only).
 *
 * ONLINE is the only healthy state; CONNECTING/RECONNECTING are transitional
 * and everything else is down. The badge tone is the ONLY color here — ISA-101
 * keeps chrome quiet and spends color on abnormality (§6.3).
 */

const STATE_TONE: Record<ConnectionState, 'neutral' | 'warn' | 'crit'> = {
  ONLINE: 'neutral',
  CONNECTING: 'warn',
  RECONNECTING: 'warn',
  OFFLINE: 'crit',
};

/** Turn the backend's own refusal into the operator's language (§11). */
export function connectionErrorMessage(error: ApiError): string {
  if (error.status === 422) return 'O endpoint deve começar com opc.tcp://';
  if (error.kind === 'forbidden') return 'Sua conta não pode alterar a conexão OPC-UA.';
  if (error.kind === 'network') return 'Sem resposta do servidor.';
  return 'Não foi possível alterar a conexão OPC-UA.';
}

export function ConnectionPanel() {
  const canConfigure = useCan('opcua.configure');
  const status = useOpcuaStatus(canConfigure);
  const save = useSaveEndpoint();
  const connect = useConnect();
  const disconnect = useDisconnect();
  const [typed, setTyped] = useState<string | null>(null);

  if (!canConfigure) {
    return (
      <p className="p-4 text-sm text-text-soft">
        Somente administradores podem configurar a conexão OPC-UA.
      </p>
    );
  }

  const stored = status.data?.endpoint ?? '';
  const endpoint = typed ?? stored;
  const state: ConnectionState = status.data?.state ?? 'OFFLINE';
  const busy = save.isPending || connect.isPending || disconnect.isPending;
  const failure = save.error ?? connect.error ?? disconnect.error ?? null;

  const handleConnect = async (): Promise<void> => {
    try {
      // PUT first: /opcua/connect only persists the endpoint for this attempt.
      if (endpoint !== '' && endpoint !== stored) await save.mutateAsync(endpoint);
      await connect.mutateAsync(endpoint === '' ? undefined : endpoint);
    } catch {
      /* surfaced by `failure` below */
    }
  };

  return (
    <section
      aria-label="Conexão OPC-UA"
      className="flex flex-col gap-3 border border-rule bg-surface p-3"
    >
      <div className="flex flex-wrap items-end gap-3">
        <Field
          label="Endpoint"
          htmlFor="opcua-endpoint"
          className="min-w-64 flex-1"
          description="Endereço do servidor OPC-UA (opc.tcp://host:porta)."
        >
          <Input
            id="opcua-endpoint"
            type="text"
            className="numeric"
            placeholder="opc.tcp://host:4840"
            aria-describedby="opcua-endpoint-desc"
            value={endpoint}
            onChange={(e) => setTyped(e.target.value)}
          />
        </Field>
        <Badge tone={STATE_TONE[state]} aria-live="polite" className="mb-2">
          {state}
        </Badge>
      </div>

      <div className="flex gap-2">
        <Button variant="primary" disabled={busy} onClick={() => void handleConnect()}>
          Connect
        </Button>
        <Button
          variant="secondary"
          disabled={busy || state !== 'ONLINE'}
          onClick={() => void disconnect.mutateAsync().catch(() => undefined)}
        >
          Disconnect
        </Button>
      </div>

      {failure !== null ? (
        <p role="alert" className="text-xs font-medium text-alarm-crit">
          {connectionErrorMessage(failure)}
        </p>
      ) : null}
    </section>
  );
}
