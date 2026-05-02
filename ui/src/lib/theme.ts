export type Theme = 'light' | 'dark'

export const THEME_STORAGE_KEY = 'lens_theme'

export function isTheme(value: string | null): value is Theme {
  return value === 'light' || value === 'dark'
}

export function getStoredTheme() {
  if (typeof window === 'undefined') {
    return null
  }

  try {
    const theme = window.localStorage.getItem(THEME_STORAGE_KEY)
    return isTheme(theme) ? theme : null
  } catch {
    return null
  }
}

export function getSystemTheme(): Theme {
  if (typeof window === 'undefined') {
    return 'light'
  }

  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

export function applyTheme(theme: Theme) {
  const root = document.documentElement
  root.classList.toggle('dark', theme === 'dark')
  root.style.colorScheme = theme
}

export function setTheme(theme: Theme) {
  try {
    window.localStorage.setItem(THEME_STORAGE_KEY, theme)
  } catch {
    // Ignore storage failures and still apply the visual theme.
  }

  applyTheme(theme)
}

export function getThemeBootstrapScript() {
  const storageKey = JSON.stringify(THEME_STORAGE_KEY)

  return `(() => {
    try {
      var stored = localStorage.getItem(${storageKey});
      var dark = stored === "dark" || (stored !== "light" && window.matchMedia("(prefers-color-scheme: dark)").matches);
      var root = document.documentElement;
      root.classList.toggle("dark", dark);
      root.style.colorScheme = dark ? "dark" : "light";
    } catch (error) {}
  })();`
}
