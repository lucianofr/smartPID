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
    <div style={{ minHeight: '100vh', display: 'grid', placeItems: 'center', background: 'var(--bg)' }}>
      <form
        onSubmit={onSubmit}
        style={{
          width: 360, padding: 'var(--sp-6)', background: 'var(--surface)',
          border: '1px solid var(--border)', color: 'var(--text)',
        }}
      >
        <h1 style={{ fontSize: 'var(--text-lg)', fontWeight: 'var(--fw-semibold)' }}>Smart PID</h1>
        <label htmlFor="u">Usuário</label>
        <input id="u" className="numeric" value={username} onChange={(e) => setUsername(e.target.value)} />
        <label htmlFor="p">Senha</label>
        <input id="p" className="numeric" type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
        {error && <p role="alert" style={{ color: 'var(--alarm-critical)' }}>{error}</p>}
        <button type="submit">Entrar</button>
      </form>
    </div>
  );
}
