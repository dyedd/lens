import {
  Activity,
  Archive,
  ArrowDownToLine,
  ArrowUpFromLine,
  Braces,
  CalendarDays,
  Check,
  ChevronDown,
  CircleCheck,
  Database,
  DollarSign,
  HardDrive,
  Timer,
} from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/Button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/Popover";
import { cn } from "@/lib/classNames";
import { OverviewStatCard, type OverviewStatView } from "./OverviewStatCard";
import {
  formatCompact,
  formatDuration,
  formatMoney,
  TIME_RANGE_OPTIONS,
  type TimeRange,
} from "./overviewMetrics";

type Props = {
  cacheReadTokens: number;
  cacheWriteTokens: number;
  consumedTime: number;
  inputCost: number;
  inputTokens: number;
  isChineseLocale: boolean;
  outputCost: number;
  outputTokens: number;
  requestCount: number;
  successRate: number;
  totalCost: number;
  totalTokens: number;
  timeRange: TimeRange;
  onTimeRangeChange: (range: TimeRange) => void;
};

/** Render the four overview summary metrics. */
export function OverviewStats(props: Props) {
  const {
    cacheReadTokens,
    cacheWriteTokens,
    consumedTime,
    inputCost,
    inputTokens,
    isChineseLocale,
    outputCost,
    outputTokens,
    requestCount,
    successRate,
    totalCost,
    totalTokens,
    timeRange,
    onTimeRangeChange,
  } = props;
  const [rangeOpen, setRangeOpen] = useState(false);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const rangeLabel =
    TIME_RANGE_OPTIONS.find((option) => option.value === timeRange)?.[
      isChineseLocale ? "zhLabel" : "enLabel"
    ] ?? (isChineseLocale ? "近 30 天" : "Last 30 days");
  const metricGroups = [
    [
      {
        icon: Activity,
        title: isChineseLocale ? "请求总量" : "Total requests",
        value: formatCompact(requestCount),
      },
      {
        icon: CircleCheck,
        title: isChineseLocale ? "成功率" : "Success rate",
        value: `${successRate}%`,
      },
      {
        icon: Timer,
        title: isChineseLocale ? "总耗时" : "Total time",
        value: formatDuration(consumedTime),
      },
    ],
    [
      {
        icon: DollarSign,
        title: isChineseLocale ? "预估成本" : "Estimated cost",
        value: formatMoney(totalCost),
      },
      {
        icon: ArrowDownToLine,
        title: isChineseLocale ? "输入成本" : "Input cost",
        value: formatMoney(inputCost),
      },
      {
        icon: ArrowUpFromLine,
        title: isChineseLocale ? "输出成本" : "Output cost",
        value: formatMoney(outputCost),
      },
    ],
    [
      {
        icon: Braces,
        title: isChineseLocale ? "Token 总数" : "Total tokens",
        value: formatCompact(totalTokens),
      },
      {
        icon: ArrowDownToLine,
        title: isChineseLocale ? "输入 Tokens" : "Input tokens",
        value: formatCompact(inputTokens),
      },
      {
        icon: ArrowUpFromLine,
        title: isChineseLocale ? "输出 Tokens" : "Output tokens",
        value: formatCompact(outputTokens),
      },
    ],
    [
      {
        icon: Database,
        title: isChineseLocale ? "缓存 Tokens" : "Cache tokens",
        value: formatCompact(cacheReadTokens + cacheWriteTokens),
      },
      {
        icon: Archive,
        title: isChineseLocale ? "缓存读取" : "Cache read",
        value: formatCompact(cacheReadTokens),
      },
      {
        icon: HardDrive,
        title: isChineseLocale ? "缓存写入" : "Cache write",
        value: formatCompact(cacheWriteTokens),
      },
    ],
  ] satisfies OverviewStatView[][];

  return (
    <section className="space-y-3">
      <div className="flex min-h-10 flex-wrap items-center justify-between gap-3 px-1">
        <h3 className="page-title">
          {isChineseLocale ? "运行概览" : "Overview metrics"}
        </h3>
        <div className="flex flex-wrap items-center justify-end gap-1.5">
          <Popover open={rangeOpen} onOpenChange={setRangeOpen}>
            <PopoverTrigger asChild>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="h-8 max-w-[220px] gap-1.5 px-2 text-sm font-normal text-muted-foreground shadow-none hover:bg-muted hover:text-foreground data-[state=open]:bg-muted data-[state=open]:text-foreground"
                aria-label={
                  isChineseLocale ? "选择时间范围" : "Select time range"
                }
              >
                <CalendarDays className="size-3.5 shrink-0 stroke-1" />
                <span className="truncate">{rangeLabel}</span>
              </Button>
            </PopoverTrigger>
            <PopoverContent align="end" className="w-44 p-2">
              <div className="space-y-0.5">
                {TIME_RANGE_OPTIONS.map((option) => {
                  const selected = option.value === timeRange;
                  return (
                    <Button
                      key={option.value}
                      type="button"
                      variant="ghost"
                      size="sm"
                      className={cn(
                        "h-8 w-full justify-start px-2 text-sm font-normal shadow-none",
                        selected && "bg-accent",
                      )}
                      onClick={() => {
                        onTimeRangeChange(option.value);
                        setRangeOpen(false);
                      }}
                    >
                      {isChineseLocale ? option.zhLabel : option.enLabel}
                      {selected ? <Check className="ml-auto size-3.5" /> : null}
                    </Button>
                  );
                })}
              </div>
            </PopoverContent>
          </Popover>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-8 gap-1.5 px-2 text-sm font-normal text-muted-foreground shadow-none hover:bg-muted hover:text-foreground"
            aria-expanded={detailsOpen}
            aria-label={
              detailsOpen
                ? isChineseLocale
                  ? "收起指标详情"
                  : "Collapse metric details"
                : isChineseLocale
                  ? "展开指标详情"
                  : "Expand metric details"
            }
            onClick={() => setDetailsOpen((open) => !open)}
          >
            <ChevronDown
              className={cn(
                "size-3.5 stroke-1 transition-transform",
                detailsOpen && "rotate-180",
              )}
            />
            <span>
              {detailsOpen
                ? isChineseLocale
                  ? "收起详情"
                  : "Hide details"
                : isChineseLocale
                  ? "展开详情"
                  : "Show details"}
            </span>
          </Button>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
        {metricGroups.map((views) => (
          <OverviewStatCard key={views[0].title} views={views} />
        ))}
      </div>
      {detailsOpen ? (
        <div className="rounded-md bg-muted/35 p-3 md:p-4">
          <div className="grid grid-cols-2 gap-x-4 gap-y-4 md:grid-cols-4">
            {metricGroups.map((views) => (
              <dl key={views[0].title} className="min-w-0 space-y-2 text-xs">
                {views.slice(1).map((view) => (
                  <div
                    key={view.title}
                    className="flex items-baseline justify-between gap-3"
                  >
                    <dt className="truncate text-muted-foreground">
                      {view.title}
                    </dt>
                    <dd className="shrink-0 font-medium tabular-nums text-foreground">
                      {view.value}
                    </dd>
                  </div>
                ))}
              </dl>
            ))}
          </div>
        </div>
      ) : null}
    </section>
  );
}
