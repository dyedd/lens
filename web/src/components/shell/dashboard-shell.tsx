"use client"

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import Image from 'next/image'
import { Activity, Globe2, KeyRound, Layers3, LayoutDashboard, Settings2, Waypoints } from 'lucide-react'
import { clearStoredToken } from '@/lib/auth'
import { useI18n } from '@/lib/i18n'

export function DashboardShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const { locale, setLocale, t } = useI18n()

  const items = [
    { href: '/dashboard', label: t.dashboard, icon: LayoutDashboard },
    { href: '/dashboard/requests', label: t.requests, icon: Activity },
    { href: '/dashboard/channels', label: t.channels, icon: Waypoints },
    { href: '/dashboard/groups', label: t.groups, icon: Layers3 },
    { href: '/dashboard/keys', label: t.keys, icon: KeyRound },
    { href: '/dashboard/settings', label: t.settings, icon: Settings2 }
  ]

  return (
    <div className="min-h-screen px-4 py-5 md:px-6">
      <div className="mx-auto flex w-full max-w-[1280px] gap-6">
        <aside className="sticky top-8 hidden h-fit self-start md:block">
          <nav className="flex w-[82px] flex-col items-center gap-3 rounded-[28px] border border-[var(--line)] bg-[var(--panel-strong)] p-3 shadow-[var(--shadow-lg)]">
            {items.map((item) => {
              const Icon = item.icon
              const active = pathname === item.href
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={
                    'group relative flex h-14 w-14 items-center justify-center rounded-[18px] transition ' +
                    (active
                      ? 'bg-[var(--accent-2)] text-[var(--text)] shadow-[var(--shadow-sm)]'
                      : 'text-[var(--muted)] hover:bg-[var(--panel-soft)] hover:text-[var(--text)]')
                  }
                  title={item.label}
                >
                  <Icon size={22} />
                </Link>
              )
            })}
          </nav>
        </aside>

        <main className="min-h-screen flex-1 rounded-[32px] border border-[var(--line)] bg-[rgba(255,253,249,0.72)] p-6 shadow-[var(--shadow-lg)] md:p-8">
          <header className="mb-8 flex items-start justify-between gap-6">
            <div className="flex items-center gap-4">
              <Image src="/logo.svg" alt="Lens" width={46} height={46} className="h-[46px] w-[46px]" />
              <div>
                <p className="text-xs uppercase tracking-[0.24em] text-[var(--muted)]">{t.appName}</p>
                <h1 className="mt-1 text-2xl font-semibold text-[var(--text)] md:text-3xl">{items.find((item) => item.href === pathname)?.label ?? t.dashboard}</h1>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <button
                type="button"
                className="inline-flex h-11 items-center gap-2 rounded-full border border-[var(--line)] bg-[var(--panel-strong)] px-4 text-sm text-[var(--text)] shadow-[var(--shadow-sm)]"
                onClick={() => setLocale(locale === 'zh-CN' ? 'en-US' : 'zh-CN')}
              >
                <Globe2 size={15} />
                <span>{locale === 'zh-CN' ? 'EN' : '中'}</span>
              </button>
              <button
                type="button"
                className="inline-flex h-11 items-center rounded-full border border-[var(--line)] bg-[var(--panel-strong)] px-4 text-sm text-[var(--muted)] shadow-[var(--shadow-sm)]"
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
