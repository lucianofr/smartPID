import { useTheme } from '../../theme/ThemeProvider';

export function ThemeSwitcher() {
  const { theme, setTheme, themes } = useTheme();
  return (
    <select
      aria-label="Theme"
      value={theme}
      onChange={(e) => setTheme(e.target.value as typeof theme)}
      style={{
        background: 'var(--field-bg)',
        color: 'var(--text)',
        border: '1px solid var(--border)',
        font: 'inherit',
        fontSize: 'var(--text-sm)',
        padding: '2px var(--sp-2)',
      }}
    >
      {themes.map((t) => (
        <option key={t.id} value={t.id}>
          {t.label}
        </option>
      ))}
    </select>
  );
}
