import { useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { ApiError } from '../api/client';
import { useAuth } from './AuthContext';

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await login(username, password);
      navigate('/', { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? 'Usuário ou senha inválidos' : 'Erro de conexão');
    }
  }

  return (
    <div className="grid min-h-screen place-items-center bg-bg px-4 font-ui">
      <form
        onSubmit={onSubmit}
        className="login-card-enter flex w-full max-w-90 flex-col gap-4 border border-border bg-surface p-8 text-text"
      >
        <header className="mb-2 flex flex-col gap-1">
          <h1
            className="text-text"
            style={{
              fontSize: 'var(--text-2xl)',
              lineHeight: 'var(--lh-tight)',
              fontWeight: 'var(--fw-semibold)',
            }}
          >
            Smart PID
          </h1>
          <p className="text-text-secondary" style={{ fontSize: 'var(--text-sm)' }}>
            Entre para acessar a plataforma
          </p>
        </header>

        <div className="flex flex-col gap-1.5">
          <label
            htmlFor="u"
            className="text-text-secondary"
            style={{ fontSize: 'var(--text-xs)', fontWeight: 'var(--fw-medium)' }}
          >
            Usuário
          </label>
          <input
            id="u"
            className="numeric h-11 border border-border bg-field-bg px-3 text-text outline-none transition-colors duration-fast focus:border-border-strong"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <label
            htmlFor="p"
            className="text-text-secondary"
            style={{ fontSize: 'var(--text-xs)', fontWeight: 'var(--fw-medium)' }}
          >
            Senha
          </label>
          <input
            id="p"
            type="password"
            className="numeric h-11 border border-border bg-field-bg px-3 text-text outline-none transition-colors duration-fast focus:border-border-strong"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
          />
        </div>

        {error && (
          <div
            role="alert"
            className="flex items-center justify-between gap-3 border border-alarm-diag px-3 py-2 text-alarm-diag"
            style={{ fontSize: 'var(--text-sm)' }}
          >
            <span>{error}</span>
            <button
              type="submit"
              className="text-alarm-diag underline transition-colors duration-fast hover:text-text"
              style={{ fontSize: 'var(--text-xs)', fontWeight: 'var(--fw-medium)' }}
            >
              Tentar novamente
            </button>
          </div>
        )}

        <button
          type="submit"
          className="mt-2 h-11 border border-border-strong bg-surface-container-high text-text transition-colors duration-fast hover:bg-surface-container focus:border-border-strong focus:outline-none"
          style={{ fontSize: 'var(--text-base)', fontWeight: 'var(--fw-medium)' }}
        >
          Entrar
        </button>
      </form>
    </div>
  );
}
