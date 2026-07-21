import { useTheme } from "../hooks/useTheme";

const OPTIONS = [
  { value: "system", label: "System" },
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
];

export default function ThemeControl() {
  const { preference, setPreference } = useTheme();
  return (
    <fieldset className="theme-control">
      <legend className="text-sm font-medium text-gray-300">Theme</legend>
      <p className="mt-1 text-sm text-muted-text">System follows your device appearance and updates automatically.</p>
      <div className="theme-options" role="radiogroup" aria-label="Theme">
        {OPTIONS.map(option => (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={preference === option.value}
            className="theme-option"
            onClick={() => setPreference(option.value)}
          >
            {option.label}
          </button>
        ))}
      </div>
    </fieldset>
  );
}
