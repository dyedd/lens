import { useId, useMemo } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  XAxis,
  YAxis,
} from "recharts";
import {
  type ChartConfig,
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from "@/components/ui/Chart";
import type {
  AttributionDimension,
  OverviewAttributionItem,
  OverviewAttributionTrendPoint,
} from "@/lib/api/overview";
import { cn } from "@/lib/classNames";
import {
  AttributionIcon,
  formatAttributionDisplayLabel,
} from "./AttributionIcon";
import {
  type AnalysisMetric,
  CHART_COLORS,
  formatCompact,
  formatDuration,
  formatMoney,
  formatTrendLabel,
} from "./overviewMetrics";

type SeriesEntry = {
  id: string;
  key: string;
  label: string;
  color: string;
  metricValue: number;
  cost: number;
  tokens: number;
  requests: number;
  share: number;
  isOther?: boolean;
};

function getMetricValue(
  item: OverviewAttributionItem,
  metric: AnalysisMetric,
): number {
  if (metric === "cost") return item.total_cost_usd;
  if (metric === "tokens") return item.total_tokens;
  if (metric === "duration") return item.wait_time_ms;
  if (metric === "cache") return item.cache_hit_rate ?? 0;
  return item.requests;
}

function formatSharePercent(share: number) {
  const pct = share * 100;
  if (pct >= 10) return `${Math.round(pct)}%`;
  if (pct > 0 && pct < 0.1) return "<0.1%";
  return `${pct.toFixed(1)}%`;
}

export function AttributionVisualGrid({
  items,
  trend,
  dimension,
  metric,
  metricLabel,
  selectedKey,
  onSelectKey,
  zh,
}: {
  items: OverviewAttributionItem[];
  trend: OverviewAttributionTrendPoint[];
  dimension: AttributionDimension;
  metric: AnalysisMetric;
  metricLabel: string;
  selectedKey: string | null;
  onSelectKey: (key: string | null) => void;
  zh: boolean;
}) {
  const gradientId = useId().replace(/:/g, "");
  const rankMetric: AnalysisMetric = metric === "cache" ? "tokens" : metric;

  const { series, totalMetric, chartData } = useMemo(() => {
    const sorted = [...items].sort(
      (a, b) =>
        getMetricValue(b, rankMetric) - getMetricValue(a, rankMetric) ||
        b.requests - a.requests,
    );
    const total = sorted.reduce(
      (sum, item) => sum + Math.max(0, getMetricValue(item, rankMetric)),
      0,
    );
    const primaryItems = sorted.slice(0, 5);
    const overflowItems = sorted.slice(5);
    const entries: SeriesEntry[] = primaryItems.map((item, index) => {
      const value = Math.max(0, getMetricValue(item, rankMetric));
      return {
        id: `s_${index}`,
        key: item.key,
        label: formatAttributionDisplayLabel(
          item.key,
          item.label,
          dimension,
          zh,
        ),
        color: CHART_COLORS[index % CHART_COLORS.length],
        metricValue: value,
        cost: item.total_cost_usd,
        tokens: item.total_tokens,
        requests: item.requests,
        share: total > 0 ? value / total : 0,
      };
    });

    if (overflowItems.length > 0) {
      const otherMetric = overflowItems.reduce(
        (sum, item) => sum + Math.max(0, getMetricValue(item, rankMetric)),
        0,
      );
      if (otherMetric > 0) {
        entries.push({
          id: "s_other",
          key: "__other__",
          label: zh
            ? `其余 ${overflowItems.length} 项`
            : `Other (${overflowItems.length})`,
          color: "var(--muted-foreground)",
          metricValue: otherMetric,
          cost: overflowItems.reduce(
            (sum, item) => sum + item.total_cost_usd,
            0,
          ),
          tokens: overflowItems.reduce(
            (sum, item) => sum + item.total_tokens,
            0,
          ),
          requests: overflowItems.reduce((sum, item) => sum + item.requests, 0),
          share: total > 0 ? otherMetric / total : 0,
          isOther: true,
        });
      }
    }

    const activeEntries =
      selectedKey !== null
        ? entries.filter((entry) => entry.key === selectedKey)
        : entries;
    const keyToSeriesId = new Map(
      entries
        .filter((entry) => !entry.isOther)
        .map((entry) => [entry.key, entry.id]),
    );
    const selectedOutsideTop =
      selectedKey !== null && !keyToSeriesId.has(selectedKey);
    const byDate = new Map<string, Record<string, number | string>>();
    for (const point of trend) {
      if (point.value === null) continue;
      let row = byDate.get(point.date);
      if (!row) {
        row = { date: point.date };
        byDate.set(point.date, row);
      }
      if (selectedKey !== null) {
        if (point.key === selectedKey) {
          const id = keyToSeriesId.get(point.key) ?? "s_focus";
          row[id] = Number(row[id] ?? 0) + point.value;
        }
      } else {
        const id = keyToSeriesId.get(point.key) ?? "s_other";
        row[id] = Number(row[id] ?? 0) + point.value;
      }
    }

    const finalSeries = selectedOutsideTop
      ? (() => {
          const item = items.find((candidate) => candidate.key === selectedKey);
          if (!item) return activeEntries;
          const value = Math.max(0, getMetricValue(item, rankMetric));
          return [
            {
              id: "s_focus",
              key: item.key,
              label: formatAttributionDisplayLabel(
                item.key,
                item.label,
                dimension,
                zh,
              ),
              color: CHART_COLORS[0],
              metricValue: value,
              cost: item.total_cost_usd,
              tokens: item.total_tokens,
              requests: item.requests,
              share: total > 0 ? value / total : 0,
            },
          ];
        })()
      : activeEntries;

    const sortedRows = Array.from(byDate.values()).sort((left, right) =>
      String(left.date).localeCompare(String(right.date)),
    );

    return { series: finalSeries, totalMetric: total, chartData: sortedRows };
  }, [dimension, items, rankMetric, selectedKey, trend, zh]);

  const chartConfig = useMemo<ChartConfig>(() => {
    const config: ChartConfig = {};
    for (const entry of series) {
      config[entry.id] = { label: entry.label, color: entry.color };
    }
    return config;
  }, [series]);

  function formatMetricValue(value: number) {
    if (metric === "cost") return formatMoney(value);
    if (metric === "duration") return formatDuration(value, zh);
    if (metric === "cache") return `${(value * 100).toFixed(1)}%`;
    return formatCompact(value);
  }

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
      <div className="flex min-w-0 flex-col justify-between rounded-xl border border-border/55 bg-card p-4 lg:col-span-7">
        <div className="space-y-3">
          <div className="flex items-center justify-between gap-2">
            <h4 className="text-[13px] font-medium text-muted-foreground">
              {metric === "cache"
                ? zh
                  ? "缓存命中趋势"
                  : "Cache hit trend"
                : zh
                  ? `${metricLabel}分布趋势`
                  : `${metricLabel} trend`}
            </h4>
            {selectedKey !== null ? (
              <button
                type="button"
                className="text-xs text-muted-foreground transition-colors hover:text-foreground"
                onClick={() => onSelectKey(null)}
              >
                {zh ? "显示全部" : "Show all"}
              </button>
            ) : null}
          </div>
          <div className="flex flex-wrap gap-1.5">
            {series.map((entry) => {
              const active = selectedKey === entry.key;
              return (
                <button
                  key={entry.id}
                  type="button"
                  disabled={entry.isOther}
                  onClick={() => {
                    if (entry.isOther) return;
                    onSelectKey(active ? null : entry.key);
                  }}
                  className={cn(
                    "inline-flex max-w-[180px] items-center gap-1.5 rounded-lg border px-2 py-1 text-xs font-medium transition-colors",
                    active
                      ? "border-foreground/30 bg-muted text-foreground"
                      : "border-border/60 bg-card/80 text-muted-foreground hover:bg-muted/60 hover:text-foreground",
                    entry.isOther && "cursor-default opacity-80",
                  )}
                >
                  <span
                    className="size-2 shrink-0 rounded-[2px]"
                    style={{ backgroundColor: entry.color }}
                  />
                  {!entry.isOther ? (
                    <AttributionIcon
                      dimension={dimension}
                      itemKey={entry.key}
                      size={14}
                    />
                  ) : null}
                  <span className="truncate">{entry.label}</span>
                </button>
              );
            })}
          </div>
        </div>

        <div className="mt-4">
          {chartData.length ? (
            <ChartContainer config={chartConfig} className="h-[196px] w-full">
              {metric === "cache" ? (
                <AreaChart
                  accessibilityLayer
                  data={chartData}
                  margin={{ left: 0, right: 4, top: 8, bottom: 0 }}
                >
                  <defs>
                    {series.map((entry) => (
                      <linearGradient
                        key={entry.id}
                        id={`${gradientId}-${entry.id}`}
                        x1="0"
                        y1="0"
                        x2="0"
                        y2="1"
                      >
                        <stop
                          offset="0%"
                          stopColor={entry.color}
                          stopOpacity={0.18}
                        />
                        <stop
                          offset="95%"
                          stopColor={entry.color}
                          stopOpacity={0.01}
                        />
                      </linearGradient>
                    ))}
                  </defs>
                  <CartesianGrid
                    vertical={false}
                    strokeDasharray="3 3"
                    strokeOpacity={0.45}
                  />
                  <XAxis
                    dataKey="date"
                    tickFormatter={formatTrendLabel}
                    tickLine={false}
                    axisLine={false}
                    fontSize={11}
                    minTickGap={20}
                  />
                  <YAxis
                    width={42}
                    domain={[0, 1]}
                    tickFormatter={(value) => formatMetricValue(Number(value))}
                    tickLine={false}
                    axisLine={false}
                    fontSize={11}
                  />
                  <ChartTooltip
                    content={
                      <ChartTooltipContent
                        labelFormatter={(value) =>
                          formatTrendLabel(String(value))
                        }
                        formatter={(value, name) => (
                          <div className="flex min-w-32 items-center justify-between gap-4">
                            <span className="text-muted-foreground">
                              {chartConfig[String(name)]?.label ?? name}
                            </span>
                            <span className="font-medium tabular-nums">
                              {formatMetricValue(Number(value))}
                            </span>
                          </div>
                        )}
                      />
                    }
                  />
                  {series
                    .filter((entry) => !entry.isOther)
                    .map((entry) => (
                      <Area
                        key={entry.id}
                        dataKey={entry.id}
                        type="monotone"
                        stroke={entry.color}
                        strokeWidth={1.8}
                        fill={`url(#${gradientId}-${entry.id})`}
                        dot={chartData.length === 1}
                        connectNulls={false}
                      />
                    ))}
                </AreaChart>
              ) : (
                <BarChart
                  accessibilityLayer
                  data={chartData}
                  margin={{ left: 0, right: 4, top: 8, bottom: 0 }}
                >
                  <CartesianGrid
                    vertical={false}
                    strokeDasharray="3 3"
                    strokeOpacity={0.45}
                  />
                  <XAxis
                    dataKey="date"
                    tickFormatter={formatTrendLabel}
                    tickLine={false}
                    axisLine={false}
                    fontSize={11}
                    minTickGap={20}
                  />
                  <YAxis
                    width={46}
                    tickFormatter={(value) => formatMetricValue(Number(value))}
                    tickLine={false}
                    axisLine={false}
                    fontSize={11}
                  />
                  <ChartTooltip
                    content={
                      <ChartTooltipContent
                        labelFormatter={(value) =>
                          formatTrendLabel(String(value))
                        }
                        formatter={(value, name) => (
                          <div className="flex min-w-36 items-center justify-between gap-4">
                            <span className="text-muted-foreground">
                              {chartConfig[String(name)]?.label ?? name}
                            </span>
                            <span className="font-medium tabular-nums">
                              {formatMetricValue(Number(value))}
                            </span>
                          </div>
                        )}
                      />
                    }
                  />
                  {series.map((entry, idx) => (
                    <Bar
                      key={entry.id}
                      dataKey={entry.id}
                      stackId="usage"
                      fill={entry.color}
                      maxBarSize={18}
                      radius={
                        idx === series.length - 1 ? [3, 3, 0, 0] : [0, 0, 0, 0]
                      }
                    />
                  ))}
                </BarChart>
              )}
            </ChartContainer>
          ) : (
            <div className="flex h-[196px] items-center justify-center text-xs text-muted-foreground">
              {zh ? "当前条件下暂无趋势样本" : "No trend points in window"}
            </div>
          )}
        </div>
      </div>

      <div className="flex min-w-0 flex-col justify-between rounded-xl border border-border/55 bg-card p-4 lg:col-span-5">
        <div className="space-y-4">
          <div className="flex items-center justify-between gap-2">
            <h4 className="text-[13px] font-medium text-muted-foreground">
              {zh ? "构成占比" : "Share breakdown"}
            </h4>
            <span className="font-mono text-xs tabular-nums text-muted-foreground">
              {rankMetric === "cost"
                ? formatMoney(totalMetric)
                : rankMetric === "duration"
                  ? formatDuration(totalMetric, zh)
                  : formatCompact(totalMetric)}
            </span>
          </div>

          <div
            className="flex h-2.5 w-full overflow-hidden rounded-full bg-muted/80"
            aria-hidden="true"
          >
            {series.map((entry) =>
              entry.share > 0 ? (
                <div
                  key={entry.id}
                  className="h-full transition-all first:rounded-l-full last:rounded-r-full"
                  style={{
                    width: `${Math.max(entry.share * 100, 1.5)}%`,
                    backgroundColor: entry.color,
                  }}
                />
              ) : null,
            )}
          </div>

          <ul className="space-y-2">
            {series.map((entry) => {
              const active = selectedKey === entry.key;
              return (
                <li key={entry.id}>
                  <button
                    type="button"
                    disabled={entry.isOther}
                    onClick={() => {
                      if (entry.isOther) return;
                      onSelectKey(active ? null : entry.key);
                    }}
                    className={cn(
                      "flex w-full items-center justify-between gap-3 rounded-lg px-2 py-1.5 text-left transition-colors",
                      active ? "bg-muted text-foreground" : "hover:bg-muted/50",
                      entry.isOther && "cursor-default hover:bg-transparent",
                    )}
                  >
                    <div className="flex min-w-0 items-center gap-2">
                      <span
                        className="size-2 shrink-0 rounded-[2px]"
                        style={{ backgroundColor: entry.color }}
                      />
                      {!entry.isOther ? (
                        <AttributionIcon
                          dimension={dimension}
                          itemKey={entry.key}
                          size={16}
                        />
                      ) : null}
                      <span className="truncate text-[13px] font-medium text-foreground">
                        {entry.label}
                      </span>
                    </div>
                    <div className="flex shrink-0 items-center gap-3 font-mono text-xs tabular-nums text-muted-foreground">
                      <span>{formatMoney(entry.cost)}</span>
                      <span className="w-12 text-right">
                        {formatCompact(entry.tokens)}
                      </span>
                      <span className="w-11 text-right font-medium text-foreground">
                        {formatSharePercent(entry.share)}
                      </span>
                    </div>
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      </div>
    </div>
  );
}
