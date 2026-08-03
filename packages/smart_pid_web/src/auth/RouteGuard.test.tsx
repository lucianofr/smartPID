import { render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { ReactNode } from 'react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { AuthProvider } from './AuthContext';
import { RouteGuard } from './RouteGuard';

const fetchMock = vi.fn();
const meResponse = (role: 'admin' | 'user') =>
  new Response(JSON.stringify({ user_id: 1, username: 'u', role }), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  });

beforeEach(() => {
  localStorage.clear();
  sessionStorage.clear();
  fetchMock.mockReset();
  vi.stubGlobal('fetch', fetchMock);
});
afterEach(() => vi.unstubAllGlobals());

function app(guarded: ReactNode) {
  return render(
    <AuthProvider>
      <MemoryRouter initialEntries={['/protegido']}>
        <Routes>
          <Route path="/login" element={<div>tela de login</div>} />
          <Route path="/" element={<div>dashboard</div>} />
          <Route path="/protegido" element={guarded} />
        </Routes>
      </MemoryRouter>
    </AuthProvider>,
  );
}

describe('RouteGuard', () => {
  it('redirects unauthenticated visitors to /login', () => {
    app(
      <RouteGuard>
        <div>conteúdo protegido</div>
      </RouteGuard>,
    );
    expect(screen.getByText('tela de login')).toBeInTheDocument();
  });

  it('renders children for an authenticated session', async () => {
    localStorage.setItem('smart-pid-token', 't');
    fetchMock.mockResolvedValueOnce(meResponse('user'));
    app(
      <RouteGuard>
        <div>conteúdo protegido</div>
      </RouteGuard>,
    );
    expect(await screen.findByText('conteúdo protegido')).toBeInTheDocument();
  });

  it('adminOnly renders nothing while the role is unknown, then admits admin', async () => {
    localStorage.setItem('smart-pid-token', 't');
    let release!: (r: Response) => void;
    fetchMock.mockReturnValueOnce(new Promise<Response>((r) => { release = r; }));
    app(
      <RouteGuard adminOnly>
        <div>painel admin</div>
      </RouteGuard>,
    );
    expect(screen.queryByText('painel admin')).not.toBeInTheDocument();
    expect(screen.queryByText('dashboard')).not.toBeInTheDocument();
    release(meResponse('admin'));
    expect(await screen.findByText('painel admin')).toBeInTheDocument();
  });

  it('adminOnly redirects a user-role session to /', async () => {
    localStorage.setItem('smart-pid-token', 't');
    fetchMock.mockResolvedValueOnce(meResponse('user'));
    app(
      <RouteGuard adminOnly>
        <div>painel admin</div>
      </RouteGuard>,
    );
    await waitFor(() => expect(screen.getByText('dashboard')).toBeInTheDocument());
    expect(screen.queryByText('painel admin')).not.toBeInTheDocument();
  });
});