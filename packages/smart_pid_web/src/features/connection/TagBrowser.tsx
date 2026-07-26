import { useEffect, useState } from 'react';
import type { OpcuaNode } from '@/api/types';
import { useCan } from '@/auth/useCan';
import { EmptyState, ErrorState, LoadingState } from '@/components/MissingState';
import { VirtualList } from '@/components/VirtualList';
import { cn } from '@/lib/utils';
import { ROOT_NODE_ID, useBrowse, useTagSearch } from './useOpcua';

/**
 * Searchable OPC-UA address space (§9 `opcua.configure`, admin-only).
 *
 * Empty box = browse the Objects folder; anything typed = server-side search.
 * The query is debounced because each keystroke is a round trip to the PLC's
 * address space, and the list is windowed because a plant namespace is a flood.
 */

const SEARCH_DEBOUNCE_MS = 250;
const LIST_HEIGHT_PX = 320;
const ROW_HEIGHT_PX = 36;

export interface TagBrowserProps {
  onSelect: (node: OpcuaNode) => void;
}

/** Shape AND color separate a folder from a tag (ISA-101 §6: never color alone). */
function NodeGlyph({ isVariable }: { isVariable: boolean }) {
  return (
    <span
      aria-hidden="true"
      className={cn('h-2 w-2 shrink-0', isVariable ? 'rotate-45 bg-accent' : 'bg-text-soft')}
    />
  );
}

export function TagBrowser({ onSelect }: TagBrowserProps) {
  const canBrowse = useCan('opcua.configure');
  const [query, setQuery] = useState('');
  const [settled, setSettled] = useState('');

  useEffect(() => {
    const timer = setTimeout(() => setSettled(query.trim()), SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [query]);

  const searching = settled.length > 0;
  const browse = useBrowse(ROOT_NODE_ID, canBrowse && !searching);
  const search = useTagSearch(settled, canBrowse);
  const active = searching ? search : browse;

  if (!canBrowse) {
    return (
      <p className="p-4 text-sm text-text-soft">
        Somente administradores podem navegar as tags OPC-UA.
      </p>
    );
  }

  const nodes: readonly OpcuaNode[] = searching
    ? (search.data?.results ?? [])
    : (browse.data?.children ?? []);

  return (
    <section
      aria-label="Navegador de tags OPC-UA"
      className="flex min-h-0 flex-col gap-3 border border-rule bg-surface p-3"
    >
      <input
        type="search"
        aria-label="Buscar tags"
        placeholder="Buscar tags…"
        className={cn(
          'min-h-11 w-full rounded-control border border-rule-strong bg-surface-sunk px-3 py-2',
          'text-sm text-text placeholder:text-text-disabled outline-none',
          'focus-visible:ring-2 focus-visible:ring-focus-ring',
        )}
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />

      {active.isPending ? (
        <LoadingState label="Lendo o espaço de endereços…" bars={3} />
      ) : active.isError ? (
        <ErrorState
          message="Não foi possível ler o espaço de endereços do servidor OPC-UA."
          onRetry={() => void active.refetch()}
        />
      ) : nodes.length === 0 ? (
        <EmptyState
          message={searching ? 'Nenhuma tag corresponde à busca.' : 'Nenhum nó neste nível.'}
          hint={searching ? undefined : 'Conecte-se ao servidor para navegar as tags.'}
        />
      ) : (
        <VirtualList
          items={nodes}
          height={LIST_HEIGHT_PX}
          estimateSize={ROW_HEIGHT_PX}
          aria-label="Tags OPC-UA"
          getKey={(node) => node.node_id}
          renderItem={(node) => (
            <button
              type="button"
              className={cn(
                'flex min-h-9 w-full items-center gap-2 rounded-control px-2 text-left text-sm text-text',
                'outline-none hover:bg-surface-sunk focus-visible:ring-2 focus-visible:ring-focus-ring',
              )}
              onClick={() => onSelect(node)}
            >
              <NodeGlyph isVariable={node.node_class === 'Variable'} />
              <span className="truncate">{node.display_name}</span>
            </button>
          )}
        />
      )}
    </section>
  );
}
