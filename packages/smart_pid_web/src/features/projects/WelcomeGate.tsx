import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useCan } from '@/auth/useCan';
import { WelcomeDialog } from './WelcomeDialog';
import { useProjectList } from './useProjects';

/** Session flag — the two fatia-7 E2E harnesses seed this key by name. */
export const WELCOME_SEEN_KEY = 'spid.welcome-seen';

/**
 * Decides whether the post-login project chooser appears at all.
 *
 * Three conditions, all required: the session is an admin (`/project/list` is
 * `require_admin`, so a `user` must never even ask), this session has not seen
 * the dialog, and the roster actually loaded with something in it. A failed or
 * empty roster keeps the gate shut — the chooser is a convenience, never a
 * blocker in front of a running plant.
 */
export function WelcomeGate() {
  const canManage = useCan('projects.manage');
  const [seen, setSeen] = useState(() => sessionStorage.getItem(WELCOME_SEEN_KEY) === '1');
  const navigate = useNavigate();
  const list = useProjectList(canManage && !seen);

  const dismiss = (): void => {
    sessionStorage.setItem(WELCOME_SEEN_KEY, '1');
    setSeen(true);
  };

  const projects = list.data?.projects ?? [];
  if (seen || !canManage || projects.length === 0) return null;

  return (
    <WelcomeDialog
      open
      projects={projects}
      onOpened={() => {
        dismiss();
        navigate('/');
      }}
      onDismiss={dismiss}
      onManage={() => {
        dismiss();
        navigate('/projects');
      }}
    />
  );
}
