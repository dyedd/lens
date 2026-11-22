export type Theme = "light" | "dark";

/** Keep in sync with the pre-paint bootstrap script in index.html. */
export const THEME_STORAGE_KEY = "lens_theme";
export const SYSTEM_COLOR_SCHEME_QUERY = "(prefers-color-scheme: dark)";

export function applyTheme(override: Theme | null) {
  const root = document.documentElement;
  const dark =
    override === null
      ? window.matchMedia(SYSTEM_COLOR_SCHEME_QUERY).matches
      : override === "dark";
  root.classList.toggle("dark", dark);
  const colorScheme = override ?? "light dark";
  root.style.colorScheme = colorScheme;
  document
    .querySelector<HTMLMetaElement>('meta[name="color-scheme"]')
    ?.setAttribute("content", colorScheme);
}

export function setTheme(theme: Theme) {
  const systemPrefersDark = window.matchMedia(
    SYSTEM_COLOR_SCHEME_QUERY,
  ).matches;
  let override: Theme | null = theme;
  try {
    const storedTheme = window.localStorage.getItem(THEME_STORAGE_KEY);
    if (
      (storedTheme === "light" || storedTheme === "dark") &&
      systemPrefersDark === (theme === "dark")
    ) {
      window.localStorage.removeItem(THEME_STORAGE_KEY);
      override = null;
    } else {
      window.localStorage.setItem(THEME_STORAGE_KEY, theme);
    }
  } catch {
    // Storage can be blocked while the page can still apply the theme.
  }
  applyTheme(override);
}
