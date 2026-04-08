"use client"

import Image from 'next/image'
import { useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Activity, DollarSign, Globe2, Layers3, LayoutDashboard, Settings2, Waypoints } from 'lucide-react'
import { apiRequest, type PublicBranding } from '@/lib/api'
import { clearStoredToken } from '@/lib/auth'
import { useI18n } from '@/lib/i18n'
import type { DashboardView } from '@/components/shell/dashboard-view-shell'

export function DashboardShell({
  children,
  activeView,
  onViewChange,
  onViewIntent,
}: {
  children: React.ReactNode
  activeView: DashboardView
  onViewChange: (view: DashboardView) => void
  onViewIntent?: (view: DashboardView) => void
}) {
  const { locale, setLocale, t } = useI18n()
  const { data: branding } = useQuery({ queryKey: ['public-branding'], queryFn: () => apiRequest<PublicBranding>('/public/branding') })
  const siteName = branding?.site_name?.trim() || 'Lens'
  const logoUrl = branding?.logo_url?.trim() || '/logo.svg'

  const items = [
    { key: 'overview' as DashboardView, label: t.dashboard, icon: LayoutDashboard },
    { key: 'requests' as DashboardView, label: t.requests, icon: Activity },
    { key: 'channels' as DashboardView, label: t.channels, icon: Waypoints },
    { key: 'groups' as DashboardView, label: t.groups, icon: Layers3 },
    { key: 'model-prices' as DashboardView, label: t.modelPrices, icon: DollarSign },
    { key: 'settings' as DashboardView, label: t.settings, icon: Settings2 }
  ]

  useEffect(() => {
    const activeLabel = items.find((item) => item.key === activeView)?.label ?? t.dashboard
    document.title = `${activeLabel} - ${siteName}`
  }, [activeView, items, siteName, t.dashboard])

  return (
    <div className="mx-auto flex h-dvh max-w-6xl flex-col overflow-hidden px-3 md:grid md:grid-cols-[auto_1fr] md:gap-6 md:px-6">
      <aside className="relative z-50 md:min-h-screen">
        <nav className="fixed bottom-6 left-1/2 z-20 flex -translate-x-1/2 items-center gap-1 rounded-3xl border border-[var(--line)] bg-[var(--panel-strong)] p-3 shadow-[var(--shadow-lg)] md:sticky md:top-30 md:left-auto md:bottom-auto md:translate-x-0 md:flex-col md:gap-3">
            {items.map((item) => {
              const Icon = item.icon
              const active = activeView === item.key
              return (
                <button
                  key={item.key}
                  type="button"
                  onClick={() => onViewChange(item.key)}
                  onMouseEnter={() => onViewIntent?.(item.key)}
                  className={
                    'group relative z-10 flex rounded-2xl p-2 md:p-3 transition-colors duration-150 ' +
                    (active
                      ? 'bg-[var(--accent-2)] text-[var(--text)] shadow-[var(--shadow-sm)]'
                      : 'text-[var(--muted)] hover:bg-[var(--panel-soft)] hover:text-[var(--text)]')
                  }
                  title={item.label}
                >
                  <Icon size={20} />
                </button>
              )
            })}
          </nav>
      </aside>

      <main className="flex min-h-0 w-full min-w-0 flex-1 flex-col">
          <header className="my-6 flex flex-none items-center gap-x-2 px-2">
            <Image src={logoUrl} alt={siteName} width={48} height={48} className="h-12 w-12 rounded-2xl object-cover" unoptimized={logoUrl !== '/logo.svg'} />
            <div className="min-w-0 flex-1 overflow-hidden">
              <h1 className="text-3xl font-bold tracking-tight text-[var(--text)]">{items.find((item) => item.key === activeView)?.label ?? t.dashboard}</h1>
            </div>
            <div className="ml-auto flex items-center gap-2">
              <button
                type="button"
                className="inline-flex h-9 w-9 items-center justify-center rounded-xl text-[var(--muted)] transition-none hover:bg-transparent hover:text-[var(--text)]"
                onClick={() => setLocale(locale === 'zh-CN' ? 'en-US' : 'zh-CN')}
                title={locale === 'zh-CN' ? '切换到英文' : 'Switch to Chinese'}
              >
                <Globe2 size={16} />
              </button>
              <button
                type="button"
                className="inline-flex h-9 items-center rounded-xl px-3 text-sm text-[var(--muted)] transition-none hover:bg-transparent hover:text-[var(--text)]"
                onClick={() => {
                  clearStoredToken()
                  window.location.href = '/login'
                }}
              >
                {t.signOut}
              </button>
            </div>
          </header>
          <div className="hide-scrollbar h-full min-h-0 flex-1 overflow-y-auto overscroll-contain rounded-t-3xl pb-24 md:pb-4">
            {children}
          </div>
      </main>
    </div>
  )
}
