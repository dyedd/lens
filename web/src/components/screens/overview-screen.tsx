"use client"

import { useQuery } from '@tanstack/react-query'
import { OverviewMetrics, RouteSnapshot, apiRequest } from '@/lib/api'

export function OverviewScreen() {
  const { data: router } = useQuery({
    queryKey: ['router'],
    queryFn: () => apiRequest<RouteSnapshot>('/router')
  })
  const { data: overview } = useQuery({
    queryKey: ['overview'],
    queryFn: () => apiRequest<OverviewMetrics>('/overview')
  })

  const cards = [
    { title: 'Total requests', value: overview?.total_requests ?? '-' },
    { title: 'Successful requests', value: overview?.successful_requests ?? '-' },
    { title: 'Failed requests', value: overview?.failed_requests ?? '-' },
    { title: 'Avg latency', value: overview ? String(overview.avg_latency_ms) + ' ms' : '-' },
    { title: 'Enabled providers', value: overview?.enabled_providers ?? '-' },
    { title: 'Active gateway keys', value: overview?.active_gateway_keys ?? '-' }
  ]

  return (
    <section className="grid gap-6">
      <div>
        <p className="text-sm uppercase tracking-[0.2em] text-[var(--accent-2)]">Overview</p>
        <h2 className="mt-2 text-4xl font-semibold">Gateway status, load balance state, and operating surface</h2>
      </div>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {cards.map((item) => (
          <div key={item.title} className="rounded-[24px] border border-[var(--line)] bg-[var(--panel-strong)] p-5">
            <p className="text-sm text-[var(--muted)]">{item.title}</p>
            <strong className="mt-3 block text-4xl">{item.value}</strong>
          </div>
        ))}
      </div>
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
        <div className="rounded-[24px] border border-[var(--line)] bg-[var(--panel-strong)] p-5">
          <p className="text-sm text-[var(--muted)]">Routing pools</p>
          <div className="mt-4 grid gap-3">
            {router?.routes.map((route) => (
              <div key={route.protocol} className="rounded-2xl border border-[var(--line)] bg-white/70 px-4 py-3">
                <strong>{route.protocol}</strong>
                <p className="mt-2 text-sm text-[var(--muted)]">{route.provider_ids.join(' -> ') || 'no providers'}</p>
              </div>
            ))}
          </div>
        </div>
        <div className="rounded-[24px] border border-[var(--line)] bg-[var(--panel-strong)] p-5">
          <p className="text-sm text-[var(--muted)]">Health state</p>
          <div className="mt-4 grid gap-3">
            {router?.health.map((item) => (
              <div key={item.provider_id} className="rounded-2xl border border-[var(--line)] bg-white/70 px-4 py-3">
                <strong>{item.provider_id}</strong>
                <p className="mt-2 text-sm text-[var(--muted)]">Failures: {item.consecutive_failures}</p>
                <p className="mt-1 text-sm text-[var(--muted)]">{item.last_error || 'No recent errors'}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  )
}
