import type { ReactNode } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { AuthProvider } from '@/auth/AuthContext';
import { RealtimeContext, type RealtimeContextValue } from '@/realtime/RealtimeProvider';
import { createFrameCache } from '@/realtime/frameCache';
import { ThemeProvider } from '@/theme/ThemeProvider';
import type { AnyEnvelope, RealtimeType } from '@/lib/envelope';

/**
 * Shared unit-test scaffolding. The real `RealtimeProvider` owns a WebSocket;
 * component tests inject a hand-driven context instead so envelopes can be
 * emitted synchronously without a socket stub.
 *
 * The fake keeps the real `FrameCache`, so `subscribe`/`replay` hand a late
 * subscriber the last frame per (type, loop_id) exactly like the provider. A
 * fake without it would let a consumer that silently drops the §7 replay pass.
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
  overrides: Partial<
    Pick<RealtimeContextValue, 'phase' | 'connected' | 'live' | 'stale' | 'staleSince'>
  > = {},
): FakeRealtime {
  const subs = new Map<RealtimeType, Set<(env: AnyEnvelope) => void>>();
  const frames = createFrameCache();
  // `stale` defaults to the honest derivation of `staleSince`, so a test that
  // only sets one of them cannot end up with a fake claiming both fresh and
  // frozen.
  const staleSince = overrides.staleSince ?? null;
  const value: RealtimeContextValue = {
    phase: overrides.phase ?? 'live',
    connected: overrides.connected ?? true,
    live: overrides.live ?? true,
    stale: overrides.stale ?? staleSince !== null,
    staleSince,
    subscribe(type, handler) {
      const set = subs.get(type) ?? new Set();
      set.add(handler);
      subs.set(type, set);
      frames.replay(type, handler);
      return () => {
        set.delete(handler);
      };
    },
    replay(type, handler) {
      frames.replay(type, handler);
    },
    lastSeenTs: () => null,
  };
  return {
    value,
    emit(env) {
      frames.put(env);
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
