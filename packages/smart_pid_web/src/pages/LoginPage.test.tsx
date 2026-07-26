import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { ApiError } from '@/api/client';
import { useAuth, type AuthContextValue } from '@/auth/AuthContext';
import type * as AuthContextModule from '@/auth/AuthContext';
import { ThemeProvider } from '@/theme/ThemeProvider';
import { LoginPage } from './LoginPage';

vi.mock('@/auth/AuthContext', async () => {
  const actual = await vi.importActual<typeof AuthContextModule>('@/auth/AuthContext');
  return { ...actual, useAuth: vi.fn() };
});

const login = vi.fn();
const useAuthMock = vi.mocked(useAuth);

function stubAuth(overrides: Partial<AuthContextValue> = {}): void {
  useAuthMock.mockReturnValue({
    token: null,
    user: null,
    isAuthenticated: false,
    login,
    logout: vi.fn(),
    refreshUser: vi.fn(),
    ...overrides,
  });
}

function LocationProbe() {
  const location = useLocation();
  return <span data-testid="pathname">{location.pathname}</span>;
}

function renderLogin(initialEntry: { pathname: string; state?: unknown } = { pathname: '/login' }) {
  return render(
    <ThemeProvider>
      <MemoryRouter initialEntries={[initialEntry]}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="*" element={<LocationProbe />} />
        </Routes>
      </MemoryRouter>
    </ThemeProvider>,
  );
}

beforeEach(() => {
  login.mockReset();
  login.mockResolvedValue(undefined);
  stubAuth();
});

afterEach(() => {
  vi.clearAllMocks();
});

describe('LoginPage', () => {
  it('submits Portuguese-labelled credentials', async () => {
    renderLogin();
    fireEvent.change(screen.getByLabelText('Usuário'), { target: { value: 'admin' } });
    fireEvent.change(screen.getByLabelText('Senha'), { target: { value: 'admin' } });
    fireEvent.click(screen.getByRole('button', { name: 'Entrar' }));
    await waitFor(() => expect(login).toHaveBeenCalledWith('admin', 'admin'));
  });

  it('marks the credential fields with the browser autofill hints', () => {
    renderLogin();
    expect(screen.getByLabelText('Usuário')).toHaveAttribute('autocomplete', 'username');
    const password = screen.getByLabelText('Senha');
    expect(password).toHaveAttribute('type', 'password');
    expect(password).toHaveAttribute('autocomplete', 'current-password');
  });

  it('renders the 401 message and keeps the form usable', async () => {
    login.mockRejectedValue(new ApiError(401, 'unauthorized', 'nope'));
    renderLogin();
    fireEvent.change(screen.getByLabelText('Usuário'), { target: { value: 'admin' } });
    fireEvent.change(screen.getByLabelText('Senha'), { target: { value: 'wrong' } });
    fireEvent.click(screen.getByRole('button', { name: 'Entrar' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Usuário ou senha inválidos');
    expect(screen.getByRole('button', { name: 'Entrar' })).toBeEnabled();
  });

  it('reports a transport failure separately from bad credentials', async () => {
    login.mockRejectedValue(new ApiError(0, 'network', 'offline'));
    renderLogin();
    fireEvent.click(screen.getByRole('button', { name: 'Entrar' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Sem conexão com o servidor');
  });

  it('navigates to the deep link captured by RouteGuard', async () => {
    renderLogin({ pathname: '/login', state: { from: { pathname: '/alarms' } } });
    fireEvent.click(screen.getByRole('button', { name: 'Entrar' }));
    expect(await screen.findByTestId('pathname')).toHaveTextContent('/alarms');
  });

  it('falls back to the dashboard when there is no deep link', async () => {
    renderLogin();
    fireEvent.click(screen.getByRole('button', { name: 'Entrar' }));
    expect(await screen.findByTestId('pathname')).toHaveTextContent('/');
  });

  it('bounces an already-authenticated session away from /login', () => {
    stubAuth({ isAuthenticated: true, token: 'jwt' });
    renderLogin();
    expect(screen.getByTestId('pathname')).toHaveTextContent('/');
  });
});
