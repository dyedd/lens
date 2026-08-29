import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { AlertCircle } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/Alert";
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationNext,
  PaginationPrevious,
} from "@/components/ui/Pagination";
import { SegmentedControl } from "@/components/ui/SegmentedControl";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/Select";
import { ToolbarSearchInput } from "@/components/ui/ToolbarSearchInput";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/Tooltip";
import { useAppTimeZone } from "@/hooks/useAppTimeZone";
import { apiRequest } from "@/lib/api/client";
import type { HealthItem, HealthSummary } from "@/lib/api/sites";
import { cn } from "@/lib/classNames";
import { useI18n } from "@/lib/I18nContext";

type HealthMode = "model" | "channel";

const PAGE_SIZE = 24;
const SEARCH_DEBOUNCE_MS = 300;
const HOURS = [
  { value: "1", zh: "1 小时", en: "1 hour" },
  { value: "6", zh: "6 小时", en: "6 hours" },
  { value: "24", zh: "24 小时", en: "24 hours" },
] as const;

function useDebouncedValue(value: string, delay: number) {
  const [debouncedValue, setDebouncedValue] = useState(value);

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedValue(value), delay);
    return () => window.clearTimeout(timer);
  }, [delay, value]);

  return debouncedValue;
}

function healthState(item: HealthItem, isChineseLocale: boolean) {
  if (!item.total_count) {
    return {
      label: isChineseLocale ? "无数据" : "No data",
      className: "border-muted-foreground/30 text-muted-foreground",
    };
  }
  if (item.success_count === item.total_count) {
    return {
      label: isChineseLocale ? "健康" : "Healthy",
      className: "border-emerald-500/40 text-emerald-700 dark:text-emerald-300",
    };
  }
  if (!item.success_count) {
    return {
      label: isChineseLocale ? "异常" : "Failed",
      className: "border-destructive/40 text-destructive",
    };
  }
  return {
    label: isChineseLocale ? "降级" : "Degraded",
    className: "border-amber-500/40 text-amber-700 dark:text-amber-300",
  };
}

function bucketClassName(bucket: HealthItem["buckets"][number]) {
  if (!bucket.total_count) return "bg-muted";
  if (bucket.success_count === bucket.total_count) return "bg-emerald-500";
  if (!bucket.success_count) return "bg-destructive";
  return "bg-amber-500";
}

function HealthTimeline({
  item,
  locale,
  timeZone,
}: {
  item: HealthItem;
  locale: "zh-CN" | "en-US";
  timeZone?: string;
}) {
  const formatter = useMemo(
    () =>
      new Intl.DateTimeFormat(locale, {
        hour: "2-digit",
        minute: "2-digit",
        timeZone,
      }),
    [locale, timeZone],
  );
  const start = item.buckets[0];
  const end = item.buckets.at(-1);

  return (
    <div className="grid gap-2">
      <div
        className="grid grid-cols-[repeat(60,minmax(0,1fr))] gap-1"
        aria-label={locale === "zh-CN" ? "健康时间轴" : "Health timeline"}
      >
        {item.buckets.map((bucket) => {
          const startAt = formatter.format(new Date(bucket.started_at));
          const endAt = formatter.format(new Date(bucket.ended_at));
          const failureCount = Math.max(
            bucket.total_count - bucket.success_count,
            0,
          );
          const ariaLabel =
            locale === "zh-CN"
              ? `时间：${startAt} - ${endAt}，请求：${bucket.total_count}，失败：${failureCount}`
              : `Time: ${startAt} - ${endAt}, requests: ${bucket.total_count}, failures: ${failureCount}`;
          return (
            <Tooltip key={bucket.started_at}>
              <TooltipTrigger asChild>
                <span
                  className={cn("h-10 rounded-sm", bucketClassName(bucket))}
                  aria-label={ariaLabel}
                />
              </TooltipTrigger>
              <TooltipContent
                side="top"
                sideOffset={6}
                className="grid min-w-36 gap-1.5"
              >
                <div className="font-medium">
                  {locale === "zh-CN" ? "时间" : "Time"}
                </div>
                <div className="text-background/80">
                  {startAt} - {endAt}
                </div>
                <div className="grid gap-0.5 border-t border-background/20 pt-1.5">
                  <div className="flex justify-between gap-4">
                    <span>{locale === "zh-CN" ? "请求" : "Requests"}</span>
                    <span className="font-medium tabular-nums">
                      {bucket.total_count}
                    </span>
                  </div>
                  <div className="flex justify-between gap-4">
                    <span>{locale === "zh-CN" ? "失败" : "Failures"}</span>
                    <span className="font-medium tabular-nums">
                      {failureCount}
                    </span>
                  </div>
                </div>
              </TooltipContent>
            </Tooltip>
          );
        })}
      </div>
      <div className="flex justify-between text-xs text-muted-foreground">
        <span>{start ? formatter.format(new Date(start.started_at)) : ""}</span>
        <span>{end ? formatter.format(new Date(end.ended_at)) : ""}</span>
      </div>
    </div>
  );
}

function HealthCard({
  item,
  locale,
  timeZone,
}: {
  item: HealthItem;
  locale: "zh-CN" | "en-US";
  timeZone?: string;
}) {
  const isChineseLocale = locale === "zh-CN";
  const state = healthState(item, isChineseLocale);
  const successRate = item.total_count
    ? `${((item.success_count / item.total_count) * 100).toFixed(2)}%`
    : "-";

  return (
    <article className="grid gap-4 rounded-lg border bg-card p-4 shadow-sm">
      <div className="flex min-w-0 items-start justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2">
          <h2 className="truncate text-base font-semibold">{item.name}</h2>
          <span
            className={cn(
              "shrink-0 rounded-full border px-2 py-0.5 text-xs font-medium",
              state.className,
            )}
          >
            {state.label}
          </span>
        </div>
        <div className="shrink-0 text-right text-sm">
          <span className="font-semibold tabular-nums">{successRate}</span>
          <span className="ml-2 text-muted-foreground">
            {isChineseLocale ? "成功率" : "success"}
          </span>
          <span className="mx-2 text-muted-foreground">·</span>
          <span className="font-semibold tabular-nums">{item.total_count}</span>
          <span className="ml-2 text-muted-foreground">
            {isChineseLocale ? "请求" : "requests"}
          </span>
        </div>
      </div>
      <HealthTimeline item={item} locale={locale} timeZone={timeZone} />
    </article>
  );
}

/** Renders request-log health by execution model group or configured channel. */
export function ModelHealthScreen() {
  const { locale } = useI18n();
  const timeZone = useAppTimeZone();
  const [hours, setHours] = useState("6");
  const [mode, setMode] = useState<HealthMode>("model");
  const [search, setSearch] = useState("");
  const [offset, setOffset] = useState(0);
  const debouncedSearch = useDebouncedValue(search.trim(), SEARCH_DEBOUNCE_MS);
  const healthQuery = useQuery({
    queryKey: ["model-health", mode, hours, debouncedSearch, offset],
    queryFn: () => {
      const query = new URLSearchParams({
        hours,
        mode,
        limit: String(PAGE_SIZE),
        offset: String(offset),
      });
      if (debouncedSearch) query.set("query", debouncedSearch);
      return apiRequest<HealthSummary>(
        `/admin/model-health?${query.toString()}`,
      );
    },
    placeholderData: keepPreviousData,
    staleTime: 5_000,
    refetchInterval: 5_000,
  });
  const handleHoursChange = (value: string) => {
    setHours(value);
    setOffset(0);
  };
  const handleModeChange = (value: HealthMode) => {
    setMode(value);
    setOffset(0);
  };
  const handleSearchChange = (value: string) => {
    setSearch(value);
    setOffset(0);
  };

  const visibleItems = healthQuery.data?.items ?? [];
  const isChineseLocale = locale === "zh-CN";
  const searchPlaceholder =
    mode === "model"
      ? isChineseLocale
        ? "搜索模型组名称"
        : "Search model group names"
      : isChineseLocale
        ? "搜索渠道名称"
        : "Search channel names";
  const hasPreviousPage = offset > 0;
  const hasNextPage = healthQuery.data?.next_offset != null;

  return (
    <section className="grid gap-4">
      <div className="flex flex-wrap items-center gap-2">
        <Select value={hours} onValueChange={handleHoursChange}>
          <SelectTrigger className="w-28">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {HOURS.map((option) => (
              <SelectItem key={option.value} value={option.value}>
                {isChineseLocale ? option.zh : option.en}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <SegmentedControl
          value={mode}
          onValueChange={handleModeChange}
          options={[
            {
              value: "model",
              label: isChineseLocale ? "模型组" : "Model groups",
            },
            { value: "channel", label: isChineseLocale ? "渠道" : "Channel" },
          ]}
        />
        <ToolbarSearchInput
          value={search}
          onChange={handleSearchChange}
          onClear={() => handleSearchChange("")}
          placeholder={searchPlaceholder}
          className="max-w-xs"
        />
      </div>

      {healthQuery.isError ? (
        <Alert variant="destructive">
          <AlertCircle />
          <AlertTitle>
            {isChineseLocale
              ? "健康数据加载失败"
              : "Failed to load health data"}
          </AlertTitle>
          <AlertDescription>
            {healthQuery.error instanceof Error
              ? healthQuery.error.message
              : isChineseLocale
                ? "无法读取请求日志健康统计"
                : "Unable to read request-log health statistics"}
          </AlertDescription>
        </Alert>
      ) : healthQuery.isLoading ? (
        <div className="py-12 text-center text-sm text-muted-foreground">
          {isChineseLocale ? "正在加载健康数据..." : "Loading health data..."}
        </div>
      ) : !visibleItems.length ? (
        <div className="py-12 text-center text-sm text-muted-foreground">
          {search.trim()
            ? isChineseLocale
              ? "没有匹配的健康数据"
              : "No matching health data"
            : isChineseLocale
              ? "暂无可展示的数据"
              : "No health data to display"}
        </div>
      ) : (
        <>
          <div className="grid gap-3 xl:grid-cols-2">
            {visibleItems.map((item) => (
              <HealthCard
                key={item.name}
                item={item}
                locale={locale}
                timeZone={timeZone}
              />
            ))}
          </div>
          {hasPreviousPage || hasNextPage ? (
            <Pagination
              id="model-health-pagination"
              className="justify-center pt-1"
            >
              <PaginationContent>
                <PaginationItem>
                  <PaginationPrevious
                    href="#model-health-pagination"
                    text={isChineseLocale ? "上一页" : "Prev"}
                    className={cn(
                      !hasPreviousPage && "pointer-events-none opacity-50",
                    )}
                    onClick={(event) => {
                      event.preventDefault();
                      if (hasPreviousPage) {
                        setOffset(Math.max(0, offset - PAGE_SIZE));
                      }
                    }}
                  />
                </PaginationItem>
                <PaginationItem>
                  <PaginationNext
                    href="#model-health-pagination"
                    text={isChineseLocale ? "下一页" : "Next"}
                    className={cn(
                      !hasNextPage && "pointer-events-none opacity-50",
                    )}
                    onClick={(event) => {
                      event.preventDefault();
                      const nextOffset = healthQuery.data?.next_offset;
                      if (nextOffset != null) {
                        setOffset(nextOffset);
                      }
                    }}
                  />
                </PaginationItem>
              </PaginationContent>
            </Pagination>
          ) : null}
        </>
      )}
    </section>
  );
}
