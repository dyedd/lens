"use client";

import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";

import { useAppTimeZone } from "@/hooks/useAppTimeZone";
import {
  apiRequest,
  type OverviewDailyPoint,
  type OverviewModelAnalytics,
  type OverviewSummary,
} from "@/lib/api";
import { getDateBucketPrefix } from "@/lib/datetime";
import { useI18n } from "@/lib/I18nContext";
import type { ChartConfig } from "@/components/ui/Chart";

import { ModelAnalyticsCard } from "./overview/ModelAnalyticsCard";
import { OverviewStats } from "./overview/OverviewStats";
import { RequestHeatmap } from "./overview/RequestHeatmap";
import {
  addDays,
  CHART_COLORS,
  formatSparklineLabel,
  formatTrendLabel,
  getPieMetricLabels,
  normalizeTrend,
  parseDateKey,
  safeKey,
  startOfHeatmapWeek,
  toLocalDateKey,
  type HeatmapMetric,
  type PieMetric,
  type TimeRange,
} from "./overview/overviewUtils";

/** Render gateway usage and model analytics dashboards. */
export function OverviewScreen() {
  const { locale } = useI18n();
  const isChineseLocale = locale === "zh-CN";
  const timeZone = useAppTimeZone();
  const [modelRange, setModelRange] = useState<TimeRange>("-1");
  const [pieMetric, setPieMetric] = useState<PieMetric>("cost");
  const [heatmapMetric, setHeatmapMetric] = useState<HeatmapMetric>("requests");
  const modelDays = Number(modelRange);
  const {
    label: pieMetricLabel,
    trendTitle: modelTrendTitle,
    cardDescription: modelCardDescription,
  } = getPieMetricLabels(pieMetric, isChineseLocale);
  const modelQuery = useMemo(
    () =>
      `/admin/overview-models?${new URLSearchParams({ days: String(modelDays), metric: pieMetric }).toString()}`,
    [modelDays, pieMetric],
  );
  const summaryQuery = useQuery({
    queryKey: ["overview-summary", 0],
    queryFn: () =>
      apiRequest<OverviewSummary>("/admin/overview-summary?days=0"),
  });
  const dailyQuery = useQuery({
    queryKey: ["overview-daily", 0],
    queryFn: () =>
      apiRequest<OverviewDailyPoint[]>("/admin/overview-daily?days=0"),
  });
  const heatmapQuery = useQuery({
    queryKey: ["overview-daily", 365],
    queryFn: () =>
      apiRequest<OverviewDailyPoint[]>("/admin/overview-daily?days=365"),
    staleTime: 60_000,
  });
  const modelsQuery = useQuery({
    queryKey: ["overview-models", modelDays, pieMetric],
    queryFn: () => apiRequest<OverviewModelAnalytics>(modelQuery),
  });
  const pageError = summaryQuery.isError
    ? summaryQuery.error
    : dailyQuery.error ||
      heatmapQuery.error ||
      (modelsQuery.isError ? modelsQuery.error : null);
  useEffect(() => {
    if (!pageError) return;
    toast.error(
      isChineseLocale ? "总览数据加载失败" : "Failed to load overview",
      {
        id: "overview-load-error",
        description:
          pageError instanceof Error
            ? pageError.message
            : isChineseLocale
              ? "无法读取总览数据"
              : "Unable to read overview data",
      },
    );
  }, [pageError, isChineseLocale]);

  const allDaily = useMemo(() => dailyQuery.data ?? [], [dailyQuery.data]);
  const successfulRequests = useMemo(
    () => allDaily.reduce((sum, item) => sum + item.successful_requests, 0),
    [allDaily],
  );
  const statTrends = useMemo(() => {
    const dailyMap = new Map(
      allDaily.map((point) => [parseDateKey(point.date), point]),
    );
    const today = new Date();
    const buckets = Array.from({ length: 30 }, (_, index) => {
      const date = toLocalDateKey(addDays(today, index - 29));
      return { date, point: dailyMap.get(date) };
    });
    const buildTrend = (getValue: (point: OverviewDailyPoint) => number) =>
      normalizeTrend(
        buckets.map(({ date, point }) => ({
          label: formatSparklineLabel(date),
          value: point ? getValue(point) : 0,
        })),
      );
    return {
      requests: buildTrend((point) => point.request_count),
      cost: buildTrend((point) => point.total_cost_usd),
      inputTokens: buildTrend((point) => point.input_tokens ?? 0),
      outputTokens: buildTrend((point) => point.output_tokens ?? 0),
    };
  }, [allDaily]);
  const summary = summaryQuery.data;
  const requestCount = summary?.request_count.value ?? 0;
  const totalCost = summary?.total_cost_usd.value ?? 0;
  const inputTokens = summary?.input_tokens.value ?? 0;
  const outputTokens = summary?.output_tokens.value ?? 0;
  const inputCost = summary?.input_cost_usd.value ?? 0;
  const outputCost = summary?.output_cost_usd.value ?? 0;
  const cacheReadTokens = summary?.cache_read_input_tokens.value ?? 0;
  const cacheWriteTokens = summary?.cache_write_input_tokens.value ?? 0;
  const successRate = requestCount
    ? Math.round((successfulRequests / requestCount) * 100)
    : 0;
  const consumedTime = summary?.wait_time_ms.value ?? 0;
  const models = modelsQuery.data;
  const pieData = useMemo(() => {
    if (!models) return { data: [], total: 0 };
    const getValue = (item: OverviewModelAnalytics["distribution"][number]) =>
      pieMetric === "requests"
        ? item.requests
        : pieMetric === "tokens"
          ? item.total_tokens
          : item.total_cost_usd;
    return {
      data: models.distribution.map((item) => ({
        model: item.model,
        value: getValue(item),
        requests: item.requests,
        total_cost_usd: item.total_cost_usd,
      })),
      total: models.distribution.reduce((sum, item) => sum + getValue(item), 0),
    };
  }, [models, pieMetric]);
  const pieChartConfig = useMemo(() => {
    const config: ChartConfig = {};
    models?.distribution.forEach((item, index) => {
      config[item.model] = {
        label: item.model,
        color: CHART_COLORS[index % CHART_COLORS.length],
      };
    });
    return config;
  }, [models]);
  const { barData, barConfig, barModels } = useMemo(() => {
    if (!models)
      return {
        barData: [],
        barConfig: {} as ChartConfig,
        barModels: [] as string[],
      };
    const modelSet = (
      models.distribution.length
        ? models.distribution.map((item) => item.model)
        : [...new Set(models.trend.map((point) => point.model))]
    ).slice(0, 12);
    if (!modelSet.length)
      return {
        barData: [],
        barConfig: {} as ChartConfig,
        barModels: [] as string[],
      };
    const dateMap = new Map<string, Record<string, number>>();
    for (const point of models.trend) {
      if (!modelSet.includes(point.model)) continue;
      const key = safeKey(point.model);
      const existing = dateMap.get(point.date) ?? {};
      existing[key] = (existing[key] ?? 0) + point.value;
      dateMap.set(point.date, existing);
    }
    const buckets =
      modelDays === -1
        ? Array.from(
            { length: 24 },
            (_, hour) =>
              `${getDateBucketPrefix(timeZone)}${String(hour).padStart(2, "0")}`,
          )
        : [...dateMap.keys()].sort();
    const config: ChartConfig = {};
    const safeModels: string[] = [];
    modelSet.forEach((model, index) => {
      const key = safeKey(model);
      safeModels.push(key);
      config[key] = {
        label: model,
        color: CHART_COLORS[index % CHART_COLORS.length],
      };
    });
    return {
      barData: buckets.map((bucket) => ({
        date: formatTrendLabel(bucket),
        ...(dateMap.get(bucket) ?? {}),
      })),
      barConfig: config,
      barModels: safeModels,
    };
  }, [modelDays, models, timeZone]);
  const heatmap = useMemo(() => {
    const pointMap = new Map(
      (heatmapQuery.data ?? []).map((item) => [
        parseDateKey(item.date),
        {
          count: item.request_count,
          tokens: item.total_tokens,
          waitTimeMs: item.wait_time_ms,
        },
      ]),
    );
    const today = new Date();
    const start = startOfHeatmapWeek(addDays(today, -364));
    const length =
      Math.floor(
        (new Date(toLocalDateKey(today)).getTime() -
          new Date(toLocalDateKey(start)).getTime()) /
          86_400_000,
      ) + 1;
    const points = Array.from({ length }, (_, index) => {
      const date = toLocalDateKey(addDays(start, index));
      const point = pointMap.get(date);
      return {
        date,
        count: point?.count ?? 0,
        tokens: point?.tokens ?? 0,
        waitTimeMs: point?.waitTimeMs ?? 0,
      };
    });
    return {
      points,
      total: points.reduce((sum, point) => sum + point.count, 0),
    };
  }, [heatmapQuery.data]);

  return (
    <section className="flex flex-col gap-4">
      <OverviewStats
        cacheReadTokens={cacheReadTokens}
        cacheWriteTokens={cacheWriteTokens}
        consumedTime={consumedTime}
        inputCost={inputCost}
        inputTokens={inputTokens}
        isChineseLocale={isChineseLocale}
        outputCost={outputCost}
        outputTokens={outputTokens}
        requestCount={requestCount}
        statTrends={statTrends}
        successRate={successRate}
        totalCost={totalCost}
      />
      <RequestHeatmap
        points={heatmap.points}
        total={heatmap.total}
        metric={heatmapMetric}
        onMetricChange={setHeatmapMetric}
        isChineseLocale={isChineseLocale}
      />
      <ModelAnalyticsCard
        barConfig={barConfig}
        barData={barData}
        barModels={barModels}
        isChineseLocale={isChineseLocale}
        modelCardDescription={modelCardDescription}
        modelRange={modelRange}
        modelTrendTitle={modelTrendTitle}
        modelsIsError={modelsQuery.isError}
        pieChartConfig={pieChartConfig}
        pieData={pieData}
        pieMetric={pieMetric}
        pieMetricLabel={pieMetricLabel}
        onMetricChange={setPieMetric}
        onRangeChange={setModelRange}
      />
    </section>
  );
}
