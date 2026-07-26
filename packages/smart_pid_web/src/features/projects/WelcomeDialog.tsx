import { useState } from 'react';
import { ApiError } from '@/api/client';
import { Button } from '@/components/Button';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/Dialog';
import type { ProjectItem } from '@/api/types';
import { formatSize } from './ProjectList';
import { projectErrorMessage, useOpenProject } from './useProjects';

export interface WelcomeDialogProps {
  open: boolean;
  projects: readonly ProjectItem[];
  /** Called after the operator opened a project — the caller navigates. */
  onOpened: () => void;
  onDismiss: () => void;
  onManage: () => void;
}

/**
 * Post-login "which plant am I looking at?" gate. Purely an affordance: it is
 * only ever shown when the roster is known to be non-empty, and dismissing it
 * is a first-class outcome — an engineer who came back to the already-open
 * project must not have to fight a modal.
 */
export function WelcomeDialog({
  open,
  projects,
  onOpened,
  onDismiss,
  onManage,
}: WelcomeDialogProps) {
  const openProject = useOpenProject();
  const [failure, setFailure] = useState<string | null>(null);

  const handleOpen = async (name: string): Promise<void> => {
    setFailure(null);
    try {
      await openProject.mutateAsync(name);
      onOpened();
    } catch (error) {
      setFailure(
        error instanceof ApiError
          ? projectErrorMessage(error, 'Não foi possível abrir o projeto.')
          : 'Não foi possível abrir o projeto.',
      );
    }
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) onDismiss();
      }}
    >
      <DialogContent aria-label="Abrir projeto">
        <DialogHeader>
          <DialogTitle>Abrir projeto</DialogTitle>
          <DialogDescription>
            Escolha o projeto que esta sessão deve acompanhar.
          </DialogDescription>
        </DialogHeader>
        <ul className="flex max-h-72 flex-col gap-2 overflow-y-auto">
          {projects.map((project) => (
            <li
              key={project.name}
              className="flex items-center gap-3 border border-rule bg-surface-sunk px-3 py-2"
            >
              <span className="flex-1 truncate text-sm font-medium text-text">{project.name}</span>
              <span className="numeric text-xs text-text-soft">
                {project.controller_count} malhas · {formatSize(project.size_bytes)}
              </span>
              <Button
                size="sm"
                aria-label={`Open ${project.name}`}
                disabled={openProject.isPending}
                onClick={() => void handleOpen(project.name)}
              >
                Open
              </Button>
            </li>
          ))}
        </ul>
        {failure !== null ? (
          <p role="alert" className="text-xs font-medium text-alarm-crit">
            {failure}
          </p>
        ) : null}
        <DialogFooter>
          <Button variant="ghost" onClick={onDismiss}>
            Agora não
          </Button>
          <Button variant="secondary" onClick={onManage}>
            Gerenciar projetos
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
