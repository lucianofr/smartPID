import type { ReactNode } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { AuthProvider } from '@/auth/AuthContext';
import { RealtimeContext, type RealtimeContextValue } from '@/realtime/RealtimeProvider';
import { ThemeProvider } from '@/theme/ThemeProvider';
import type { AnyEnvelope, RealtimeType } from '@/lib/envelope';

/**
 * Shared unit-test scaffolding. The real `RealtimeProvider` owns a WebSocket;
 * component tests inject a hand-driven context instead so envelopes can be
 * emitted synchronously without a socket stub.
 */

export function createQueryClient(): QueryClient {
  return new QueryClient({
    // staleTime keeps preseeded `setQueryData` fixtures from firing a real fetch.
    defaultOptions: { queries: { retry: false, gcTime: 0, staleTime: Number.POSITIVE_INFINITY } },
  });
}

export interface FakeRealtime {
  value: RealtimeContextValue;
  /** Push one envelope to every subscriber of its type. */
  emit(env: AnyEnvelope): void;
}

export function createFakeRealtime(
  overrides: Partial<Pick<RealtimeContextValue, 'phase' | 'connected' | 'live'>> = {},
): FakeRealtime {
  const subs = new Map<RealtimeType, Set<(env: AnyEnvelope) => void>>();
  const value: RealtimeContextValue = {
    phase: overrides.phase ?? 'live',
    connected: overrides.connected ?? true,
    live: overrides.live ?? true,
    subscribe(type, handler) {
      const set = subs.get(type) ?? new Set();
      set.add(handler);
      subs.set(type, set);
      return () => {
        set.delete(handler);
      };
    },
    lastSeenTs: () => null,
  };
  return {
    value,
    emit(env) {
      subs.get(env.type)?.forEach((h) => h(env));
    },
  };
}

export interface TestProvidersProps {
  children: ReactNode;
  queryClient?: QueryClient;
  realtime?: RealtimeContextValue;
  initialEntries?: string[];
}

export function TestProviders({
  children,
  queryClient,
  realtime,
  initialEntries = ['/'],
}: TestProvidersProps) {
  const client = queryClient ?? createQueryClient();
  const rt = realtime ?? createFakeRealtime().value;
  return (
    <ThemeProvider>
      <QueryClientProvider client={client}>
        <AuthProvider>
          <MemoryRouter initialEntries={initialEntries}>
            <RealtimeContext.Provider value={rt}>{children}</RealtimeContext.Provider>
          </MemoryRouter>
        </AuthProvider>
      </QueryClientProvider>
    </ThemeProvider>
  );
}
