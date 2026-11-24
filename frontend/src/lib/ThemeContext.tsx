import { createContext, useContext, useEffect, useMemo } from "react";
import {
  applyTheme,
  SYSTEM_COLOR_SCHEME_QUERY,
  setTheme,
  THEME_STORAGE_KEY,
  type Theme,
} from "@/lib/theme";

type ThemeValue = {
  toggleTheme: () => void;
};

const ThemeContext = createContext<ThemeValue | null>(null);

/** Provides color-theme controls to client components. */
export function ThemeProvider({ children }: { children: React.ReactNode }) {
  useEffect(() => {
    const preference = window.matchMedia(SYSTEM_COLOR_SCHEME_QUERY);
    function syncTheme() {
      let stored: string | null;
      try {
        stored = window.localStorage.getItem(THEME_STORAGE_KEY);
      } catch {
        stored = document.documentElement.style.colorScheme;
      }
      applyTheme(stored === "light" || stored === "dark" ? stored : null);
    }
    function handleThemeStorageChange(event: StorageEvent) {
      if (event.key !== THEME_STORAGE_KEY && event.key !== null) return;
      try {
        if (event.storageArea !== window.localStorage) return;
      } catch {
        return;
      }
      syncTheme();
    }

    syncTheme();
    preference.addEventListener("change", syncTheme);
    window.addEventListener("storage", handleThemeStorageChange);
    return () => {
      preference.removeEventListener("change", syncTheme);
      window.removeEventListener("storage", handleThemeStorageChange);
    };
  }, []);

  const value = useMemo<ThemeValue>(
    () => ({
      toggleTheme: () => {
        const nextTheme: Theme = document.documentElement.classList.contains(
          "dark",
        )
          ? "light"
          : "dark";
        setTheme(nextTheme);
      },
    }),
    [],
  );

  return (
    <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
  );
}

/** Returns the active color-theme controls. */
export function useTheme() {
  const value = useContext(ThemeContext);
  if (!value) {
    throw new Error("useTheme must be used within ThemeProvider");
  }
  return value;
}
