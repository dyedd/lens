import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/Tooltip";
import { cn } from "@/lib/classNames";

import type { HeatmapPoint } from "./overviewMetrics";

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
  isChineseLocale: boolean;
};

export function RequestHeatmap({ points, isChineseLocale }: Props) {
  const maxValue = points.reduce((max, point) => Math.max(max, point.count), 0);
  const weekCount = Math.ceil(points.length / 7);
  const minGridWidth =
    1.25 + 0.5 + weekCount * 0.75 + Math.max(0, weekCount - 1) * 0.25;
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
                className="whitespace-nowrap text-xs leading-none text-muted-foreground"
                style={{
                  gridColumn: `${month.column} / span ${Math.min(4, weekCount - month.column + 1)}`,
                }}
              >
                {month.label}
              </div>
            ))}
          </div>
          <div className="grid grid-rows-7 gap-1 text-xs leading-none text-muted-foreground">
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
                    aria-label={`${formatDate(point.date, isChineseLocale)}，${isChineseLocale ? "请求" : "requests"} ${point.count.toLocaleString()}`}
                    className={cn(
                      "aspect-square w-full cursor-pointer rounded-[3px] ring-1 ring-foreground/5 transition-colors hover:ring-ring/70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/70",
                      toneClass(point.count),
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
                      <span>{point.count.toLocaleString()}</span>
                    </div>
                  </div>
                </TooltipContent>
              </Tooltip>
            ))}
          </div>
        </div>
      </div>
      <div className="mt-3 flex items-center justify-end gap-1.5 text-xs text-muted-foreground">
        <span>{isChineseLocale ? "请求少" : "Fewer requests"}</span>
        <span className="size-3 rounded-[3px] bg-muted-foreground/20 ring-1 ring-foreground/5" />
        <span className="size-3 rounded-[3px] bg-primary/20 ring-1 ring-foreground/5" />
        <span className="size-3 rounded-[3px] bg-primary/40 ring-1 ring-foreground/5" />
        <span className="size-3 rounded-[3px] bg-primary/65 ring-1 ring-foreground/5" />
        <span className="size-3 rounded-[3px] bg-primary ring-1 ring-foreground/5" />
        <span>{isChineseLocale ? "请求多" : "More requests"}</span>
      </div>
    </div>
  );
}
