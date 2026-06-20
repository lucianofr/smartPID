import { useState } from 'react';
import type { OpcuaNode } from './opcuaApi';
import { useBrowse, useSearch } from './useOpcua';

const ROOT_NODE = 'i=85'; // OPC-UA Objects folder

function nodeIcon(nodeClass: string): string {
  return nodeClass === 'Variable' ? 'tag' : 'folder';
}

interface TagBrowserProps {
  onSelect: (node: OpcuaNode) => void;
}

const SEARCH =
  'bg-surface text-text border border-border-strong rounded-control px-3 py-2 ' +
  'focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-[var(--state-running)]';

const NODE_BUTTON =
  'flex items-center gap-2 w-full text-left text-text bg-transparent border-0 rounded-control px-2 py-1 cursor-pointer ' +
  'hover:bg-surface-container-high focus-visible:outline-2 focus-visible:-outline-offset-1 focus-visible:outline-[var(--state-running)]';

/**
 * Geometric node glyph (Task 8.3): folder = filled square (--text-secondary),
 * variable/tag = diamond (--state-running). Shape AND color distinguish the two
 * (ISA-101 §6), driven by the node class so it stays inline.
 */
function NodeGlyph({ icon }: { icon: string }) {
  const isTag = icon === 'tag';
  return (
    <span
      aria-hidden
      className="flex-[0_0_auto] h-[9px] w-[9px]"
      style={{
        backgroundColor: isTag ? 'var(--state-running)' : 'var(--text-secondary)',
        clipPath: isTag ? 'polygon(50% 0, 100% 50%, 50% 100%, 0 50%)' : undefined,
      }}
    />
  );
}

export function TagBrowser({ onSelect }: TagBrowserProps) {
  const [query, setQuery] = useState('');
  const browse = useBrowse(query ? null : ROOT_NODE);
  const search = useSearch(query);

  const nodes: OpcuaNode[] = query ? (search.data?.results ?? []) : (browse.data?.children ?? []);

  return (
    <div
      className="flex flex-col gap-3 border border-border rounded-card bg-surface-container p-4 min-h-0"
      aria-label="OPC-UA tag browser"
    >
      <input
        type="search"
        className={SEARCH}
        style={{ fontSize: 'var(--text-sm)' }}
        placeholder="Search tags..."
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />
      <ul className="list-none m-0 p-0 flex flex-col overflow-auto min-h-0">
        {nodes.map((n) => {
          const icon = nodeIcon(n.node_class);
          return (
            <li key={n.node_id} className="flex items-center" data-icon={icon}>
              <button
                type="button"
                className={NODE_BUTTON}
                style={{ fontSize: 'var(--text-sm)' }}
                onClick={() => onSelect(n)}
              >
                <NodeGlyph icon={icon} />
                {n.display_name}
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
