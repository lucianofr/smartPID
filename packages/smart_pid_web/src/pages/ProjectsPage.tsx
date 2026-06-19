import { useState } from 'react';
import { useOpcuaStatus } from '../api/executive';
import { AppShell } from '../components/shell/AppShell';
import { ProjectImportDropzone } from '../features/projects/ProjectImportDropzone';
import { ProjectList } from '../features/projects/ProjectList';
import { useCreateProject } from '../features/projects/useProjects';
import './ProjectsPage.css';

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
      <div className="projects-page">
        <header className="projects-page__header">
          <h1>Projects</h1>
        </header>
        <form className="projects-page__new" onSubmit={handleCreate}>
          <label htmlFor="new-name">New project name</label>
          <input id="new-name" value={name} onChange={(e) => setName(e.target.value)} />
          <button type="submit" disabled={create.isPending}>
            Create
          </button>
        </form>
        {create.isError && (
          <p role="alert" className="projects-page__error">
            {create.error instanceof Error ? create.error.message : 'Create failed'}
          </p>
        )}
        <ProjectImportDropzone />
        <ProjectList />
      </div>
    </AppShell>
  );
}
