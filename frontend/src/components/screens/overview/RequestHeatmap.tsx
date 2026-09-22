import { SegmentedControl } from "@/components/ui/SegmentedControl";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/Tooltip";
import { cn } from "@/lib/classNames";

import {
  formatCompact,
  formatDuration,
  type HeatmapMetric,
  type HeatmapPoint,
} from "./overviewMetrics";

const METRIC_OPTIONS = [
  { value: "requests", zhLabel: "请求", enLabel: "Requests" },
  { value: "tokens", zhLabel: "Token 消耗", enLabel: "Token usage" },
  { value: "duration", zhLabel: "消耗时间", enLabel: "Time spent" },
] satisfies Array<{ value: HeatmapMetric; zhLabel: string; enLabel: string }>;

function metricValue(point: HeatmapPoint, metric: HeatmapMetric) {
  if (metric === "tokens") return point.tokens;
  if (metric === "duration") return point.waitTimeMs;
  return point.count;
}

function legendLabel(metric: HeatmapMetric, isChinese: boolean) {
  if (metric === "tokens")
    return isChinese
      ? { low: "Token 少", high: "Token 多" }
      : { low: "Fewer tokens", high: "More tokens" };
  if (metric === "duration")
    return isChinese
      ? { low: "时间短", high: "时间长" }
      : { low: "Less time", high: "More time" };
  return isChinese
    ? { low: "请求少", high: "请求多" }
    : { low: "Fewer requests", high: "More requests" };
}

function formatDate(value: string, isChinese: boolean) {
  return new Date(`${value}T00:00:00`).toLocaleDateString(
    isChinese ? "zh-CN" : "en-US",
    { year: "numeric", month: isChinese ? "long" : "short", day: "numeric" },
  );
}

function getMonthLabel(month: number, isChinese: boolean) {
  return isChinese
    ? `${month + 1}月`
    : new Date(2024, month, 1).toLocaleDateString("en-US", { month: "short" });
}

type Props = {
  points: HeatmapPoint[];
  total: number;
  metric: HeatmapMetric;
  onMetricChange: (metric: HeatmapMetric) => void;
  isChineseLocale: boolean;
};

/** Render the request activity heatmap. */
export function RequestHeatmap({
  points,
  total,
  metric,
  onMetricChange,
  isChineseLocale,
}: Props) {
  const maxValue = points.reduce(
    (max, point) => Math.max(max, metricValue(point, metric)),
    0,
  );
  const weekCount = Math.ceil(points.length / 7);
  const minGridWidth =
    1.25 + 0.5 + weekCount * 0.75 + Math.max(0, weekCount - 1) * 0.25;
  const labels = legendLabel(metric, isChineseLocale);
  const monthLabels = points.reduce<
    Array<{ key: string; label: string; column: number }>
  >((items, point, index) => {
    const date = new Date(`${point.date}T00:00:00`);
    if (date.getDate() > 7) return items;
    const key = `${date.getFullYear()}-${date.getMonth()}`;
    if (!items.some((item) => item.key === key))
      items.push({
        key,
        label: getMonthLabel(date.getMonth(), isChineseLocale),
        column: Math.floor(index / 7) + 1,
      });
    return items;
  }, []);
  function toneClass(value: number) {
    if (!value || !maxValue) return "bg-muted-foreground/20";
    const level = Math.ceil((value / maxValue) * 4);
    if (level <= 1) return "bg-primary/20";
    if (level === 2) return "bg-primary/40";
    if (level === 3) return "bg-primary/65";
    return "bg-primary";
  }
  return (
    <section className="space-y-3 px-1">
      <div className="flex min-h-10 flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <h3 className="text-sm font-semibold">
            {isChineseLocale ? "热力图" : "Heatmap"}
          </h3>
          <p className="mt-1 text-xs text-muted-foreground">
            {isChineseLocale ? (
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
          </p>
        </div>
        <SegmentedControl
          value={metric}
          onValueChange={onMetricChange}
          options={METRIC_OPTIONS.map((option) => ({
            value: option.value,
            label: isChineseLocale ? option.zhLabel : option.enLabel,
          }))}
        />
      </div>
      <div className="rounded-md bg-muted/35 p-2 md:p-3">
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
              <span className="flex items-center">
                {isChineseLocale ? "一" : "M"}
              </span>
              <span />
              <span className="flex items-center">
                {isChineseLocale ? "三" : "W"}
              </span>
              <span />
              <span className="flex items-center">
                {isChineseLocale ? "五" : "F"}
              </span>
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
                      aria-label={`${formatDate(point.date, isChineseLocale)}，${isChineseLocale ? "请求" : "requests"} ${formatCompact(point.count)}，Token ${formatCompact(point.tokens)}，${isChineseLocale ? "消耗时间" : "time spent"} ${formatDuration(point.waitTimeMs)}`}
                      className={cn(
                        "aspect-square w-full cursor-pointer rounded-[3px] ring-1 ring-foreground/5 transition-colors hover:ring-ring/70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/70",
                        toneClass(metricValue(point, metric)),
                      )}
                    />
                  </TooltipTrigger>
                  <TooltipContent side="top" sideOffset={6} className="block">
                    <div className="grid gap-1">
                      <div className="font-medium">
                        {formatDate(point.date, isChineseLocale)}
                      </div>
                      <div className="grid grid-cols-[auto_auto] gap-x-3 gap-y-1 tabular-nums">
                        <span className="opacity-75">
                          {isChineseLocale ? "请求" : "Requests"}
                        </span>
                        <span>{formatCompact(point.count)}</span>
                        <span className="opacity-75">
                          {isChineseLocale ? "Token 消耗" : "Tokens"}
                        </span>
                        <span>{formatCompact(point.tokens)}</span>
                        <span className="opacity-75">
                          {isChineseLocale ? "消耗时间" : "Time spent"}
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
          <span>{labels.low}</span>
          <span className="size-3 rounded-[3px] bg-muted-foreground/20 ring-1 ring-foreground/5" />
          <span className="size-3 rounded-[3px] bg-primary/20 ring-1 ring-foreground/5" />
          <span className="size-3 rounded-[3px] bg-primary/40 ring-1 ring-foreground/5" />
          <span className="size-3 rounded-[3px] bg-primary/65 ring-1 ring-foreground/5" />
          <span className="size-3 rounded-[3px] bg-primary ring-1 ring-foreground/5" />
          <span>{labels.high}</span>
        </div>
      </div>
    </section>
  );
}
