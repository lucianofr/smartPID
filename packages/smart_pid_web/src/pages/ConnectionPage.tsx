import { useState } from 'react';
import type { OpcuaNode } from '@/api/types';
import { ConnectionPanel } from '@/features/connection/ConnectionPanel';
import { TagBrowser } from '@/features/connection/TagBrowser';

/**
 * OPC-UA connection workspace (`[cfg] › Connection`, admin-only).
 *
 * The selected node is echoed rather than acted on: tag BINDING lives in the
 * loop configuration dialog (phase 5) — this page only tells the engineer which
 * node id to paste there.
 */
export function ConnectionPage() {
  const [selected, setSelected] = useState<OpcuaNode | null>(null);

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-y-auto">
      <header className="shrink-0 border-b border-rule px-3 py-2">
        <h1 className="type-display text-lg text-text">Conexão OPC-UA</h1>
      </header>
      <div className="flex flex-col gap-3 p-3">
        <ConnectionPanel />
        <TagBrowser onSelect={setSelected} />
        {selected !== null ? (
          <p className="text-sm text-text-soft">
            Nó selecionado: <code className="numeric text-text">{selected.node_id}</code>
          </p>
        ) : null}
      </div>
    </div>
  );
}
