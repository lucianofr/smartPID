import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

vi.mock('./useOpcua', () => ({
  useBrowse: () => ({
    data: {
      parent_node_id: 'i=85',
      children: [
        { node_id: 'ns=2;s=FT-101', display_name: 'FT-101', node_class: 'Variable' },
        { node_id: 'ns=2;s=Folder', display_name: 'Folder', node_class: 'Object' },
      ],
    },
    isLoading: false,
  }),
  useSearch: () => ({ data: { query: '', results: [] }, isLoading: false }),
}));

import { TagBrowser } from './TagBrowser';

describe('TagBrowser', () => {
  it('renders browse children as a tree with a search box', () => {
    render(<TagBrowser onSelect={vi.fn()} />);
    expect(screen.getByRole('searchbox')).toBeInTheDocument();
    expect(screen.getByText('FT-101')).toBeInTheDocument();
    expect(screen.getByText('Folder')).toBeInTheDocument();
  });
});
