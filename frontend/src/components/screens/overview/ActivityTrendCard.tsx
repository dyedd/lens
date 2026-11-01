import { useState } from "react";
import { CartesianGrid, Line, LineChart, XAxis, YAxis } from "recharts";
import {
  type ChartConfig,
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from "@/components/ui/Chart";
import { SegmentedControl } from "@/components/ui/SegmentedControl";
import type { Locale } from "@/lib/I18nContext";
import {
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
  isHourly: boolean;
  locale: Locale;
  isLoading: boolean;
  isError: boolean;
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
  isHourly,
  locale,
  isLoading,
  isError,
  heatmapPoints,
  isHeatmapLoading,
  isHeatmapError,
}: Props) {
  const zh = locale === "zh-CN";
  const [view, setView] = useState<"trend" | "heatmap">("trend");
  const [metric, setMetric] = useState<ActivityMetric>("requests");
  const config: ChartConfig = {
    value: {
      label:
        metric === "cost"
          ? zh
            ? "成本"
            : "Cost"
          : metric === "tokens"
            ? "Token"
            : metric === "duration"
              ? zh
                ? "总时长"
                : "Total duration"
              : zh
                ? "请求"
                : "Requests",
      color: "var(--chart-4)",
    },
  };
  const chartPoints = points.map((point) => ({
    ...point,
    value:
      metric === "cost"
        ? point.cost
        : metric === "duration"
          ? point.waitTimeMs
          : metric === "tokens"
            ? point.tokens
            : point.requests,
  }));
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
    <section className="space-y-3 px-1">
      <div className="flex min-h-10 flex-wrap items-center justify-between gap-3">
        <h3 className="text-sm font-semibold">
          {zh ? "请求活动" : "Request activity"}
        </h3>
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs text-muted-foreground">
            {view === "heatmap"
              ? zh
                ? "最近一年 · 按天"
                : "Last year · daily"
              : isHourly
                ? zh
                  ? "今天 · 按小时"
                  : "Today · hourly"
                : zh
                  ? "按天"
                  : "Daily"}
          </span>
          <SegmentedControl
            value={view}
            onValueChange={setView}
            options={[
              { value: "trend", label: zh ? "趋势图" : "Trend" },
              { value: "heatmap", label: zh ? "年度热力图" : "Year heatmap" },
            ]}
          />
          {view === "trend" ? (
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
      {view === "heatmap" ? (
        isHeatmapLoading || isHeatmapError ? (
          <div
            className="rounded-md bg-muted/35 p-6 text-center text-xs text-muted-foreground"
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
        <div className="rounded-md bg-muted/35 p-3 md:p-4">
          {!isLoading && !isError && points.length ? (
            <ChartContainer
              config={config}
              className="h-[220px] w-full sm:h-[260px]"
            >
              <LineChart
                accessibilityLayer
                data={chartPoints}
                margin={{ left: 8, right: 8 }}
              >
                <CartesianGrid vertical={false} strokeDasharray="3 3" />
                <XAxis
                  dataKey="date"
                  tickLine={false}
                  axisLine={false}
                  fontSize={11}
                  minTickGap={16}
                  tickFormatter={formatBucket}
                />
                <YAxis
                  allowDecimals={metric !== "requests"}
                  tickFormatter={
                    metric === "cost"
                      ? formatMoney
                      : metric === "duration"
                        ? (value: number) => formatDuration(value, zh)
                        : undefined
                  }
                  tickLine={false}
                  axisLine={false}
                  fontSize={11}
                />
                <ChartTooltip
                  content={
                    <ChartTooltipContent
                      labelFormatter={(value) => formatBucket(String(value))}
                      formatter={(value, name, item) => (
                        <div className="flex min-w-36 justify-between gap-6">
                          <span className="text-muted-foreground">
                            {config[String(name) as keyof typeof config]
                              ?.label ?? name}
                          </span>
                          <span className="font-medium tabular-nums">
                            {metric === "cost"
                              ? `$${Number(value).toFixed(2)}`
                              : metric === "duration"
                                ? formatDuration(Number(value), zh)
                                : Number(value).toLocaleString()}
                          </span>
                          {metric === "requests" ? (
                            <span className="text-muted-foreground">
                              {zh ? "成功" : "Successful"}{" "}
                              {Number(item.payload.successful).toLocaleString()}
                              {" / "}
                              {zh ? "失败" : "Failed"}{" "}
                              {Number(item.payload.failed).toLocaleString()}
                            </span>
                          ) : null}
                        </div>
                      )}
                    />
                  }
                />
                <Line
                  dataKey="value"
                  type="linear"
                  stroke="var(--chart-4)"
                  strokeWidth={2}
                  dot={chartPoints.length === 1}
                  activeDot={{ r: 4 }}
                />
              </LineChart>
            </ChartContainer>
          ) : (
            <div
              className="flex min-h-[220px] items-center justify-center text-xs text-muted-foreground"
              role="status"
            >
              {message}
            </div>
          )}
        </div>
      )}
    </section>
  );
}
