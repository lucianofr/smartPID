import { type ReactNode } from 'react';
import { Settings } from 'lucide-react';
import { NavLink, useNavigate } from 'react-router-dom';
import { Button } from '@/components/Button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/DropdownMenu';
import { useAuth } from '@/auth/AuthContext';
import { useConnectionStatus } from '@/realtime/useConnectionStatus';
import { useTheme, type ThemeId } from '@/theme/ThemeProvider';
import { cn } from '@/lib/utils';
import { useCurrentProject } from '@/features/projects/useCurrentProject';
import { WelcomeGate } from '@/features/projects/WelcomeGate';
import { StepMark, Wordmark, WORDMARK_TEXT } from './BrandMark';
import { appRoutes, cfgRoutes, navRoutes } from './routes';
import { ConnectionBanner } from './ConnectionBanner';

export interface AppShellProps {
  children?: ReactNode;
}

/**
 * Nav treatment, direction 1a: the active route is marked by a 2px accent rule
 * under the label, not by a filled pill. The transparent rule is carried on
 * every state so switching routes cannot shift the baseline by 2px.
 *
 * `min-h-11 min-w-11` is the §8.3 / e2e/target-size 44px floor and is NOT
 * negotiable for a control-station target, even though 1a draws a 9/14 box.
 */
const NAV_LINK_BASE = cn(
  'inline-flex min-h-11 min-w-11 items-center justify-center whitespace-nowrap',
  'rounded-t-control border-b-2 border-transparent px-3.5 py-2.5 text-sm',
  'outline-none transition-colors hover:text-text',
  'focus-visible:ring-2 focus-visible:ring-focus-ring',
);
const NAV_LINK_ACTIVE = 'border-brand-accent font-semibold text-text';
const NAV_LINK_IDLE = 'font-medium text-text-soft';

/** Avatar initials from a username — at most two characters, uppercased. */
export function initials(username: string): string {
  const parts = username.trim().split(/[\s._-]+/).filter((part) => part.length > 0);
  if (parts.length === 0) return '?';
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase();
}

export function AppShell({ children }: AppShellProps) {
  const { logout, user } = useAuth();
  const { theme, setTheme, themes } = useTheme();
  const status = useConnectionStatus();
  // Gated on a resolved session: `/project/current` is `require_user`, so the
  // login route would otherwise spend a certain 401 on every cold load.
  const { data: project } = useCurrentProject(user !== null);
  const navigate = useNavigate();
  // An `adminOnly` route redirects a user back to `/`, so offering it in the
  // configuration menu would only advertise a dead end (phase 10).
  const visible = appRoutes.filter((r) => r.adminOnly !== true || user?.role === 'admin');
  const nav = navRoutes(visible);
  const cfg = cfgRoutes(visible);

  // A socket that reports itself open is not evidence that anything is coming
  // through it (E2E-047), so the dot follows `stale` as well as `connected`.
  const linkUp = status.connected && !status.stale;

  return (
    <div className="flex h-full min-h-0 flex-col bg-bg text-text">
      <header
        className={cn(
          'flex h-16 shrink-0 items-center gap-3 border-b border-rule bg-surface',
          'px-4 md:gap-6 md:px-7',
        )}
      >
        {/* With `Executivo` visible in the nav the wordmark link is redundant as
            a route to it; the brand points at the landing route instead.
            min-w-0 + truncate: at the §6.9 320px floor the wordmark, nav and
            action cluster together exceed the viewport and the page gained a
            horizontal scrollbar. The brand is the only element here that can
            give way — nav already scrolls and the actions are load-bearing. */}
        <NavLink
          to="/"
          // Named explicitly: the two-tone wordmark is three text runs, and the
          // separator the accname algorithm puts between them depends on the
          // computed `display` of the coloured span — which jsdom and a real
          // browser disagree about. See BrandMark.Wordmark.
          aria-label={WORDMARK_TEXT}
          className={cn(
            'flex min-h-11 min-w-0 shrink items-center gap-2.5 rounded-control px-1 text-text',
            'outline-none focus-visible:ring-2 focus-visible:ring-focus-ring',
          )}
        >
          <StepMark className="text-brand-accent" />
          <Wordmark className="truncate" />
        </NavLink>

        <nav
          aria-label="Navegação principal"
          className="flex min-w-0 items-center gap-0.5 overflow-x-auto"
        >
          {nav.map((route) => (
            <NavLink
              key={route.path}
              to={route.path}
              end={route.path === '/'}
              className={({ isActive }) =>
                cn(NAV_LINK_BASE, isActive ? NAV_LINK_ACTIVE : NAV_LINK_IDLE)
              }
            >
              {route.nav.label}
            </NavLink>
          ))}
        </nav>

        {/* Which plant am I looking at — the answer rides at the end of the nav
            row, not in a page body. Pending and failed both render nothing: a
            placeholder here would read as a project named "—". */}
        {project !== undefined ? (
          <div className="hidden min-w-0 shrink items-center gap-2.5 md:flex">
            <span aria-hidden="true" className="h-[22px] w-px shrink-0 bg-rule" />
            <span className="sr-only">Projeto ativo</span>
            <span className="min-w-0 truncate text-sm font-medium text-text-soft">
              {project.name}
            </span>
          </div>
        ) : null}

        <div className="ml-auto flex shrink-0 items-center gap-4">
          {/* Compact, always-on link state. It answers "is the field link up?"
              at a glance; `ConnectionBanner` below still owns the interrupting
              announcement when the answer is no. Dropped below lg so the 320px
              floor keeps its budget for the nav and the actions. */}
          <div className="hidden items-center gap-2 text-sm text-text-soft lg:flex">
            <span
              aria-hidden="true"
              className={cn(
                'h-[7px] w-[7px] shrink-0 rounded-pill',
                linkUp ? 'bg-live' : 'bg-state-error',
              )}
            />
            {linkUp ? 'OPC-UA conectado' : 'OPC-UA sem conexão'}
          </div>

          <span aria-hidden="true" className="hidden h-[22px] w-px shrink-0 bg-rule lg:block" />

          {user !== null ? (
            <div className="hidden items-center gap-2.5 text-sm font-semibold text-text-soft sm:flex">
              {/* brand-ink is dark in every theme; brand-accent-soft is light in
                  every theme. `text-on-accent` would be navy-on-navy under
                  optimizer-dark, where --on-accent is #0D1F38. */}
              <span
                aria-hidden="true"
                className={cn(
                  'flex h-7 w-7 shrink-0 items-center justify-center rounded-pill',
                  'bg-brand-ink text-2xs font-bold text-brand-accent-soft',
                )}
              >
                {initials(user.username)}
              </span>
              <span className="max-w-[14ch] truncate">{user.username}</span>
            </div>
          ) : null}

          <div className="flex items-center gap-1">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" aria-label="Configurações">
                  <Settings className="h-4 w-4" aria-hidden="true" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuLabel>Tema</DropdownMenuLabel>
                <DropdownMenuRadioGroup
                  value={theme}
                  onValueChange={(next) => setTheme(next as ThemeId)}
                >
                  {themes.map((t) => (
                    <DropdownMenuRadioItem key={t.id} value={t.id}>
                      {t.label}
                    </DropdownMenuRadioItem>
                  ))}
                </DropdownMenuRadioGroup>
                {cfg.length > 0 ? (
                  <>
                    <DropdownMenuSeparator />
                    <DropdownMenuLabel>Administração</DropdownMenuLabel>
                    {cfg.map((route) => (
                      <DropdownMenuItem key={route.path} onSelect={() => navigate(route.path)}>
                        {route.cfg.label}
                      </DropdownMenuItem>
                    ))}
                  </>
                ) : null}
              </DropdownMenuContent>
            </DropdownMenu>
            <Button variant="ghost" onClick={logout}>
              Sair
            </Button>
          </div>
        </div>
      </header>

      {/* Directly under the top bar and above every route: whether the numbers
          below are current is the first thing an operator must be able to read. */}
      <ConnectionBanner />

      <main className="flex min-h-0 flex-1 flex-col">{children}</main>

      {/* Admin-only, once per session, and only when the roster actually loaded. */}
      <WelcomeGate />
    </div>
  );
}
