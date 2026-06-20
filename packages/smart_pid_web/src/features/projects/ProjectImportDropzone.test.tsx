import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

const importMut = vi.fn().mockResolvedValue({ name: 'imp', path: 'x', controller_count: 1 });
vi.mock('./useProjects', () => ({
  useImportProject: () => ({ mutateAsync: importMut, isPending: false }),
}));

import { ProjectImportDropzone } from './ProjectImportDropzone';

describe('ProjectImportDropzone', () => {
  it('imports a selected .spid file', async () => {
    render(<ProjectImportDropzone />);
    const file = new File([new Uint8Array([1, 2])], 'imp.spid');
    const input = screen.getByLabelText(/import .spid/i) as HTMLInputElement;
    fireEvent.change(input, { target: { files: [file] } });
    await waitFor(() => expect(importMut).toHaveBeenCalled());
    expect(importMut.mock.calls[0][0].file.name).toBe('imp.spid');
  });
});
