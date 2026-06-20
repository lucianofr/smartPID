import { useState } from 'react';
import { useOpcuaStatus } from '../api/executive';
import { AppShell } from '../components/shell/AppShell';
import { ProjectImportDropzone } from '../features/projects/ProjectImportDropzone';
import { ProjectList } from '../features/projects/ProjectList';
import { useCreateProject } from '../features/projects/useProjects';

const NEW_LABEL = 'flex flex-col gap-1 uppercase tracking-[0.04em] text-text-secondary';

const NEW_INPUT = 'bg-surface text-text border border-border rounded-control px-3 py-2';

const NEW_BUTTON =
  'cursor-pointer bg-surface text-text border border-border rounded-control px-4 py-2 disabled:text-text-disabled disabled:cursor-not-allowed';

export function ProjectsPage(): JSX.Element {
  const opcQ = useOpcuaStatus();
  const opcDown = opcQ.data ? opcQ.data.state !== 'ONLINE' : false;
  const create = useCreateProject();
  const [name, setName] = useState('');
  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    try {
      await create.mutateAsync(name.trim());
      setName('');
    } catch {
      /* surfaced via create.isError */
    }
  }
  return (
    <AppShell opcDown={opcDown}>
      <div className="flex flex-col gap-6 max-w-[60rem]">
        <header>
          <h1 className="m-0 text-text" style={{ fontSize: 'var(--text-2xl)' }}>
            Projects
          </h1>
        </header>
        <form
          className="flex items-end gap-3 p-4 bg-surface-container border border-border rounded-card"
          onSubmit={handleCreate}
        >
          <label className={NEW_LABEL} style={{ fontSize: 'var(--text-xs)' }} htmlFor="new-name">
            New project name
            <input
              id="new-name"
              className={NEW_INPUT}
              style={{ fontSize: 'var(--text-sm)' }}
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </label>
          <button
            type="submit"
            className={NEW_BUTTON}
            style={{ fontSize: 'var(--text-sm)' }}
            disabled={create.isPending}
          >
            Create
          </button>
        </form>
        {create.isError && (
          <p role="alert" className="mt-2 text-alarm-critical" style={{ fontSize: 'var(--text-sm)' }}>
            {create.error instanceof Error ? create.error.message : 'Create failed'}
          </p>
        )}
        <ProjectImportDropzone />
        <ProjectList />
      </div>
    </AppShell>
  );
}
