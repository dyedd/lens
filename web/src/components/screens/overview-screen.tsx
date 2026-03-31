"use client"

import { useMemo } from 'react'
import { Activity, ArrowDownToLine, ArrowUpFromLine, ChartColumnBig, Clock, DollarSign, FastForward, MessageSquare, Rewind } from 'lucide-react'
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
  const palette = ['#ece8df', '#d9ebd6', '#bfe0bc', '#95c892', '#61a866']
  return <span className="block h-4 w-4 rounded-[5px]" style={{ backgroundColor: palette[level] }} />
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
        { label: locale === 'zh-CN' ? '消耗时间' : 'Latency', value: ((overview?.avg_latency_ms ?? 0) / 1000).toFixed(2) + ' s', icon: Clock },
      ]
    },
    {
      title: locale === 'zh-CN' ? '全部统计' : 'Total stats',
      headerIcon: ChartColumnBig,
      items: [
        { label: locale === 'zh-CN' ? '活跃渠道' : 'Providers', value: formatCount(overview?.enabled_providers ?? 0), icon: Activity },
        { label: locale === 'zh-CN' ? '失败请求' : 'Failed', value: formatCount(overview?.failed_requests ?? 0), icon: DollarSign },
      ]
    },
    {
      title: locale === 'zh-CN' ? '输入统计' : 'Input stats',
      headerIcon: ArrowDownToLine,
      items: [
        { label: locale === 'zh-CN' ? '模型组' : 'Groups', value: formatCount(overview?.enabled_groups ?? 0), icon: Rewind },
        { label: locale === 'zh-CN' ? '网关密钥' : 'Keys', value: formatCount(overview?.active_gateway_keys ?? 0), icon: DollarSign },
      ]
    },
    {
      title: locale === 'zh-CN' ? '输出统计' : 'Output stats',
      headerIcon: ArrowUpFromLine,
      items: [
        { label: locale === 'zh-CN' ? '成功请求' : 'Success', value: formatCount(overview?.successful_requests ?? 0), icon: FastForward },
        { label: locale === 'zh-CN' ? '成功率' : 'Success rate', value: overview?.total_requests ? Math.round((overview.successful_requests / overview.total_requests) * 100) + '%' : '0%', icon: DollarSign },
      ]
    },
  ]

  const heatLevels = useMemo(() => {
    const values = (router?.health ?? []).map((item) => item.consecutive_failures)
    const cells = Array.from({ length: 27 * 7 }, (_, index) => {
      const value = values[index % Math.max(values.length, 1)] ?? 0
      if (value === 0) return 1
      if (value <= 1) return 2
      if (value <= 2) return 3
      return 4
    })
    return cells
  }, [router])

  return (
    <section className="space-y-6">
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        {cards.map((card) => {
          const HeaderIcon = card.headerIcon
          return (
            <section key={card.title} className="flex items-center gap-4 rounded-[26px] border border-[var(--line)] bg-[var(--panel-strong)] p-4 shadow-[var(--shadow-sm)]">
              <div className="flex h-full flex-col items-center justify-center gap-3 border-r border-[var(--line)] pr-4">
                <HeaderIcon className="h-4 w-4 text-[var(--muted)]" />
                <h3 className="text-xs font-medium [writing-mode:vertical-lr] text-[var(--text)]">{card.title}</h3>
              </div>
              <div className="flex flex-1 flex-col gap-4">
                {card.items.map((item) => {
                  const Icon = item.icon
                  return (
                    <div key={item.label} className="flex items-center gap-3">
                      <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-[rgba(97,168,102,0.12)] text-[var(--accent)]">
                        <Icon className="h-5 w-5" />
                      </div>
                      <div>
                        <p className="text-xs text-[var(--muted)]">{item.label}</p>
                        <p className="text-[16px] font-semibold text-[var(--text)]">{item.value}</p>
                      </div>
                    </div>
                  )
                })}
              </div>
            </section>
          )
        })}
      </div>

      <section className="rounded-[26px] border border-[var(--line)] bg-[var(--panel-strong)] p-4 shadow-[var(--shadow-sm)]">
        <div className="grid grid-cols-[repeat(27,1rem)] grid-rows-[repeat(7,1rem)] gap-1 overflow-x-auto">
          {heatLevels.map((level, index) => <HeatmapCell key={index} level={level} />)}
        </div>
      </section>

      <section className="rounded-[26px] border border-[var(--line)] bg-[var(--panel-strong)] p-4 shadow-[var(--shadow-sm)]">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h3 className="text-lg font-semibold text-[var(--text)]">{locale === 'zh-CN' ? '趋势' : 'Trend'}</h3>
            <div className="mt-3 flex gap-4 text-sm">
              <div>
                <p className="text-[var(--muted)]">{locale === 'zh-CN' ? '请求次数' : 'Requests'}</p>
                <strong className="text-xl">{overview?.total_requests ?? 0}</strong>
              </div>
              <div>
                <p className="text-[var(--muted)]">{locale === 'zh-CN' ? '失败次数' : 'Failures'}</p>
                <strong className="text-xl">{overview?.failed_requests ?? 0}</strong>
              </div>
              <div>
                <p className="text-[var(--muted)]">{locale === 'zh-CN' ? '平均延迟' : 'Latency'}</p>
                <strong className="text-xl">{overview?.avg_latency_ms ?? 0} ms</strong>
              </div>
            </div>
          </div>
          <div className="rounded-full bg-[var(--panel-soft)] px-4 py-2 text-sm text-[var(--muted)]">{locale === 'zh-CN' ? '今天' : 'Today'}</div>
        </div>
        <div className="mt-5 h-60 rounded-[22px] border border-dashed border-[var(--line)] bg-[linear-gradient(180deg,rgba(97,168,102,0.18),rgba(97,168,102,0.04))] p-4">
          <div className="flex h-full items-end gap-3">
            {Array.from({ length: 10 }, (_, index) => {
              const value = index === 0 ? 86 : index === 1 ? 44 : index === 2 ? 6 : 1
              return (
                <div key={index} className="flex flex-1 flex-col justify-end gap-2">
                  <div className="w-full rounded-t-[16px] bg-[rgba(97,168,102,0.36)]" style={{ height: `${Math.max(value, 1)}%` }} />
                  <span className="text-center text-xs text-[var(--muted)]">{index + 1}:00</span>
                </div>
              )
            })}
          </div>
        </div>
      </section>
    </section>
  )
}
