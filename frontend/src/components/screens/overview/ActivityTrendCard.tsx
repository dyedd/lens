import { useId, useState } from "react";
import { Area, AreaChart, CartesianGrid, XAxis, YAxis } from "recharts";
import {
  type ChartConfig,
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from "@/components/ui/Chart";
import { SegmentedControl } from "@/components/ui/SegmentedControl";
import type { Locale } from "@/lib/I18nContext";
import {
  formatCompact,
  formatDuration,
  formatMoney,
  type HeatmapPoint,
} from "./overviewMetrics";
import { RequestHeatmap } from "./RequestHeatmap";

export type ActivityPoint = {
  date: string;
  requests: number;
  successful: number;
  failed: number;
  cost: number;
  waitTimeMs: number;
  tokens: number;
};

type ActivityMetric = "requests" | "tokens" | "cost" | "duration";

type Props = {
  points: ActivityPoint[];
  locale: Locale;
  isLoading: boolean;
  isError: boolean;
  showHeatmapOption?: boolean;
  heatmapPoints: HeatmapPoint[];
  isHeatmapLoading: boolean;
  isHeatmapError: boolean;
};

function formatBucket(bucket: string) {
  return bucket.length === 10
    ? `${bucket.slice(8, 10)}:00`
    : `${bucket.slice(4, 6)}/${bucket.slice(6, 8)}`;
}

export function ActivityTrendCard({
  points,
  locale,
  isLoading,
  isError,
  showHeatmapOption = false,
  heatmapPoints,
  isHeatmapLoading,
  isHeatmapError,
}: Props) {
  const zh = locale === "zh-CN";
  const gradientId = useId().replace(/:/g, "");
  const [view, setView] = useState<"trend" | "heatmap">("trend");
  const [metric, setMetric] = useState<ActivityMetric>("requests");
  const effectiveView =
    showHeatmapOption && view === "heatmap" ? "heatmap" : "trend";

  const primaryLabel =
    metric === "cost"
      ? zh
        ? "成本"
        : "Cost"
      : metric === "tokens"
        ? "Tokens"
        : metric === "duration"
          ? zh
            ? "总时长"
            : "Duration"
          : zh
            ? "请求"
            : "Requests";
  const secondaryMetric: "avgLatency" | "requests" =
    metric === "duration" ? "requests" : "avgLatency";
  const secondaryLabel =
    secondaryMetric === "requests"
      ? zh
        ? "请求数"
        : "Requests"
      : zh
        ? "平均耗时"
        : "Avg latency";

  const config: ChartConfig = {
    value: { label: primaryLabel, color: "var(--trend-primary)" },
    secondaryValue: { label: secondaryLabel, color: "var(--trend-secondary)" },
  };

  const chartPoints = points.map((point) => {
    const avgLatencyMs =
      point.requests > 0 ? Math.round(point.waitTimeMs / point.requests) : 0;
    return {
      ...point,
      value:
        metric === "cost"
          ? point.cost
          : metric === "duration"
            ? point.waitTimeMs
            : metric === "tokens"
              ? point.tokens
              : point.requests,
      secondaryValue:
        secondaryMetric === "requests" ? point.requests : avgLatencyMs,
    };
  });

  function formatPrimaryValue(value: number) {
    if (metric === "cost") return formatMoney(value);
    if (metric === "duration") return formatDuration(value, zh);
    return formatCompact(value);
  }

  function formatPrimaryTooltip(value: number) {
    if (metric === "cost") return `$${value.toFixed(2)}`;
    if (metric === "duration") return formatDuration(value, zh);
    return value.toLocaleString();
  }

  function formatSecondaryValue(value: number) {
    if (secondaryMetric === "requests") return formatCompact(value);
    return formatDuration(value, zh);
  }

  const message = isLoading
    ? zh
      ? "正在加载请求趋势…"
      : "Loading request trend…"
    : isError
      ? zh
        ? "请求趋势加载失败，请刷新重试"
        : "Unable to load request trend. Refresh to retry."
      : zh
        ? "当前时段暂无请求"
        : "No requests in this period";

  return (
    <section className="overflow-hidden rounded-xl border border-border/55 bg-card">
      <div className="flex min-h-10 flex-wrap items-center justify-between gap-3 px-5 pt-4 pb-2">
        <h3 className="page-section-title">
          {zh ? "请求活动" : "Request activity"}
        </h3>
        <div className="flex flex-wrap items-center gap-2">
          {showHeatmapOption ? (
            <SegmentedControl
              value={effectiveView}
              onValueChange={setView}
              options={[
                { value: "trend", label: zh ? "趋势图" : "Trend" },
                {
                  value: "heatmap",
                  label: zh ? "年度热力图" : "Year heatmap",
                },
              ]}
            />
          ) : null}
          {effectiveView === "trend" ? (
            <SegmentedControl
              value={metric}
              onValueChange={setMetric}
              options={[
                { value: "requests", label: zh ? "请求" : "Requests" },
                { value: "tokens", label: "Token" },
                { value: "cost", label: zh ? "成本" : "Cost" },
                { value: "duration", label: zh ? "总时长" : "Duration" },
              ]}
            />
          ) : null}
        </div>
      </div>
      <div className="p-4 sm:p-5">
        {effectiveView === "heatmap" ? (
          isHeatmapLoading || isHeatmapError ? (
            <div
              className="rounded-xl bg-muted/35 p-6 text-center text-xs text-muted-foreground"
              role="status"
            >
              {isHeatmapError
                ? zh
                  ? "请求活动加载失败，请刷新重试"
                  : "Unable to load request activity. Refresh to retry."
                : zh
                  ? "正在加载请求活动…"
                  : "Loading request activity…"}
            </div>
          ) : (
            <RequestHeatmap points={heatmapPoints} isChineseLocale={zh} />
          )
        ) : (
          <div className="pt-1">
            {!isLoading && !isError && points.length ? (
              <div className="space-y-3">
                <ChartContainer
                  config={config}
                  className="h-[240px] w-full sm:h-[268px]"
                >
                  <AreaChart
                    accessibilityLayer
                    data={chartPoints}
                    margin={{ left: 4, right: 4, top: 8, bottom: 0 }}
                  >
                    <defs>
                      <linearGradient
                        id={`${gradientId}-area`}
                        x1="0"
                        y1="0"
                        x2="0"
                        y2="1"
                      >
                        <stop
                          offset="0%"
                          stopColor="var(--trend-primary)"
                          stopOpacity={0.22}
                        />
                        <stop
                          offset="95%"
                          stopColor="var(--trend-primary)"
                          stopOpacity={0.01}
                        />
                      </linearGradient>
                    </defs>
                    <CartesianGrid
                      vertical={false}
                      strokeDasharray="3 3"
                      strokeOpacity={0.5}
                    />
                    <XAxis
                      dataKey="date"
                      tickLine={false}
                      axisLine={false}
                      fontSize={11}
                      minTickGap={20}
                      tickMargin={8}
                      tickFormatter={formatBucket}
                    />
                    <YAxis
                      yAxisId="left"
                      width={48}
                      allowDecimals={metric === "cost"}
                      tickFormatter={(value) =>
                        formatPrimaryValue(Number(value))
                      }
                      tickLine={false}
                      axisLine={false}
                      fontSize={11}
                    />
                    <YAxis
                      yAxisId="right"
                      orientation="right"
                      width={46}
                      allowDecimals={false}
                      tickFormatter={(value) =>
                        formatSecondaryValue(Number(value))
                      }
                      tickLine={false}
                      axisLine={false}
                      fontSize={11}
                    />
                    <ChartTooltip
                      content={
                        <ChartTooltipContent
                          labelFormatter={(value) =>
                            formatBucket(String(value))
                          }
                          formatter={(value, name, item) => {
                            if (String(name) === "secondaryValue") {
                              return (
                                <div className="flex min-w-36 items-center justify-between gap-4">
                                  <span className="text-muted-foreground">
                                    {secondaryLabel}
                                  </span>
                                  <span className="font-medium tabular-nums">
                                    {formatSecondaryValue(Number(value))}
                                  </span>
                                </div>
                              );
                            }
                            return (
                              <div className="flex min-w-40 items-center justify-between gap-4">
                                <span className="text-muted-foreground">
                                  {primaryLabel}
                                </span>
                                <span className="font-medium tabular-nums">
                                  {formatPrimaryTooltip(Number(value))}
                                </span>
                                {metric === "requests" ? (
                                  <span className="text-xs text-muted-foreground">
                                    {zh ? "成功" : "OK"}{" "}
                                    {Number(
                                      item.payload.successful,
                                    ).toLocaleString()}
                                    {" · "}
                                    {zh ? "失败" : "Err"}{" "}
                                    {Number(
                                      item.payload.failed,
                                    ).toLocaleString()}
                                  </span>
                                ) : null}
                              </div>
                            );
                          }}
                        />
                      }
                    />
                    <Area
                      yAxisId="left"
                      dataKey="value"
                      type="monotone"
                      stroke="var(--trend-primary)"
                      strokeWidth={2}
                      fill={`url(#${gradientId}-area)`}
                      dot={chartPoints.length === 1}
                      activeDot={{ r: 4 }}
                    />
                    <Area
                      yAxisId="right"
                      dataKey="secondaryValue"
                      type="monotone"
                      stroke="var(--trend-secondary)"
                      strokeWidth={1.6}
                      strokeDasharray="4 4"
                      fill="transparent"
                      dot={false}
                      activeDot={{ r: 3.5 }}
                    />
                  </AreaChart>
                </ChartContainer>
                <div className="flex flex-wrap items-center justify-center gap-5 pt-1 text-xs text-muted-foreground">
                  <span className="inline-flex items-center gap-1.5">
                    <span
                      className="size-2.5 rounded-[3px]"
                      style={{ backgroundColor: "var(--trend-primary)" }}
                    />
                    <span>{primaryLabel}</span>
                  </span>
                  <span className="inline-flex items-center gap-1.5">
                    <span
                      className="size-2.5 rounded-[3px]"
                      style={{ backgroundColor: "var(--trend-secondary)" }}
                    />
                    <span>{secondaryLabel}</span>
                  </span>
                </div>
              </div>
            ) : (
              <div
                className="flex min-h-[240px] items-center justify-center text-xs text-muted-foreground"
                role="status"
              >
                {message}
              </div>
            )}
          </div>
        )}
      </div>
    </section>
  );
}
