import { useState } from 'react';
import { ApiError } from '@/api/client';
import { useCan } from '@/auth/useCan';
import { Button } from '@/components/Button';
import { Field, Input } from '@/components/Field';
import { ProjectImportDropzone } from '@/features/projects/ProjectImportDropzone';
import { ProjectList } from '@/features/projects/ProjectList';
import { projectErrorMessage, useCreateProject } from '@/features/projects/useProjects';

/**
 * Portable project management (`[cfg] › Projects`, admin-only).
 *
 * A rejected create KEEPS the typed name: the only 409 the backend raises here
 * is "a project with this name already exists", and the operator is about to
 * edit that name rather than retype it from scratch.
 */
export function ProjectsPage() {
  const canManage = useCan('projects.manage');
  const create = useCreateProject();
  const [name, setName] = useState('');
  const [failure, setFailure] = useState<string | null>(null);

  const handleCreate = async (): Promise<void> => {
    const trimmed = name.trim();
    if (trimmed === '') return;
    setFailure(null);
    try {
      await create.mutateAsync(trimmed);
      setName('');
    } catch (error) {
      setFailure(
        error instanceof ApiError
          ? projectErrorMessage(error, 'Não foi possível criar o projeto.')
          : 'Não foi possível criar o projeto.',
      );
    }
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-y-auto">
      <header className="shrink-0 border-b border-rule px-3 py-2">
        <h1 className="type-display text-lg text-text">Projetos</h1>
      </header>
      <div className="flex flex-col gap-4 p-3">
        {canManage ? (
          <form
            aria-label="Novo projeto"
            className="flex flex-wrap items-end gap-3 border border-rule bg-surface p-3"
            noValidate
            onSubmit={(event) => {
              event.preventDefault();
              void handleCreate();
            }}
          >
            <Field label="New project name" htmlFor="project-new-name" className="min-w-56 flex-1">
              <Input
                id="project-new-name"
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </Field>
            <Button type="submit" variant="primary" className="mb-0" disabled={create.isPending}>
              Create
            </Button>
          </form>
        ) : null}
        {failure !== null ? (
          <p role="alert" className="text-xs font-medium text-alarm-crit">
            {failure}
          </p>
        ) : null}
        <ProjectImportDropzone />
        <ProjectList />
      </div>
    </div>
  );
}
