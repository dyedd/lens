"use client"

import { createContext, useContext, useMemo } from 'react'
import { setTheme, type Theme } from '@/lib/theme'

type ThemeValue = {
  toggleTheme: () => void
}

const ThemeContext = createContext<ThemeValue | null>(null)

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const value = useMemo<ThemeValue>(() => ({
    toggleTheme: () => {
      const nextTheme: Theme = document.documentElement.classList.contains('dark') ? 'light' : 'dark'
      setTheme(nextTheme)
    },
  }), [])

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}

export function useTheme() {
  const value = useContext(ThemeContext)
  if (!value) {
    throw new Error('useTheme must be used within ThemeProvider')
  }
  return value
}
