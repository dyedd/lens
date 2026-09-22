import {
  keepPreviousData,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { useDeferredValue, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import { useAppTimeZone } from "@/hooks/useAppTimeZone";
import { apiRequest, getApiErrorMessage } from "@/lib/api/client";
import type { ProtocolKind } from "@/lib/api/protocols";
import type { RequestLogDetail, RequestLogPage } from "@/lib/api/requests";
import type { SettingItem } from "@/lib/api/settings";
import { titleForLocale, useI18n } from "@/lib/I18nContext";
import {
  buildModelPrefixOptions,
  resolveEffectiveModelPrefix,
  type SelectedModelPrefix,
} from "@/lib/modelPrefix";

import {
  filterOptionsWithSelected,
  type PAGE_SIZE_OPTIONS,
  parseRelayLogBodyEnabled,
  REQUEST_LOG_DETAIL_GC_TIME,
  type SortMode,
  type StatusFilter,
} from "./requestView";

/** Manage request log filters, queries, and actions. */
export function useRequestsScreen() {
  const queryClient = useQueryClient();
  const { locale } = useI18n();
  const timeZone = useAppTimeZone();
  const [detailId, setDetailId] = useState<number | null>(null);
  const [showBackToTop, setShowBackToTop] = useState(false);
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] =
    useState<(typeof PAGE_SIZE_OPTIONS)[number]>(25);
  const [selectedModelPrefix, setSelectedModelPrefix] =
    useState<SelectedModelPrefix>("all");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [protocolFilter, setProtocolFilter] = useState<"all" | ProtocolKind>(
    "all",
  );
  const [channelFilter, setChannelFilter] = useState("all");
  const [selectedGatewayKeyId, setSelectedGatewayKeyId] = useState("all");
  const [sortMode, setSortMode] = useState<SortMode>("latest");
  const [keyword, setKeyword] = useState("");
  const [clearingLogs, setClearingLogs] = useState(false);
  const deferredKeyword = useDeferredValue(keyword.trim());
  const gatewayKeyId =
    selectedGatewayKeyId === "all" ? null : selectedGatewayKeyId;
  const status = statusFilter === "all" ? null : statusFilter;
  const protocol = protocolFilter === "all" ? null : protocolFilter;
  const channel = channelFilter === "all" ? null : channelFilter;
  const requestLogsQuery = useMemo(() => {
    const params = new URLSearchParams({
      limit: String(pageSize),
      offset: String(page * pageSize),
    });
    if (selectedModelPrefix !== "all")
      params.set("model_prefix", selectedModelPrefix);
    if (status) params.set("status", status);
    if (protocol) params.set("protocol", protocol);
    if (channel) params.set("channel", channel);
    if (gatewayKeyId) params.set("gateway_key_id", gatewayKeyId);
    if (deferredKeyword) params.set("keyword", deferredKeyword);
    if (sortMode !== "latest") params.set("sort", sortMode);
    return `/admin/request-logs/page?${params.toString()}`;
  }, [
    channel,
    deferredKeyword,
    gatewayKeyId,
    page,
    pageSize,
    protocol,
    selectedModelPrefix,
    sortMode,
    status,
  ]);
  const logsQuery = useQuery({
    queryKey: [
      "request-logs",
      page,
      pageSize,
      selectedModelPrefix,
      status,
      protocol,
      channel,
      gatewayKeyId,
      deferredKeyword,
      sortMode,
    ],
    queryFn: () => apiRequest<RequestLogPage>(requestLogsQuery),
    placeholderData: keepPreviousData,
    refetchInterval: page === 0 ? 5000 : false,
  });
  const settingsQuery = useQuery({
    queryKey: ["settings"],
    queryFn: () => apiRequest<SettingItem[]>("/admin/settings"),
    staleTime: 60_000,
  });
  const relayLogBodyEnabled = parseRelayLogBodyEnabled(settingsQuery.data);
  const detailQuery = useQuery({
    queryKey: ["request-log-detail", detailId],
    queryFn: () =>
      apiRequest<RequestLogDetail>(`/admin/request-logs/${detailId}`),
    enabled: detailId !== null,
    staleTime: 60_000,
    gcTime: REQUEST_LOG_DETAIL_GC_TIME,
  });
  const modelPrefixOptions = useMemo(
    () => buildModelPrefixOptions(logsQuery.data?.model_names ?? [], locale),
    [logsQuery.data?.model_names, locale],
  );
  const effectiveModelPrefix = resolveEffectiveModelPrefix(
    modelPrefixOptions,
    selectedModelPrefix,
  );
  const channelOptions = useMemo(
    () => filterOptionsWithSelected(logsQuery.data?.channels, channel),
    [channel, logsQuery.data?.channels],
  );
  const gatewayKeyOptions = useMemo(
    () => filterOptionsWithSelected(logsQuery.data?.gateway_keys, gatewayKeyId),
    [gatewayKeyId, logsQuery.data?.gateway_keys],
  );
  const total = logsQuery.data?.total ?? 0;
  const totalPages = Math.max(Math.ceil(total / pageSize), 1);
  const activeFilterCount = [
    selectedModelPrefix !== "all",
    statusFilter !== "all",
    protocolFilter !== "all",
    channelFilter !== "all",
    gatewayKeyId !== null,
  ].filter(Boolean).length;
  useEffect(() => {
    if (selectedModelPrefix !== effectiveModelPrefix)
      setSelectedModelPrefix(effectiveModelPrefix);
  }, [effectiveModelPrefix, selectedModelPrefix]);
  useEffect(() => {
    if (page > 0 && page >= totalPages) setPage(Math.max(0, totalPages - 1));
  }, [page, totalPages]);
  useEffect(() => {
    if (!logsQuery.isError) return;
    toast.error(
      titleForLocale(locale, "请求日志加载失败", "Failed to load request logs"),
      {
        id: "request-logs-load-error",
        description:
          logsQuery.error instanceof Error
            ? logsQuery.error.message
            : titleForLocale(
                locale,
                "无法读取请求日志",
                "Unable to read request logs",
              ),
      },
    );
  }, [locale, logsQuery.error, logsQuery.isError]);
  useEffect(() => {
    function handleScroll() {
      setShowBackToTop(window.scrollY > 320);
    }
    handleScroll();
    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);
  function updateFilter(callback: () => void) {
    callback();
    setPage(0);
  }
  function resetFilters() {
    setSelectedModelPrefix("all");
    setStatusFilter("all");
    setProtocolFilter("all");
    setChannelFilter("all");
    setSelectedGatewayKeyId("all");
    setPage(0);
  }
  function changePageSize(size: (typeof PAGE_SIZE_OPTIONS)[number]) {
    setPageSize(size);
    setPage(0);
  }
  async function refreshLogs() {
    await Promise.all([
      logsQuery.refetch(),
      detailId !== null ? detailQuery.refetch() : Promise.resolve(),
    ]);
  }
  async function clearRequestLogs() {
    if (
      !window.confirm(
        titleForLocale(
          locale,
          "确认删除全部请求日志？",
          "Delete all request logs?",
        ),
      )
    )
      return;
    setClearingLogs(true);
    try {
      await apiRequest<void>("/admin/request-logs", { method: "DELETE" });
      setPage(0);
      setDetailId(null);
      await Promise.all(
        [
          ["request-logs"],
          ["overview-summary"],
          ["overview-daily"],
          ["overview-models"],
          ["gateway-api-keys"],
        ].map((queryKey) => queryClient.invalidateQueries({ queryKey })),
      );
      toast.success(
        titleForLocale(locale, "请求日志已清空", "Request logs cleared"),
      );
    } catch (error) {
      toast.error(
        getApiErrorMessage(
          error,
          titleForLocale(
            locale,
            "清空请求日志失败",
            "Failed to clear request logs",
          ),
        ),
      );
    } finally {
      setClearingLogs(false);
    }
  }
  return {
    activeFilterCount,
    changePageSize,
    channelFilter,
    channelOptions,
    clearRequestLogs,
    clearingLogs,
    detailId,
    detailQuery,
    effectiveModelPrefix,
    gatewayKeyId,
    gatewayKeyOptions,
    keyword,
    locale,
    logsQuery,
    modelPrefixOptions,
    page,
    pageSize,
    protocolFilter,
    refreshLogs,
    relayLogBodyEnabled,
    resetFilters,
    selectedGatewayKeyId,
    setChannelFilter,
    setDetailId,
    setKeyword,
    setPage,
    setProtocolFilter,
    setSelectedGatewayKeyId,
    setSelectedModelPrefix,
    setSortMode,
    setStatusFilter,
    showBackToTop,
    sortMode,
    statusFilter,
    timeZone,
    total,
    totalPages,
    updateFilter,
  };
}
