"use client";

import {
  useEffect,
  useMemo,
  useState,
  type ComponentType,
  type ReactNode,
} from "react";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Label,
  Pie,
  PieChart,
  XAxis,
  YAxis,
} from "recharts";
import {
  Activity,
  ArrowDownToLine,
  ArrowUpFromLine,
  DollarSign,
} from "lucide-react";
import {
  OverviewDailyPoint,
  OverviewModelAnalytics,
  OverviewSummary,
  apiRequest,
} from "@/lib/api";
import { getDateBucketPrefix } from "@/lib/datetime";
import { useAppTimeZone } from "@/hooks/use-app-time-zone";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  ChartContainer,
  ChartLegend,
  ChartLegendContent,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

type TimeRange = "-1" | "7" | "30" | "0";
type PieMetric = "cost" | "requests" | "tokens";
type HeatmapMetric = "requests" | "tokens" | "duration";
type HeatmapPoint = {
  date: string;
  count: number;
  tokens: number;
  waitTimeMs: number;
};
type StatTrendPoint = {
  label: string;
  value: number;
};

const TIME_RANGE_OPTIONS: Array<{
  value: TimeRange;
  zhLabel: string;
  enLabel: string;
}> = [
    { value: "-1", zhLabel: "今天", enLabel: "Today" },
    { value: "7", zhLabel: "近 7 天", enLabel: "Last 7 days" },
    { value: "30", zhLabel: "近 30 天", enLabel: "Last 30 days" },
    { value: "0", zhLabel: "全部", enLabel: "All time" },
  ];

const PIE_METRIC_OPTIONS: Array<{
  value: PieMetric;
  zhLabel: string;
  enLabel: string;
}> = [
    { value: "cost", zhLabel: "费用", enLabel: "Cost" },
    { value: "requests", zhLabel: "请求", enLabel: "Requests" },
    { value: "tokens", zhLabel: "Token", enLabel: "Tokens" },
  ];

const HEATMAP_METRIC_OPTIONS: Array<{
  value: HeatmapMetric;
  zhLabel: string;
  enLabel: string;
}> = [
    { value: "requests", zhLabel: "请求", enLabel: "Requests" },
    { value: "tokens", zhLabel: "Token 消耗", enLabel: "Token usage" },
    { value: "duration", zhLabel: "消耗时间", enLabel: "Time spent" },
  ];

const CHART_COLORS = [
  "var(--chart-4)",
  "var(--chart-3)",
  "var(--chart-2)",
  "var(--chart-1)",
  "var(--chart-5)",
  "var(--primary)",
  "var(--muted-foreground)",
];

function safeKey(name: string) {
  return name.replace(/[^a-zA-Z0-9_-]/g, "_");
}

function formatCompact(value: number, digits = 1) {
  if (value >= 1_000_000_000)
    return (value / 1_000_000_000).toFixed(digits) + "B";
  if (value >= 1_000_000) return (value / 1_000_000).toFixed(digits) + "M";
  if (value >= 1_000) return (value / 1_000).toFixed(digits) + "K";
  return String(Math.round(value));
}

function formatMoney(value: number) {
  if (value >= 1000) return "$" + formatCompact(value, 2);
  return "$" + value.toFixed(value >= 100 ? 0 : 2);
}

function formatDuration(ms: number) {
  if (ms >= 3_600_000) return (ms / 3_600_000).toFixed(1) + "h";
  if (ms >= 60_000) return (ms / 60_000).toFixed(1) + "m";
  if (ms >= 1000) return (ms / 1000).toFixed(1) + "s";
  return Math.round(ms) + "ms";
}

function formatTrendLabel(bucket: string) {
  if (bucket.length >= 10) {
    return `${bucket.slice(8, 10)}:00`;
  }
  return `${bucket.slice(4, 6)}/${bucket.slice(6, 8)}`;
}

function parseDateKey(value: string) {
  if (value.includes("-")) return value;
  if (value.length >= 8) {
    return `${value.slice(0, 4)}-${value.slice(4, 6)}-${value.slice(6, 8)}`;
  }
  return value;
}

function formatSparklineLabel(value: string) {
  const date = parseDateKey(value);
  if (date.length >= 10) return `${date.slice(5, 7)}/${date.slice(8, 10)}`;
  return value;
}

function toLocalDateKey(date: Date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function addDays(date: Date, days: number) {
  const next = new Date(date);
  next.setDate(next.getDate() + days);
  return next;
}

function startOfHeatmapWeek(date: Date) {
  const day = date.getDay();
  const offset = day === 0 ? -6 : 1 - day;
  return addDays(date, offset);
}

function formatHeatmapDate(value: string, zh: boolean) {
  const date = new Date(`${value}T00:00:00`);
  return date.toLocaleDateString(zh ? "zh-CN" : "en-US", {
    year: "numeric",
    month: zh ? "long" : "short",
    day: "numeric",
  });
}

function getMonthLabel(monthIndex: number, zh: boolean) {
  if (zh) return `${monthIndex + 1}月`;
  return new Date(2024, monthIndex, 1).toLocaleDateString("en-US", {
    month: "short",
  });
}

function heatmapMetricValue(point: HeatmapPoint, metric: HeatmapMetric) {
  if (metric === "tokens") return point.tokens;
  if (metric === "duration") return point.waitTimeMs;
  return point.count;
}

function heatmapLegendLabel(metric: HeatmapMetric, zh: boolean) {
  if (metric === "tokens") {
    return zh
      ? { low: "Token 少", high: "Token 多" }
      : { low: "Fewer tokens", high: "More tokens" };
  }
  if (metric === "duration") {
    return zh
      ? { low: "时间短", high: "时间长" }
      : { low: "Less time", high: "More time" };
  }
  return zh
    ? { low: "请求少", high: "请求多" }
    : { low: "Fewer requests", high: "More requests" };
}

function normalizeTrend(points: StatTrendPoint[]) {
  if (points.length >= 2) return points;
  return [
    { label: "", value: 0 },
    { label: "", value: 0 },
  ];
}

function OverviewStatCard({
  icon: Icon,
  title,
  value,
  valueMeta,
  description,
  trend,
  gradientId,
}: {
  icon: ComponentType<{ className?: string }>;
  title: string;
  value: string;
  valueMeta?: ReactNode;
  description: string;
  trend: StatTrendPoint[];
  gradientId: string;
}) {
  return (
    <Card size="sm" className="overflow-hidden py-0">
      <CardHeader className="flex flex-row items-start justify-between gap-3 px-5 pt-5 pb-0">
        <CardTitle className="truncate text-sm font-medium text-muted-foreground">
          {title}
        </CardTitle>
        <span
          aria-hidden="true"
          className="flex size-9 shrink-0 items-center justify-center rounded-full bg-primary/[0.08] text-primary"
        >
          <Icon className="size-4" />
        </span>
      </CardHeader>
      <CardContent className="grid min-h-[148px] grid-cols-[minmax(0,1fr)_38%] grid-rows-[1fr_auto] items-end gap-x-3 gap-y-3 px-5 pt-2 pb-5">
        <div className="min-w-0 self-center">
          <div className="flex min-w-0 flex-wrap items-baseline gap-x-1.5 gap-y-0.5">
            <div className="brand-times-italic shrink-0 text-3xl font-semibold tracking-normal text-foreground tabular-nums">
              {value}
            </div>
            {valueMeta ? (
              <div className="min-w-0 text-xs font-medium text-muted-foreground tabular-nums sm:text-sm">
                {valueMeta}
              </div>
            ) : null}
          </div>
        </div>
        <div className="h-20 min-w-0 self-center">
          <ChartContainer
            config={{ value: { label: title, color: "var(--primary)" } }}
            className="h-full w-full aspect-auto"
            initialDimension={{ width: 160, height: 80 }}
          >
            <AreaChart
              accessibilityLayer
              data={trend}
              margin={{ top: 8, right: 0, left: 0, bottom: 4 }}
            >
              <defs>
                <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
                  <stop
                    offset="5%"
                    stopColor="var(--color-value)"
                    stopOpacity={0.3}
                  />
                  <stop
                    offset="95%"
                    stopColor="var(--color-value)"
                    stopOpacity={0}
                  />
                </linearGradient>
              </defs>
              <YAxis
                hide
                domain={[0, (dataMax: number) => Math.max(dataMax, 1)]}
              />
              <Area
                type="natural"
                dataKey="value"
                stroke="var(--color-value)"
                strokeWidth={2.5}
                fill={`url(#${gradientId})`}
                fillOpacity={1}
                dot={false}
                activeDot={false}
                isAnimationActive={false}
              />
            </AreaChart>
          </ChartContainer>
        </div>
        <div className="col-span-2 min-w-0 truncate text-sm text-muted-foreground tabular-nums">
          {description}
        </div>
      </CardContent>
    </Card>
  );
}

function EmptyBlock({ label }: { label: string }) {
  return (
    <div className="flex min-h-[260px] w-full items-center justify-center rounded-lg border border-dashed text-sm text-muted-foreground">
      {label}
    </div>
  );
}

function RequestHeatmap({
  points,
  total,
  metric,
  onMetricChange,
  zh,
}: {
  points: HeatmapPoint[];
  total: number;
  metric: HeatmapMetric;
  onMetricChange: (metric: HeatmapMetric) => void;
  zh: boolean;
}) {
  const maxValue = points.reduce(
    (max, point) => Math.max(max, heatmapMetricValue(point, metric)),
    0,
  );
  const weekCount = Math.ceil(points.length / 7);
  const minGridWidth =
    1.25 + 0.5 + weekCount * 0.75 + Math.max(0, weekCount - 1) * 0.25;
  const legendLabel = heatmapLegendLabel(metric, zh);
  const monthLabels = points.reduce<
    Array<{ key: string; label: string; column: number }>
  >((labels, point, index) => {
    const date = new Date(`${point.date}T00:00:00`);
    if (date.getDate() > 7) return labels;
    const key = `${date.getFullYear()}-${date.getMonth()}`;
    if (labels.some((label) => label.key === key)) return labels;
    labels.push({
      key,
      label: getMonthLabel(date.getMonth(), zh),
      column: Math.floor(index / 7) + 1,
    });
    return labels;
  }, []);

  const toneClass = (value: number) => {
    if (!value || !maxValue) return "bg-muted-foreground/20";
    const level = Math.ceil((value / maxValue) * 4);
    if (level <= 1) return "bg-primary/20";
    if (level === 2) return "bg-primary/40";
    if (level === 3) return "bg-primary/65";
    return "bg-primary";
  };

  return (
    <Card size="sm" className="py-0">
      <CardHeader className="flex flex-col items-start justify-between gap-3 border-b py-4 sm:flex-row sm:items-center">
        <div className="min-w-0">
          <CardTitle className="text-base">
            {zh ? "热力图" : "Heatmap"}
          </CardTitle>
          <CardDescription>
            {zh ? (
              <>
                最近一年，共{" "}
                <span className="font-medium tabular-nums text-foreground">
                  {formatCompact(total)}
                </span>{" "}
                次请求
              </>
            ) : (
              <>
                <span className="font-medium tabular-nums text-foreground">
                  {formatCompact(total)}
                </span>{" "}
                requests over the last year
              </>
            )}
          </CardDescription>
        </div>
        <Select
          value={metric}
          onValueChange={(value) => onMetricChange(value as HeatmapMetric)}
        >
          <SelectTrigger
            className="w-full sm:w-36"
            aria-label={zh ? "选择热力图指标" : "Select heatmap metric"}
          >
            <SelectValue />
          </SelectTrigger>
          <SelectContent align="end" className="rounded-xl">
            {HEATMAP_METRIC_OPTIONS.map((option) => (
              <SelectItem
                key={option.value}
                value={option.value}
                className="rounded-lg"
              >
                {zh ? option.zhLabel : option.enLabel}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </CardHeader>
      <CardContent className="px-4 py-4">
        <div className="overflow-x-auto pb-1">
          <div
            className="grid w-full grid-cols-[1.25rem_minmax(0,1fr)] gap-x-2"
            style={{ minWidth: `${minGridWidth}rem` }}
          >
            <div />
            <div
              className="mb-1 grid gap-1"
              style={{
                gridTemplateColumns: `repeat(${weekCount}, minmax(0.75rem, 1fr))`,
              }}
            >
              {monthLabels.map((month) => (
                <div
                  key={month.key}
                  className="text-[11px] leading-none text-muted-foreground"
                  style={{ gridColumn: `${month.column} / span 4` }}
                >
                  {month.label}
                </div>
              ))}
            </div>

            <div className="grid grid-rows-7 gap-1 text-[11px] leading-none text-muted-foreground">
              <span className="flex items-center">{zh ? "一" : "M"}</span>
              <span />
              <span className="flex items-center">{zh ? "三" : "W"}</span>
              <span />
              <span className="flex items-center">{zh ? "五" : "F"}</span>
              <span />
              <span />
            </div>
            <div
              className="grid grid-flow-col grid-rows-7 gap-1"
              style={{ gridAutoColumns: "minmax(0.75rem, 1fr)" }}
            >
              {points.map((point) => (
                <Tooltip key={point.date}>
                  <TooltipTrigger asChild>
                    <button
                      type="button"
                      aria-label={`${formatHeatmapDate(point.date, zh)}，${zh ? "请求" : "requests"
                        } ${formatCompact(point.count)}，Token ${formatCompact(
                          point.tokens,
                        )}，${zh ? "消耗时间" : "time spent"
                        } ${formatDuration(point.waitTimeMs)}`}
                      className={cn(
                        "aspect-square w-full cursor-pointer rounded-[3px] ring-1 ring-foreground/5 transition-colors hover:ring-ring/70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/70",
                        toneClass(heatmapMetricValue(point, metric)),
                      )}
                    />
                  </TooltipTrigger>
                  <TooltipContent side="top" sideOffset={6} className="block">
                    <div className="grid gap-1">
                      <div className="font-medium">
                        {formatHeatmapDate(point.date, zh)}
                      </div>
                      <div className="grid grid-cols-[auto_auto] gap-x-3 gap-y-1 tabular-nums">
                        <span className="opacity-75">
                          {zh ? "请求" : "Requests"}
                        </span>
                        <span>{formatCompact(point.count)}</span>
                        <span className="opacity-75">
                          {zh ? "Token 消耗" : "Tokens"}
                        </span>
                        <span>{formatCompact(point.tokens)}</span>
                        <span className="opacity-75">
                          {zh ? "消耗时间" : "Time spent"}
                        </span>
                        <span>{formatDuration(point.waitTimeMs)}</span>
                      </div>
                    </div>
                  </TooltipContent>
                </Tooltip>
              ))}
            </div>
          </div>
        </div>
        <div className="mt-3 flex items-center justify-end gap-1.5 text-[11px] text-muted-foreground">
          <span>{legendLabel.low}</span>
          <span className="size-3 rounded-[3px] bg-muted-foreground/20 ring-1 ring-foreground/5" />
          <span className="size-3 rounded-[3px] bg-primary/20 ring-1 ring-foreground/5" />
          <span className="size-3 rounded-[3px] bg-primary/40 ring-1 ring-foreground/5" />
          <span className="size-3 rounded-[3px] bg-primary/65 ring-1 ring-foreground/5" />
          <span className="size-3 rounded-[3px] bg-primary ring-1 ring-foreground/5" />
          <span>{legendLabel.high}</span>
        </div>
      </CardContent>
    </Card>
  );
}

export function OverviewScreen() {
  const { locale } = useI18n();
  const zh = locale === "zh-CN";

  const [modelRange, setModelRange] = useState<TimeRange>("-1");
  const [pieMetric, setPieMetric] = useState<PieMetric>("cost");
  const [heatmapMetric, setHeatmapMetric] = useState<HeatmapMetric>("requests");

  const modelDays = Number(modelRange);
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
        : "Tokens";
  const modelTrendTitle = zh
    ? `${pieMetricLabel}趋势`
    : `${pieMetricLabel} trend`;
  const modelCardDescription = zh
    ? `模型占比和${pieMetricLabel}趋势`
    : `Model share and ${pieMetricLabel.toLowerCase()} trend`;
  const formatModelMetric = (value: number) =>
    pieMetric === "cost" ? formatMoney(value) : formatCompact(value);

  const modelQuery = useMemo(() => {
    const params = new URLSearchParams({
      days: String(modelDays),
      metric: pieMetric,
    });
    return `/admin/overview-models?${params.toString()}`;
  }, [modelDays, pieMetric]);

  const {
    data: summary,
    error: summaryError,
    isError: summaryIsError,
  } = useQuery({
    queryKey: ["overview-summary", 0],
    queryFn: () =>
      apiRequest<OverviewSummary>("/admin/overview-summary?days=0"),
  });

  const { data: allDaily, error: allDailyError } = useQuery({
    queryKey: ["overview-daily", 0],
    queryFn: () =>
      apiRequest<OverviewDailyPoint[]>("/admin/overview-daily?days=0"),
  });

  const { data: heatmapDaily, error: heatmapDailyError } = useQuery({
    queryKey: ["overview-daily", 365],
    queryFn: () =>
      apiRequest<OverviewDailyPoint[]>("/admin/overview-daily?days=365"),
    staleTime: 60_000,
  });

  const {
    data: models,
    error: modelsError,
    isError: modelsIsError,
  } = useQuery({
    queryKey: ["overview-models", modelDays, pieMetric],
    queryFn: () => apiRequest<OverviewModelAnalytics>(modelQuery),
  });

  const timeZone = useAppTimeZone();

  const pageError = summaryIsError
    ? summaryError
    : allDailyError ||
    heatmapDailyError ||
    (modelsIsError ? modelsError : null);

  useEffect(() => {
    if (!pageError) return;
    toast.error(zh ? "总览数据加载失败" : "Failed to load overview", {
      id: "overview-load-error",
      description:
        pageError instanceof Error
          ? pageError.message
          : zh
            ? "无法读取总览数据"
            : "Unable to read overview data",
    });
  }, [pageError, zh]);

  const allMetrics = useMemo(() => {
    const source = allDaily ?? [];
    const successfulRequests = source.reduce(
      (sum, item) => sum + item.successful_requests,
      0,
    );
    return {
      successfulRequests,
    };
  }, [allDaily]);

  const statTrends = useMemo(() => {
    const source = allDaily ?? [];
    const dailyMap = new Map(
      source.map((point) => [parseDateKey(point.date), point]),
    );
    const today = new Date();
    const buckets = Array.from({ length: 30 }, (_, index) => {
      const date = toLocalDateKey(addDays(today, index - 29));
      return {
        date,
        point: dailyMap.get(date),
      };
    });
    const buildTrend = (getValue: (point: OverviewDailyPoint) => number) =>
      normalizeTrend(
        buckets.map(({ date, point }) => ({
          label: formatSparklineLabel(date),
          value: point ? getValue(point) : 0,
        })),
      );

    return {
      requests: buildTrend((point) => point.request_count),
      cost: buildTrend((point) => point.total_cost_usd),
      inputTokens: buildTrend((point) => point.input_tokens ?? 0),
      outputTokens: buildTrend((point) => point.output_tokens ?? 0),
    };
  }, [allDaily]);

  const requestCount = summary?.request_count.value ?? 0;
  const totalCost = summary?.total_cost_usd.value ?? 0;
  const inputTokens = summary?.input_tokens.value ?? 0;
  const outputTokens = summary?.output_tokens.value ?? 0;
  const inputCost = summary?.input_cost_usd.value ?? 0;
  const outputCost = summary?.output_cost_usd.value ?? 0;
  const cacheReadTokens = summary?.cache_read_input_tokens.value ?? 0;
  const cacheWriteTokens = summary?.cache_write_input_tokens.value ?? 0;
  const successRate = requestCount
    ? Math.round((allMetrics.successfulRequests / requestCount) * 100)
    : 0;
  const consumedTime = summary?.wait_time_ms.value ?? 0;

  const pieData = useMemo(() => {
    if (!models) return { data: [], total: 0 };
    const source = models.distribution;
    const getValue = (item: (typeof source)[number]) => {
      if (pieMetric === "requests") return item.requests;
      if (pieMetric === "tokens") return item.total_tokens;
      return item.total_cost_usd;
    };
    const total = source.reduce((sum, item) => sum + getValue(item), 0);
    return {
      data: source.map((item) => ({
        model: item.model,
        value: getValue(item),
        requests: item.requests,
        total_cost_usd: item.total_cost_usd,
      })),
      total,
    };
  }, [models, pieMetric]);

  const pieChartConfig = useMemo(() => {
    const config: ChartConfig = {};
    models?.distribution.forEach((item, i) => {
      config[item.model] = {
        label: item.model,
        color: CHART_COLORS[i % CHART_COLORS.length],
      };
    });
    return config;
  }, [models]);

  const { barData, barConfig, barModels } = useMemo(() => {
    if (!models)
      return {
        barData: [],
        barConfig: {} as ChartConfig,
        barModels: [] as string[],
      };

    const isHourlyTrend = modelDays === -1;
    const modelSet = (
      models.distribution.length
        ? models.distribution.map((item) => item.model)
        : [...new Set(models.trend.map((point) => point.model))]
    ).slice(0, 12);
    if (!modelSet.length)
      return {
        barData: [],
        barConfig: {} as ChartConfig,
        barModels: [] as string[],
      };
    const dateMap = new Map<string, Record<string, number>>();

    for (const point of models.trend) {
      if (!modelSet.includes(point.model)) continue;
      const key = safeKey(point.model);
      const existing = dateMap.get(point.date) ?? {};
      existing[key] = (existing[key] ?? 0) + point.value;
      dateMap.set(point.date, existing);
    }

    const sortedDates = [...dateMap.keys()].sort();
    const trendBuckets = isHourlyTrend
      ? Array.from(
        { length: 24 },
        (_, hour) =>
          `${getDateBucketPrefix(timeZone)}${String(hour).padStart(2, "0")}`,
      )
      : sortedDates;
    const data = trendBuckets.map((bucket) => ({
      date: formatTrendLabel(bucket),
      ...(dateMap.get(bucket) ?? {}),
    }));

    const config: ChartConfig = {};
    const safeModels: string[] = [];
    modelSet.forEach((model, i) => {
      const key = safeKey(model);
      safeModels.push(key);
      config[key] = {
        label: model,
        color: CHART_COLORS[i % CHART_COLORS.length],
      };
    });

    return { barData: data, barConfig: config, barModels: safeModels };
  }, [modelDays, models, timeZone]);

  const heatmap = useMemo(() => {
    const source = heatmapDaily ?? [];
    const pointMap = new Map(
      source.map((item) => [
        parseDateKey(item.date),
        {
          count: item.request_count,
          tokens: item.total_tokens,
          waitTimeMs: item.wait_time_ms,
        },
      ]),
    );
    const today = new Date();
    const start = startOfHeatmapWeek(addDays(today, -364));
    const length =
      Math.floor(
        (new Date(toLocalDateKey(today)).getTime() -
          new Date(toLocalDateKey(start)).getTime()) /
        86_400_000,
      ) + 1;
    const points = Array.from({ length }, (_, index) => {
      const date = toLocalDateKey(addDays(start, index));
      const point = pointMap.get(date);
      return {
        date,
        count: point?.count ?? 0,
        tokens: point?.tokens ?? 0,
        waitTimeMs: point?.waitTimeMs ?? 0,
      };
    });
    return {
      points,
      total: points.reduce((sum, point) => sum + point.count, 0),
    };
  }, [heatmapDaily]);

  return (
    <section className="flex flex-col gap-4">
      <section>
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <OverviewStatCard
            icon={Activity}
            title={zh ? "请求总量" : "Total requests"}
            value={formatCompact(requestCount)}
            valueMeta={
              <>
                <span className="brand-times-italic tabular-nums">
                  {successRate}%
                </span>{" "}
                {zh ? "成功率" : "success rate"}
              </>
            }
            description={`${zh ? "消耗时间" : "Time spent"} ${formatDuration(consumedTime)}`}
            trend={statTrends.requests}
            gradientId="overview-requests-trend"
          />
          <OverviewStatCard
            icon={DollarSign}
            title={zh ? "总费用" : "Total spend"}
            value={formatMoney(totalCost)}
            description={`${zh ? "输入" : "Input"} ${formatMoney(inputCost)} + ${zh ? "输出" : "Output"} ${formatMoney(outputCost)}`}
            trend={statTrends.cost}
            gradientId="overview-cost-trend"
          />
          <OverviewStatCard
            icon={ArrowDownToLine}
            title={zh ? "输入 Tokens" : "Input tokens"}
            value={formatCompact(inputTokens)}
            description={`${zh ? "缓存读取" : "Cache read"} ${formatCompact(cacheReadTokens)}`}
            trend={statTrends.inputTokens}
            gradientId="overview-input-token-trend"
          />
          <OverviewStatCard
            icon={ArrowUpFromLine}
            title={zh ? "输出 Tokens" : "Output tokens"}
            value={formatCompact(outputTokens)}
            description={`${zh ? "缓存写入" : "Cache write"} ${formatCompact(cacheWriteTokens)}`}
            trend={statTrends.outputTokens}
            gradientId="overview-output-token-trend"
          />
        </div>
      </section>

      <RequestHeatmap
        points={heatmap.points}
        total={heatmap.total}
        metric={heatmapMetric}
        onMetricChange={setHeatmapMetric}
        zh={zh}
      />

      <Card size="sm" className="py-0">
        <CardHeader className="flex flex-col items-start justify-between gap-3 border-b py-4 lg:flex-row lg:items-center">
          <div className="min-w-0">
            <CardTitle className="text-base">
              {zh ? "模型分析" : "Model analytics"}
            </CardTitle>
            <CardDescription>{modelCardDescription}</CardDescription>
          </div>
          <div className="flex w-full flex-col gap-2 sm:w-auto sm:flex-row">
            <Select
              value={pieMetric}
              onValueChange={(value) => setPieMetric(value as PieMetric)}
            >
              <SelectTrigger
                className="w-full sm:w-32"
                aria-label={zh ? "选择模型占比指标" : "Select model metric"}
              >
                <SelectValue />
              </SelectTrigger>
              <SelectContent align="end" className="rounded-xl">
                {PIE_METRIC_OPTIONS.map((option) => (
                  <SelectItem
                    key={option.value}
                    value={option.value}
                    className="rounded-lg"
                  >
                    {zh ? option.zhLabel : option.enLabel}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select
              value={modelRange}
              onValueChange={(value) => setModelRange(value as TimeRange)}
            >
              <SelectTrigger
                className="w-full sm:w-36"
                aria-label={zh ? "选择模型统计范围" : "Select model range"}
              >
                <SelectValue />
              </SelectTrigger>
              <SelectContent align="end" className="rounded-xl">
                {TIME_RANGE_OPTIONS.map((option) => (
                  <SelectItem
                    key={option.value}
                    value={option.value}
                    className="rounded-lg"
                  >
                    {zh ? option.zhLabel : option.enLabel}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </CardHeader>
        <CardContent className="grid gap-5 p-4 lg:grid-cols-[minmax(18rem,0.72fr)_minmax(0,1fr)]">
          <div className="min-w-0">
            <div className="mb-3 text-sm font-medium text-foreground">
              {zh ? "模型组合" : "Model mix"}
            </div>
            {pieData.data.length ? (
              <div className="grid gap-3">
                <ChartContainer
                  config={pieChartConfig}
                  className="mx-auto h-[240px] w-full max-w-[300px]"
                >
                  <PieChart>
                    <ChartTooltip
                      content={
                        <ChartTooltipContent nameKey="model" hideLabel />
                      }
                    />
                    <Pie
                      data={pieData.data}
                      dataKey="value"
                      nameKey="model"
                      innerRadius={58}
                      outerRadius={96}
                      paddingAngle={2}
                    >
                      <Label
                        content={({ viewBox }) => {
                          if (
                            !viewBox ||
                            !("cx" in viewBox) ||
                            !("cy" in viewBox)
                          ) {
                            return null;
                          }

                          return (
                            <text
                              x={viewBox.cx}
                              y={viewBox.cy}
                              textAnchor="middle"
                              dominantBaseline="middle"
                            >
                              <tspan
                                x={viewBox.cx}
                                y={viewBox.cy}
                                className="brand-times-italic fill-foreground text-xl font-semibold tabular-nums"
                              >
                                {pieMetric === "cost"
                                  ? formatMoney(pieData.total)
                                  : formatCompact(pieData.total)}
                              </tspan>
                              <tspan
                                x={viewBox.cx}
                                y={(viewBox.cy || 0) + 20}
                                className="fill-muted-foreground text-xs"
                              >
                                {pieMetricLabel}
                              </tspan>
                            </text>
                          );
                        }}
                      />
                      {pieData.data.map((_, index) => (
                        <Cell
                          key={index}
                          fill={CHART_COLORS[index % CHART_COLORS.length]}
                        />
                      ))}
                    </Pie>
                  </PieChart>
                </ChartContainer>
                <div className="grid max-h-24 grid-cols-2 gap-x-3 gap-y-1 overflow-y-auto pr-1 text-[11px] text-muted-foreground">
                  {pieData.data.map((item, index) => (
                    <div
                      key={`${item.model}-${index}`}
                      className="flex min-w-0 items-center gap-1.5"
                      title={item.model}
                    >
                      <span
                        className="size-2 shrink-0 rounded-[2px]"
                        style={{
                          backgroundColor:
                            CHART_COLORS[index % CHART_COLORS.length],
                        }}
                      />
                      <span className="truncate">{item.model}</span>
                    </div>
                  ))}
                </div>
              </div>
            ) : modelsIsError ? null : (
              <EmptyBlock
                label={zh ? "暂无模型占比数据" : "No model mix data"}
              />
            )}
          </div>

          <div className="min-w-0 lg:border-l lg:pl-5">
            <div className="mb-3 text-sm font-medium text-foreground">
              {modelTrendTitle}
            </div>
            {barData.length ? (
              <ChartContainer
                config={barConfig}
                className="h-[260px] w-full sm:h-[320px]"
              >
                <BarChart
                  accessibilityLayer
                  data={barData}
                  margin={{ left: 8, right: 8 }}
                >
                  <CartesianGrid vertical={false} strokeDasharray="3 3" />
                  <XAxis
                    dataKey="date"
                    tickLine={false}
                    axisLine={false}
                    fontSize={11}
                  />
                  <YAxis
                    tickLine={false}
                    axisLine={false}
                    fontSize={11}
                    tickFormatter={formatModelMetric}
                  />
                  <ChartTooltip content={<ChartTooltipContent />} />
                  <ChartLegend
                    content={
                      <ChartLegendContent className="flex-wrap justify-start gap-x-3 gap-y-2 pb-3" />
                    }
                  />
                  {barModels.map((key) => (
                    <Bar
                      key={key}
                      dataKey={key}
                      stackId="a"
                      fill={barConfig[key]?.color}
                      radius={[4, 4, 0, 0]}
                    />
                  ))}
                </BarChart>
              </ChartContainer>
            ) : modelsIsError ? null : (
              <EmptyBlock label={zh ? "暂无消耗趋势数据" : "No trend data"} />
            )}
          </div>
        </CardContent>
      </Card>
    </section>
  );
}
