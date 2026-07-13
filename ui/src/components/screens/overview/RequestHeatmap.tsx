import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/Card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/Select";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/Tooltip";
import { cn } from "@/lib/utils";

import {
  formatCompact,
  formatDuration,
  type HeatmapMetric,
  type HeatmapPoint,
} from "./overviewUtils";

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
    <Card size="sm" className="py-0">
      <CardHeader className="flex flex-col items-start justify-between gap-3 border-b py-4 sm:flex-row sm:items-center">
        <div className="min-w-0">
          <CardTitle className="text-base">
            {isChineseLocale ? "热力图" : "Heatmap"}
          </CardTitle>
          <CardDescription>
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
          </CardDescription>
        </div>
        <Select
          value={metric}
          onValueChange={(value) => onMetricChange(value as HeatmapMetric)}
        >
          <SelectTrigger
            className="w-full sm:w-36"
            aria-label={
              isChineseLocale ? "选择热力图指标" : "Select heatmap metric"
            }
          >
            <SelectValue />
          </SelectTrigger>
          <SelectContent align="end" className="rounded-xl">
            {METRIC_OPTIONS.map((option) => (
              <SelectItem
                key={option.value}
                value={option.value}
                className="rounded-lg"
              >
                {isChineseLocale ? option.zhLabel : option.enLabel}
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
      </CardContent>
    </Card>
  );
}
