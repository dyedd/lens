"use client"

import { useMemo } from 'react'
import { Activity, ArrowDownToLine, ArrowUpFromLine, ChartColumnBig, Clock, FastForward, KeyRound, Layers3, MessageSquare, Waypoints } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { OverviewMetrics, RouteSnapshot, apiRequest } from '@/lib/api'
import { useI18n } from '@/lib/i18n'

function formatCount(value: number) {
  if (value >= 1_000_000_000) return (value / 1_000_000_000).toFixed(2) + ' B'
  if (value >= 1_000_000) return (value / 1_000_000).toFixed(2) + ' M'
  if (value >= 1_000) return (value / 1_000).toFixed(2) + ' k'
  return String(value)
}

function HeatmapCell({ level }: { level: number }) {
  const palette = ['#ece8df', '#d9e6d9', '#bfd2bf', '#89aa8a', '#587c63']
  return <span className="block h-3.5 w-3.5 rounded-[4px]" style={{ backgroundColor: palette[level] }} />
}

export function OverviewScreen() {
  const { locale } = useI18n()
  const { data: router } = useQuery({ queryKey: ['router'], queryFn: () => apiRequest<RouteSnapshot>('/router') })
  const { data: overview } = useQuery({ queryKey: ['overview'], queryFn: () => apiRequest<OverviewMetrics>('/overview') })

  const cards = [
    {
      title: locale === 'zh-CN' ? '请求统计' : 'Request stats',
      headerIcon: Activity,
      items: [
        { label: locale === 'zh-CN' ? '请求次数' : 'Requests', value: formatCount(overview?.total_requests ?? 0), icon: MessageSquare },
        { label: locale === 'zh-CN' ? '平均延迟' : 'Latency', value: (overview?.avg_latency_ms ?? 0) + ' ms', icon: Clock },
      ]
    },
    {
      title: locale === 'zh-CN' ? '运行状态' : 'Runtime',
      headerIcon: ChartColumnBig,
      items: [
        { label: locale === 'zh-CN' ? '活跃渠道' : 'Providers', value: formatCount(overview?.enabled_providers ?? 0), icon: Waypoints },
        { label: locale === 'zh-CN' ? '活跃分组' : 'Groups', value: formatCount(overview?.enabled_groups ?? 0), icon: Layers3 },
      ]
    },
    {
      title: locale === 'zh-CN' ? '输入侧' : 'Input side',
      headerIcon: ArrowDownToLine,
      items: [
        { label: locale === 'zh-CN' ? '网关密钥' : 'Gateway keys', value: formatCount(overview?.active_gateway_keys ?? 0), icon: KeyRound },
        { label: locale === 'zh-CN' ? '失败请求' : 'Failures', value: formatCount(overview?.failed_requests ?? 0), icon: Activity },
      ]
    },
    {
      title: locale === 'zh-CN' ? '输出侧' : 'Output side',
      headerIcon: ArrowUpFromLine,
      items: [
        { label: locale === 'zh-CN' ? '成功请求' : 'Success', value: formatCount(overview?.successful_requests ?? 0), icon: FastForward },
        { label: locale === 'zh-CN' ? '成功率' : 'Success rate', value: overview?.total_requests ? Math.round((overview.successful_requests / overview.total_requests) * 100) + '%' : '0%', icon: Activity },
      ]
    },
  ]

  const heatLevels = useMemo(() => {
    const values = (router?.health ?? []).map((item) => item.consecutive_failures)
    return Array.from({ length: 54 * 7 }, (_, index) => {
      const value = values[index % Math.max(values.length, 1)] ?? 0
      if (value === 0) return 1
      if (value <= 1) return 2
      if (value <= 2) return 3
      return 4
    })
  }, [router])

  const trendBars = useMemo(() => {
    const source = [86, 44, 6, 1, 18, 28, 37, 46, 22, 13, 32, 48]
    return source.map((value, index) => ({
      label: index + 1,
      value,
    }))
  }, [])

  return (
    <section className="space-y-4">
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        {cards.map((card) => {
          const HeaderIcon = card.headerIcon
          return (
            <section key={card.title} className="flex items-center gap-4 rounded-3xl border border-[var(--line)] bg-[var(--panel-strong)] p-5 shadow-[var(--shadow-sm)]">
              <div className="flex h-full flex-col items-center justify-center gap-3 self-stretch border-r border-[var(--line)] pr-4">
                <HeaderIcon className="h-4 w-4 text-[var(--muted)]" />
                <h3 className="text-sm font-medium [writing-mode:vertical-lr] text-[var(--text)]">{card.title}</h3>
              </div>
              <div className="flex flex-1 flex-col gap-4">
                {card.items.map((item) => {
                  const Icon = item.icon
                  return (
                    <div key={item.label} className="flex items-center gap-3">
                      <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[rgba(88,124,99,0.12)] text-[var(--accent)]">
                        <Icon className="h-5 w-5" />
                      </div>
                      <div>
                        <p className="text-xs text-[var(--muted)]">{item.label}</p>
                        <p className="text-xl font-semibold text-[var(--text)]">{item.value}</p>
                      </div>
                    </div>
                  )
                })}
              </div>
            </section>
          )
        })}
      </div>

      <section className="rounded-3xl border border-[var(--line)] bg-[var(--panel-strong)] p-4 shadow-[var(--shadow-sm)]">
        <div className="overflow-x-auto">
          <div className="ml-auto grid w-fit grid-flow-col grid-cols-[repeat(54,0.875rem)] grid-rows-[repeat(7,0.875rem)] gap-1">
            {heatLevels.map((level, index) => <HeatmapCell key={index} level={level} />)}
          </div>
        </div>
      </section>

      <section className="rounded-3xl border border-[var(--line)] bg-[var(--panel-strong)] pt-4 shadow-[var(--shadow-sm)]">
        <div className="flex items-start justify-between gap-4 px-4 pb-2">
          <div>
            <h3 className="text-base font-semibold text-[var(--text)]">{locale === 'zh-CN' ? '趋势' : 'Trend'}</h3>
            <div className="mt-2 flex gap-4 text-sm">
              <div>
                <p className="text-xs text-[var(--muted)]">{locale === 'zh-CN' ? '请求次数' : 'Requests'}</p>
                <strong className="text-xl text-[var(--text)]">{overview?.total_requests ?? 0}</strong>
              </div>
              <div>
                <p className="text-xs text-[var(--muted)]">{locale === 'zh-CN' ? '失败次数' : 'Failures'}</p>
                <strong className="text-xl text-[var(--text)]">{overview?.failed_requests ?? 0}</strong>
              </div>
              <div>
                <p className="text-xs text-[var(--muted)]">{locale === 'zh-CN' ? '平均延迟' : 'Latency'}</p>
                <strong className="text-xl text-[var(--text)]">{overview?.avg_latency_ms ?? 0} ms</strong>
              </div>
            </div>
          </div>
          <div className="rounded-xl bg-[var(--panel)] px-3 py-2 text-sm text-[var(--muted)]">{locale === 'zh-CN' ? '今天' : 'Today'}</div>
        </div>
        <div className="mt-2 h-48 rounded-b-3xl border-t border-[var(--line)] bg-[linear-gradient(180deg,rgba(88,124,99,0.16),rgba(88,124,99,0.03))] px-4 pb-4 pt-3">
          <div className="flex h-full items-end gap-2">
            {trendBars.map((bar) => (
              <div key={bar.label} className="flex flex-1 flex-col justify-end gap-2">
                <div className="w-full rounded-t-[14px] bg-[rgba(88,124,99,0.38)]" style={{ height: `${Math.max(bar.value, 1)}%` }} />
                <span className="text-center text-xs text-[var(--muted)]">{bar.label}:00</span>
              </div>
            ))}
          </div>
        </div>
      </section>
    </section>
  )
}
