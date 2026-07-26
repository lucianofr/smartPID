import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { endpoints } from '@/api/endpoints';
import { ApiError } from '@/api/client';
import { useCan } from '@/auth/useCan';
import { Button } from '@/components/Button';
import { EmptyState, ErrorState, LoadingState } from '@/components/MissingState';
import { usePreferences } from '@/features/settings/useSettings';
import { cn } from '@/lib/utils';
import { projectErrorMessage, useDeleteProject, useOpenProject, useProjectList } from './useProjects';

/**
 * Project roster with the per-row lifecycle (§9 `projects.manage`, admin-only).
 *
 * Opening a project swaps the whole plant database underneath the session, so
 * the operator is returned to the dashboard rather than left staring at a table
 * that now describes a different plant.
 */

const TH = 'border-b border-rule px-3 py-2 text-left text-2xs uppercase tracking-wider text-text-soft';
const TD = 'border-b border-rule px-3 py-2 align-middle';

export function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function ProjectList() {
  const canManage = useCan('projects.manage');
  const list = useProjectList(canManage);
  const open = useOpenProject();
  const remove = useDeleteProject();
  const { confirmDestructive } = usePreferences();
  const navigate = useNavigate();
  const [failure, setFailure] = useState<string | null>(null);

  if (!canManage) {
    return (
      <p className="p-4 text-sm text-text-soft">
        Somente administradores podem gerenciar projetos.
      </p>
    );
  }
  if (list.isPending) return <LoadingState label="Carregando projetos…" />;
  if (list.isError) {
    return (
      <ErrorState
        message="Não foi possível carregar a lista de projetos."
        onRetry={() => void list.refetch()}
      />
    );
  }

  const projects = list.data.projects;
  if (projects.length === 0) {
    return (
      <EmptyState
        message="Nenhum projeto no servidor."
        hint="Crie um projeto ou importe um arquivo .spid."
      />
    );
  }

  const report = (error: unknown, fallback: string): void => {
    setFailure(error instanceof ApiError ? projectErrorMessage(error, fallback) : fallback);
  };

  const handleOpen = async (name: string): Promise<void> => {
    setFailure(null);
    try {
      await open.mutateAsync(name);
      navigate('/');
    } catch (error) {
      report(error, 'Não foi possível abrir o projeto.');
    }
  };

  const handleDelete = async (name: string): Promise<void> => {
    if (confirmDestructive && !window.confirm(`Excluir o projeto "${name}"?`)) return;
    setFailure(null);
    try {
      await remove.mutateAsync(name);
    } catch (error) {
      report(error, 'Não foi possível excluir o projeto.');
    }
  };

  // The bearer token travels in a header, so the download cannot be an <a href>.
  const handleDownload = async (): Promise<void> => {
    setFailure(null);
    try {
      const blob = await endpoints.downloadProject();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = 'project.spid';
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      report(error, 'Não foi possível baixar o projeto.');
    }
  };

  return (
    <div className="flex flex-col gap-2">
      <table className="w-full border-collapse border border-rule bg-surface text-sm text-text">
        <caption className="sr-only">Projetos disponíveis no servidor</caption>
        <thead>
          <tr>
            <th className={TH}>Name</th>
            <th className={cn(TH, 'text-right')}>Loops</th>
            <th className={cn(TH, 'text-right')}>Size</th>
            <th className={cn(TH, 'text-right')}>Actions</th>
          </tr>
        </thead>
        <tbody>
          {projects.map((project) => (
            <tr key={project.name}>
              <td className={cn(TD, 'font-medium')}>{project.name}</td>
              <td className={cn(TD, 'numeric text-right')}>{project.controller_count}</td>
              <td className={cn(TD, 'numeric text-right')}>{formatSize(project.size_bytes)}</td>
              <td className={cn(TD, 'text-right')}>
                <span className="flex justify-end gap-2">
                  <Button size="sm" onClick={() => void handleOpen(project.name)}>
                    Open
                  </Button>
                  <Button size="sm" onClick={() => void handleDownload()}>
                    Download
                  </Button>
                  <Button
                    size="sm"
                    variant="destructive"
                    onClick={() => void handleDelete(project.name)}
                  >
                    Delete
                  </Button>
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {failure !== null ? (
        <p role="alert" className="text-xs font-medium text-alarm-crit">
          {failure}
        </p>
      ) : null}
    </div>
  );
}
