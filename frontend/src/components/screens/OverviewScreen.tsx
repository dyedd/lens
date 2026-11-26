import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { siteModelCounts } from "@/components/screens/channels/channelDisplay";
import { useAppTimeZone } from "@/hooks/useAppTimeZone";
import { useModelGroupsQuery } from "@/hooks/useModelGroupsQuery";
import { apiRequest } from "@/lib/api/client";
import {
  type AttributionDimension,
  OVERVIEW_DAILY_QUERY_KEY,
  type OverviewAttribution,
  type OverviewDailyPoint,
  type OverviewSummary,
} from "@/lib/api/overview";
import type { Site } from "@/lib/api/sites";
import { getDateBucketPrefix } from "@/lib/datetime";
import { useI18n } from "@/lib/I18nContext";
import { ActivityTrendCard } from "./overview/ActivityTrendCard";
import { AttributionAnalyticsCard } from "./overview/AttributionAnalyticsCard";
import { OverviewStats } from "./overview/OverviewStats";
import {
  type AnalysisMetric,
  addDays,
  parseDateKey,
  startOfHeatmapWeek,
  type TimeRange,
  toLocalDateKey,
} from "./overview/overviewMetrics";

export function OverviewScreen() {
  const { locale } = useI18n();
  const isChineseLocale = locale === "zh-CN";
  const timeZone = useAppTimeZone();
  const [timeRange, setTimeRange] = useState<TimeRange>("-1");
  const [metric, setMetric] = useState<AnalysisMetric>("tokens");
  const [dimension, setDimension] = useState<AttributionDimension>("model");
  const [filterKey, setFilterKey] = useState<string | null>(null);
  const days = Number(timeRange);
  const summaryQuery = useQuery({
    queryKey: ["overview-summary", days, timeZone],
    queryFn: () =>
      apiRequest<OverviewSummary>(`/admin/overview-summary?days=${days}`),
  });
  const dailyQuery = useQuery({
    queryKey: [...OVERVIEW_DAILY_QUERY_KEY, days, timeZone],
    queryFn: () =>
      apiRequest<OverviewDailyPoint[]>(`/admin/overview-daily?days=${days}`),
  });
  const heatmapQuery = useQuery({
    queryKey: [...OVERVIEW_DAILY_QUERY_KEY, 371, timeZone],
    queryFn: () =>
      apiRequest<OverviewDailyPoint[]>("/admin/overview-daily?days=371"),
    staleTime: 60_000,
  });
  const sitesQuery = useQuery({
    queryKey: ["sites"],
    queryFn: () => apiRequest<Site[]>("/admin/sites"),
    staleTime: 2 * 60_000,
  });
  const groupsQuery = useModelGroupsQuery();
  const attributionQuery = useQuery({
    queryKey: [
      "overview-attribution",
      days,
      dimension,
      metric,
      filterKey,
      timeZone,
    ],
    queryFn: () => {
      const params = new URLSearchParams({
        days: String(days),
        dimension,
        metric,
      });
      if (filterKey !== null) params.set("filter_key", filterKey);
      return apiRequest<OverviewAttribution>(
        `/admin/overview-attribution?${params}`,
      );
    },
  });
  const hourlyQuery = useQuery({
    queryKey: [...OVERVIEW_DAILY_QUERY_KEY, -1, timeZone, "hourly"],
    queryFn: () =>
      apiRequest<OverviewDailyPoint[]>(
        "/admin/overview-daily?days=-1&granularity=hourly",
      ),
    enabled: days === -1,
  });
  const activityQuery = days === -1 ? hourlyQuery : dailyQuery;
  const queries = [summaryQuery, dailyQuery, heatmapQuery, attributionQuery];
  if (days === -1) queries.push(hourlyQuery);
  const pageError = queries.find((query) => query.error)?.error;
  useEffect(() => {
    if (!pageError) return;
    toast.error(
      isChineseLocale ? "概览数据加载失败" : "Failed to load overview",
      {
        id: "overview-load-error",
        description: pageError instanceof Error ? pageError.message : undefined,
      },
    );
  }, [pageError, isChineseLocale]);
  const completed = (dailyQuery.data ?? []).reduce(
    (counts, point) => ({
      successful: counts.successful + point.successful_requests,
      failed: counts.failed + point.failed_requests,
    }),
    { successful: 0, failed: 0 },
  );
  const summary = summaryQuery.data;
  const sites = sitesQuery.data ?? [];
  const groups = groupsQuery.data ?? [];
  const totalChannels = sites.length;
  const enabledChannels = sites.filter((site) => site.enabled).length;
  const enabledUpstreamModels = sites.reduce(
    (count, site) => count + siteModelCounts(site).enabled,
    0,
  );
  const todayKey = parseDateKey(getDateBucketPrefix(timeZone));
  const activityPoints = useMemo(() => {
    const points = activityQuery.data ?? [];
    if (
      days !== -1 ||
      !points.length ||
      points.some((point) => point.date.length !== 10)
    )
      return points;
    const today = getDateBucketPrefix(timeZone);
    const hour = Number(
      new Intl.DateTimeFormat("en-GB", {
        timeZone,
        hour: "2-digit",
        hourCycle: "h23",
      }).format(new Date()),
    );
    const byHour = new Map(points.map((point) => [point.date, point]));
    const lastHour = Math.max(
      hour,
      ...points.map((point) => Number(point.date.slice(8, 10))),
    );
    return Array.from({ length: lastHour + 1 }, (_, index) => {
      const date = `${today}${String(index).padStart(2, "0")}`;
      return (
        byHour.get(date) ?? {
          date,
          request_count: 0,
          input_tokens: 0,
          output_tokens: 0,
          total_tokens: 0,
          total_cost_usd: 0,
          wait_time_ms: 0,
          successful_requests: 0,
          failed_requests: 0,
        }
      );
    });
  }, [activityQuery.data, days, timeZone]);
  const heatmapPoints = useMemo(() => {
    if (days !== 0) return [];
    const counts = new Map(
      (heatmapQuery.data ?? []).map((point) => [
        parseDateKey(point.date),
        point.request_count,
      ]),
    );
    const today = new Date(`${todayKey}T12:00:00`);
    const start = startOfHeatmapWeek(addDays(today, -364));
    const points = [];
    for (
      let date = start;
      toLocalDateKey(date) <= todayKey;
      date = addDays(date, 1)
    ) {
      const key = toLocalDateKey(date);
      points.push({ date: key, count: counts.get(key) ?? 0 });
    }
    return points;
  }, [days, heatmapQuery.data, todayKey]);
  return (
    <section className="flex min-w-0 flex-col gap-6">
      <OverviewStats
        cacheReadTokens={summary?.cache_read_input_tokens?.value ?? 0}
        cacheWriteTokens={summary?.cache_write_input_tokens?.value ?? 0}
        consumedTime={summary?.wait_time_ms?.value ?? 0}
        enabledChannels={enabledChannels}
        enabledUpstreamModels={enabledUpstreamModels}
        inputCost={summary?.input_cost_usd?.value ?? 0}
        inputTokens={summary?.input_tokens?.value ?? 0}
        isChineseLocale={isChineseLocale}
        isRefreshing={
          queries.some((query) => query.isFetching) ||
          sitesQuery.isFetching ||
          groupsQuery.isFetching
        }
        loading={!summary || !dailyQuery.data}
        modelGroupCount={groups.length}
        outputCost={summary?.output_cost_usd?.value ?? 0}
        outputTokens={summary?.output_tokens?.value ?? 0}
        requestCount={summary?.request_count?.value ?? 0}
        resourcesLoading={sitesQuery.isPending || groupsQuery.isPending}
        successfulRequests={completed.successful}
        failedRequests={completed.failed}
        successRate={
          completed.successful + completed.failed
            ? Math.round(
                (completed.successful /
                  (completed.successful + completed.failed)) *
                  1000,
              ) / 10
            : Number.NaN
        }
        totalChannels={totalChannels}
        totalCost={summary?.total_cost_usd?.value ?? 0}
        totalTokens={summary?.total_tokens?.value ?? 0}
        timeRange={timeRange}
        onTimeRangeChange={setTimeRange}
        onRefresh={() => {
          for (const query of queries) void query.refetch();
          void sitesQuery.refetch();
          void groupsQuery.refetch();
        }}
      />
      <ActivityTrendCard
        points={activityPoints.map((point) => ({
          date: point.date,
          requests: point.request_count,
          successful: point.successful_requests,
          failed: point.failed_requests,
          cost: point.total_cost_usd,
          waitTimeMs: point.wait_time_ms,
          tokens: point.total_tokens,
        }))}
        locale={locale}
        isLoading={activityQuery.isPending}
        isError={activityQuery.isError}
        showHeatmapOption={timeRange === "0"}
        heatmapPoints={heatmapPoints}
        isHeatmapLoading={heatmapQuery.isPending}
        isHeatmapError={heatmapQuery.isError}
      />
      <AttributionAnalyticsCard
        key={timeRange}
        timeRange={timeRange}
        analytics={attributionQuery.data}
        dimension={dimension}
        onDimensionChange={(value) => {
          setDimension(value);
          setFilterKey(null);
        }}
        filterKey={filterKey}
        onFilterChange={setFilterKey}
        metric={metric}
        onMetricChange={setMetric}
        locale={locale}
        isLoading={attributionQuery.isPending}
        isError={attributionQuery.isError}
      />
    </section>
  );
}
