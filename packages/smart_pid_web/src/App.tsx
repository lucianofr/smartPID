import { ThemeProvider } from '@/theme/ThemeProvider';

export function App() {
  return (
    <ThemeProvider>
      <main className="flex min-h-screen flex-col items-center justify-center gap-2 bg-bg text-text">
        <h1 className="type-display text-2xl">SMART PID</h1>
        <p className="text-sm text-text-soft">Fundação do rewrite — fase 2. Rotas chegam na fase 4.</p>
      </main>
    </ThemeProvider>
  );
}