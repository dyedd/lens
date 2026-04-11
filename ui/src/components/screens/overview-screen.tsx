"use client"

import { useMemo, useState } from "react"
import { createPortal } from "react-dom"
import { Activity, ArrowDownToLine, ArrowUpFromLine, Bot, Clock3, DollarSign, MessageSquare, Sparkles } from "lucide-react"
import { useQuery } from "@tanstack/react-query"
import { Pie, PieChart, Cell, Bar, BarChart, CartesianGrid, XAxis, YAxis } from "recharts"
import { OverviewDailyPoint, OverviewModelAnalytics, OverviewSummary, RequestLogItem, apiRequest } from "@/lib/api"
import { useI18n } from "@/lib/i18n"
import { SegmentedControl } from "@/components/ui/segmented-control"
import { ChartContainer, ChartTooltip, ChartTooltipContent, ChartLegend, ChartLegendContent, type ChartConfig } from "@/components/ui/chart"

type TimeRange = "-1" | "7" | "30" | "0"
type PieMetric = "cost" | "requests" | "tokens"

const CHART_COLORS = [
  "#2563eb",
  "#16a34a",
  "#d97706",
  "#dc2626",
  "#7c3aed",
  "#6366f1",
  "#f59e0b",
  "#10b981",
  "#ef4444",
  "#8b5cf6",
  "#ec4899",
  "#14b8a6",
]

function safeKey(name: string) {
  return name.replace(/[^a-zA-Z0-9_-]/g, "_")
}

function formatCompact(value: number, digits = 1) {
  if (value >= 1_000_000_000) return (value / 1_000_000_000).toFixed(digits) + "B"
  if (value >= 1_000_000) return (value / 1_000_000).toFixed(digits) + "M"
  if (value >= 1_000) return (value / 1_000).toFixed(digits) + "K"
  return String(Math.round(value))
}

function formatMoney(value: number) {
  if (value >= 1000) return "$" + formatCompact(value, 2)
  return "$" + value.toFixed(value >= 100 ? 0 : 2)
}

function formatDuration(ms: number) {
  if (ms >= 3_600_000) return (ms / 3_600_000).toFixed(1) + "h"
  if (ms >= 60_000) return (ms / 60_000).toFixed(1) + "m"
  if (ms >= 1000) return (ms / 1000).toFixed(1) + "s"
  return ms + "ms"
}

export function OverviewScreen() {
  const { locale } = useI18n()
  const zh = locale === "zh-CN"

  const [timeRange, setTimeRange] = useState<TimeRange>("-1")
  const [pieMetric, setPieMetric] = useState<PieMetric>("cost")
  const [logOffset, setLogOffset] = useState(0)

  const days = Number(timeRange)

  const { data: summary } = useQuery({ queryKey: ["overview-summary", days], queryFn: () => apiRequest<OverviewSummary>(`/admin/overview-summary?days=${days}`) })
  const { data: daily } = useQuery({ queryKey: ["overview-daily", days], queryFn: () => apiRequest<OverviewDailyPoint[]>(`/admin/overview-daily?days=${days}`) })
  const { data: models } = useQuery({ queryKey: ["overview-models", days], queryFn: () => apiRequest<OverviewModelAnalytics>(`/admin/overview-models?days=${days}`) })
  const { data: latestLogs } = useQuery({ queryKey: ["overview-logs", days, logOffset], queryFn: () => apiRequest<RequestLogItem[]>(`/admin/overview-logs?days=${days}&limit=50&offset=${logOffset}`) })
  const logs = latestLogs ?? []

  const periodMetrics = useMemo(() => {
    const source = daily ?? []
    const totalRequests = source.reduce((sum, item) => sum + item.request_count, 0)
    const successfulRequests = source.reduce((sum, item) => sum + item.successful_requests, 0)
    const totalWaitTime = source.reduce((sum, item) => sum + item.wait_time_ms, 0)

    return {
      totalRequests,
      successfulRequests,
      successRate: totalRequests > 0 ? Math.round((successfulRequests / totalRequests) * 100) : 0,
      avgLatencyMs: totalRequests > 0 ? Math.round(totalWaitTime / totalRequests) : 0,
    }
  }, [daily])

  const summaryCards = [
    {
      key: "request_count",
      title: zh ? "请求统计" : "Requests",
      icon: Activity,
      items: [
        { label: zh ? "请求次数" : "Request count", value: formatCompact(summary?.request_count.value ?? 0), icon: MessageSquare },
        { label: zh ? "耗时总计" : "Total wait", value: formatDuration(summary?.wait_time_ms.value ?? 0), icon: Clock3 },
      ],
    },
    {
      key: "total",
      title: zh ? "总量统计" : "Totals",
      icon: Sparkles,
      items: [
        { label: zh ? "总 Token" : "Total tokens", value: formatCompact(summary?.total_tokens.value ?? 0), icon: Bot },
        { label: zh ? "总费用" : "Total cost", value: formatMoney(summary?.total_cost_usd.value ?? 0), icon: DollarSign },
      ],
    },
    {
      key: "input",
      title: zh ? "输入统计" : "Input",
      icon: ArrowDownToLine,
      items: [
        { label: zh ? "输入 Token" : "Input tokens", value: formatCompact(summary?.input_tokens.value ?? 0), icon: Bot },
        { label: zh ? "输入费用" : "Input cost", value: formatMoney(summary?.input_cost_usd.value ?? 0), icon: DollarSign },
      ],
    },
    {
      key: "output",
      title: zh ? "输出统计" : "Output",
      icon: ArrowUpFromLine,
      items: [
        { label: zh ? "输出 Token" : "Output tokens", value: formatCompact(summary?.output_tokens.value ?? 0), icon: Bot },
        { label: zh ? "输出费用" : "Output cost", value: formatMoney(summary?.output_cost_usd.value ?? 0), icon: DollarSign },
      ],
    },
  ]

  // --- Pie chart data ---
  const pieData = useMemo(() => {
    if (!models) return { data: [], total: 0 }
    const source = models.distribution
    const getValue = (item: typeof source[0]) => {
      if (pieMetric === "requests") return item.requests
      if (pieMetric === "tokens") return item.total_tokens
      return item.total_cost_usd
    }
    const total = source.reduce((sum, item) => sum + getValue(item), 0)
    return {
      data: source.map((item) => ({
        model: item.model,
        value: getValue(item),
        requests: item.requests,
        total_cost_usd: item.total_cost_usd,
      })),
      total,
    }
  }, [models, pieMetric])

  const pieChartConfig = useMemo(() => {
    const config: ChartConfig = {}
    models?.distribution.forEach((item, i) => {
      config[safeKey(item.model)] = {
        label: item.model,
        color: CHART_COLORS[i % CHART_COLORS.length],
      }
    })
    return config
  }, [models])

  // --- Stacked bar chart data ---
  const { barData, barConfig, barModels } = useMemo(() => {
    if (!models) return { barData: [], barConfig: {} as ChartConfig, barModels: [] as string[] }

    const modelSet = [...new Set(models.trend.map((t) => t.model))].slice(0, 12)
    const dateMap = new Map<string, Record<string, number>>()
    for (const point of models.trend) {
      if (!modelSet.includes(point.model)) continue
      const key = safeKey(point.model)
      const existing = dateMap.get(point.date) ?? {}
      existing[key] = (existing[key] ?? 0) + point.value
      dateMap.set(point.date, existing)
    }

    const sortedDates = [...dateMap.keys()].sort()
    const data = sortedDates.map((date) => ({
      date: date.slice(4, 6) + "/" + date.slice(6, 8),
      ...dateMap.get(date)!,
    }))

    const config: ChartConfig = {}
    const safeModels: string[] = []
    modelSet.forEach((model, i) => {
      const key = safeKey(model)
      safeModels.push(key)
      config[key] = {
        label: model,
        color: CHART_COLORS[i % CHART_COLORS.length],
      }
    })

    return { barData: data, barConfig: config, barModels: safeModels }
  }, [models])

  return (
    <section className="space-y-4 md:space-y-6">
      {typeof document !== "undefined" && document.getElementById("header-portal") ? createPortal(
        <div className="flex flex-1 items-center justify-end gap-2">
          <SegmentedControl
            value={timeRange}
            onValueChange={(v) => { setTimeRange(v as TimeRange); setLogOffset(0) }}
            options={[
              { value: "-1", label: zh ? "今天" : "Today" },
              { value: "7", label: zh ? "近7天" : "7 days" },
              { value: "30", label: zh ? "近30天" : "30 days" },
              { value: "0", label: zh ? "全部" : "All" },
            ]}
          />
        </div>,
        document.getElementById("header-portal")!
      ) : null}

      {/* Summary cards */}
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

      {/* Model analytics: Pie + Stacked Bar + Ranking */}
      <section className="rounded-[28px] border border-[var(--line)] bg-[var(--panel-strong)] p-4 shadow-[var(--shadow-sm)]">
        <div className="flex flex-col gap-3 pb-3 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <h3 className="text-[13px] font-semibold text-[var(--text)]">{zh ? "模型分析" : "Model analytics"}</h3>
            <p className="mt-1 text-[12px] text-[var(--muted)]">{zh ? "基于模型维度聚合日志数据" : "Aggregated by model from request logs"}</p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-5 border-b border-[var(--line)] pb-4 text-[13px]">
          <div>
            <div className="text-[12px] text-[var(--muted)]">{zh ? "总请求" : "Requests"}</div>
            <div className="text-[18px] font-semibold text-[var(--text)]">{formatCompact(periodMetrics.totalRequests)}</div>
          </div>
          <div>
            <div className="text-[12px] text-[var(--muted)]">{zh ? "成功请求" : "Success"}</div>
            <div className="text-[18px] font-semibold text-[var(--text)]">{formatCompact(periodMetrics.successfulRequests)}</div>
          </div>
          <div>
            <div className="text-[12px] text-[var(--muted)]">{zh ? "成功率" : "Success rate"}</div>
            <div className="text-[18px] font-semibold text-[var(--text)]">{periodMetrics.successRate}%</div>
          </div>
          <div>
            <div className="text-[12px] text-[var(--muted)]">{zh ? "平均延迟" : "Latency"}</div>
            <div className="text-[18px] font-semibold text-[var(--text)]">{periodMetrics.avgLatencyMs} ms</div>
          </div>
        </div>

        {/* Pie chart */}
        <div className="mt-5 space-y-5">
          <div className="flex items-center justify-between">
            <h4 className="text-[13px] font-medium text-[var(--text)]">{zh ? "消耗占比" : "Cost share"}</h4>
            <SegmentedControl
              value={pieMetric}
              onValueChange={(v) => setPieMetric(v as PieMetric)}
              options={[
                { value: "cost", label: zh ? "费用" : "Cost" },
                { value: "requests", label: zh ? "请求" : "Requests" },
                { value: "tokens", label: "Token" },
              ]}
            />
          </div>

          <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_240px]">
            <div className="rounded-[24px] bg-[var(--panel)] p-4">
              {pieData.data.length ? (
                <ChartContainer config={pieChartConfig} className="h-[280px] w-full">
                  <PieChart width={400} height={280}>
                    <ChartTooltip content={<ChartTooltipContent nameKey="model" hideLabel />} />
                    <Pie
                      data={pieData.data}
                      dataKey="value"
                      nameKey="model"
                      innerRadius={60}
                      outerRadius={100}
                      paddingAngle={2}
                    >
                      {pieData.data.map((_, i) => (
                        <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                      ))}
                    </Pie>
                    <ChartLegend content={<ChartLegendContent nameKey="model" />} />
                  </PieChart>
                </ChartContainer>
              ) : (
                <div className="flex h-[280px] w-full items-center justify-center text-sm text-[var(--muted)]">{zh ? "暂无数据" : "No data"}</div>
              )}
            </div>

            {/* Ranking details */}
            <div className="rounded-[24px] bg-[var(--panel)] p-4">
              <h4 className="text-[13px] font-medium text-[var(--text)]">{zh ? "调用排行" : "Calls rank"}</h4>
              <div className="mt-3 space-y-3">
                {models?.request_ranking.slice(0, 6).map((item) => (
                  <div key={item.model} className="rounded-2xl border border-[var(--line)] bg-[var(--panel-strong)] px-3 py-3">
                    <div className="truncate text-[13px] font-medium text-[var(--text)]">{item.model}</div>
                    <div className="mt-2 flex items-center justify-between text-[12px] text-[var(--muted)]">
                      <span>{zh ? "请求" : "Requests"} {formatCompact(item.requests)}</span>
                      <span>{zh ? "费用" : "Cost"} {formatMoney(item.total_cost_usd)}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Stacked bar chart */}
        <div className="mt-5 space-y-3">
          <h4 className="text-[13px] font-medium text-[var(--text)]">{zh ? "消耗趋势" : "Cost trend"}</h4>
          <div className="rounded-[24px] bg-[var(--panel)] p-4">
            {barData.length ? (
              <ChartContainer config={barConfig} className="h-[300px] w-full">
                <BarChart width={800} height={300} data={barData} margin={{ top: 4, right: 4, bottom: 4, left: 4 }}>
                  <CartesianGrid vertical={false} strokeDasharray="3 3" />
                  <XAxis dataKey="date" tickLine={false} axisLine={false} fontSize={11} />
                  <YAxis tickLine={false} axisLine={false} fontSize={11} tickFormatter={(v: number) => formatMoney(v)} />
                  <ChartTooltip content={<ChartTooltipContent />} />
                  <ChartLegend content={<ChartLegendContent />} />
                  {barModels.map((key) => (
                    <Bar key={key} dataKey={key} stackId="a" fill={barConfig[key]?.color} radius={[2, 2, 0, 0]} />
                  ))}
                </BarChart>
              </ChartContainer>
            ) : (
              <div className="flex h-[280px] w-full items-center justify-center text-sm text-[var(--muted)]">{zh ? "暂无模型日志数据" : "No model logs yet"}</div>
            )}
          </div>
        </div>
      </section>

      {/* Consume log */}
      <section className="rounded-[28px] border border-[var(--line)] bg-[var(--panel-strong)] p-4 shadow-[var(--shadow-sm)]">
        <div className="flex items-center justify-between pb-3">
          <div>
            <h3 className="text-[13px] font-semibold text-[var(--text)]">{zh ? "消费日志" : "Consume log"}</h3>
            <p className="mt-1 text-[12px] text-[var(--muted)]">{zh ? "近期请求明细记录" : "Recent request log details"}</p>
          </div>
        </div>

        <div className="overflow-x-auto rounded-[22px] bg-[var(--panel)]">
          {logs.length > 0 ? (
            <table className="w-full text-[12px]">
              <thead>
                <tr className="border-b border-[var(--line)] text-left text-[var(--muted)]">
                  <th className="px-3 py-2.5 font-medium">{zh ? "时间" : "Time"}</th>
                  <th className="px-3 py-2.5 font-medium">{zh ? "模型" : "Model"}</th>
                  <th className="px-3 py-2.5 font-medium text-right">Token</th>
                  <th className="px-3 py-2.5 font-medium text-right">{zh ? "费用" : "Cost"}</th>
                  <th className="px-3 py-2.5 font-medium text-right">{zh ? "延迟" : "Latency"}</th>
                  <th className="px-3 py-2.5 font-medium">{zh ? "状态" : "Status"}</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((log) => (
                  <tr key={log.id} className="border-b border-[var(--line)] last:border-b-0">
                    <td className="px-3 py-2.5 text-[var(--text)] whitespace-nowrap">{log.created_at.slice(5, 16).replace("T", " ")}</td>
                    <td className="px-3 py-2.5 text-[var(--text)] max-w-[180px] truncate">{log.resolved_model || log.requested_model || "-"}</td>
                    <td className="px-3 py-2.5 text-right text-[var(--text)] whitespace-nowrap">
                      <span className="text-[var(--muted)]">{formatCompact(log.input_tokens)}</span>
                      <span className="mx-0.5 text-[var(--line-strong)]">/</span>
                      <span>{formatCompact(log.output_tokens)}</span>
                    </td>
                    <td className="px-3 py-2.5 text-right text-[var(--text)] whitespace-nowrap">{formatMoney(log.total_cost_usd)}</td>
                    <td className="px-3 py-2.5 text-right text-[var(--text)] whitespace-nowrap">{formatDuration(log.latency_ms)}</td>
                    <td className="px-3 py-2.5 whitespace-nowrap">
                      <span className={log.success ? "text-[var(--success)]" : "text-[var(--danger)]"}>
                        {log.success ? (zh ? "成功" : "OK") : log.status_code}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="flex h-24 items-center justify-center text-sm text-[var(--muted)]">{zh ? "暂无日志" : "No logs"}</div>
          )}
        </div>

        {latestLogs && latestLogs.length >= 50 && (
          <div className="mt-3 flex justify-center">
            <button
              type="button"
              onClick={() => setLogOffset((prev) => prev + 50)}
              className="rounded-xl bg-[var(--panel)] px-4 py-2 text-[12px] font-medium text-[var(--muted)] transition-colors hover:text-[var(--text)]"
            >
              {zh ? "加载更多" : "Load more"}
            </button>
          </div>
        )}
      </section>
    </section>
  )
}
