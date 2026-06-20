import { useState } from 'react';
import { useOpcuaStatus } from '../../api/executive';
import { useConnect, useDisconnect, useSaveEndpoint } from './useOpcua';

/**
 * OPC-UA connection panel (Task 8.3). Inline/CSS migrated to flat ISA-101 token
 * utilities. ONLINE is the only healthy state; CONNECTING/RECONNECTING are
 * transitional (warning); everything else reads as down/critical. The state dot
 * color is data-driven, so it stays an inline state/alarm token var.
 */
function dotColor(state: string): string {
  if (state === 'ONLINE') return 'var(--state-running)';
  if (state === 'CONNECTING' || state === 'RECONNECTING') return 'var(--alarm-warning)';
  return 'var(--alarm-critical)';
}

const INPUT =
  'numeric flex-[1_1_18rem] min-w-[12rem] bg-surface text-text border border-border-strong rounded-control px-3 py-2 ' +
  'focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-[var(--state-running)]';

const BUTTON =
  'cursor-pointer bg-surface text-text border border-border-strong rounded-control px-4 py-2 ' +
  'hover:bg-surface-container-high disabled:opacity-50 disabled:cursor-not-allowed';

const BUTTON_PRIMARY =
  'cursor-pointer bg-surface text-[var(--state-running)] border border-[var(--state-running)] rounded-control px-4 py-2 ' +
  'hover:bg-surface-container-high disabled:opacity-50 disabled:cursor-not-allowed';

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
    <section
      className="flex flex-col gap-3 border border-border rounded-card bg-surface-container p-4"
      aria-label="OPC-UA connection"
    >
      <div className="flex items-center gap-3 flex-wrap">
        <label
          className="uppercase tracking-[0.04em] text-text-secondary"
          style={{ fontSize: 'var(--text-xs)' }}
          htmlFor="opc-endpoint"
        >
          Endpoint
        </label>
        <input
          id="opc-endpoint"
          className={INPUT}
          style={{ fontSize: 'var(--text-sm)' }}
          type="text"
          placeholder="opc.tcp://host:4840"
          value={value}
          onChange={(e) => setEndpoint(e.target.value)}
        />
        <span
          className="inline-flex items-center gap-2 numeric text-text-secondary"
          style={{ fontSize: 'var(--text-xs)' }}
          aria-live="polite"
        >
          <span
            aria-hidden
            className="h-[9px] w-[9px] rounded-pill"
            style={{ backgroundColor: dotColor(state) }}
          />
          {state}
        </span>
      </div>
      <div className="flex gap-2">
        <button
          type="button"
          className={BUTTON_PRIMARY}
          style={{ fontSize: 'var(--text-sm)' }}
          onClick={handleConnect}
          disabled={connect.isPending}
        >
          Connect
        </button>
        <button
          type="button"
          className={BUTTON}
          style={{ fontSize: 'var(--text-sm)' }}
          onClick={() => disconnect.mutateAsync()}
          disabled={!online || disconnect.isPending}
        >
          Disconnect
        </button>
      </div>
    </section>
  );
}
