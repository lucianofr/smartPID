import { useState } from 'react';
import { projectApi } from './projectApi';
import { useDeleteProject, useOpenProject, useProjectList } from './useProjects';
import { useSettings } from '../settings/useSettings';
import './ProjectList.css';

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function ProjectList(): JSX.Element {
  const list = useProjectList();
  const del = useDeleteProject();
  const open = useOpenProject();
  const { preferences } = useSettings();
  const [downloadError, setDownloadError] = useState<string | null>(null);

  async function handleOpen(name: string): Promise<void> {
    try {
      await open.mutateAsync(name);
    } catch {
      /* surfaced via open.isError */
    }
  }

  async function handleDelete(name: string): Promise<void> {
    if (preferences.confirmDestructive && !window.confirm(`Delete project "${name}"?`)) return;
    try {
      await del.mutateAsync(name);
    } catch {
      /* surfaced via del.isError */
    }
  }

  async function handleDownload(): Promise<void> {
    setDownloadError(null);
    try {
      const blob = await projectApi.download();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'project.spid';
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setDownloadError(e instanceof Error ? e.message : 'Download failed');
    }
  }

  if (list.isLoading) return <p className="project-list__loading">Loading projects…</p>;
  const projects = list.data?.projects ?? [];

  return (
    <>
      <table className="project-list" aria-label="Projects">
        <thead>
          <tr>
            <th>Name</th>
            <th className="project-list__num">Loops</th>
            <th className="project-list__num">Size</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {projects.map((p) => (
            <tr key={p.name}>
              <td className="project-list__name">{p.name}</td>
              <td className="project-list__num numeric">{p.controller_count}</td>
              <td className="project-list__num numeric">{formatSize(p.size_bytes)}</td>
              <td className="project-list__actions">
                <button type="button" onClick={() => void handleOpen(p.name)}>
                  Open
                </button>
                <button type="button" onClick={() => void handleDownload()}>
                  Download
                </button>
                <button
                  type="button"
                  className="project-list__delete"
                  onClick={() => void handleDelete(p.name)}
                >
                  Delete
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {(open.isError || del.isError || downloadError) && (
        <p role="alert" className="project-list__error">
          {downloadError ??
            (open.error instanceof Error
              ? open.error.message
              : del.error instanceof Error
                ? del.error.message
                : 'Action failed')}
        </p>
      )}
    </>
  );
}
