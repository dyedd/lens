"use client"

import { Activity, Gauge, KeyRound, Layers3, Network } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { OverviewMetrics, RouteSnapshot, apiRequest } from '@/lib/api'
import { useI18n } from '@/lib/i18n'

export function OverviewScreen() {
  const { locale } = useI18n()
  const { data: router } = useQuery({ queryKey: ['router'], queryFn: () => apiRequest<RouteSnapshot>('/router') })
  const { data: overview } = useQuery({ queryKey: ['overview'], queryFn: () => apiRequest<OverviewMetrics>('/overview') })

  const cards = [
    { icon: Activity, title: locale === 'zh-CN' ? '总请求数' : 'Total requests', value: overview?.total_requests ?? '-' },
    { icon: Gauge, title: locale === 'zh-CN' ? '平均延迟' : 'Average latency', value: overview ? String(overview.avg_latency_ms) + ' ms' : '-' },
    { icon: Network, title: locale === 'zh-CN' ? '启用渠道' : 'Enabled providers', value: overview?.enabled_providers ?? '-' },
    { icon: Layers3, title: locale === 'zh-CN' ? '模型组' : 'Model groups', value: overview?.enabled_groups ?? '-' },
    { icon: KeyRound, title: locale === 'zh-CN' ? '网关密钥' : 'Gateway keys', value: overview?.active_gateway_keys ?? '-' },
    { icon: Activity, title: locale === 'zh-CN' ? '失败请求' : 'Failed requests', value: overview?.failed_requests ?? '-' }
  ]

  return (
    <section className="grid gap-6">
      <div className="rounded-[30px] border border-[var(--line)] bg-[linear-gradient(135deg,rgba(47,111,237,0.08),rgba(19,162,168,0.08))] p-6 md:p-8">
        <p className="text-sm uppercase tracking-[0.22em] text-[var(--accent)]">{locale === 'zh-CN' ? '总览' : 'Overview'}</p>
        <h2 className="mt-3 text-4xl font-semibold leading-tight">
          {locale === 'zh-CN' ? '渠道健康度、路由状态与请求面一屏可见。' : 'See channel health, route state, and request activity at a glance.'}
        </h2>
      </div>
      <div className="grid gap-4 md:grid-cols-2 2xl:grid-cols-3">
        {cards.map((item) => {
          const Icon = item.icon
          return (
            <div key={item.title} className="rounded-[28px] border border-[var(--line)] bg-[var(--panel-strong)] p-5 shadow-[var(--shadow-sm)]">
              <div className="flex items-center justify-between gap-3">
                <p className="text-sm text-[var(--muted)]">{item.title}</p>
                <span className="rounded-2xl bg-[rgba(47,111,237,0.08)] p-3 text-[var(--accent)]"><Icon size={18} /></span>
              </div>
              <strong className="mt-6 block text-4xl">{item.value}</strong>
            </div>
          )
        })}
      </div>
      <div className="grid gap-4 xl:grid-cols-[1.25fr_0.95fr]">
        <div className="rounded-[30px] border border-[var(--line)] bg-[var(--panel-strong)] p-5 shadow-[var(--shadow-sm)]">
          <div className="flex items-center justify-between gap-3">
            <strong>{locale === 'zh-CN' ? '路由池' : 'Routing pools'}</strong>
            <span className="text-sm text-[var(--muted)]">{router?.routes.length ?? 0} {locale === 'zh-CN' ? '个协议面' : 'protocols'}</span>
          </div>
          <div className="mt-4 grid gap-3">
            {router?.routes.map((route) => (
              <div key={route.protocol} className="rounded-3xl border border-[var(--line)] bg-[var(--panel-soft)] px-4 py-4">
                <div className="flex items-center justify-between gap-4">
                  <strong>{route.protocol}</strong>
                  <span className="text-xs uppercase tracking-[0.18em] text-[var(--muted)]">{route.provider_ids.length}</span>
                </div>
                <p className="mt-3 text-sm leading-6 text-[var(--muted)]">{route.provider_ids.join(' → ') || (locale === 'zh-CN' ? '暂无可用渠道' : 'No active providers')}</p>
              </div>
            ))}
          </div>
        </div>
        <div className="rounded-[30px] border border-[var(--line)] bg-[var(--panel-strong)] p-5 shadow-[var(--shadow-sm)]">
          <div className="flex items-center justify-between gap-3">
            <strong>{locale === 'zh-CN' ? '失败与健康状态' : 'Health and failures'}</strong>
            <span className="text-sm text-[var(--muted)]">{router?.health.length ?? 0}</span>
          </div>
          <div className="mt-4 grid gap-3">
            {router?.health.map((item) => (
              <div key={item.provider_id} className="rounded-3xl border border-[var(--line)] bg-[var(--panel-soft)] px-4 py-4">
                <div className="flex items-center justify-between gap-4">
                  <strong>{item.provider_id}</strong>
                  <span className={item.consecutive_failures > 0 ? 'text-sm text-[var(--danger)]' : 'text-sm text-[var(--success)]'}>
                    {locale === 'zh-CN' ? `失败 ${item.consecutive_failures}` : `${item.consecutive_failures} failures`}
                  </span>
                </div>
                <p className="mt-3 text-sm leading-6 text-[var(--muted)]">{item.last_error || (locale === 'zh-CN' ? '近期无错误' : 'No recent errors')}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  )
}
