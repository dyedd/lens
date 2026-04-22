"use client"

import { useMemo, useState, type ReactNode } from "react"
import { keepPreviousData, useQuery } from "@tanstack/react-query"
import { Activity, Bot, Boxes, Clock3, DollarSign, KeyRound, Waypoints } from "lucide-react"
import { Bar, BarChart, CartesianGrid, Cell, Label, Pie, PieChart, XAxis, YAxis } from "recharts"
import { GatewayApiKey, OverviewDashboardData, OverviewMetrics, apiRequest } from "@/lib/api"
import { useI18n } from "@/lib/i18n"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { ChartContainer, ChartLegend, ChartLegendContent, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/components/ui/chart"
import { NativeSelect, NativeSelectOption } from "@/components/ui/native-select"
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

function shortenGatewayKeyId(value?: string | null) {
  if (!value) return ""
  if (value.length <= 10) return value
  return `${value.slice(0, 4)}...${value.slice(-4)}`
}

function formatGatewayKeyOptionLabel(item: Pick<GatewayApiKey, "id" | "remark">) {
  return item.remark.trim() || shortenGatewayKeyId(item.id)
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

export function OverviewScreen() {
  const { locale } = useI18n()
  const zh = locale === "zh-CN"

  const [timeRange, setTimeRange] = useState<TimeRange>("-1")
  const [pieMetric, setPieMetric] = useState<PieMetric>("cost")
  const [logOffset, setLogOffset] = useState(0)
  const [selectedGatewayKeyId, setSelectedGatewayKeyId] = useState("all")

  const days = Number(timeRange)
  const effectiveGatewayKeyId = selectedGatewayKeyId === "all" ? null : selectedGatewayKeyId
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
    if (effectiveGatewayKeyId) {
      params.set("gateway_key_id", effectiveGatewayKeyId)
    }
    return `/admin/overview-dashboard?${params.toString()}`
  }, [days, effectiveGatewayKeyId, logOffset])

  const { data: dashboardData } = useQuery({
    queryKey: ["overview-dashboard", days, logOffset, effectiveGatewayKeyId],
    queryFn: () => apiRequest<OverviewDashboardData>(dashboardQuery),
    placeholderData: keepPreviousData,
  })

  const { data: overviewMetrics } = useQuery({
    queryKey: ["overview-metrics"],
    queryFn: () => apiRequest<OverviewMetrics>("/admin/overview"),
    staleTime: 30_000,
  })

  const { data: gatewayApiKeys } = useQuery({
    queryKey: ["gateway-api-keys", "overview-screen"],
    queryFn: () => apiRequest<GatewayApiKey[]>("/admin/gateway-api-keys"),
    staleTime: 60_000,
  })

  const summary = dashboardData?.summary
  const performance = dashboardData?.performance
  const daily = dashboardData?.daily
  const models = dashboardData?.models
  const logs = dashboardData?.logs ?? []

  const gatewayKeyOptions = useMemo(() => {
    const items = (gatewayApiKeys ?? []).map((item) => ({
      id: item.id,
      label: formatGatewayKeyOptionLabel(item),
    }))
    if (effectiveGatewayKeyId && !items.some((item) => item.id === effectiveGatewayKeyId)) {
      items.unshift({
        id: effectiveGatewayKeyId,
        label: shortenGatewayKeyId(effectiveGatewayKeyId),
      })
    }
    return items
  }, [effectiveGatewayKeyId, gatewayApiKeys])

  const periodMetrics = useMemo(() => {
    const source = daily ?? []
    const totalRequests = source.reduce((sum, item) => sum + item.request_count, 0)
    const successfulRequests = source.reduce((sum, item) => sum + item.successful_requests, 0)

    return {
      totalRequests,
      successfulRequests,
    }
  }, [daily])

  const successRate = periodMetrics.totalRequests > 0
    ? Math.round((periodMetrics.successfulRequests / periodMetrics.totalRequests) * 100)
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
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <NativeSelect
            aria-label={zh ? "API Key 筛选" : "API key filter"}
            className="w-full sm:w-56"
            value={selectedGatewayKeyId}
            onChange={(event) => {
              setSelectedGatewayKeyId(event.target.value)
              setLogOffset(0)
            }}
          >
            <NativeSelectOption value="all">{zh ? "全部 API Key" : "All API keys"}</NativeSelectOption>
            {gatewayKeyOptions.map((item) => (
              <NativeSelectOption key={item.id} value={item.id}>{item.label}</NativeSelectOption>
            ))}
          </NativeSelect>
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
      </div>

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
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
          <CardContent className="px-4 pt-3 pb-3">
            <div className="mb-2 flex items-center gap-2 text-sm font-medium">
              <Activity className="size-4 text-muted-foreground" />
              {zh ? "请求统计" : "Requests"}
            </div>
            <div className="flex flex-col gap-3">
              <div className="flex items-center gap-2.5">
                <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-blue-500/15 text-blue-600"><Activity className="size-4" /></span>
                <div className="min-w-0 flex-1">
                  <div className="text-xs text-muted-foreground">{zh ? "请求次数" : "Requests"}</div>
                  <div className="text-base font-semibold">{formatCompact(summary?.request_count.value ?? 0)}</div>
                </div>
              </div>
              <div className="flex items-center gap-2.5">
                <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-emerald-500/15 text-emerald-600"><Activity className="size-4" /></span>
                <div className="min-w-0 flex-1">
                  <div className="text-xs text-muted-foreground">{zh ? "成功请求" : "Success"}</div>
                  <div className="text-base font-semibold">
                    {formatCompact(periodMetrics.successfulRequests)}
                    <span className="text-xs font-normal text-muted-foreground"> ({successRate}%)</span>
                  </div>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card size="sm" className="py-0">
          <CardContent className="px-4 pt-3 pb-3">
            <div className="mb-2 flex items-center gap-2 text-sm font-medium">
              <Bot className="size-4 text-muted-foreground" />
              {zh ? "Token 消耗" : "Token Usage"}
            </div>
            <div className="flex flex-col gap-3">
              <div className="flex items-center gap-2.5">
                <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-blue-500/15 text-blue-600"><Bot className="size-4" /></span>
                <div className="min-w-0 flex-1">
                  <div className="text-xs text-muted-foreground">{zh ? "输入 Token" : "Input Tokens"}</div>
                  <div className="text-base font-semibold">
                    {formatCompact(summary?.input_tokens.value ?? 0)}
                    <span className="text-xs font-normal text-muted-foreground"> / {formatMoney(summary?.input_cost_usd.value ?? 0)}</span>
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-2.5">
                <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-rose-500/15 text-rose-600"><DollarSign className="size-4" /></span>
                <div className="min-w-0 flex-1">
                  <div className="text-xs text-muted-foreground">{zh ? "输出 Token" : "Output Tokens"}</div>
                  <div className="text-base font-semibold">
                    {formatCompact(summary?.output_tokens.value ?? 0)}
                    <span className="text-xs font-normal text-muted-foreground"> / {formatMoney(summary?.output_cost_usd.value ?? 0)}</span>
                  </div>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card size="sm" className="py-0">
          <CardContent className="px-4 pt-3 pb-3">
            <div className="mb-2 flex items-center gap-2 text-sm font-medium">
              <Clock3 className="size-4 text-muted-foreground" />
              {zh ? "性能指标" : "Performance"}
            </div>
            <div className="flex flex-col gap-3">
              <div className="flex items-center gap-2.5">
                <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-blue-500/15 text-blue-600"><Activity className="size-4" /></span>
                <div className="min-w-0 flex-1">
                  <div className="text-xs text-muted-foreground">{zh ? "平均 RPM" : "Avg RPM"}</div>
                  <div className="text-base font-semibold">{formatPerMinute(performance?.avg_requests_per_minute ?? 0)}</div>
                </div>
              </div>
              <div className="flex items-center gap-2.5">
                <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-emerald-500/15 text-emerald-600"><Bot className="size-4" /></span>
                <div className="min-w-0 flex-1">
                  <div className="text-xs text-muted-foreground">{zh ? "平均 TPM" : "Avg TPM"}</div>
                  <div className="text-base font-semibold">{formatPerMinute(performance?.avg_tokens_per_minute ?? 0)}</div>
                </div>
              </div>
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
                      <TableCell className="px-3 py-2.5 whitespace-nowrap text-foreground">{log.created_at.slice(5, 16).replace("T", " ")}</TableCell>
                      <TableCell className="max-w-[180px] truncate px-3 py-2.5 text-foreground">{log.resolved_group_name || log.requested_group_name || "-"}</TableCell>
                      <TableCell className="px-3 py-2.5 text-right whitespace-nowrap text-foreground">
                        <span className="text-muted-foreground">{formatCompact(log.input_tokens)}</span>
                        <span className="mx-0.5 text-border">/</span>
                        <span>{formatCompact(log.output_tokens)}</span>
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
