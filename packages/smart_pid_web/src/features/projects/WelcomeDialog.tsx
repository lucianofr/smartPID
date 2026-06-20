import { useNavigate } from 'react-router-dom';
import { useOpenProject, useProjectList } from './useProjects';

/**
 * Post-login welcome/open-project dialog (Task 8.3 — CSS migrated to flat ISA-101
 * token utilities). Deliberately NOT the shadcn/Radix Dialog: it is a plain,
 * non-portal overlay that returns `null` when closed (WelcomeDialog.test asserts
 * an empty DOM in that case). The translucent scrim uses the sanctioned
 * black/opacity utility (same precedent as the dialog-primitive scrim), never a
 * raw palette color.
 */
const ITEM =
  'grid grid-cols-[1fr_auto_auto] items-center gap-3 p-3 bg-surface border border-border rounded-control';

const BUTTON =
  'cursor-pointer bg-surface text-text border border-border rounded-control px-4 py-1 hover:border-border-strong';

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
      className="fixed inset-0 z-[1100] flex items-center justify-center p-4 bg-black/70"
      role="dialog"
      aria-modal="true"
      aria-label="Welcome — choose a project"
    >
      <div className="w-[min(560px,100%)] max-h-[85vh] flex flex-col gap-3 p-5 bg-surface-container text-text border border-border-strong rounded-card">
        <header className="border-b border-border pb-3">
          <h2 className="m-0" style={{ fontSize: 'var(--text-lg)' }}>
            Open a project
          </h2>
        </header>
        <ul className="list-none m-0 p-0 flex flex-col gap-2 overflow-y-auto">
          {list.isLoading && <li className="text-text-secondary p-3">Loading…</li>}
          {!list.isLoading && projects.length === 0 && (
            <li className="text-text-secondary p-3">No projects yet.</li>
          )}
          {projects.map((p) => (
            <li key={p.name} className={ITEM}>
              <span className="font-semibold">{p.name}</span>
              <span
                className="numeric text-text-secondary"
                style={{ fontSize: 'var(--text-xs)' }}
              >
                {p.controller_count} loops
              </span>
              <button
                type="button"
                className={BUTTON}
                style={{ fontSize: 'var(--text-xs)' }}
                onClick={() => void handleOpen(p.name)}
              >
                Open
              </button>
            </li>
          ))}
        </ul>
        {openProject.isError && (
          <p role="alert" className="m-0 text-alarm-critical" style={{ fontSize: 'var(--text-sm)' }}>
            {openProject.error instanceof Error
              ? openProject.error.message
              : 'Failed to open project.'}
          </p>
        )}
        <footer className="flex justify-end gap-2 border-t border-border pt-3">
          <button
            type="button"
            className={BUTTON}
            style={{ fontSize: 'var(--text-xs)' }}
            onClick={goToProjects}
          >
            New
          </button>
          <button
            type="button"
            className={BUTTON}
            style={{ fontSize: 'var(--text-xs)' }}
            onClick={goToProjects}
          >
            Import
          </button>
          <button
            type="button"
            className={BUTTON}
            style={{ fontSize: 'var(--text-xs)' }}
            onClick={onDismiss}
          >
            Close
          </button>
        </footer>
      </div>
    </div>
  );
}
