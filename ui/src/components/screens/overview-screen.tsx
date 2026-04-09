"use client"

import { useMemo, useState } from 'react'
import { createPortal } from 'react-dom'
import { Activity, ArrowDownToLine, ArrowUpFromLine, Bot, Clock3, DollarSign, MessageSquare, Sparkles } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { OverviewDailyPoint, OverviewMetrics, OverviewModelAnalytics, OverviewSummary, apiRequest } from '@/lib/api'
import { useI18n } from '@/lib/i18n'
import { SegmentedControl } from '@/components/ui/segmented-control'

type HeatMetric = 'requests' | 'tokens' | 'cost'
type ModelPanel = 'distribution' | 'trend' | 'requests' | 'ranking'

function formatCompact(value: number, digits = 1) {
  if (value >= 1_000_000_000) return (value / 1_000_000_000).toFixed(digits) + 'B'
  if (value >= 1_000_000) return (value / 1_000_000).toFixed(digits) + 'M'
  if (value >= 1_000) return (value / 1_000).toFixed(digits) + 'K'
  return String(Math.round(value))
}

function formatMoney(value: number) {
  if (value >= 1000) return '$' + formatCompact(value, 2)
  return '$' + value.toFixed(value >= 100 ? 0 : 2)
}

function formatDuration(ms: number) {
  if (ms >= 3_600_000) return (ms / 3_600_000).toFixed(1) + 'h'
  if (ms >= 60_000) return (ms / 60_000).toFixed(1) + 'm'
  if (ms >= 1000) return (ms / 1000).toFixed(1) + 's'
  return ms + 'ms'
}

function dailyValue(item: OverviewDailyPoint, metric: HeatMetric) {
  if (metric === 'tokens') return item.total_tokens
  if (metric === 'cost') return item.total_cost_usd
  return item.request_count
}

function heatLevel(value: number, maxValue: number) {
  if (value <= 0 || maxValue <= 0) return 0
  const ratio = value / maxValue
  if (ratio >= 0.8) return 4
  if (ratio >= 0.5) return 3
  if (ratio >= 0.2) return 2
  return 1
}

function HeatCell({ level }: { level: number }) {
  const palette = ['#edf3ff', '#dbe9ff', '#bfd6ff', '#7aa7ff', '#2563eb']
  return <span className="block h-3.5 w-3.5 rounded-[4px]" style={{ backgroundColor: palette[level] }} />
}

export function OverviewScreen() {
  const { locale } = useI18n()
  const [heatMetric, setHeatMetric] = useState<HeatMetric>('requests')
  const [modelPanel, setModelPanel] = useState<ModelPanel>('distribution')

  const { data: metrics } = useQuery({ queryKey: ['overview'], queryFn: () => apiRequest<OverviewMetrics>('/overview') })
  const { data: summary } = useQuery({ queryKey: ['overview-summary'], queryFn: () => apiRequest<OverviewSummary>('/overview/summary') })
  const { data: daily } = useQuery({ queryKey: ['overview-daily'], queryFn: () => apiRequest<OverviewDailyPoint[]>('/overview/daily') })
  const { data: models } = useQuery({ queryKey: ['overview-models'], queryFn: () => apiRequest<OverviewModelAnalytics>('/overview/models') })

  const summaryCards = [
    {
      key: 'request_count',
      title: locale === 'zh-CN' ? '请求统计' : 'Requests',
      icon: Activity,
      items: [
        { label: locale === 'zh-CN' ? '请求次数' : 'Request count', value: formatCompact(summary?.request_count.value ?? 0), icon: MessageSquare },
        { label: locale === 'zh-CN' ? '耗时总计' : 'Total wait', value: formatDuration(summary?.wait_time_ms.value ?? 0), icon: Clock3 },
      ]
    },
    {
      key: 'total',
      title: locale === 'zh-CN' ? '总量统计' : 'Totals',
      icon: Sparkles,
      items: [
        { label: locale === 'zh-CN' ? '总 Token' : 'Total tokens', value: formatCompact(summary?.total_tokens.value ?? 0), icon: Bot },
        { label: locale === 'zh-CN' ? '总费用' : 'Total cost', value: formatMoney(summary?.total_cost_usd.value ?? 0), icon: DollarSign },
      ]
    },
    {
      key: 'input',
      title: locale === 'zh-CN' ? '输入统计' : 'Input',
      icon: ArrowDownToLine,
      items: [
        { label: locale === 'zh-CN' ? '输入 Token' : 'Input tokens', value: formatCompact(summary?.input_tokens.value ?? 0), icon: Bot },
        { label: locale === 'zh-CN' ? '输入费用' : 'Input cost', value: formatMoney(summary?.input_cost_usd.value ?? 0), icon: DollarSign },
      ]
    },
    {
      key: 'output',
      title: locale === 'zh-CN' ? '输出统计' : 'Output',
      icon: ArrowUpFromLine,
      items: [
        { label: locale === 'zh-CN' ? '输出 Token' : 'Output tokens', value: formatCompact(summary?.output_tokens.value ?? 0), icon: Bot },
        { label: locale === 'zh-CN' ? '输出费用' : 'Output cost', value: formatMoney(summary?.output_cost_usd.value ?? 0), icon: DollarSign },
      ]
    },
  ]

  const heatmap = useMemo(() => {
    const source = daily ?? []
    const maxValue = source.reduce((max, item) => Math.max(max, dailyValue(item, heatMetric)), 0)
    return source.map((item) => ({
      date: item.date,
      level: heatLevel(dailyValue(item, heatMetric), maxValue),
      value: dailyValue(item, heatMetric),
    }))
  }, [daily, heatMetric])

  const chartBars = useMemo(() => {
    if (!models) return []
    if (modelPanel === 'distribution') return models.distribution.map((item) => ({ label: item.model, value: item.total_cost_usd, meta: formatMoney(item.total_cost_usd) }))
    if (modelPanel === 'requests') return models.distribution.map((item) => ({ label: item.model, value: item.requests, meta: formatCompact(item.requests) }))
    if (modelPanel === 'ranking') return models.request_ranking.map((item) => ({ label: item.model, value: item.requests, meta: formatCompact(item.requests) }))

    const grouped = new Map<string, number>()
    for (const point of models.trend) {
      grouped.set(point.date, (grouped.get(point.date) ?? 0) + point.value)
    }
    return [...grouped.entries()].slice(-14).map(([date, value]) => ({
      label: date.slice(4, 6) + '/' + date.slice(6, 8),
      value,
      meta: formatMoney(value),
    }))
  }, [modelPanel, models])

  const maxBar = Math.max(...chartBars.map((item) => item.value), 1)

  return (
    <section className="space-y-4 md:space-y-6">
      {typeof document !== 'undefined' && document.getElementById('header-portal') ? createPortal(
        <div className="flex flex-1 items-center justify-end gap-2">
            {/* The page title itself is enough, but we could add global actions here if needed */}
        </div>,
        document.getElementById('header-portal')!
      ) : null}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
        {summaryCards.map((card) => {
          const HeaderIcon = card.icon
          return (
            <section key={card.key} className="flex min-w-0 items-center gap-3 rounded-[28px] border border-[var(--line)] bg-[var(--panel-strong)] p-4 shadow-[var(--shadow-sm)] xl:gap-4 xl:p-5">
              <div className="flex shrink-0 self-stretch border-r border-[var(--line)] pr-3 xl:pr-4">
                <div className="flex flex-col items-center justify-center gap-3">
                  <HeaderIcon className="h-4 w-4 text-[var(--muted)]" />
                  <h3 className="text-[13px] font-medium [writing-mode:vertical-lr] text-[var(--text)]">{card.title}</h3>
                </div>
              </div>
              <div className="flex min-w-0 flex-1 flex-col gap-4">
                {card.items.map((item) => {
                  const Icon = item.icon
                  return (
                    <div key={item.label} className="flex items-center gap-3">
                      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-2xl bg-[rgba(37,99,235,0.12)] text-[var(--accent)] xl:h-10 xl:w-10">
                        <Icon className="h-4.5 w-4.5" />
                      </div>
                      <div className="min-w-0">
                        <p className="text-[12px] text-[var(--muted)]">{item.label}</p>
                        <strong className="block min-w-0 text-[clamp(1.35rem,1.2rem+0.22vw,1.7rem)] font-semibold leading-none tracking-tight text-[var(--text)]">{item.value}</strong>
                      </div>
                    </div>
                  )
                })}
              </div>
            </section>
          )
        })}
      </div>

      <section className="rounded-[28px] border border-[var(--line)] bg-[var(--panel-strong)] p-4 shadow-[var(--shadow-sm)]">
        <div className="flex flex-col gap-3 pb-3 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <h3 className="text-[13px] font-semibold text-[var(--text)]">{locale === 'zh-CN' ? '模型分析' : 'Model analytics'}</h3>
            <p className="mt-1 text-[12px] text-[var(--muted)]">{locale === 'zh-CN' ? '基于模型维度聚合最近日志数据' : 'Aggregated by model from recent request logs'}</p>
          </div>
          <div className="overflow-x-auto pb-1">
            <SegmentedControl
              value={modelPanel}
              onValueChange={setModelPanel}
              options={[
                { value: 'distribution', label: locale === 'zh-CN' ? '消耗分布' : 'Cost share' },
                { value: 'trend', label: locale === 'zh-CN' ? '消耗趋势' : 'Cost trend' },
                { value: 'requests', label: locale === 'zh-CN' ? '调用分布' : 'Calls share' },
                { value: 'ranking', label: locale === 'zh-CN' ? '调用排行' : 'Calls rank' },
              ]}
            />
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-5 border-b border-[var(--line)] pb-4 text-[13px]">
          <div>
            <div className="text-[12px] text-[var(--muted)]">{locale === 'zh-CN' ? '模型数' : 'Models'}</div>
            <div className="text-[18px] font-semibold text-[var(--text)]">{models?.available_models.length ?? 0}</div>
          </div>
          <div>
            <div className="text-[12px] text-[var(--muted)]">{locale === 'zh-CN' ? '成功请求' : 'Success'}</div>
            <div className="text-[18px] font-semibold text-[var(--text)]">{formatCompact(metrics?.successful_requests ?? 0)}</div>
          </div>
          <div>
            <div className="text-[12px] text-[var(--muted)]">{locale === 'zh-CN' ? '平均延迟' : 'Latency'}</div>
            <div className="text-[18px] font-semibold text-[var(--text)]">{metrics?.avg_latency_ms ?? 0} ms</div>
          </div>
        </div>

        <div className="mt-5 grid min-h-[320px] grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_240px]">
          <div className="flex items-end gap-3 rounded-[24px] bg-[var(--panel)] px-4 pb-4 pt-6">
            {chartBars.length ? chartBars.map((item) => (
              <div key={item.label} className="flex min-w-0 flex-1 flex-col justify-end gap-2">
                <div className="rounded-t-[14px] bg-[linear-gradient(180deg,rgba(37,99,235,0.72),rgba(37,99,235,0.24))]" style={{ height: `${Math.max((item.value / maxBar) * 220, 10)}px` }} />
                <div className="truncate text-center text-[11px] text-[var(--muted)]" title={item.label}>{item.label}</div>
              </div>
            )) : <div className="flex h-full w-full items-center justify-center text-sm text-[var(--muted)]">{locale === 'zh-CN' ? '暂无模型日志数据' : 'No model logs yet'}</div>}
          </div>

          <div className="rounded-[24px] bg-[var(--panel)] p-4">
            <h4 className="text-[13px] font-medium text-[var(--text)]">{locale === 'zh-CN' ? '明细' : 'Details'}</h4>
            <div className="mt-3 space-y-3">
              {(modelPanel === 'ranking' ? models?.request_ranking : models?.distribution)?.slice(0, 6).map((item) => (
                  <div key={item.model} className="rounded-2xl border border-[var(--line)] bg-[var(--panel-strong)] px-3 py-3">
                    <div className="truncate text-[13px] font-medium text-[var(--text)]">{item.model}</div>
                    <div className="mt-2 flex items-center justify-between text-[12px] text-[var(--muted)]">
                    <span>{locale === 'zh-CN' ? '请求' : 'Requests'} {formatCompact(item.requests)}</span>
                    <span>{locale === 'zh-CN' ? '费用' : 'Cost'} {formatMoney(item.total_cost_usd)}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="rounded-[28px] border border-[var(--line)] bg-[var(--panel-strong)] p-4 shadow-[var(--shadow-sm)]">
        <div className="flex flex-col gap-3 pb-3 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <h3 className="text-[13px] font-semibold text-[var(--text)]">{locale === 'zh-CN' ? '活跃热力图' : 'Activity heatmap'}</h3>
            <p className="mt-1 text-[12px] text-[var(--muted)]">{locale === 'zh-CN' ? '支持查看每日请求、Token 与费用' : 'Switch between requests, tokens, and cost'}</p>
          </div>
          <div className="overflow-x-auto pb-1">
            <SegmentedControl
              value={heatMetric}
              onValueChange={setHeatMetric}
              options={[
                { value: 'requests', label: locale === 'zh-CN' ? '请求' : 'Requests' },
                { value: 'tokens', label: 'Token' },
                { value: 'cost', label: locale === 'zh-CN' ? '费用' : 'Cost' },
              ]}
            />
          </div>
        </div>

        <div className="overflow-x-auto rounded-[22px] bg-[var(--panel)] p-4">
          <div className="ml-auto grid w-fit grid-flow-col grid-cols-[repeat(54,0.875rem)] grid-rows-[repeat(7,0.875rem)] gap-1">
            {Array.from({ length: 54 * 7 }, (_, index) => {
              const item = heatmap[index] ?? { level: 0, date: '', value: 0 }
              return <HeatCell key={index} level={item.level} />
            })}
          </div>
        </div>

        <div className="mt-4 grid grid-cols-1 gap-3 text-center md:grid-cols-3">
            <div className="rounded-2xl bg-[var(--panel)] px-3 py-4">
              <div className="text-[12px] text-[var(--muted)]">{locale === 'zh-CN' ? '总请求' : 'Requests'}</div>
              <div className="mt-1 text-[18px] font-semibold text-[var(--text)]">{formatCompact(metrics?.total_requests ?? 0)}</div>
            </div>
            <div className="rounded-2xl bg-[var(--panel)] px-3 py-4">
              <div className="text-[12px] text-[var(--muted)]">{locale === 'zh-CN' ? '成功率' : 'Success rate'}</div>
              <div className="mt-1 text-[18px] font-semibold text-[var(--text)]">{metrics?.total_requests ? Math.round(((metrics?.successful_requests ?? 0) / metrics.total_requests) * 100) + '%' : '0%'}</div>
            </div>
            <div className="rounded-2xl bg-[var(--panel)] px-3 py-4">
              <div className="text-[12px] text-[var(--muted)]">{locale === 'zh-CN' ? '服务 API Key' : 'Service keys'}</div>
              <div className="mt-1 text-[18px] font-semibold text-[var(--text)]">{formatCompact(metrics?.active_gateway_keys ?? 0)}</div>
            </div>
        </div>
      </section>
    </section>
  )
}
