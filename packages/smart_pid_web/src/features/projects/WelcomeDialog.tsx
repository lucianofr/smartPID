import { useNavigate } from 'react-router-dom';
import { useOpenProject, useProjectList } from './useProjects';
import './WelcomeDialog.css';

export function WelcomeDialog({
  open,
  onDismiss,
}: {
  open: boolean;
  onDismiss: () => void;
}): JSX.Element | null {
  const list = useProjectList();
  const openProject = useOpenProject();
  const navigate = useNavigate();

  if (!open) return null;

  const projects = list.data?.projects ?? [];

  async function handleOpen(name: string) {
    try {
      await openProject.mutateAsync(name);
      onDismiss();
    } catch {
      /* surfaced via openProject.isError */
    }
  }

  function goToProjects() {
    onDismiss();
    navigate('/projects');
  }

  return (
    <div
      className="welcome-overlay"
      role="dialog"
      aria-modal="true"
      aria-label="Welcome — choose a project"
    >
      <div className="welcome-dialog">
        <header className="welcome-dialog__header">
          <h2 className="welcome-dialog__title">Open a project</h2>
        </header>
        <ul className="welcome-dialog__list">
          {list.isLoading && <li className="welcome-dialog__loading">Loading…</li>}
          {!list.isLoading && projects.length === 0 && (
            <li className="welcome-dialog__empty">No projects yet.</li>
          )}
          {projects.map((p) => (
            <li key={p.name} className="welcome-dialog__item">
              <span className="welcome-dialog__name">{p.name}</span>
              <span className="numeric welcome-dialog__count">{p.controller_count} loops</span>
              <button
                type="button"
                className="welcome-dialog__open"
                onClick={() => void handleOpen(p.name)}
              >
                Open
              </button>
            </li>
          ))}
        </ul>
        {openProject.isError && (
          <p role="alert" className="welcome-dialog__error">
            {openProject.error instanceof Error
              ? openProject.error.message
              : 'Failed to open project.'}
          </p>
        )}
        <footer className="welcome-dialog__actions">
          <button type="button" className="welcome-dialog__secondary" onClick={goToProjects}>
            New
          </button>
          <button type="button" className="welcome-dialog__secondary" onClick={goToProjects}>
            Import
          </button>
          <button type="button" className="welcome-dialog__secondary" onClick={onDismiss}>
            Close
          </button>
        </footer>
      </div>
    </div>
  );
}
