import { useCallback, useEffect, useState, type ReactNode } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { Button } from '@/components/Button';
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/components/Command';
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
import { useTheme, type ThemeId } from '@/theme/ThemeProvider';
import { cn } from '@/lib/utils';
import { WelcomeGate } from '@/features/projects/WelcomeGate';
import { appRoutes, cfgRoutes, commandRoutes, navRoutes } from './routes';

export interface AppShellProps {
  children?: ReactNode;
}

/** `k` opens the palette only when the operator is not typing into a control. */
function isEditableTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  if (target.isContentEditable) return true;
  const tag = target.tagName;
  return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT';
}

const NAV_LINK_CLASS = cn(
  'inline-flex min-h-11 min-w-11 items-center rounded-control px-3 text-sm font-medium',
  'text-text-soft outline-none hover:bg-surface-sunk hover:text-text',
  'focus-visible:ring-2 focus-visible:ring-focus-ring',
);

export function AppShell({ children }: AppShellProps) {
  const { logout, user } = useAuth();
  const { theme, setTheme, themes } = useTheme();
  const navigate = useNavigate();
  const [paletteOpen, setPaletteOpen] = useState(false);
  // An `adminOnly` route redirects a user back to `/`, so offering it in the
  // [cfg] menu or the palette would only advertise a dead end (phase 10).
  const visible = appRoutes.filter((r) => r.adminOnly !== true || user?.role === 'admin');
  const nav = navRoutes(visible);
  const cfg = cfgRoutes(visible);
  const commands = commandRoutes(visible);

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent): void => {
      if (e.key !== 'k' || e.ctrlKey || e.metaKey || e.altKey) return;
      if (isEditableTarget(e.target)) return;
      e.preventDefault();
      setPaletteOpen((open) => !open);
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);

  const runCommand = useCallback(
    (path: string) => {
      setPaletteOpen(false);
      navigate(path);
    },
    [navigate],
  );

  return (
    <div className="flex h-full min-h-0 flex-col bg-bg text-text">
      <header className="flex shrink-0 items-center gap-2 border-b border-rule bg-surface px-3 py-1.5">
        {/* The wordmark is the plant-wide entry point (phase 9 executive view). */}
        <NavLink
          to="/executive"
          className={cn(
            // min-w-0 + truncate: at the §6.9 320px floor the wordmark, nav and
            // action cluster together exceed the viewport and the page gained a
            // horizontal scrollbar. The brand is the only element here that can
            // give way — nav already scrolls and the actions are load-bearing.
            'type-display min-w-0 shrink truncate rounded-control px-1 text-sm uppercase tracking-widest text-text',
            'outline-none focus-visible:ring-2 focus-visible:ring-focus-ring',
          )}
        >
          Smart PID
        </NavLink>
        <nav aria-label="Navegação principal" className="flex min-w-0 items-center gap-1 overflow-x-auto">
          {nav.map((route) => (
            <NavLink
              key={route.path}
              to={route.path}
              end={route.path === '/'}
              className={({ isActive }) => cn(NAV_LINK_CLASS, isActive && 'bg-surface-sunk text-text')}
            >
              {route.nav.label}
            </NavLink>
          ))}
        </nav>
        <div className="ml-auto flex shrink-0 items-center gap-1">
          <Button
            variant="ghost"
            aria-label="Comandos"
            aria-keyshortcuts="k"
            onClick={() => setPaletteOpen(true)}
          >
            <span aria-hidden="true" className="numeric text-xs">
              [k]
            </span>
          </Button>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" aria-label="Configurações">
                <span aria-hidden="true" className="numeric text-xs">
                  [cfg]
                </span>
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
      </header>

      <main className="flex min-h-0 flex-1 flex-col">{children}</main>

      {/* Admin-only, once per session, and only when the roster actually loaded. */}
      <WelcomeGate />

      <CommandDialog open={paletteOpen} onOpenChange={setPaletteOpen}>
        <CommandInput />
        <CommandList>
          <CommandEmpty />
          <CommandGroup heading="Navegação">
            {commands.map((route) => (
              <CommandItem
                key={route.path}
                value={[route.command.label, ...(route.command.keywords ?? [])].join(' ')}
                onSelect={() => runCommand(route.path)}
              >
                {route.command.label}
              </CommandItem>
            ))}
          </CommandGroup>
        </CommandList>
      </CommandDialog>
    </div>
  );
}


