import { useCallback, useEffect, useState } from "react";

const FALLBACK = "system";

export function useTheme() {
  const api = window.MyBeaconTheme;
  const [preference, setPreferenceState] = useState(() => api?.getPreference?.() || FALLBACK);
  const [resolvedTheme, setResolvedTheme] = useState(() => document.documentElement.dataset.theme || "dark");

  useEffect(() => {
    const handleChange = event => {
      setPreferenceState(event.detail.preference);
      setResolvedTheme(event.detail.theme);
    };
    window.addEventListener("mybeacon-theme-change", handleChange);
    return () => window.removeEventListener("mybeacon-theme-change", handleChange);
  }, []);

  const setPreference = useCallback(value => {
    if (api) api.setPreference(value);
  }, [api]);

  return { preference, resolvedTheme, setPreference };
}
