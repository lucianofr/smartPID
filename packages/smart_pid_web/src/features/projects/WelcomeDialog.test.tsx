import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

const open = vi.fn().mockResolvedValue({ name: 'p1', path: 'x', controller_count: 0 });
vi.mock('./useProjects', () => ({
  useProjectList: () => ({
    data: { projects: [{ name: 'p1', controller_count: 2, size_bytes: 1024 }] },
    isLoading: false,
  }),
  useOpenProject: () => ({ mutateAsync: open, isPending: false }),
}));

import { WelcomeDialog } from './WelcomeDialog';

function renderDialog(open: boolean, onDismiss = vi.fn()) {
  return render(
    <MemoryRouter>
      <WelcomeDialog open={open} onDismiss={onDismiss} />
    </MemoryRouter>,
  );
}

describe('WelcomeDialog', () => {
  it('renders backend projects when open', () => {
    renderDialog(true);
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(screen.getByText('p1')).toBeInTheDocument();
  });
  it('renders nothing when closed', () => {
    const { container } = renderDialog(false);
    expect(container).toBeEmptyDOMElement();
  });
  it('opens a project then dismisses', () => {
    renderDialog(true);
    fireEvent.click(screen.getByRole('button', { name: /^open$/i }));
    expect(open).toHaveBeenCalledWith('p1');
  });
});
