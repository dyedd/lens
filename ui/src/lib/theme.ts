export type Theme = "light" | "dark";

export const THEME_STORAGE_KEY = "lens_theme";

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

export function getThemeBootstrapScript() {
  const storageKey = JSON.stringify(THEME_STORAGE_KEY);

  return `(() => {
    try {
      var stored = localStorage.getItem(${storageKey});
      var dark = stored === "dark" || (stored !== "light" && window.matchMedia("(prefers-color-scheme: dark)").matches);
      var root = document.documentElement;
      root.classList.toggle("dark", dark);
      root.style.colorScheme = dark ? "dark" : "light";
    } catch (error) {
      // localStorage may throw on quota/private mode; default theme still applies
    }
  })();`;
}
