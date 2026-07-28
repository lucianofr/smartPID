import { useEffect, useState } from 'react';
import type { OpcuaNode } from '@/api/types';
import { useCan } from '@/auth/useCan';
import { Button } from '@/components/Button';
import { EmptyState, ErrorState, LoadingState } from '@/components/MissingState';
import { VirtualList } from '@/components/VirtualList';
import { cn } from '@/lib/utils';
import { ROOT_NODE_ID, useBrowse, useTagSearch } from './useOpcua';

/**
 * Searchable OPC-UA address space (§9 `opcua.configure`, admin-only).
 *
 * Empty box = browse the address space from the Objects folder; anything typed
 * = server-side search. The query is debounced because each keystroke is a
 * round trip to the PLC's address space, and the list is windowed because a
 * plant namespace is a flood.
 *
 * A folder is a waypoint, never an answer: clicking a non-Variable node walks
 * INTO it instead of reporting it as the selection. That is what keeps this
 * usable as a NodeID picker — an Object id in a `node_id_pv` binding is a
 * subscription the adapter can never fulfil.
 */

const SEARCH_DEBOUNCE_MS = 250;
const LIST_HEIGHT_PX = 320;
const ROW_HEIGHT_PX = 36;

/** Standard OPC-UA entry point; the trail is always rooted here. */
const OBJECTS_ROOT: OpcuaNode = {
  node_id: ROOT_NODE_ID,
  display_name: 'Objects',
  node_class: 'Object',
};

export interface TagBrowserProps {
  onSelect: (node: OpcuaNode) => void;
  /**
   * Show each node's NodeID next to its name. A plant namespace repeats
   * `PV` once per loop, so a picker MUST show the id it is about to bind;
   * the connection page's read-only tree does not need the noise.
   */
  showNodeId?: boolean;
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

export function TagBrowser({ onSelect, showNodeId = false }: TagBrowserProps) {
  const canBrowse = useCan('opcua.configure');
  const [query, setQuery] = useState('');
  const [settled, setSettled] = useState('');
  const [path, setPath] = useState<readonly OpcuaNode[]>([]);

  useEffect(() => {
    const timer = setTimeout(() => setSettled(query.trim()), SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [query]);

  const searching = settled.length > 0;
  const trail: readonly OpcuaNode[] = [OBJECTS_ROOT, ...path];
  const current = trail[trail.length - 1];
  const browse = useBrowse(current.node_id, canBrowse && !searching);
  const search = useTagSearch(settled, canBrowse);
  const active = searching ? search : browse;

  /** Descending out of a search result drops the query — the tree is the view now. */
  const enter = (node: OpcuaNode): void => {
    setQuery('');
    setSettled('');
    setPath((prev) => [...prev, node]);
  };

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

      {searching ? null : (
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            disabled={path.length === 0}
            onClick={() => setPath((prev) => prev.slice(0, -1))}
          >
            Voltar
          </Button>
          <p data-testid="tag-browser-path" className="truncate text-xs text-text-soft">
            {trail.map((node) => node.display_name).join(' › ')}
          </p>
        </div>
      )}

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
              onClick={() => (node.node_class === 'Variable' ? onSelect(node) : enter(node))}
            >
              <NodeGlyph isVariable={node.node_class === 'Variable'} />
              <span className="truncate">{node.display_name}</span>
              {showNodeId ? (
                <span className="numeric ml-auto shrink-0 text-2xs text-text-soft">
                  {node.node_id}
                </span>
              ) : null}
            </button>
          )}
        />
      )}
    </section>
  );
}
