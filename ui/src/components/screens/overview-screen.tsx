"use client"

import { useMemo, useState, type ReactNode } from "react"
import { keepPreviousData, useQuery } from "@tanstack/react-query"
import {
  Activity,
  ArrowDownToLine,
  ArrowUpFromLine,
  Bot,
  Boxes,
  CheckCircle2,
  CircleX,
  Clock3,
  Database,
  Gauge,
  KeyRound,
  Upload,
  Waypoints,
} from "lucide-react"
import { Bar, BarChart, CartesianGrid, Cell, Label, Pie, PieChart, XAxis, YAxis } from "recharts"
import { OverviewDashboardData, OverviewMetrics, apiRequest } from "@/lib/api"
import { formatLogDateTime } from "@/lib/datetime"
import { useI18n } from "@/lib/i18n"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { ChartContainer, ChartLegend, ChartLegendContent, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/components/ui/chart"
import { SegmentedControl } from "@/components/ui/segmented-control"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"

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
  return Math.round(ms) + "ms"
}

function formatPerMinute(value: number) {
  if (value >= 1000) return formatCompact(value, 1) + "/m"
  if (value >= 100) return value.toFixed(0) + "/m"
  if (value >= 10) return value.toFixed(1) + "/m"
  return value.toFixed(2) + "/m"
}

function formatTrendLabel(bucket: string) {
  if (bucket.length >= 10) {
    return `${bucket.slice(8, 10)}:00`
  }
  return `${bucket.slice(4, 6)}/${bucket.slice(6, 8)}`
}

function getTodayBucketPrefix() {
  const now = new Date()
  const year = String(now.getFullYear())
  const month = String(now.getMonth() + 1).padStart(2, "0")
  const day = String(now.getDate()).padStart(2, "0")
  return `${year}${month}${day}`
}

function formatRatio(current: number, total: number) {
  return `${formatCompact(current, 0)}/${formatCompact(total, 0)}`
}

function OverviewStatCard({
  icon,
  label,
  value,
  toneClassName,
}: {
  icon: ReactNode
  label: string
  value: string
  toneClassName: string
}) {
  return (
    <Card size="sm" className="py-0">
      <CardContent className="px-4 pt-3 pb-3">
        <div className="flex items-center gap-2.5">
          <span className={`flex size-9 shrink-0 items-center justify-center rounded-full ${toneClassName}`}>
            {icon}
          </span>
          <div className="min-w-0 flex-1">
            <div className="text-xs text-muted-foreground">{label}</div>
            <div className="text-base font-semibold">{value}</div>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

function OverviewMetricCell({
  icon,
  label,
  value,
  toneClassName,
}: {
  icon: ReactNode
  label: string
  value: string
  toneClassName: string
}) {
  return (
    <div className="flex min-w-0 items-center gap-2.5 rounded-xl bg-muted/20 px-3 py-2.5">
      <span className={`flex size-8 shrink-0 items-center justify-center rounded-full ${toneClassName}`}>
        {icon}
      </span>
      <div className="min-w-0 flex-1">
        <div className="truncate text-xs text-muted-foreground">{label}</div>
        <div className="mt-1 truncate text-base font-semibold leading-5 text-foreground">{value}</div>
      </div>
    </div>
  )
}

export function OverviewScreen() {
  const { locale } = useI18n()
  const zh = locale === "zh-CN"

  const [timeRange, setTimeRange] = useState<TimeRange>("-1")
  const [pieMetric, setPieMetric] = useState<PieMetric>("cost")
  const [logOffset, setLogOffset] = useState(0)

  const days = Number(timeRange)
  const pieMetricLabel = zh
    ? pieMetric === "cost"
      ? "费用"
      : pieMetric === "requests"
        ? "请求"
        : "Token"
    : pieMetric === "cost"
      ? "Cost"
      : pieMetric === "requests"
        ? "Requests"
        : "Tokens"

  const dashboardQuery = useMemo(() => {
    const params = new URLSearchParams({
      days: String(days),
      log_limit: "50",
      log_offset: String(logOffset),
    })
    return `/admin/overview-dashboard?${params.toString()}`
  }, [days, logOffset])

  const { data: dashboardData } = useQuery({
    queryKey: ["overview-dashboard", days, logOffset],
    queryFn: () => apiRequest<OverviewDashboardData>(dashboardQuery),
    placeholderData: keepPreviousData,
  })

  const { data: overviewMetrics } = useQuery({
    queryKey: ["overview-metrics"],
    queryFn: () => apiRequest<OverviewMetrics>("/admin/overview"),
    staleTime: 30_000,
  })

  const summary = dashboardData?.summary
  const performance = dashboardData?.performance
  const daily = dashboardData?.daily
  const models = dashboardData?.models
  const logs = dashboardData?.logs ?? []

  const periodMetrics = useMemo(() => {
    const source = daily ?? []
    const totalRequests = source.reduce((sum, item) => sum + item.request_count, 0)
    const successfulRequests = source.reduce((sum, item) => sum + item.successful_requests, 0)
    const failedRequests = source.reduce((sum, item) => sum + item.failed_requests, 0)

    return {
      totalRequests,
      successfulRequests,
      failedRequests,
    }
  }, [daily])

  const successRate = periodMetrics.totalRequests > 0
    ? Math.round((periodMetrics.successfulRequests / periodMetrics.totalRequests) * 100)
    : 0
  const avgLatencyMs = summary?.request_count.value
    ? summary.wait_time_ms.value / summary.request_count.value
    : 0
  const avgTokensPerRequest = summary?.request_count.value
    ? summary.total_tokens.value / summary.request_count.value
    : 0

  const pieData = useMemo(() => {
    if (!models) return { data: [], total: 0 }
    const source = models.distribution
    const getValue = (item: typeof source[number]) => {
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
      config[item.model] = {
        label: item.model,
        color: CHART_COLORS[i % CHART_COLORS.length],
      }
    })
    return config
  }, [models])

  const { barData, barConfig, barModels } = useMemo(() => {
    if (!models) return { barData: [], barConfig: {} as ChartConfig, barModels: [] as string[] }

    const isHourlyTrend = days === -1
    const modelSet = [...new Set(models.trend.map((point) => point.model))].slice(0, 12)
    if (!modelSet.length) return { barData: [], barConfig: {} as ChartConfig, barModels: [] as string[] }
    const dateMap = new Map<string, Record<string, number>>()

    for (const point of models.trend) {
      if (!modelSet.includes(point.model)) continue
      const key = safeKey(point.model)
      const existing = dateMap.get(point.date) ?? {}
      existing[key] = (existing[key] ?? 0) + point.value
      dateMap.set(point.date, existing)
    }

    const sortedDates = [...dateMap.keys()].sort()
    const trendBuckets = isHourlyTrend
      ? Array.from({ length: 24 }, (_, hour) => `${getTodayBucketPrefix()}${String(hour).padStart(2, "0")}`)
      : sortedDates
    const data = trendBuckets.map((bucket) => ({
      date: formatTrendLabel(bucket),
      ...(dateMap.get(bucket) ?? {}),
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
  }, [days, models])

  return (
    <section className="flex flex-col gap-3 md:gap-4">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <h1 className="text-xl font-semibold text-foreground">{zh ? "总览" : "Overview"}</h1>
        <SegmentedControl
          value={timeRange}
          onValueChange={(value) => {
            setTimeRange(value as TimeRange)
            setLogOffset(0)
          }}
          options={[
            { value: "-1", label: zh ? "今天" : "Today" },
            { value: "7", label: zh ? "近7天" : "7 days" },
            { value: "30", label: zh ? "近30天" : "30 days" },
            { value: "0", label: zh ? "全部" : "All" },
          ]}
        />
      </div>

      <div className="grid grid-cols-1 items-start gap-3 lg:grid-cols-3">
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:col-span-3 lg:grid-cols-4">
          <OverviewStatCard
            icon={<Waypoints className="size-4" />}
            label={zh ? "渠道" : "Channels"}
            value={formatRatio(overviewMetrics?.enabled_channels ?? 0, overviewMetrics?.total_channels ?? 0)}
            toneClassName="bg-amber-500/15 text-amber-600"
          />
          <OverviewStatCard
            icon={<Boxes className="size-4" />}
            label={zh ? "模型组" : "Model groups"}
            value={formatRatio(overviewMetrics?.enabled_groups ?? 0, overviewMetrics?.total_groups ?? 0)}
            toneClassName="bg-violet-500/15 text-violet-600"
          />
          <OverviewStatCard
            icon={<KeyRound className="size-4" />}
            label="API Key"
            value={formatRatio(overviewMetrics?.enabled_gateway_keys ?? 0, overviewMetrics?.total_gateway_keys ?? 0)}
            toneClassName="bg-emerald-500/15 text-emerald-600"
          />
          <OverviewStatCard
            icon={<Clock3 className="size-4" />}
            label={zh ? "AI 编码时长" : "AI coding time"}
            value={formatDuration(summary?.wait_time_ms.value ?? 0)}
            toneClassName="bg-sky-500/15 text-sky-600"
          />
        </div>

        <Card size="sm" className="py-0">
          <CardContent className="px-4 py-3">
            <div className="mb-2 flex items-center gap-2 pl-3 text-sm font-medium">
              <Activity className="size-4 text-muted-foreground" />
              {zh ? "请求统计" : "Requests"}
            </div>
            <div className="grid grid-cols-2 gap-2">
              <OverviewMetricCell
                icon={<Activity className="size-4" />}
                label={zh ? "请求次数" : "Requests"}
                value={formatCompact(summary?.request_count.value ?? 0)}
                toneClassName="bg-blue-500/15 text-blue-600"
              />
              <OverviewMetricCell
                icon={<CheckCircle2 className="size-4" />}
                label={zh ? "成功请求" : "Success"}
                value={formatCompact(periodMetrics.successfulRequests)}
                toneClassName="bg-emerald-500/15 text-emerald-600"
              />
              <OverviewMetricCell
                icon={<CircleX className="size-4" />}
                label={zh ? "失败请求" : "Failed"}
                value={formatCompact(periodMetrics.failedRequests)}
                toneClassName="bg-rose-500/15 text-rose-600"
              />
              <OverviewMetricCell
                icon={<Gauge className="size-4" />}
                label={zh ? "成功率" : "Success Rate"}
                value={`${successRate}%`}
                toneClassName="bg-amber-500/15 text-amber-600"
              />
            </div>
          </CardContent>
        </Card>

        <Card size="sm" className="py-0">
          <CardContent className="px-4 py-3">
            <div className="mb-2 flex items-center gap-2 pl-3 text-sm font-medium">
              <Bot className="size-4 text-muted-foreground" />
              {zh ? "Token 消耗" : "Token Usage"}
            </div>
            <div className="grid grid-cols-2 gap-2">
              <OverviewMetricCell
                icon={<ArrowDownToLine className="size-4" />}
                label={zh ? "输入 Token" : "Input Tokens"}
                value={`${formatCompact(summary?.input_tokens.value ?? 0)} / ${formatMoney(summary?.input_cost_usd.value ?? 0)}`}
                toneClassName="bg-blue-500/15 text-blue-600"
              />
              <OverviewMetricCell
                icon={<ArrowUpFromLine className="size-4" />}
                label={zh ? "输出 Token" : "Output Tokens"}
                value={`${formatCompact(summary?.output_tokens.value ?? 0)} / ${formatMoney(summary?.output_cost_usd.value ?? 0)}`}
                toneClassName="bg-rose-500/15 text-rose-600"
              />
              <OverviewMetricCell
                icon={<Database className="size-4" />}
                label={zh ? "缓存读取" : "Cache Read"}
                value={formatCompact(summary?.cache_read_input_tokens.value ?? 0)}
                toneClassName="bg-emerald-500/15 text-emerald-600"
              />
              <OverviewMetricCell
                icon={<Upload className="size-4" />}
                label={zh ? "缓存写入" : "Cache Write"}
                value={formatCompact(summary?.cache_write_input_tokens.value ?? 0)}
                toneClassName="bg-amber-500/15 text-amber-600"
              />
            </div>
          </CardContent>
        </Card>

        <Card size="sm" className="py-0">
          <CardContent className="px-4 py-3">
            <div className="mb-2 flex items-center gap-2 pl-3 text-sm font-medium">
              <Clock3 className="size-4 text-muted-foreground" />
              {zh ? "性能指标" : "Performance"}
            </div>
            <div className="grid grid-cols-2 gap-2">
              <OverviewMetricCell
                icon={<Activity className="size-4" />}
                label={zh ? "平均 RPM" : "Avg RPM"}
                value={formatPerMinute(performance?.avg_requests_per_minute ?? 0)}
                toneClassName="bg-blue-500/15 text-blue-600"
              />
              <OverviewMetricCell
                icon={<Bot className="size-4" />}
                label={zh ? "平均 TPM" : "Avg TPM"}
                value={formatPerMinute(performance?.avg_tokens_per_minute ?? 0)}
                toneClassName="bg-emerald-500/15 text-emerald-600"
              />
              <OverviewMetricCell
                icon={<Clock3 className="size-4" />}
                label={zh ? "平均耗时" : "Avg Latency"}
                value={formatDuration(avgLatencyMs)}
                toneClassName="bg-sky-500/15 text-sky-600"
              />
              <OverviewMetricCell
                icon={<Database className="size-4" />}
                label={zh ? "Token / 次" : "Tokens / Request"}
                value={formatCompact(avgTokensPerRequest)}
                toneClassName="bg-violet-500/15 text-violet-600"
              />
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-3 xl:grid-cols-[minmax(0,1fr)_260px]">
        <Card size="sm" className="py-0">
          <CardHeader className="flex flex-row items-center justify-between gap-2 border-b py-4">
            <CardTitle className="flex-1 text-base">{zh ? "模型占比" : "Model share"}</CardTitle>
            <SegmentedControl
              value={pieMetric}
              onValueChange={(value) => setPieMetric(value as PieMetric)}
              options={[
                { value: "cost", label: zh ? "费用" : "Cost" },
                { value: "requests", label: zh ? "请求" : "Requests" },
                { value: "tokens", label: "Token" },
              ]}
            />
          </CardHeader>
          <CardContent className="flex-1 pb-0 pt-4">
            {pieData.data.length ? (
              <ChartContainer config={pieChartConfig} className="mx-auto aspect-square max-h-[300px]">
                <PieChart>
                  <ChartTooltip content={<ChartTooltipContent nameKey="model" hideLabel />} />
                  <Pie data={pieData.data} dataKey="value" nameKey="model" innerRadius={60} outerRadius={100} paddingAngle={2}>
                    <Label
                      content={({ viewBox }) => {
                        if (!viewBox || !("cx" in viewBox) || !("cy" in viewBox)) {
                          return null
                        }

                        return (
                          <text x={viewBox.cx} y={viewBox.cy} textAnchor="middle" dominantBaseline="middle">
                            <tspan x={viewBox.cx} y={viewBox.cy} className="fill-foreground text-xl font-semibold">
                              {pieMetric === "cost" ? formatMoney(pieData.total) : formatCompact(pieData.total)}
                            </tspan>
                            <tspan x={viewBox.cx} y={(viewBox.cy || 0) + 20} className="fill-muted-foreground text-xs">
                              {pieMetricLabel}
                            </tspan>
                          </text>
                        )
                      }}
                    />
                    {pieData.data.map((_, index) => (
                      <Cell key={index} fill={CHART_COLORS[index % CHART_COLORS.length]} />
                    ))}
                  </Pie>
                  <ChartLegend content={<ChartLegendContent nameKey="model" className="flex-nowrap gap-3 text-[11px]" />} />
                </PieChart>
              </ChartContainer>
            ) : (
              <div className="flex h-[280px] w-full items-center justify-center text-sm text-muted-foreground">{zh ? "暂无数据" : "No data"}</div>
            )}
          </CardContent>
          <CardFooter className="hidden" />
        </Card>

        <Card size="sm" className="py-0">
          <CardHeader className="border-b py-4">
            <CardTitle className="text-base">{zh ? "调用排行" : "Calls rank"}</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-2 py-4">
            {models?.request_ranking.slice(0, 6).map((item, index) => (
              <div key={`${item.model}-${index}`} className="rounded-md border bg-muted/20 px-3 py-2.5">
                <div className="truncate text-sm font-medium text-foreground">{item.model}</div>
                <div className="mt-1.5 flex items-center justify-between text-xs text-muted-foreground">
                  <span>{zh ? "请求" : "Requests"} {formatCompact(item.requests)}</span>
                  <span>{zh ? "费用" : "Cost"} {formatMoney(item.total_cost_usd)}</span>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>

      <Card size="sm" className="py-0">
        <CardHeader className="border-b py-4">
          <CardTitle className="text-base">{zh ? "消耗趋势" : "Cost trend"}</CardTitle>
        </CardHeader>
        <CardContent className="px-2 pt-4 sm:px-4">
          {barData.length ? (
            <ChartContainer config={barConfig} className="h-[300px] w-full">
              <BarChart accessibilityLayer data={barData} margin={{ left: 8, right: 8 }}>
                <CartesianGrid vertical={false} strokeDasharray="3 3" />
                <XAxis dataKey="date" tickLine={false} axisLine={false} fontSize={11} />
                <YAxis tickLine={false} axisLine={false} fontSize={11} tickFormatter={(value: number) => formatMoney(value)} />
                <ChartTooltip content={<ChartTooltipContent />} />
                <ChartLegend content={<ChartLegendContent className="pb-3" />} />
                {barModels.map((key) => (
                  <Bar key={key} dataKey={key} stackId="a" fill={barConfig[key]?.color} radius={[3, 3, 0, 0]} />
                ))}
              </BarChart>
            </ChartContainer>
          ) : (
            <div className="flex h-[280px] w-full items-center justify-center text-sm text-muted-foreground">{zh ? "暂无模型日志数据" : "No model logs yet"}</div>
          )}
        </CardContent>
        <CardFooter className="hidden" />
      </Card>

      <Card size="sm" className="py-0">
        <CardHeader className="px-4 pt-4 pb-0">
          <CardTitle className="text-base">{zh ? "消费日志" : "Consume log"}</CardTitle>
        </CardHeader>
        <CardContent className="px-4 py-4">
          <div className="overflow-hidden rounded-lg border bg-background">
            {logs.length > 0 ? (
              <Table className="text-xs">
                <TableHeader>
                  <TableRow className="hover:bg-transparent">
                    <TableHead className="px-3 py-2.5 font-medium text-muted-foreground">{zh ? "时间" : "Time"}</TableHead>
                    <TableHead className="px-3 py-2.5 font-medium text-muted-foreground">{zh ? "模型" : "Model"}</TableHead>
                    <TableHead className="px-3 py-2.5 text-right font-medium text-muted-foreground">Token</TableHead>
                    <TableHead className="px-3 py-2.5 text-right font-medium text-muted-foreground">{zh ? "费用" : "Cost"}</TableHead>
                    <TableHead className="px-3 py-2.5 text-right font-medium text-muted-foreground">{zh ? "延迟" : "Latency"}</TableHead>
                    <TableHead className="px-3 py-2.5 font-medium text-muted-foreground">{zh ? "状态" : "Status"}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {logs.map((log) => (
                    <TableRow key={log.id}>
                      <TableCell className="px-3 py-2.5 whitespace-nowrap text-foreground">{formatLogDateTime(log.created_at, locale)}</TableCell>
                      <TableCell className="max-w-[180px] truncate px-3 py-2.5 text-foreground">{log.resolved_group_name || log.requested_group_name || "-"}</TableCell>
                      <TableCell className="px-3 py-2.5 text-right whitespace-nowrap text-foreground">
                        <div>
                          <span className="text-muted-foreground">{formatCompact(log.input_tokens)}</span>
                          <span className="mx-0.5 text-border">/</span>
                          <span>{formatCompact(log.output_tokens)}</span>
                        </div>
                        <div className="mt-0.5 text-[11px] text-muted-foreground">
                          {zh ? "缓存" : "Cache"}: {zh ? "读" : "R"} {formatCompact(log.cache_read_input_tokens)} / {zh ? "写" : "W"} {formatCompact(log.cache_write_input_tokens)}
                        </div>
                      </TableCell>
                      <TableCell className="px-3 py-2.5 text-right whitespace-nowrap text-foreground">{formatMoney(log.total_cost_usd)}</TableCell>
                      <TableCell className="px-3 py-2.5 text-right whitespace-nowrap text-foreground">{formatDuration(log.latency_ms)}</TableCell>
                      <TableCell className="px-3 py-2.5 whitespace-nowrap">
                        <Badge variant={log.success ? "secondary" : "destructive"} className="px-2 py-0.5">
                          {log.success ? (zh ? "成功" : "OK") : log.status_code}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            ) : (
              <div className="flex h-24 items-center justify-center text-sm text-muted-foreground">{zh ? "暂无日志" : "No logs"}</div>
            )}
          </div>

          {logs.length >= 50 ? (
            <div className="mt-3 flex justify-center">
              <Button type="button" variant="outline" size="sm" onClick={() => setLogOffset((current) => current + 50)}>
                {zh ? "加载更多" : "Load more"}
              </Button>
            </div>
          ) : null}
        </CardContent>
      </Card>
    </section>
  )
}
