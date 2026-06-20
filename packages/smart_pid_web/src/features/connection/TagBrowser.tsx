import { useState } from 'react';
import type { OpcuaNode } from './opcuaApi';
import { useBrowse, useSearch } from './useOpcua';
import './TagBrowser.css';

const ROOT_NODE = 'i=85'; // OPC-UA Objects folder

function nodeIcon(nodeClass: string): string {
  return nodeClass === 'Variable' ? 'tag' : 'folder';
}

interface TagBrowserProps {
  onSelect: (node: OpcuaNode) => void;
}

export function TagBrowser({ onSelect }: TagBrowserProps) {
  const [query, setQuery] = useState('');
  const browse = useBrowse(query ? null : ROOT_NODE);
  const search = useSearch(query);

  const nodes: OpcuaNode[] = query ? (search.data?.results ?? []) : (browse.data?.children ?? []);

  return (
    <div className="tag-browser" aria-label="OPC-UA tag browser">
      <input
        type="search"
        className="tag-browser__search"
        placeholder="Search tags..."
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />
      <ul className="tag-browser__tree">
        {nodes.map((n) => (
          <li
            key={n.node_id}
            className="tag-browser__node"
            data-icon={nodeIcon(n.node_class)}
          >
            <button
              type="button"
              className="tag-browser__node-btn"
              onClick={() => onSelect(n)}
            >
              {n.display_name}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
