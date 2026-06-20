import { useTheme } from '../../theme/ThemeProvider';

export function ThemeSwitcher() {
  const { theme, setTheme, themes } = useTheme();
  return (
    <select
      aria-label="Theme"
      value={theme}
      onChange={(e) => setTheme(e.target.value as typeof theme)}
      className="h-8 rounded-none border border-border bg-field-bg px-2 font-[inherit] text-sm text-text transition-colors duration-200 hover:border-border-strong focus:outline-none focus:ring-2 focus:ring-border-strong"
    >
      {themes.map((t) => (
        <option key={t.id} value={t.id}>
          {t.label}
        </option>
      ))}
    </select>
  );
}
