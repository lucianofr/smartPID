import type { AccessLogRow } from '@/api/types';
import { useCan } from '@/auth/useCan';
import { Badge } from '@/components/Badge';
import { EmptyState, ErrorState, LoadingState } from '@/components/MissingState';
import { formatDateTime } from '@/lib/format';
import { cn } from '@/lib/utils';
import { ACCESS_LOG_LIMIT, useAccessLog, useActiveSessions } from './useSessions';

/**
 * Security view of the settings page: who is connected right now, from which
 * address, and the platform's sign-in history.
 *
 * The two tables answer different questions and must not be read as one. The
 * live list is process memory — it empties on a daemon restart, because every
 * connection it was tracking died with that process. The history is
 * `users.db`, so it survives both a restart and a project switch.
 */

const TH = 'border-b border-rule px-3 py-2 text-left text-2xs uppercase tracking-wider text-text-soft';
const TD = 'border-b border-rule px-3 py-2 align-middle';

/** Sign-in vocabulary of the access log (AuditAction.LOGIN / LOGOUT). */
const EVENT_LABEL: Readonly<Record<string, string>> = {
  LOGIN: 'Entrada',
  LOGOUT: 'Saída',
};

function eventLabel(event: AccessLogRow['event']): string {
  // An unmapped value is printed verbatim rather than swallowed: a log row is
  // evidence, and hiding one because this build does not know its name yet
  // would be the worst possible failure for an audit surface.
  return EVENT_LABEL[event] ?? event;
}

export function SessionsPanel() {
  const canManage = useCan('users.manage');
  const sessions = useActiveSessions(canManage);
  const log = useAccessLog(canManage);

  // SettingsForm already states the admin-only denial on this page; a second
  // copy of it under the form would be noise, and the route is `adminOnly`.
  if (!canManage) return null;

  return (
    <div className="flex flex-col gap-5 p-3">
      <section aria-labelledby="sessions-live" className="flex flex-col gap-2">
        <h2 id="sessions-live" className="text-xs font-semibold uppercase tracking-wider text-text">
          Usuários conectados
        </h2>
        <p className="text-xs text-text-soft">
          Uma linha por usuário e endereço de origem. A lista é mantida em memória: reiniciar o
          serviço a esvazia.
        </p>
        {sessions.isPending ? (
          <LoadingState label="Carregando sessões…" bars={2} />
        ) : sessions.isError ? (
          <ErrorState
            message="Não foi possível carregar as sessões ativas."
            onRetry={() => void sessions.refetch()}
          />
        ) : sessions.data.length === 0 ? (
          <EmptyState message="Nenhuma sessão ativa." />
        ) : (
          <table className="w-full border-collapse border border-rule bg-surface text-sm text-text">
            <caption className="sr-only">Sessões ativas</caption>
            <thead>
              <tr>
                <th className={TH}>Usuário</th>
                <th className={TH}>Perfil</th>
                <th className={TH}>IP de origem</th>
                <th className={TH}>Início</th>
                <th className={TH}>Última atividade</th>
                <th className={TH}>Conexão</th>
              </tr>
            </thead>
            <tbody>
              {sessions.data.map((session) => (
                <tr key={`${session.user_id}@${session.ip}`}>
                  <td className={cn(TD, 'font-medium')}>{session.username}</td>
                  <td className={TD}>{session.role}</td>
                  <td className={cn(TD, 'numeric')}>{session.ip}</td>
                  <td className={cn(TD, 'numeric')}>{formatDateTime(session.since)}</td>
                  <td className={cn(TD, 'numeric')}>{formatDateTime(session.last_seen)}</td>
                  <td className={TD}>
                    <Badge tone={session.online ? 'running' : 'neutral'}>
                      {session.online ? 'Aberta' : 'Ociosa'}
                    </Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section aria-labelledby="sessions-log" className="flex flex-col gap-2">
        <h2 id="sessions-log" className="text-xs font-semibold uppercase tracking-wider text-text">
          Últimos logins
        </h2>
        <p className="text-xs text-text-soft">
          Entradas e saídas de todas as contas, mais recentes primeiro (até {ACCESS_LOG_LIMIT}{' '}
          registros). Preservado ao trocar de projeto.
        </p>
        {log.isPending ? (
          <LoadingState label="Carregando histórico de acesso…" bars={2} />
        ) : log.isError ? (
          <ErrorState
            message="Não foi possível carregar o histórico de acesso."
            onRetry={() => void log.refetch()}
          />
        ) : log.data.length === 0 ? (
          <EmptyState message="Nenhum acesso registrado." />
        ) : (
          <table className="w-full border-collapse border border-rule bg-surface text-sm text-text">
            <caption className="sr-only">Histórico de acesso</caption>
            <thead>
              <tr>
                <th className={TH}>Quando</th>
                <th className={TH}>Usuário</th>
                <th className={TH}>Evento</th>
                <th className={TH}>IP de origem</th>
              </tr>
            </thead>
            <tbody>
              {log.data.map((entry) => (
                <tr key={entry.id}>
                  <td className={cn(TD, 'numeric')}>{formatDateTime(entry.timestamp)}</td>
                  <td className={cn(TD, 'font-medium')}>{entry.username}</td>
                  <td className={TD}>
                    <Badge tone={entry.event === 'LOGIN' ? 'accent' : 'neutral'}>
                      {eventLabel(entry.event)}
                    </Badge>
                  </td>
                  <td className={cn(TD, 'numeric')}>{entry.ip}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
