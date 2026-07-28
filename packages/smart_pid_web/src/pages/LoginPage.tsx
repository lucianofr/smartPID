import { useId, useState, type FormEvent } from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';
import { ApiError } from '@/api/client';
import { Button } from '@/components/Button';
import { Field, Input } from '@/components/Field';
import { useAuth } from '@/auth/AuthContext';

/** RouteGuard stores the blocked location in `state.from` (a router Location). */
function deepLinkFrom(state: unknown): string {
  if (typeof state !== 'object' || state === null || !('from' in state)) return '/';
  const from = state.from;
  if (typeof from !== 'object' || from === null || !('pathname' in from)) return '/';
  const pathname = from.pathname;
  return typeof pathname === 'string' && pathname !== '/login' ? pathname : '/';
}

function messageFor(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.kind === 'unauthorized') return 'Usuário ou senha inválidos';
    if (error.kind === 'network') return 'Sem conexão com o servidor';
  }
  return 'Não foi possível entrar. Tente novamente.';
}

export function LoginPage() {
  const { login, isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const target = deepLinkFrom(location.state);

  const userId = useId();
  const passwordId = useId();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  if (isAuthenticated) return <Navigate to={target} replace />;

  const submit = async (e: FormEvent<HTMLFormElement>): Promise<void> => {
    e.preventDefault();
    setError(null);
    setPending(true);
    try {
      await login(username, password);
      navigate(target, { replace: true });
    } catch (err) {
      setError(messageFor(err));
    } finally {
      setPending(false);
    }
  };

  return (
    <main className="flex min-h-screen items-center justify-center bg-bg p-6 text-text">
      <form
        onSubmit={(e) => void submit(e)}
        aria-labelledby={`${userId}-title`}
        className="flex w-full max-w-sm flex-col gap-4 border border-rule-strong bg-surface p-6"
      >
        <h1 id={`${userId}-title`} className="type-display text-xl uppercase tracking-widest">
          Smart PID
        </h1>

        <Field label="Usuário" htmlFor={userId}>
          <Input
            id={userId}
            name="username"
            autoComplete="username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
          />
        </Field>

        <Field label="Senha" htmlFor={passwordId}>
          <Input
            id={passwordId}
            name="password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </Field>

        {error !== null ? (
          <p role="alert" className="text-sm font-medium text-alarm-crit">
            {error}
          </p>
        ) : null}

        <Button type="submit" variant="primary" disabled={pending}>
          Entrar
        </Button>
      </form>
    </main>
  );
}
