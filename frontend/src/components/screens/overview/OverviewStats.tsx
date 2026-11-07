import {
  Activity,
  Braces,
  CalendarDays,
  Check,
  CircleCheck,
  DatabaseZap,
  DollarSign,
  RefreshCw,
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
  formatRate,
  requestLogsHref,
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
  isRefreshing: boolean;
  loading?: boolean;
  outputCost: number;
  outputTokens: number;
  requestCount: number;
  successRate: number;
  successfulRequests: number;
  failedRequests: number;
  totalCost: number;
  totalTokens: number;
  timeRange: TimeRange;
  onRefresh: () => void;
  onTimeRangeChange: (range: TimeRange) => void;
};

export function OverviewStats(props: Props) {
  const {
    cacheReadTokens,
    cacheWriteTokens,
    consumedTime,
    inputCost,
    inputTokens,
    isChineseLocale,
    isRefreshing,
    loading = false,
    outputCost,
    outputTokens,
    requestCount,
    successRate,
    successfulRequests,
    failedRequests,
    totalCost,
    totalTokens,
    timeRange,
    onRefresh,
    onTimeRangeChange,
  } = props;
  const [rangeOpen, setRangeOpen] = useState(false);
  const rangeLabel =
    TIME_RANGE_OPTIONS.find((option) => option.value === timeRange)?.[
      isChineseLocale ? "zhLabel" : "enLabel"
    ] ?? (isChineseLocale ? "今天" : "Today");
  const display = (value: string) => (loading ? "—" : value);
  const metricCards: OverviewStatView[] = [
    {
      icon: Activity,
      title: isChineseLocale ? "请求量" : "Requests",
      value: display(formatCompact(requestCount)),
    },
    {
      icon: CircleCheck,
      title: isChineseLocale ? "成功率" : "Success rate",
      value: display(Number.isFinite(successRate) ? `${successRate}%` : "—"),
      details: [
        {
          label: isChineseLocale ? "成功" : "Successful",
          value: display(formatCompact(successfulRequests)),
          href: loading
            ? undefined
            : requestLogsHref(timeRange, { status: "success" }),
        },
        {
          label: isChineseLocale ? "失败" : "Failed",
          value: display(formatCompact(failedRequests)),
          href: loading
            ? undefined
            : requestLogsHref(timeRange, { status: "failed" }),
        },
      ],
    },
    {
      icon: DollarSign,
      title: isChineseLocale ? "预估成本" : "Estimated cost",
      value: display(formatMoney(totalCost)),
      details: [
        {
          label: isChineseLocale ? "输入" : "Input",
          value: display(formatMoney(inputCost)),
        },
        {
          label: isChineseLocale ? "输出" : "Output",
          value: display(formatMoney(outputCost)),
        },
      ],
    },
    {
      icon: Braces,
      title: isChineseLocale ? "Token 用量" : "Token usage",
      value: display(formatCompact(totalTokens)),
      details: [
        {
          label: isChineseLocale ? "输入" : "Input",
          value: display(formatCompact(inputTokens)),
        },
        {
          label: isChineseLocale ? "输出" : "Output",
          value: display(formatCompact(outputTokens)),
        },
      ],
    },
    {
      icon: DatabaseZap,
      title: isChineseLocale ? "Token 缓存命中率" : "Token cache hit rate",
      value: display(
        formatRate(inputTokens > 0 ? cacheReadTokens / inputTokens : null),
      ),
      details: [
        {
          label: isChineseLocale ? "缓存读取" : "Cache read",
          value: display(formatCompact(cacheReadTokens)),
        },
        {
          label: isChineseLocale ? "缓存写入" : "Cache write",
          value: display(formatCompact(cacheWriteTokens)),
        },
      ],
    },
    {
      icon: Timer,
      title: isChineseLocale ? "总时长" : "Total time",
      value: display(formatDuration(consumedTime, isChineseLocale)),
    },
  ];

  return (
    <section className="space-y-3">
      <div className="flex min-h-10 flex-wrap items-center justify-between gap-3 px-1">
        <h3 className="text-sm font-semibold">
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
            disabled={isRefreshing}
            aria-label={isChineseLocale ? "刷新概览" : "Refresh overview"}
            onClick={onRefresh}
          >
            <RefreshCw
              className={cn(
                "size-3.5 stroke-1",
                isRefreshing && "animate-spin",
              )}
            />
            <span>{isChineseLocale ? "刷新" : "Refresh"}</span>
          </Button>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-2 md:grid-cols-3 xl:grid-cols-6">
        {metricCards.map((view) => (
          <OverviewStatCard key={view.title} view={view} />
        ))}
      </div>
    </section>
  );
}
