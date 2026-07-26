import { SettingsForm } from '@/features/settings/SettingsForm';

/**
 * Application preferences (`[cfg] › Settings`). Route-guarded `adminOnly`, and
 * the form re-checks `settings.manage` — the guard protects the URL, the
 * capability check protects the controls.
 */
export function SettingsPage() {
  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-y-auto">
      <header className="shrink-0 border-b border-rule px-3 py-2">
        <h1 className="type-display text-lg text-text">Configurações</h1>
        <p className="text-xs text-text-soft">
          Preferências locais deste navegador — não alteram o servidor.
        </p>
      </header>
      <SettingsForm />
    </div>
  );
}
