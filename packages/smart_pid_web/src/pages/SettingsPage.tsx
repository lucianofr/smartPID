import { useOpcuaStatus } from '../api/executive';
import { AppShell } from '../components/shell/AppShell';
import { SettingsForm } from '../features/settings/SettingsForm';

export function SettingsPage(): JSX.Element {
  const opcQ = useOpcuaStatus();
  const opcDown = opcQ.data ? opcQ.data.state !== 'ONLINE' : false;
  return (
    <AppShell opcDown={opcDown}>
      <div className="flex flex-col gap-6">
        <header>
          <h1 className="m-0 font-semibold text-text" style={{ fontSize: 'var(--text-xl)' }}>
            Settings
          </h1>
        </header>
        <SettingsForm />
      </div>
    </AppShell>
  );
}
