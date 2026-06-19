import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { apiGet } from '../api/client';
import type { OpcuaStatus } from '../api/executive';
import { AppShell } from '../components/shell/AppShell';
import { ConnectionPanel } from '../features/connection/ConnectionPanel';
import { TagBrowser } from '../features/connection/TagBrowser';
import type { OpcuaNode } from '../features/connection/opcuaApi';
import './ConnectionPage.css';

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
      <div className="connection-page">
        <header className="connection-page__header">
          <h1>OPC Connection</h1>
        </header>
        <ConnectionPanel />
        <TagBrowser onSelect={setSelected} />
        {selected && (
          <p className="connection-page__selected">
            Selected: <code className="numeric">{selected.node_id}</code>
          </p>
        )}
      </div>
    </AppShell>
  );
}
