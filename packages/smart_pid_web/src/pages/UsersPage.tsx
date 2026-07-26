import { UsersPanel } from '@/features/users/UsersPanel';

/**
 * Account management (`[cfg] › Users`, admin-only).
 *
 * Route-guarded AND capability-checked: the guard protects the URL, the panel
 * protects the controls, and `require_admin` on every `/users` route is what
 * actually enforces it.
 */
export function UsersPage() {
  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-y-auto">
      <header className="shrink-0 border-b border-rule px-3 py-2">
        <h1 className="type-display text-lg text-text">Usuários</h1>
        <p className="text-xs text-text-soft">
          Contas de acesso ao sistema. Desativar preserva o histórico de auditoria.
        </p>
      </header>
      <div className="p-3">
        <UsersPanel />
      </div>
    </div>
  );
}
