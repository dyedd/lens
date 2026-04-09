"use client"

import Image from 'next/image'
import { useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Activity, DollarSign, Globe2, Layers3, LayoutDashboard, Settings2, Waypoints } from 'lucide-react'
import { apiRequest, type PublicBranding } from '@/lib/api'
import { clearStoredToken } from '@/lib/auth'
import { useI18n } from '@/lib/i18n'
import type { DashboardView } from '@/components/shell/dashboard-view-shell'
import { cn } from '@/lib/cn'

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
    <div className="mx-auto flex h-dvh max-w-[960px] flex-col overflow-hidden px-4 md:grid md:grid-cols-[auto_1fr] md:gap-6 md:px-6">
      <aside className="relative z-50 md:min-h-screen pt-4 md:pt-10">
        <nav className="fixed bottom-6 left-1/2 z-20 flex -translate-x-1/2 items-center gap-2 rounded-full border border-[var(--line)] bg-[rgba(255,255,255,0.85)] p-2 shadow-[var(--shadow-lg)] backdrop-blur-xl md:sticky md:top-12 md:left-auto md:bottom-auto md:translate-x-0 md:flex-col md:gap-4 md:rounded-[var(--radius-lg)]">
            {items.map((item) => {
              const Icon = item.icon
              const active = activeView === item.key
              return (
                <button
                  key={item.key}
                  type="button"
                  onClick={() => onViewChange(item.key)}
                  onMouseEnter={() => onViewIntent?.(item.key)}
                  className={cn(
                    'group relative z-10 flex rounded-full p-3 transition-all duration-300 md:rounded-[var(--radius-md)]',
                    active
                      ? 'bg-[var(--accent)] text-white shadow-[var(--shadow-sm)] scale-105'
                      : 'text-[var(--muted)] hover:bg-[var(--panel-soft)] hover:text-[var(--text)]'
                  )}
                  title={item.label}
                >
                  <Icon size={22} strokeWidth={active ? 2.5 : 2} />
                  {active && (
                    <span className="absolute -bottom-1 left-1/2 h-1 w-1 -translate-x-1/2 rounded-full bg-[var(--accent)] md:hidden" />
                  )}
                </button>
              )
            })}
          </nav>
      </aside>

      <main className="flex min-h-0 w-full min-w-0 flex-1 flex-col">
          <header className="mt-8 mb-6 flex flex-none items-center gap-x-4 px-2">
            <Image src={logoUrl} alt={siteName} width={64} height={64} className="h-[52px] w-[52px] object-contain" unoptimized={logoUrl !== '/logo.svg'} />
            <div className="flex shrink-0 items-center gap-3 pr-2">
              <h1 className="text-[24px] font-bold tracking-tight text-[var(--text)]">{items.find((item) => item.key === activeView)?.label ?? t.dashboard}</h1>
            </div>
            <div id="header-portal" className="min-w-0 flex-1 flex items-center justify-end" />
            <div className="ml-auto flex shrink-0 items-center gap-2 pl-2 border-l border-[var(--line)]">
              <button
                type="button"
                className="inline-flex h-9 w-9 items-center justify-center rounded-full text-[var(--muted)] transition-all hover:bg-[var(--panel-soft)] hover:text-[var(--text)]"
                onClick={() => setLocale(locale === 'zh-CN' ? 'en-US' : 'zh-CN')}
                title={locale === 'zh-CN' ? '切换到英文' : 'Switch to Chinese'}
              >
                <Globe2 size={18} />
              </button>
              <button
                type="button"
                className="inline-flex h-9 items-center rounded-full px-4 text-[13px] font-medium text-[var(--muted)] transition-all hover:bg-[var(--panel-soft)] hover:text-[var(--danger)]"
                onClick={() => {
                  clearStoredToken()
                  window.location.href = '/login'
                }}
              >
                {t.signOut}
              </button>
            </div>
          </header>
          <div className="hide-scrollbar h-full min-h-0 flex-1 overflow-y-auto overscroll-contain rounded-t-[var(--radius-lg)] pb-28 pt-2 md:pb-8">
            {children}
          </div>
      </main>
    </div>
  )
}
