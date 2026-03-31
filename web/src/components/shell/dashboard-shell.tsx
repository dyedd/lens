"use client"

import Image from 'next/image'
import { Activity, Globe2, KeyRound, Layers3, LayoutDashboard, Settings2, Waypoints } from 'lucide-react'
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

  const items = [
    { key: 'overview' as DashboardView, label: t.dashboard, icon: LayoutDashboard },
    { key: 'requests' as DashboardView, label: t.requests, icon: Activity },
    { key: 'channels' as DashboardView, label: t.channels, icon: Waypoints },
    { key: 'groups' as DashboardView, label: t.groups, icon: Layers3 },
    { key: 'keys' as DashboardView, label: t.keys, icon: KeyRound },
    { key: 'settings' as DashboardView, label: t.settings, icon: Settings2 }
  ]

  return (
    <div className="min-h-screen px-4 py-4 md:px-5">
      <div className="mx-auto flex w-full max-w-[1240px] gap-5">
        <aside className="sticky top-7 hidden h-fit self-start md:block">
          <nav className="flex w-[76px] flex-col items-center gap-2.5 rounded-[26px] border border-[var(--line)] bg-[var(--panel-strong)] p-2.5 shadow-[var(--shadow-lg)]">
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
                    'group relative flex h-12 w-12 items-center justify-center rounded-[16px] transition-colors duration-150 ' +
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

        <main className="min-h-screen flex-1 rounded-[28px] border border-[var(--line)] bg-[rgba(255,253,249,0.72)] p-5 shadow-[var(--shadow-lg)] md:p-6">
          <header className="mb-6 flex items-start justify-between gap-5">
            <div className="flex items-center gap-4">
              <Image src="/logo.svg" alt="Lens" width={42} height={42} className="h-[42px] w-[42px]" />
              <div>
                <p className="text-xs uppercase tracking-[0.24em] text-[var(--muted)]">{t.appName}</p>
                <h1 className="mt-1 text-[26px] font-semibold leading-none tracking-[-0.03em] text-[var(--text)] md:text-[30px]">{items.find((item) => item.key === activeView)?.label ?? t.dashboard}</h1>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <button
                type="button"
                className="inline-flex h-10 items-center gap-2 rounded-full border border-[var(--line)] bg-[var(--panel-strong)] px-4 text-sm text-[var(--text)] shadow-[var(--shadow-sm)]"
                onClick={() => setLocale(locale === 'zh-CN' ? 'en-US' : 'zh-CN')}
              >
                <Globe2 size={15} />
                <span>{locale === 'zh-CN' ? 'EN' : '中'}</span>
              </button>
              <button
                type="button"
                className="inline-flex h-10 items-center rounded-full border border-[var(--line)] bg-[var(--panel-strong)] px-4 text-sm text-[var(--muted)] shadow-[var(--shadow-sm)]"
                onClick={() => {
                  clearStoredToken()
                  window.location.href = '/login'
                }}
              >
                {t.signOut}
              </button>
            </div>
          </header>
          {children}
        </main>
      </div>
    </div>
  )
}
