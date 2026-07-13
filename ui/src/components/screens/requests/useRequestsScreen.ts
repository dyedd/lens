import { useDeferredValue, useEffect, useMemo, useState } from "react";
import {
  keepPreviousData,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { toast } from "sonner";

import { useAppTimeZone } from "@/hooks/useAppTimeZone";
import {
  apiRequest,
  getApiErrorMessage,
  type ProtocolKind,
  type RequestLogDetail,
  type RequestLogPage,
  type SettingItem,
} from "@/lib/api";
import { titleForLocale, useI18n } from "@/lib/I18nContext";
import {
  buildModelPrefixOptions,
  resolveEffectiveModelPrefix,
  type SelectedModelPrefix,
} from "@/lib/modelPrefix";

import {
  PAGE_SIZE,
  REQUEST_LOG_DETAIL_GC_TIME,
  buildPaginationItems,
  filterOptionsWithSelected,
  parseRelayLogBodyEnabled,
  type SortMode,
  type StatusFilter,
} from "./requestLogUtils";

/** Manage request log filters, queries, and actions. */
export function useRequestsScreen() {
  const queryClient = useQueryClient();
  const { locale } = useI18n();
  const timeZone = useAppTimeZone();
  const [detailId, setDetailId] = useState<number | null>(null);
  const [attemptDetailId, setAttemptDetailId] = useState<number | null>(null);
  const [showBackToTop, setShowBackToTop] = useState(false);
  const [page, setPage] = useState(0);
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
      limit: String(PAGE_SIZE),
      offset: String(page * PAGE_SIZE),
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
    protocol,
    selectedModelPrefix,
    sortMode,
    status,
  ]);
  const logsQuery = useQuery({
    queryKey: [
      "request-logs",
      page,
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
    enabled: relayLogBodyEnabled && detailId !== null,
    staleTime: 60_000,
    gcTime: REQUEST_LOG_DETAIL_GC_TIME,
  });
  const attemptQuery = useQuery({
    queryKey: ["request-log-attempt-detail", attemptDetailId],
    queryFn: () =>
      apiRequest<RequestLogDetail>(`/admin/request-logs/${attemptDetailId}`),
    enabled: attemptDetailId !== null,
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
  const totalPages = Math.max(
    Math.ceil((logsQuery.data?.total ?? 0) / PAGE_SIZE),
    1,
  );
  const activeFilterCount = [
    selectedModelPrefix !== "all",
    statusFilter !== "all",
    protocolFilter !== "all",
    channelFilter !== "all",
    gatewayKeyId !== null,
    Boolean(keyword.trim()),
  ].filter(Boolean).length;
  useEffect(() => {
    if (!relayLogBodyEnabled && detailId !== null) setDetailId(null);
  }, [detailId, relayLogBodyEnabled]);
  useEffect(() => {
    if (selectedModelPrefix !== effectiveModelPrefix)
      setSelectedModelPrefix(effectiveModelPrefix);
  }, [effectiveModelPrefix, selectedModelPrefix]);
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
  async function refreshLogs() {
    await Promise.all([
      logsQuery.refetch(),
      relayLogBodyEnabled && detailId !== null
        ? detailQuery.refetch()
        : Promise.resolve(),
      attemptDetailId !== null ? attemptQuery.refetch() : Promise.resolve(),
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
      setAttemptDetailId(null);
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
    attemptDetailId,
    attemptQuery,
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
    protocolFilter,
    refreshLogs,
    relayLogBodyEnabled,
    selectedGatewayKeyId,
    setAttemptDetailId,
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
    totalPages,
    updateFilter,
    paginationItems: buildPaginationItems(page + 1, totalPages),
  };
}
