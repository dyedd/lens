import {
  Activity,
  Boxes,
  Braces,
  CalendarDays,
  Check,
  CircleCheck,
  DatabaseZap,
  DollarSign,
  RefreshCw,
  Server,
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
  enabledChannels: number;
  enabledUpstreamModels: number;
  inputCost: number;
  inputTokens: number;
  isChineseLocale: boolean;
  isRefreshing: boolean;
  loading?: boolean;
  modelGroupCount: number;
  outputCost: number;
  outputTokens: number;
  requestCount: number;
  resourcesLoading?: boolean;
  successRate: number;
  successfulRequests: number;
  failedRequests: number;
  totalChannels: number;
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
    enabledChannels,
    enabledUpstreamModels,
    inputCost,
    inputTokens,
    isChineseLocale,
    isRefreshing,
    loading = false,
    modelGroupCount,
    outputCost,
    outputTokens,
    requestCount,
    resourcesLoading = false,
    successRate,
    successfulRequests,
    failedRequests,
    totalChannels,
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
  const resourceDisplay = (value: string) => (resourcesLoading ? "—" : value);
  const avgDurationMs =
    requestCount > 0 ? Math.round(consumedTime / requestCount) : null;
  const disabledChannels = Math.max(0, totalChannels - enabledChannels);

  const metricCards: OverviewStatView[] = [
    {
      icon: Activity,
      title: isChineseLocale ? "请求量" : "Requests",
      value: display(formatCompact(requestCount)),
      details: [
        {
          label: isChineseLocale ? "记录" : "Logs",
          value: isChineseLocale ? "查看明细" : "View logs",
          href: loading ? undefined : requestLogsHref(timeRange),
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
      title: isChineseLocale ? "缓存命中率" : "Cache hit rate",
      value: display(
        formatRate(inputTokens > 0 ? cacheReadTokens / inputTokens : null),
      ),
      details: [
        {
          label: isChineseLocale ? "读取" : "Read",
          value: display(formatCompact(cacheReadTokens)),
        },
        {
          label: isChineseLocale ? "写入" : "Write",
          value: display(formatCompact(cacheWriteTokens)),
        },
      ],
    },
    {
      icon: Timer,
      title: isChineseLocale ? "总时长" : "Total time",
      value: display(formatDuration(consumedTime, isChineseLocale)),
      details: [
        {
          label: isChineseLocale ? "平均耗时" : "Avg latency",
          value: display(
            avgDurationMs !== null
              ? formatDuration(avgDurationMs, isChineseLocale)
              : "—",
          ),
        },
        {
          label: isChineseLocale ? "周期" : "Window",
          value: rangeLabel,
        },
      ],
    },
    {
      icon: Server,
      title: isChineseLocale ? "接入渠道" : "Channels",
      value: resourceDisplay(formatCompact(totalChannels)),
      details: [
        {
          label: isChineseLocale ? "已启用" : "Enabled",
          value: resourceDisplay(formatCompact(enabledChannels)),
          href: resourcesLoading ? undefined : "/channels",
        },
        {
          label: isChineseLocale ? "已停用" : "Paused",
          value: resourceDisplay(formatCompact(disabledChannels)),
          href: resourcesLoading ? undefined : "/channels",
        },
      ],
    },
    {
      icon: Boxes,
      title: isChineseLocale ? "模型与分组" : "Models & groups",
      value: resourceDisplay(formatCompact(modelGroupCount)),
      details: [
        {
          label: isChineseLocale ? "模型组" : "Groups",
          value: resourceDisplay(formatCompact(modelGroupCount)),
          href: resourcesLoading ? undefined : "/groups",
        },
        {
          label: isChineseLocale ? "上游模型" : "Upstream",
          value: resourceDisplay(formatCompact(enabledUpstreamModels)),
          href: resourcesLoading ? undefined : "/channels",
        },
      ],
    },
  ];

  return (
    <section className="space-y-4">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="page-title">
          {isChineseLocale ? "运行概览" : "Overview metrics"}
        </h1>
        <div className="flex flex-wrap items-center justify-end gap-1.5">
          <Popover open={rangeOpen} onOpenChange={setRangeOpen}>
            <PopoverTrigger asChild>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="h-8 max-w-[220px] gap-1.5 px-2.5 text-[13px] font-medium text-muted-foreground shadow-none hover:bg-muted hover:text-foreground"
                aria-label={
                  isChineseLocale ? "选择时间范围" : "Select time range"
                }
              >
                <CalendarDays className="size-3.5 shrink-0" />
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
                        "h-8 w-full justify-start px-2 text-[13px] font-normal shadow-none",
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
            className="h-8 gap-1.5 px-2.5 text-[13px] font-medium text-muted-foreground shadow-none hover:bg-muted hover:text-foreground"
            disabled={isRefreshing}
            aria-label={isChineseLocale ? "刷新概览" : "Refresh overview"}
            onClick={onRefresh}
          >
            <RefreshCw
              className={cn("size-3.5", isRefreshing && "animate-spin")}
            />
            <span>{isChineseLocale ? "刷新" : "Refresh"}</span>
          </Button>
        </div>
      </header>
      <div className="grid grid-cols-1 gap-3.5 sm:grid-cols-2 md:grid-cols-4">
        {metricCards.map((view) => (
          <OverviewStatCard key={view.title} view={view} />
        ))}
      </div>
    </section>
  );
}
