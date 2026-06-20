import { useOpcuaStatus } from '../api/executive';
import { AppShell } from '../components/shell/AppShell';
import { SettingsForm } from '../features/settings/SettingsForm';
import './SettingsPage.css';

export function SettingsPage(): JSX.Element {
  const opcQ = useOpcuaStatus();
  const opcDown = opcQ.data ? opcQ.data.state !== 'ONLINE' : false;
  return (
    <AppShell opcDown={opcDown}>
      <div className="settings-page">
        <header className="settings-page__header">
          <h1>Settings</h1>
        </header>
        <SettingsForm />
      </div>
    </AppShell>
  );
}
