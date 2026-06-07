"use client";

import { useDeferredValue, useEffect, useMemo, useState } from "react";
import {
  keepPreviousData,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { toast } from "sonner";
import {
  AlertCircle,
  ArrowUp,
  Filter,
  RefreshCcw,
  RotateCcw,
  Trash2,
} from "lucide-react";
import {
  ApiError,
  ProtocolKind,
  RequestLogDetail,
  RequestLogPage,
  SettingItem,
  apiRequest,
} from "@/lib/api";
import { useAppTimeZone } from "@/hooks/use-app-time-zone";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";
import { getModelFamilyKey, getModelFamilyLabel } from "@/lib/model-icons";
import { Dialog, AppDialogContent } from "@/components/ui/dialog";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Field,
  FieldGroup,
  FieldLabel,
  FieldLegend,
  FieldSet,
} from "@/components/ui/field";
import {
  NativeSelect,
  NativeSelectOption,
} from "@/components/ui/native-select";
import {
  Pagination,
  PaginationContent,
  PaginationEllipsis,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from "@/components/ui/pagination";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { ToolbarSearchInput } from "@/components/ui/toolbar-search-input";

import { SeriesChip } from "./requests/components";
import { AttemptChain, RequestCard } from "./requests/request-card";
import {
  PAGE_SIZE,
  REQUEST_LOG_DETAIL_GC_TIME,
  buildPaginationItems,
  filterOptionLabel,
  filterOptionsWithSelected,
  formatErrorDisplay,
  gatewayKeyFilterOptionLabel,
  parseRelayLogBodyEnabled,
  titleForLocale,
  type ModelPrefixOption,
  type SelectedModelPrefix,
  type SortMode,
  type StatusFilter,
} from "./requests/shared";
import { JsonViewer } from "./requests/viewer";

export function RequestsScreen() {
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

  const effectiveGatewayKeyId =
    selectedGatewayKeyId === "all" ? null : selectedGatewayKeyId;
  const statusQueryValue = statusFilter === "all" ? null : statusFilter;
  const protocolQueryValue = protocolFilter === "all" ? null : protocolFilter;
  const channelQueryValue = channelFilter === "all" ? null : channelFilter;
  const keywordQueryValue = deferredKeyword || null;

  const requestLogsQuery = useMemo(() => {
    const params = new URLSearchParams({
      limit: String(PAGE_SIZE),
      offset: String(page * PAGE_SIZE),
    });

    if (selectedModelPrefix !== "all") {
      params.set("model_prefix", selectedModelPrefix);
    }
    if (statusQueryValue) params.set("status", statusQueryValue);
    if (protocolQueryValue) params.set("protocol", protocolQueryValue);
    if (channelQueryValue) params.set("channel", channelQueryValue);
    if (effectiveGatewayKeyId) {
      params.set("gateway_key_id", effectiveGatewayKeyId);
    }
    if (keywordQueryValue) params.set("keyword", keywordQueryValue);
    if (sortMode !== "latest") params.set("sort", sortMode);

    return `/admin/request-logs/page?${params.toString()}`;
  }, [
    channelQueryValue,
    effectiveGatewayKeyId,
    keywordQueryValue,
    page,
    protocolQueryValue,
    selectedModelPrefix,
    sortMode,
    statusQueryValue,
  ]);

  const {
    data,
    error,
    isError,
    isLoading,
    isFetching,
    refetch: refetchRequestLogs,
  } = useQuery({
    queryKey: [
      "request-logs",
      page,
      selectedModelPrefix,
      statusQueryValue,
      protocolQueryValue,
      channelQueryValue,
      effectiveGatewayKeyId,
      keywordQueryValue,
      sortMode,
    ],
    queryFn: () => apiRequest<RequestLogPage>(requestLogsQuery),
    placeholderData: keepPreviousData,
    refetchInterval: page === 0 ? 5000 : false,
  });

  const { data: settings } = useQuery({
    queryKey: ["settings"],
    queryFn: () => apiRequest<SettingItem[]>("/admin/settings"),
    staleTime: 60_000,
  });
  const relayLogBodyEnabled = parseRelayLogBodyEnabled(settings);

  const {
    data: detail,
    error: detailError,
    isError: detailIsError,
    isLoading: detailLoading,
    refetch: refetchDetail,
  } = useQuery({
    queryKey: ["request-log-detail", detailId],
    queryFn: () =>
      apiRequest<RequestLogDetail>(`/admin/request-logs/${detailId}`),
    enabled: relayLogBodyEnabled && detailId !== null,
    staleTime: 60_000,
    gcTime: REQUEST_LOG_DETAIL_GC_TIME,
  });

  const {
    data: attemptDetail,
    error: attemptDetailError,
    isError: attemptDetailIsError,
    isLoading: attemptDetailLoading,
    refetch: refetchAttemptDetail,
  } = useQuery({
    queryKey: ["request-log-attempt-detail", attemptDetailId],
    queryFn: () =>
      apiRequest<RequestLogDetail>(`/admin/request-logs/${attemptDetailId}`),
    enabled: attemptDetailId !== null,
    staleTime: 60_000,
    gcTime: REQUEST_LOG_DETAIL_GC_TIME,
  });

  const modelPrefixOptions = useMemo(() => {
    const optionsByPrefix = new Map<string, ModelPrefixOption>();
    for (const model of data?.model_names ?? []) {
      const prefix = getModelFamilyKey(model);
      if (prefix && !optionsByPrefix.has(prefix)) {
        optionsByPrefix.set(prefix, {
          key: prefix,
          label: getModelFamilyLabel(model),
          sampleModel: model,
        });
      }
    }

    return [
      {
        key: "all" as const,
        label: titleForLocale(locale, "全部", "All"),
        sampleModel: "all",
      },
      ...Array.from(optionsByPrefix.values()).sort((a, b) =>
        a.label.localeCompare(b.label),
      ),
    ];
  }, [data?.model_names, locale]);

  const visibleData = data?.items ?? [];
  const showModelPrefixFilter = modelPrefixOptions.length > 1;
  const effectiveSelectedModelPrefix = modelPrefixOptions.some(
    (item) => item.key === selectedModelPrefix,
  )
    ? selectedModelPrefix
    : "all";

  const channelOptions = useMemo(() => {
    return filterOptionsWithSelected(data?.channels, channelQueryValue);
  }, [channelQueryValue, data?.channels]);

  const gatewayKeyOptions = useMemo(() => {
    return filterOptionsWithSelected(data?.gateway_keys, effectiveGatewayKeyId);
  }, [data?.gateway_keys, effectiveGatewayKeyId]);
  const showGatewayKeyFilter =
    Boolean(data?.gateway_has_multiple_keys) || effectiveGatewayKeyId !== null;

  const total = data?.total ?? 0;
  const totalPages = Math.max(Math.ceil(total / PAGE_SIZE), 1);
  const hasNextPage = page < totalPages - 1;
  const paginationItems = buildPaginationItems(page + 1, totalPages);
  const activeFilterCount = [
    selectedModelPrefix !== "all",
    statusFilter !== "all",
    protocolFilter !== "all",
    channelFilter !== "all",
    effectiveGatewayKeyId !== null,
    Boolean(keyword.trim()),
  ].filter(Boolean).length;

  useEffect(() => {
    if (!relayLogBodyEnabled && detailId !== null) {
      setDetailId(null);
    }
  }, [detailId, relayLogBodyEnabled]);

  useEffect(() => {
    if (selectedModelPrefix !== effectiveSelectedModelPrefix) {
      setSelectedModelPrefix(effectiveSelectedModelPrefix);
    }
  }, [effectiveSelectedModelPrefix, selectedModelPrefix]);

  useEffect(() => {
    if (!isError) return;
    toast.error(
      titleForLocale(locale, "请求日志加载失败", "Failed to load request logs"),
      {
        id: "request-logs-load-error",
        description:
          error instanceof Error
            ? error.message
            : titleForLocale(
                locale,
                "无法读取请求日志",
                "Unable to read request logs",
              ),
      },
    );
  }, [error, isError, locale]);

  useEffect(() => {
    function handleScroll() {
      setShowBackToTop(window.scrollY > 320);
    }

    handleScroll();
    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  async function refreshLogs() {
    await Promise.all([
      refetchRequestLogs(),
      relayLogBodyEnabled && detailId !== null
        ? refetchDetail()
        : Promise.resolve(),
      attemptDetailId !== null ? refetchAttemptDetail() : Promise.resolve(),
    ]);
  }

  async function clearRequestLogs() {
    const confirmed = window.confirm(
      titleForLocale(
        locale,
        "确认删除全部请求日志？",
        "Delete all request logs?",
      ),
    );
    if (!confirmed) return;

    setClearingLogs(true);
    try {
      await apiRequest<void>("/admin/request-logs", { method: "DELETE" });
      setPage(0);
      setDetailId(null);
      setAttemptDetailId(null);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["request-logs"] }),
        queryClient.invalidateQueries({ queryKey: ["overview"] }),
        queryClient.invalidateQueries({ queryKey: ["overview-dashboard"] }),
        queryClient.invalidateQueries({ queryKey: ["overview-summary"] }),
        queryClient.invalidateQueries({ queryKey: ["overview-daily"] }),
        queryClient.invalidateQueries({ queryKey: ["overview-models"] }),
        queryClient.invalidateQueries({ queryKey: ["gateway-api-keys"] }),
      ]);
      toast.success(
        titleForLocale(locale, "请求日志已清空", "Request logs cleared"),
      );
    } catch (requestError) {
      toast.error(
        requestError instanceof ApiError
          ? requestError.message
          : titleForLocale(
              locale,
              "清空请求日志失败",
              "Failed to clear request logs",
            ),
      );
    } finally {
      setClearingLogs(false);
    }
  }

  function handleModelPrefixChange(value: SelectedModelPrefix) {
    setSelectedModelPrefix(value);
    setPage(0);
  }

  function handleStatusChange(value: StatusFilter) {
    setStatusFilter(value);
    setPage(0);
  }

  function handleProtocolChange(value: "all" | ProtocolKind) {
    setProtocolFilter(value);
    setPage(0);
  }

  function handleChannelChange(value: string) {
    setChannelFilter(value);
    setPage(0);
  }

  function handleGatewayKeyChange(value: string) {
    setSelectedGatewayKeyId(value);
    setPage(0);
  }

  function handleSortChange(value: SortMode) {
    setSortMode(value);
    setPage(0);
  }

  function handleKeywordChange(value: string) {
    setKeyword(value);
    setPage(0);
  }

  function resetFilters() {
    setSelectedModelPrefix("all");
    setStatusFilter("all");
    setProtocolFilter("all");
    setChannelFilter("all");
    setSelectedGatewayKeyId("all");
    setSortMode("latest");
    setKeyword("");
    setPage(0);
  }

  return (
    <TooltipProvider>
      <section className="flex flex-col gap-4 md:gap-5">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h1 className="text-xl font-semibold text-foreground">
              {titleForLocale(locale, "请求日志", "Requests")}
            </h1>
          </div>
          <div className="flex flex-wrap items-center gap-2 self-start lg:self-auto">
            <Button
              type="button"
              variant="outline"
              onClick={() => void refreshLogs()}
              disabled={isFetching}
            >
              <RefreshCcw
                data-icon="inline-start"
                className={cn(isFetching && "animate-spin")}
              />
              {titleForLocale(locale, "刷新", "Refresh")}
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={resetFilters}
              disabled={!activeFilterCount && sortMode === "latest"}
            >
              <RotateCcw data-icon="inline-start" />
              {titleForLocale(locale, "重置", "Reset")}
            </Button>
          </div>
        </div>

        <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,4fr)_320px]">
          <div className="order-2 grid gap-4 xl:order-1">
            {showModelPrefixFilter ? (
              <div className="rounded-2xl border bg-card px-4 py-3 sm:px-5 sm:py-4">
                <div className="flex items-center justify-between gap-3 sm:mb-3">
                  <div className="text-base font-semibold text-foreground">
                    {titleForLocale(
                      locale,
                      "选择模型系列",
                      "Choose model series",
                    )}
                  </div>
                </div>

                <NativeSelect
                  className="mt-3 w-full sm:hidden"
                  value={effectiveSelectedModelPrefix}
                  onChange={(event) =>
                    handleModelPrefixChange(event.target.value)
                  }
                >
                  {modelPrefixOptions.map((option) => (
                    <NativeSelectOption key={option.key} value={option.key}>
                      {option.label}
                    </NativeSelectOption>
                  ))}
                </NativeSelect>

                <div className="hidden snap-x gap-3 overflow-x-auto pb-1 sm:flex">
                  {modelPrefixOptions.map((option) => (
                    <SeriesChip
                      key={option.key}
                      selected={effectiveSelectedModelPrefix === option.key}
                      label={option.label}
                      sampleModel={option.sampleModel}
                      isAll={option.key === "all"}
                      onClick={() => handleModelPrefixChange(option.key)}
                    />
                  ))}
                </div>
              </div>
            ) : null}

            <div className="rounded-2xl border bg-card p-3 sm:p-4">
              {!isError && !isLoading && visibleData.length === 0 ? (
                <div className="rounded-xl border border-dashed bg-background px-6 py-14 text-center text-sm text-muted-foreground">
                  {activeFilterCount
                    ? titleForLocale(
                        locale,
                        "当前筛选条件下没有请求日志。",
                        "No request logs match the current filters.",
                      )
                    : titleForLocale(
                        locale,
                        "暂无请求日志。",
                        "No request logs yet.",
                      )}
                </div>
              ) : null}

              {visibleData.length ? (
                <div className="flex flex-col gap-3">
                  {visibleData.map((item) => (
                    <RequestCard
                      key={item.id}
                      item={item}
                      locale={locale}
                      timeZone={timeZone}
                      canOpenDetail={relayLogBodyEnabled}
                      onOpenDetail={() => setDetailId(item.id)}
                      onOpenAttempts={() => setAttemptDetailId(item.id)}
                    />
                  ))}
                </div>
              ) : null}
            </div>
          </div>

          <aside className="order-1 xl:order-2">
            <div className="rounded-2xl border bg-card p-4 xl:sticky xl:top-4">
              <div className="mb-4 flex items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <span className="inline-flex size-9 items-center justify-center rounded-xl bg-primary/[0.08] text-primary">
                    <Filter size={16} />
                  </span>
                  <div>
                    <div className="text-sm font-semibold text-foreground">
                      {titleForLocale(locale, "筛选", "Filters")}
                    </div>
                    <div className="text-xs text-muted-foreground">
                      {locale === "zh-CN"
                        ? `已启用 ${activeFilterCount} 项`
                        : `${activeFilterCount} active`}
                    </div>
                  </div>
                </div>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={resetFilters}
                  disabled={!activeFilterCount && sortMode === "latest"}
                >
                  {titleForLocale(locale, "清空", "Clear")}
                </Button>
              </div>

              <div>
                <FieldSet className="gap-4">
                  <FieldLegend>
                    {titleForLocale(locale, "筛选条件", "Refine results")}
                  </FieldLegend>
                  <FieldGroup className="gap-4">
                    <Field>
                      <FieldLabel>
                        {titleForLocale(locale, "关键词", "Keyword")}
                      </FieldLabel>
                      <ToolbarSearchInput
                        value={keyword}
                        onChange={handleKeywordChange}
                        onClear={() => handleKeywordChange("")}
                        placeholder={titleForLocale(
                          locale,
                          "模型 / 渠道 / API Key / 错误 / 状态码",
                          "Model / channel / API key / error / status",
                        )}
                        className="max-w-none"
                      />
                    </Field>

                    <Field>
                      <FieldLabel>
                        {titleForLocale(locale, "状态", "Status")}
                      </FieldLabel>
                      <div className="grid grid-cols-2 gap-2">
                        {[
                          {
                            key: "all" as const,
                            label: titleForLocale(locale, "全部", "All"),
                          },
                          {
                            key: "running" as const,
                            label: titleForLocale(locale, "进行中", "Running"),
                          },
                          {
                            key: "success" as const,
                            label: titleForLocale(locale, "成功", "Success"),
                          },
                          {
                            key: "failed" as const,
                            label: titleForLocale(locale, "失败", "Failed"),
                          },
                        ].map((option) => (
                          <Button
                            key={option.key}
                            type="button"
                            variant={
                              statusFilter === option.key
                                ? "default"
                                : "outline"
                            }
                            size="sm"
                            onClick={() => handleStatusChange(option.key)}
                          >
                            {option.label}
                          </Button>
                        ))}
                      </div>
                    </Field>

                    <Field>
                      <FieldLabel htmlFor="request-log-protocol">
                        {titleForLocale(locale, "协议", "Protocol")}
                      </FieldLabel>
                      <NativeSelect
                        id="request-log-protocol"
                        className="w-full"
                        value={protocolFilter}
                        onChange={(event) =>
                          handleProtocolChange(
                            event.target.value as "all" | ProtocolKind,
                          )
                        }
                      >
                        <NativeSelectOption value="all">
                          {titleForLocale(locale, "全部协议", "All protocols")}
                        </NativeSelectOption>
                        <NativeSelectOption value="openai_chat">
                          OpenAI Chat
                        </NativeSelectOption>
                        <NativeSelectOption value="openai_responses">
                          OpenAI Responses
                        </NativeSelectOption>
                        <NativeSelectOption value="openai_embedding">
                          OpenAI Embedding
                        </NativeSelectOption>
                        <NativeSelectOption value="rerank">
                          Rerank
                        </NativeSelectOption>
                        <NativeSelectOption value="anthropic">
                          Anthropic
                        </NativeSelectOption>
                        <NativeSelectOption value="gemini">
                          Gemini
                        </NativeSelectOption>
                      </NativeSelect>
                    </Field>

                    <Field>
                      <FieldLabel htmlFor="request-log-channel">
                        {titleForLocale(locale, "渠道", "Channel")}
                      </FieldLabel>
                      <NativeSelect
                        id="request-log-channel"
                        className="w-full"
                        value={channelFilter}
                        onChange={(event) =>
                          handleChannelChange(event.target.value)
                        }
                      >
                        <NativeSelectOption value="all">
                          {titleForLocale(locale, "全部渠道", "All channels")}
                        </NativeSelectOption>
                        {channelOptions.map((channel) => (
                          <NativeSelectOption
                            key={channel.id}
                            value={channel.id}
                          >
                            {filterOptionLabel(channel)}
                          </NativeSelectOption>
                        ))}
                      </NativeSelect>
                    </Field>

                    {showGatewayKeyFilter ? (
                      <Field>
                        <FieldLabel htmlFor="request-log-gateway-key">
                          API Key
                        </FieldLabel>
                        <NativeSelect
                          id="request-log-gateway-key"
                          className="w-full"
                          value={selectedGatewayKeyId}
                          onChange={(event) =>
                            handleGatewayKeyChange(event.target.value)
                          }
                        >
                          <NativeSelectOption value="all">
                            {titleForLocale(
                              locale,
                              "全部 API Key",
                              "All API keys",
                            )}
                          </NativeSelectOption>
                          {gatewayKeyOptions.map((item) => (
                            <NativeSelectOption key={item.id} value={item.id}>
                              {gatewayKeyFilterOptionLabel(item, locale)}
                            </NativeSelectOption>
                          ))}
                        </NativeSelect>
                      </Field>
                    ) : null}

                    <Field>
                      <FieldLabel htmlFor="request-log-sort">
                        {titleForLocale(locale, "排序", "Sort by")}
                      </FieldLabel>
                      <NativeSelect
                        id="request-log-sort"
                        className="w-full"
                        value={sortMode}
                        onChange={(event) =>
                          handleSortChange(event.target.value as SortMode)
                        }
                      >
                        <NativeSelectOption value="latest">
                          {titleForLocale(locale, "最新优先", "Latest first")}
                        </NativeSelectOption>
                        <NativeSelectOption value="cost">
                          {titleForLocale(locale, "费用优先", "Highest cost")}
                        </NativeSelectOption>
                        <NativeSelectOption value="latency">
                          {titleForLocale(
                            locale,
                            "耗时优先",
                            "Longest latency",
                          )}
                        </NativeSelectOption>
                        <NativeSelectOption value="tokens">
                          {titleForLocale(locale, "Token 优先", "Most tokens")}
                        </NativeSelectOption>
                      </NativeSelect>
                    </Field>
                  </FieldGroup>
                </FieldSet>
                <div className="mt-4 border-t pt-4">
                  <Button
                    type="button"
                    variant="outline"
                    className="w-full text-destructive hover:text-destructive"
                    onClick={() => void clearRequestLogs()}
                    disabled={clearingLogs}
                  >
                    <Trash2 data-icon="inline-start" />
                    {clearingLogs
                      ? titleForLocale(locale, "清空中...", "Clearing...")
                      : titleForLocale(
                          locale,
                          "清空请求日志",
                          "Clear request logs",
                        )}
                  </Button>
                </div>
              </div>
            </div>
          </aside>
        </div>

        {totalPages > 1 ? (
          <Pagination id="requests-pagination" className="justify-center pt-1">
            <PaginationContent>
              <PaginationItem>
                <PaginationPrevious
                  href="#requests-pagination"
                  text={titleForLocale(locale, "上一页", "Prev")}
                  onClick={(event) => {
                    event.preventDefault();
                    if (page === 0) return;
                    setPage((current) => Math.max(current - 1, 0));
                  }}
                  className={cn(page === 0 && "pointer-events-none opacity-50")}
                />
              </PaginationItem>
              {paginationItems.map((item, index) => (
                <PaginationItem key={`${item}-${index}`}>
                  {item === "ellipsis" ? (
                    <PaginationEllipsis />
                  ) : (
                    <PaginationLink
                      href="#requests-pagination"
                      size="default"
                      isActive={item === page + 1}
                      onClick={(event) => {
                        event.preventDefault();
                        if (item === page + 1) return;
                        setPage(item - 1);
                      }}
                    >
                      {item}
                    </PaginationLink>
                  )}
                </PaginationItem>
              ))}

              <PaginationItem>
                <PaginationNext
                  href="#requests-pagination"
                  text={titleForLocale(locale, "下一页", "Next")}
                  onClick={(event) => {
                    event.preventDefault();
                    if (!hasNextPage) return;
                    setPage((current) => current + 1);
                  }}
                  className={cn(
                    !hasNextPage && "pointer-events-none opacity-50",
                  )}
                />
              </PaginationItem>
            </PaginationContent>
          </Pagination>
        ) : null}

        <Dialog
          open={relayLogBodyEnabled && detailId !== null}
          onOpenChange={(open) => {
            if (!open) setDetailId(null);
          }}
        >
          <AppDialogContent
            className="max-w-6xl"
            title={titleForLocale(locale, "日志详情", "Log detail")}
          >
            {detailIsError ? (
              <Alert variant="destructive">
                <AlertCircle />
                <AlertTitle>
                  {titleForLocale(
                    locale,
                    "详情加载失败",
                    "Failed to load detail",
                  )}
                </AlertTitle>
                <AlertDescription>
                  {detailError instanceof Error
                    ? detailError.message
                    : titleForLocale(
                        locale,
                        "无法读取日志详情",
                        "Unable to read log detail",
                      )}
                </AlertDescription>
              </Alert>
            ) : detailLoading || !detail ? (
              <div className="rounded-md border bg-background px-5 py-8 text-sm text-muted-foreground">
                {titleForLocale(locale, "正在加载详情...", "Loading detail...")}
              </div>
            ) : (
              <div className="grid min-h-[60dvh] overflow-hidden sm:min-h-[560px] xl:grid-cols-2">
                <JsonViewer
                  key={`request-${detail.id}`}
                  title={titleForLocale(locale, "请求内容", "Request")}
                  content={detail.request_content}
                  emptyText={titleForLocale(
                    locale,
                    "无输入内容",
                    "No request content",
                  )}
                  locale={locale}
                />
                <JsonViewer
                  key={`response-${detail.id}`}
                  className="border-t xl:border-t-0 xl:border-l"
                  title={titleForLocale(locale, "响应内容", "Response")}
                  content={detail.response_content}
                  emptyText={titleForLocale(
                    locale,
                    "无输出内容",
                    "No response content",
                  )}
                  locale={locale}
                />
              </div>
            )}
          </AppDialogContent>
        </Dialog>

        <Dialog
          open={attemptDetailId !== null}
          onOpenChange={(open) => {
            if (!open) setAttemptDetailId(null);
          }}
        >
          <AppDialogContent
            className="max-w-4xl"
            title={titleForLocale(locale, "尝试链路", "Attempts")}
          >
            {attemptDetailIsError ? (
              <Alert variant="destructive">
                <AlertCircle />
                <AlertTitle>
                  {titleForLocale(
                    locale,
                    "尝试链路加载失败",
                    "Failed to load attempts",
                  )}
                </AlertTitle>
                <AlertDescription>
                  {attemptDetailError instanceof Error
                    ? attemptDetailError.message
                    : titleForLocale(
                        locale,
                        "无法读取尝试链路",
                        "Unable to read attempts",
                      )}
                </AlertDescription>
              </Alert>
            ) : attemptDetailLoading || !attemptDetail ? (
              <div className="rounded-md border bg-background px-5 py-8 text-sm text-muted-foreground">
                {titleForLocale(
                  locale,
                  "正在加载尝试链路...",
                  "Loading attempts...",
                )}
              </div>
            ) : (
              <div className="grid gap-4">
                {formatErrorDisplay(attemptDetail.error_message) ? (
                  <div className="rounded-lg border border-destructive/20 bg-destructive/10 px-4 py-4 text-sm text-destructive">
                    <div className="flex items-start gap-3">
                      <AlertCircle size={16} className="mt-0.5 shrink-0" />
                      <span className="whitespace-pre-wrap break-words">
                        {formatErrorDisplay(attemptDetail.error_message)}
                      </span>
                    </div>
                  </div>
                ) : null}
                <AttemptChain detail={attemptDetail} locale={locale} />
              </div>
            )}
          </AppDialogContent>
        </Dialog>

        {showBackToTop ? (
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                type="button"
                variant="outline"
                size="icon-lg"
                className="fixed right-4 bottom-4 z-40 rounded-full shadow-sm sm:right-6 sm:bottom-6"
                onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
              >
                <ArrowUp />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="left">
              {titleForLocale(locale, "返回顶部", "Back to top")}
            </TooltipContent>
          </Tooltip>
        ) : null}

        <style jsx global>{`
          .json-view-shell .w-rjv-inner > span,
          .json-view-shell .w-rjv-line,
          .json-view-shell .w-rjv-inner > div:not(.w-rjv-wrap) {
            min-height: 1.5rem;
            line-height: 1.5rem;
          }

          .json-view-shell .w-rjv-inner > span {
            display: flex;
            flex-wrap: wrap;
            align-items: center;
          }
        `}</style>
      </section>
    </TooltipProvider>
  );
}
