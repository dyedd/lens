"use client"

import { useQuery } from '@tanstack/react-query'
import { apiRequest, RouteSnapshot } from '@/lib/api'

export function OverviewScreen() {
  const { data } = useQuery({
    queryKey: ['router'],
    queryFn: () => apiRequest<RouteSnapshot>('/router')
  })

  return (
    <section className="grid gap-6">
      <div>
        <p className="text-sm uppercase tracking-[0.2em] text-[var(--accent-2)]">Overview</p>
        <h2 className="mt-2 text-4xl font-semibold">Gateway status, load balance state, and operating surface</h2>
      </div>
      <div className="grid gap-4 md:grid-cols-3">
        {[
          { title: 'Protocols', value: data?.routes.length ?? '-' },
          { title: 'Weighted providers', value: data?.routes.reduce((acc, route) => acc + route.provider_ids.length, 0) ?? '-' },
          { title: 'Health entries', value: data?.health.length ?? '-' }
        ].map((item) => (
          <div key={item.title} className="rounded-[24px] border border-[var(--line)] bg-[var(--panel-strong)] p-5">
            <p className="text-sm text-[var(--muted)]">{item.title}</p>
            <strong className="mt-3 block text-4xl">{item.value}</strong>
          </div>
        ))}
      </div>
      <div className="rounded-[24px] border border-[var(--line)] bg-[var(--panel-strong)] p-5">
        <p className="text-sm text-[var(--muted)]">Routing pools</p>
        <div className="mt-4 grid gap-3">
          {data?.routes.map((route) => (
            <div key={route.protocol} className="rounded-2xl border border-[var(--line)] bg-white/70 px-4 py-3">
              <strong>{route.protocol}</strong>
              <p className="mt-2 text-sm text-[var(--muted)]">{route.provider_ids.join(' -> ') || 'no providers'}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
