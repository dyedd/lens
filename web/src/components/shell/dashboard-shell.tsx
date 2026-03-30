"use client"

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { Activity, KeyRound, Layers3, LayoutDashboard, Settings2, Waypoints } from 'lucide-react'
import { clearStoredToken } from '@/lib/auth'

const items = [
  { href: '/dashboard', label: 'Overview', icon: LayoutDashboard },
  { href: '/dashboard/requests', label: 'Requests', icon: Activity },
  { href: '/dashboard/channels', label: 'Channels', icon: Waypoints },
  { href: '/dashboard/groups', label: 'Groups', icon: Layers3 },
  { href: '/dashboard/keys', label: 'API Keys', icon: KeyRound },
  { href: '/dashboard/settings', label: 'Settings', icon: Settings2 }
]

export function DashboardShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()

  return (
    <div className="min-h-screen px-4 py-5 md:px-6">
      <div className="mx-auto grid min-h-[calc(100vh-2.5rem)] w-full max-w-7xl grid-cols-1 gap-4 lg:grid-cols-[260px_minmax(0,1fr)]">
        <aside className="rounded-[28px] border border-[var(--line)] bg-[var(--panel)] p-5 backdrop-blur lg:sticky lg:top-5 lg:h-[calc(100vh-2.5rem)]">
          <div className="mb-10">
            <p className="text-xs uppercase tracking-[0.22em] text-[var(--accent-2)]">Lens Admin</p>
            <h1 className="mt-3 text-3xl font-semibold">One hub for your native LLM channels</h1>
          </div>
          <nav className="grid gap-2">
            {items.map((item) => {
              const Icon = item.icon
              const active = pathname === item.href
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`flex items-center gap-3 rounded-2xl px-4 py-3 transition ${active ? 'bg-[var(--panel-strong)] text-[var(--text)] shadow-sm' : 'text-[var(--muted)] hover:bg-[var(--panel-strong)]'}`}
                >
                  <Icon size={18} />
                  <span>{item.label}</span>
                </Link>
              )
            })}
          </nav>
          <button
            type="button"
            className="mt-8 w-full rounded-full border border-[var(--line)] px-4 py-3 text-left text-[var(--muted)] hover:bg-[var(--panel-strong)]"
            onClick={() => {
              clearStoredToken()
              window.location.href = '/login'
            }}
          >
            Sign out
          </button>
        </aside>
        <main className="rounded-[28px] border border-[var(--line)] bg-[var(--panel)] p-5 backdrop-blur md:p-6">
          {children}
        </main>
      </div>
    </div>
  )
}
