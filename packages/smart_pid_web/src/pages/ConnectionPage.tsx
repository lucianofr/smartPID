import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { apiGet } from '../api/client';
import type { OpcuaStatus } from '../api/executive';
import { AppShell } from '../components/shell/AppShell';
import { ConnectionPanel } from '../features/connection/ConnectionPanel';
import { TagBrowser } from '../features/connection/TagBrowser';
import type { OpcuaNode } from '../features/connection/opcuaApi';

export function ConnectionPage(): JSX.Element {
  const opcua = useQuery({
    queryKey: ['opcua-status'],
    queryFn: () => apiGet<OpcuaStatus>('/opcua/status'),
    refetchInterval: 5_000,
  });
  const opcDown = opcua.data ? opcua.data.state !== 'ONLINE' : false;
  const [selected, setSelected] = useState<OpcuaNode | null>(null);
  return (
    <AppShell opcDown={opcDown}>
      <div className="flex flex-col gap-4 max-w-[64rem]">
        <header>
          <h1 className="m-0 text-text" style={{ fontSize: 'var(--text-xl)' }}>
            OPC Connection
          </h1>
        </header>
        <ConnectionPanel />
        <TagBrowser onSelect={setSelected} />
        {selected && (
          <p className="m-0 text-text-secondary" style={{ fontSize: 'var(--text-sm)' }}>
            Selected: <code className="numeric text-text">{selected.node_id}</code>
          </p>
        )}
      </div>
    </AppShell>
  );
}
