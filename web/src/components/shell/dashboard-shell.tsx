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
    <div className="min-h-screen px-3 py-3 md:px-4 md:py-4">
      <div className="mx-auto grid min-h-[calc(100vh-1.5rem)] w-full max-w-[1640px] grid-cols-1 gap-4 xl:grid-cols-[276px_minmax(0,1fr)]">
        <aside className="rounded-[34px] border border-white/70 bg-[linear-gradient(180deg,rgba(255,255,255,0.78),rgba(244,248,253,0.74))] p-4 text-[var(--text)] shadow-[var(--shadow-lg)] backdrop-blur-[24px] xl:sticky xl:top-4 xl:h-[calc(100vh-2rem)]">
          <div className="rounded-[28px] border border-white/80 bg-[linear-gradient(180deg,rgba(248,251,255,0.92),rgba(239,245,252,0.78))] p-5 shadow-[inset_0_1px_0_rgba(255,255,255,0.85)]">
            <p className="text-xs uppercase tracking-[0.26em] text-[var(--accent)]">{t.appName}</p>
            <h1 className="mt-3 text-3xl font-semibold leading-tight">
              {locale === 'zh-CN' ? '聚合网关控制台' : 'Gateway control room'}
            </h1>
            <p className="mt-4 text-sm leading-6 text-[var(--muted)]">
              {locale === 'zh-CN'
                ? '左侧导航负责全局切换，右侧内容采用 iOS 风格分块、玻璃卡片和弹窗操作。'
                : 'Navigation stays on the left, while content uses an iOS-inspired glass layout and modal actions.'}
            </p>
          </div>
          <div className="mt-4 flex items-center justify-between rounded-[24px] border border-white/70 bg-[rgba(255,255,255,0.72)] px-4 py-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.85)]">
            <div>
              <p className="text-xs uppercase tracking-[0.2em] text-[var(--muted)]">{t.language}</p>
              <p className="mt-1 text-sm text-[var(--text)]">{locale === 'zh-CN' ? '简体中文' : 'English'}</p>
            </div>
            <button
              type="button"
              className="inline-flex items-center gap-2 rounded-full border border-white/80 bg-white px-3 py-2 text-sm text-[var(--text)] shadow-[0_10px_24px_rgba(24,46,79,0.08)] transition hover:translate-y-[-1px]"
              onClick={() => setLocale(locale === 'zh-CN' ? 'en-US' : 'zh-CN')}
            >
              <Globe2 size={15} />
              <span>{locale === 'zh-CN' ? 'EN' : '中'}</span>
            </button>
          </div>
          <nav className="mt-4 grid gap-2">
            {items.map((item) => {
              const Icon = item.icon
              const active = pathname === item.href
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={
                    'group flex items-center gap-3 rounded-[22px] px-4 py-3 transition ' +
                    (active
                      ? 'border border-white/75 bg-white text-[var(--text)] shadow-[0_18px_34px_rgba(24,46,79,0.12)]'
                      : 'text-[var(--muted)] hover:bg-white/60 hover:text-[var(--text)]')
                  }
                >
                  <span className={active ? 'rounded-xl bg-[rgba(47,111,237,0.1)] p-2 text-[var(--accent)]' : 'rounded-xl bg-[rgba(22,34,53,0.05)] p-2 group-hover:bg-white'}>
                    <Icon size={16} />
                  </span>
                  <span>{item.label}</span>
                </Link>
              )
            })}
          </nav>
          <button
            type="button"
            className="mt-6 w-full rounded-[22px] border border-white/75 bg-[rgba(255,255,255,0.72)] px-4 py-3 text-left text-[var(--muted)] transition hover:bg-white hover:text-[var(--text)]"
            onClick={() => {
              clearStoredToken()
              window.location.href = '/login'
            }}
          >
            {t.signOut}
          </button>
        </aside>
        <main className="rounded-[36px] border border-white/70 bg-[var(--panel)] p-4 shadow-[var(--shadow-lg)] backdrop-blur-[24px] md:p-6">
          {children}
        </main>
      </div>
    </div>
  )
}
