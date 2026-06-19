import { useState } from 'react';
import { useOpcuaStatus } from '../../api/executive';
import { useConnect, useDisconnect, useSaveEndpoint } from './useOpcua';
import './ConnectionPanel.css';

/**
 * Maps an OPC-UA connection state to the dot modifier class. ONLINE is the only
 * healthy state; CONNECTING/RECONNECTING are transitional (warning); everything
 * else (OFFLINE, ERROR, ...) reads as down/critical.
 */
function dotModifier(state: string): string {
  if (state === 'ONLINE') return 'connection-panel__dot--online';
  if (state === 'CONNECTING' || state === 'RECONNECTING') return 'connection-panel__dot--pending';
  return 'connection-panel__dot--offline';
}

export function ConnectionPanel() {
  const status = useOpcuaStatus();
  const save = useSaveEndpoint();
  const connect = useConnect();
  const disconnect = useDisconnect();
  const [endpoint, setEndpoint] = useState('');

  const current = status.data?.endpoint ?? '';
  const value = endpoint || current;
  const state = status.data?.state ?? 'OFFLINE';
  const online = state === 'ONLINE';

  async function handleConnect() {
    if (value && value !== current) await save.mutateAsync(value);
    await connect.mutateAsync(value || undefined);
  }

  return (
    <section className="connection-panel" aria-label="OPC-UA connection">
      <div className="connection-panel__row">
        <label className="connection-panel__label" htmlFor="opc-endpoint">
          Endpoint
        </label>
        <input
          id="opc-endpoint"
          className="connection-panel__input"
          type="text"
          placeholder="opc.tcp://host:4840"
          value={value}
          onChange={(e) => setEndpoint(e.target.value)}
        />
        <span className="connection-panel__state" aria-live="polite">
          <span aria-hidden className={`connection-panel__dot ${dotModifier(state)}`} />
          {state}
        </span>
      </div>
      <div className="connection-panel__actions">
        <button
          type="button"
          className="connection-panel__btn connection-panel__btn--primary"
          onClick={handleConnect}
          disabled={connect.isPending}
        >
          Connect
        </button>
        <button
          type="button"
          className="connection-panel__btn"
          onClick={() => disconnect.mutateAsync()}
          disabled={!online || disconnect.isPending}
        >
          Disconnect
        </button>
      </div>
    </section>
  );
}
