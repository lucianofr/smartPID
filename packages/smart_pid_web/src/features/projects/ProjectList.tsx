import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { projectApi } from './projectApi';
import { useDeleteProject, useOpenProject, useProjectList } from './useProjects';
import { useSettings } from '../settings/useSettings';

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/**
 * Projects table (Fatia 7; Task 8.3 — CSS migrated to flat ISA-101 token
 * utilities). Per-row Open/Download/Delete actions; Delete carries the
 * --alarm-critical token via the `text-alarm-critical`/`border-alarm-critical`
 * utilities (the one sanctioned color use, signalling a destructive action).
 */
const TH = 'text-left px-3 py-2 border-b border-border text-text-secondary uppercase tracking-[0.04em]';

const TD = 'px-3 py-2 border-b border-divider align-middle';

const ACTION_BUTTON =
  'cursor-pointer bg-surface text-text border border-border rounded-control px-3 py-1 hover:border-border-strong';

export function ProjectList(): JSX.Element {
  const list = useProjectList();
  const del = useDeleteProject();
  const open = useOpenProject();
  const { preferences } = useSettings();
  const navigate = useNavigate();
  const [downloadError, setDownloadError] = useState<string | null>(null);

  async function handleOpen(name: string): Promise<void> {
    try {
      await open.mutateAsync(name);
      navigate('/');
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

  if (list.isLoading) return <p className="text-text-secondary p-4">Loading projects…</p>;
  const projects = list.data?.projects ?? [];

  return (
    <>
      <table
        className="w-full border-collapse bg-surface-container text-text border border-border rounded-card"
        style={{ fontSize: 'var(--text-sm)' }}
        aria-label="Projects"
      >
        <thead>
          <tr>
            <th className={TH} style={{ fontSize: 'var(--text-xs)' }}>
              Name
            </th>
            <th
              className={`${TH} text-right whitespace-nowrap`}
              style={{ fontSize: 'var(--text-xs)' }}
            >
              Loops
            </th>
            <th
              className={`${TH} text-right whitespace-nowrap`}
              style={{ fontSize: 'var(--text-xs)' }}
            >
              Size
            </th>
            <th className={TH} style={{ fontSize: 'var(--text-xs)' }}>
              Actions
            </th>
          </tr>
        </thead>
        <tbody>
          {projects.map((p) => (
            <tr key={p.name} className="[&:last-child>td]:border-b-0">
              <td className={`${TD} font-semibold`}>{p.name}</td>
              <td className={`${TD} numeric text-right whitespace-nowrap`}>{p.controller_count}</td>
              <td className={`${TD} numeric text-right whitespace-nowrap`}>
                {formatSize(p.size_bytes)}
              </td>
              <td className={`${TD} flex gap-2 justify-end`}>
                <button type="button" className={ACTION_BUTTON} onClick={() => void handleOpen(p.name)}>
                  Open
                </button>
                <button type="button" className={ACTION_BUTTON} onClick={() => void handleDownload()}>
                  Download
                </button>
                <button
                  type="button"
                  className={`${ACTION_BUTTON} text-alarm-critical border-alarm-critical hover:border-alarm-critical`}
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
        <p role="alert" className="mt-2 text-alarm-critical" style={{ fontSize: 'var(--text-sm)' }}>
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
