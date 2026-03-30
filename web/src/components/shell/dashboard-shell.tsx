"use client"

import Link from 'next/link'
import { usePathname } from 'next/navigation'
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
      <div className="mx-auto grid min-h-[calc(100vh-2.5rem)] w-full max-w-[1540px] grid-cols-1 gap-5 xl:grid-cols-[280px_minmax(0,1fr)]">
        <aside className="rounded-[32px] border border-[var(--line)] bg-[linear-gradient(180deg,rgba(15,35,65,0.94),rgba(12,27,48,0.98))] p-5 text-white shadow-[var(--shadow-lg)] xl:sticky xl:top-5 xl:h-[calc(100vh-2.5rem)]">
          <div className="rounded-[28px] border border-white/10 bg-white/5 p-5">
            <p className="text-xs uppercase tracking-[0.26em] text-white/45">{t.appName}</p>
            <h1 className="mt-3 text-3xl font-semibold leading-tight">
              {locale === 'zh-CN' ? '多协议模型聚合控制台' : 'Multi-protocol gateway control room'}
            </h1>
            <p className="mt-4 text-sm leading-6 text-white/62">
              {locale === 'zh-CN'
                ? '参考 octopus 形态，聚焦渠道池、模型组、请求观测与网关访问控制。'
                : 'Octopus-inspired admin surface for channel pools, model groups, request observability, and gateway access.'}
            </p>
          </div>
          <div className="mt-5 flex items-center justify-between rounded-2xl border border-white/10 bg-white/5 px-4 py-3">
            <div>
              <p className="text-xs uppercase tracking-[0.2em] text-white/45">{t.language}</p>
              <p className="mt-1 text-sm text-white/88">{locale === 'zh-CN' ? '简体中文' : 'English'}</p>
            </div>
            <button
              type="button"
              className="inline-flex items-center gap-2 rounded-full border border-white/12 bg-white/10 px-3 py-2 text-sm text-white/85 transition hover:bg-white/16"
              onClick={() => setLocale(locale === 'zh-CN' ? 'en-US' : 'zh-CN')}
            >
              <Globe2 size={15} />
              <span>{locale === 'zh-CN' ? 'EN' : '中'}</span>
            </button>
          </div>
          <nav className="mt-5 grid gap-2">
            {items.map((item) => {
              const Icon = item.icon
              const active = pathname === item.href
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={
                    'group flex items-center gap-3 rounded-2xl px-4 py-3 transition ' +
                    (active
                      ? 'bg-[linear-gradient(135deg,rgba(47,111,237,0.28),rgba(19,162,168,0.16))] text-white shadow-[0_14px_30px_rgba(0,0,0,0.18)]'
                      : 'text-white/68 hover:bg-white/8 hover:text-white')
                  }
                >
                  <span className={active ? 'rounded-xl bg-white/14 p-2' : 'rounded-xl bg-white/6 p-2 group-hover:bg-white/10'}>
                    <Icon size={16} />
                  </span>
                  <span>{item.label}</span>
                </Link>
              )
            })}
          </nav>
          <button
            type="button"
            className="mt-6 w-full rounded-2xl border border-white/12 bg-white/7 px-4 py-3 text-left text-white/80 transition hover:bg-white/12"
            onClick={() => {
              clearStoredToken()
              window.location.href = '/login'
            }}
          >
            {t.signOut}
          </button>
        </aside>
        <main className="rounded-[32px] border border-[var(--line)] bg-[var(--panel)] p-4 shadow-[var(--shadow-lg)] backdrop-blur md:p-6">
          {children}
        </main>
      </div>
    </div>
  )
}
