export type Theme = "light" | "dark";

/** Keep in sync with the pre-paint bootstrap script in index.html. */
export const THEME_STORAGE_KEY = "lens_theme";

/** Persists and applies the selected color theme. */
export function setTheme(theme: Theme) {
  try {
    window.localStorage.setItem(THEME_STORAGE_KEY, theme);
  } catch {
    // localStorage may throw on quota/private mode; theme still applies via inline style
  }
  const root = document.documentElement;
  root.classList.toggle("dark", theme === "dark");
  root.style.colorScheme = theme;
}
