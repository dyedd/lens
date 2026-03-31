"use client"

import { createContext, useContext, useEffect, useMemo, useState } from 'react'

export type Locale = 'zh-CN' | 'en-US'

type Copy = {
  appName: string
  loginTitle: string
  loginSubtitle: string
  username: string
  password: string
  signIn: string
  signingIn: string
  dashboard: string
  requests: string
  channels: string
  groups: string
  settings: string
  signOut: string
  overview: string
  language: string
  refresh: string
}

const messages: Record<Locale, Copy> = {
  'zh-CN': {
    appName: '',
    loginTitle: '统一管理渠道、模型组与系统配置',
    loginSubtitle: 'OpenAI Chat / OpenAI Responses / Anthropic / Gemini',
    username: '用户名',
    password: '密码',
    signIn: '登录',
    signingIn: '登录中...',
    dashboard: '总览',
    requests: '请求日志',
    channels: '渠道管理',
    groups: '模型组',
    settings: '系统设置',
    signOut: '退出登录',
    overview: '总览',
    language: '语言',
    refresh: '刷新'
  },
  'en-US': {
    appName: '',
    loginTitle: 'Manage channels, model groups, and system settings',
    loginSubtitle: 'OpenAI Chat / OpenAI Responses / Anthropic / Gemini',
    username: 'Username',
    password: 'Password',
    signIn: 'Sign in',
    signingIn: 'Signing in...',
    dashboard: 'Overview',
    requests: 'Requests',
    channels: 'Channels',
    groups: 'Groups',
    settings: 'Settings',
    signOut: 'Sign out',
    overview: 'Overview',
    language: 'Language',
    refresh: 'Refresh'
  }
}

type I18nValue = {
  locale: Locale
  setLocale: (locale: Locale) => void
  t: Copy
}

const I18nContext = createContext<I18nValue | null>(null)

export function I18nProvider({ children }: { children: React.ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>('zh-CN')

  useEffect(() => {
    const stored = window.localStorage.getItem('lens_locale') as Locale | null
    if (stored === 'zh-CN' || stored === 'en-US') {
      setLocaleState(stored)
    }
  }, [])

  const value = useMemo<I18nValue>(() => ({
    locale,
    setLocale: (nextLocale) => {
      window.localStorage.setItem('lens_locale', nextLocale)
      setLocaleState(nextLocale)
    },
    t: messages[locale]
  }), [locale])

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}

export function useI18n() {
  const value = useContext(I18nContext)
  if (!value) {
    throw new Error('useI18n must be used within I18nProvider')
  }
  return value
}
