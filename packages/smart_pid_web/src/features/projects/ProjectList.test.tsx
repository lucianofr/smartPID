import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

const remove = vi.fn().mockResolvedValue(undefined);
const open = vi.fn().mockResolvedValue({ name: 'p1', path: 'x', controller_count: 0 });
vi.mock('./useProjects', () => ({
  useProjectList: () => ({
    data: { projects: [{ name: 'p1', controller_count: 3, size_bytes: 2048 }] },
    isLoading: false,
  }),
  useDeleteProject: () => ({ mutateAsync: remove, isPending: false }),
  useOpenProject: () => ({ mutateAsync: open, isPending: false }),
}));
vi.mock('../settings/useSettings', () => ({
  useSettings: () => ({ preferences: { confirmDestructive: false } }),
}));

import { ProjectList } from './ProjectList';

describe('ProjectList', () => {
  it('lists projects with loop count and size', () => {
    render(<ProjectList />);
    expect(screen.getByText('p1')).toBeInTheDocument();
    expect(screen.getByText(/3/)).toBeInTheDocument();
  });

  it('deletes a project (no confirm when confirmDestructive is off)', async () => {
    render(<ProjectList />);
    fireEvent.click(screen.getByRole('button', { name: /delete/i }));
    expect(remove).toHaveBeenCalledWith('p1');
  });

  it('opens a project', async () => {
    render(<ProjectList />);
    fireEvent.click(screen.getByRole('button', { name: /^open$/i }));
    expect(open).toHaveBeenCalledWith('p1');
  });
});
