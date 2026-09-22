import {
  ArrowDownUp,
  Check,
  Funnel,
  RefreshCw,
  Search,
  Trash2,
} from "lucide-react";
import { Button } from "@/components/ui/Button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/DropdownMenu";
import { Input } from "@/components/ui/Input";
import { TablePagination } from "@/components/ui/Pagination";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/Popover";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/Select";
import { ToolbarButton } from "@/components/ui/ToolbarButton";
import type { ProtocolKind } from "@/lib/api/protocols";
import type {
  RequestLogFilterOption,
  RequestLogItem,
} from "@/lib/api/requests";
import { cn } from "@/lib/classNames";
import { titleForLocale } from "@/lib/I18nContext";
import type { ModelPrefixOption, SelectedModelPrefix } from "@/lib/modelPrefix";
import { protocolOptions } from "@/lib/protocols";
import { RequestsTable } from "./RequestsTable";
import {
  channelFilterOptionLabel,
  gatewayKeyFilterOptionLabel,
  PAGE_SIZE_OPTIONS,
  type SortMode,
  type StatusFilter,
} from "./requestView";

type Locale = "zh-CN" | "en-US";

type Props = {
  locale: Locale;
  items: RequestLogItem[];
  loading: boolean;
  fetching: boolean;
  keyword: string;
  statusFilter: StatusFilter;
  protocolFilter: "all" | ProtocolKind;
  channelFilter: string;
  channelOptions: RequestLogFilterOption[];
  selectedGatewayKeyId: string;
  gatewayKeyOptions: RequestLogFilterOption[];
  showGatewayKeyFilter: boolean;
  modelPrefixOptions: ModelPrefixOption[];
  effectiveModelPrefix: SelectedModelPrefix;
  sortMode: SortMode;
  activeFilterCount: number;
  clearingLogs: boolean;
  timeZone: string;
  page: number;
  pageSize: (typeof PAGE_SIZE_OPTIONS)[number];
  total: number;
  totalPages: number;
  onKeywordChange: (value: string) => void;
  onStatusChange: (value: StatusFilter) => void;
  onProtocolChange: (value: "all" | ProtocolKind) => void;
  onChannelChange: (value: string) => void;
  onGatewayKeyChange: (value: string) => void;
  onModelPrefixChange: (value: SelectedModelPrefix) => void;
  onSortChange: (value: SortMode) => void;
  onReset: () => void;
  onRefresh: () => void;
  onClear: () => void;
  onPageChange: (page: number) => void;
  onPageSizeChange: (size: (typeof PAGE_SIZE_OPTIONS)[number]) => void;
  onOpenDetail: (id: number) => void;
};

/** Renders request logs as a toolbar and table. */
export function RequestsOverview({
  locale,
  items,
  loading,
  fetching,
  keyword,
  statusFilter,
  protocolFilter,
  channelFilter,
  channelOptions,
  selectedGatewayKeyId,
  gatewayKeyOptions,
  showGatewayKeyFilter,
  modelPrefixOptions,
  effectiveModelPrefix,
  sortMode,
  activeFilterCount,
  clearingLogs,
  timeZone,
  page,
  pageSize,
  total,
  totalPages,
  onKeywordChange,
  onStatusChange,
  onProtocolChange,
  onChannelChange,
  onGatewayKeyChange,
  onModelPrefixChange,
  onSortChange,
  onReset,
  onRefresh,
  onClear,
  onPageChange,
  onPageSizeChange,
  onOpenDetail,
}: Props) {
  const displayPage = page + 1;
  const familyOptions = modelPrefixOptions.filter(
    (option) => option.key !== "all",
  );
  const sortOptions: Array<{ value: SortMode; label: string }> = [
    {
      value: "latest",
      label: titleForLocale(locale, "最新优先", "Latest first"),
    },
    {
      value: "cost",
      label: titleForLocale(locale, "费用优先", "Highest cost"),
    },
    {
      value: "latency",
      label: titleForLocale(locale, "耗时优先", "Longest latency"),
    },
    {
      value: "tokens",
      label: titleForLocale(locale, "Token 优先", "Most tokens"),
    },
  ];
  const emptyLabel = activeFilterCount
    ? titleForLocale(
        locale,
        "当前筛选条件下没有请求日志。",
        "No request logs match the current filters.",
      )
    : titleForLocale(locale, "暂无请求日志。", "No request logs yet.");

  return (
    <div className="space-y-3 pb-10">
      <div className="flex h-10 items-center justify-between gap-3 px-1">
        <h3 className="text-sm font-semibold">
          {titleForLocale(locale, "请求日志", "Request logs")}
        </h3>
        <Button
          type="button"
          size="sm"
          variant="ghost"
          className="h-8 gap-1.5 px-2 text-xs text-muted-foreground shadow-none"
          disabled={clearingLogs}
          onClick={onClear}
        >
          <Trash2 className="size-3.5 stroke-1" />
          {clearingLogs
            ? titleForLocale(locale, "清空中...", "Clearing...")
            : titleForLocale(locale, "清空请求日志", "Clear logs")}
        </Button>
      </div>

      <section className="flex min-h-10 flex-nowrap items-center gap-1.5 overflow-x-auto overscroll-x-contain py-1 [scrollbar-width:none] md:gap-3 [&::-webkit-scrollbar]:hidden">
        <div className="flex min-w-max flex-nowrap items-center gap-1.5 md:min-w-0 md:flex-1">
          <div className="relative min-w-[160px] flex-1 md:max-w-[320px]">
            <Search className="pointer-events-none absolute top-1/2 left-3 size-3.5 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={keyword}
              placeholder={titleForLocale(
                locale,
                "模型 / 渠道 / API Key / 错误",
                "Model / channel / API key / error",
              )}
              onChange={(event) => onKeywordChange(event.target.value)}
              className="bg-background pl-8"
            />
          </div>

          <Popover>
            <PopoverTrigger asChild>
              <ToolbarButton
                aria-label={titleForLocale(locale, "筛选", "Filter")}
              >
                <Funnel className="size-3.5" />
                <span className="hidden sm:inline">
                  {titleForLocale(locale, "筛选", "Filter")}
                </span>
                {activeFilterCount ? (
                  <span className="text-[10px] tabular-nums">
                    {activeFilterCount}
                  </span>
                ) : null}
              </ToolbarButton>
            </PopoverTrigger>
            <PopoverContent align="start" className="w-[260px] p-2">
              <div className="space-y-2">
                <div className="space-y-1">
                  <p className="px-1 text-[10px] text-muted-foreground">
                    {titleForLocale(locale, "状态", "Status")}
                  </p>
                  <Select
                    value={statusFilter}
                    onValueChange={(value) =>
                      onStatusChange(value as StatusFilter)
                    }
                  >
                    <SelectTrigger className="h-7 px-2 text-[11px] text-muted-foreground">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">
                        {titleForLocale(locale, "全部状态", "All statuses")}
                      </SelectItem>
                      <SelectItem value="running">
                        {titleForLocale(locale, "进行中", "Running")}
                      </SelectItem>
                      <SelectItem value="success">
                        {titleForLocale(locale, "成功", "Success")}
                      </SelectItem>
                      <SelectItem value="failed">
                        {titleForLocale(locale, "失败", "Failed")}
                      </SelectItem>
                      <SelectItem value="cancelled">
                        {titleForLocale(locale, "已取消", "Cancelled")}
                      </SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-1">
                  <p className="px-1 text-[10px] text-muted-foreground">
                    {titleForLocale(locale, "协议", "Protocol")}
                  </p>
                  <Select
                    value={protocolFilter}
                    onValueChange={(value) =>
                      onProtocolChange(value as "all" | ProtocolKind)
                    }
                  >
                    <SelectTrigger className="h-7 px-2 text-[11px] text-muted-foreground">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">
                        {titleForLocale(locale, "全部协议", "All protocols")}
                      </SelectItem>
                      {protocolOptions(locale).map((option) => (
                        <SelectItem key={option.value} value={option.value}>
                          {option.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-1">
                  <p className="px-1 text-[10px] text-muted-foreground">
                    {titleForLocale(locale, "渠道", "Channel")}
                  </p>
                  <Select value={channelFilter} onValueChange={onChannelChange}>
                    <SelectTrigger className="h-7 px-2 text-[11px] text-muted-foreground">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">
                        {titleForLocale(locale, "全部渠道", "All channels")}
                      </SelectItem>
                      {channelOptions.map((channel) => (
                        <SelectItem key={channel.id} value={channel.id}>
                          {channelFilterOptionLabel(channel, locale)}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                {showGatewayKeyFilter ? (
                  <div className="space-y-1">
                    <p className="px-1 text-[10px] text-muted-foreground">
                      API Key
                    </p>
                    <Select
                      value={selectedGatewayKeyId}
                      onValueChange={onGatewayKeyChange}
                    >
                      <SelectTrigger className="h-7 px-2 text-[11px] text-muted-foreground">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">
                          {titleForLocale(
                            locale,
                            "全部 API Key",
                            "All API keys",
                          )}
                        </SelectItem>
                        {gatewayKeyOptions.map((item) => (
                          <SelectItem key={item.id} value={item.id}>
                            {gatewayKeyFilterOptionLabel(item, locale)}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                ) : null}
                {familyOptions.length ? (
                  <div className="space-y-1">
                    <p className="px-1 text-[10px] text-muted-foreground">
                      {titleForLocale(locale, "厂商", "Family")}
                    </p>
                    <Select
                      value={effectiveModelPrefix}
                      onValueChange={onModelPrefixChange}
                    >
                      <SelectTrigger className="h-7 px-2 text-[11px] text-muted-foreground">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">
                          {titleForLocale(locale, "全部厂商", "All families")}
                        </SelectItem>
                        {familyOptions.map((option) => (
                          <SelectItem key={option.key} value={option.key}>
                            {option.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                ) : null}
                {activeFilterCount ? (
                  <div className="flex justify-end border-t border-border/60 pt-2">
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      className="h-7 px-2 text-xs shadow-none"
                      onClick={onReset}
                    >
                      {titleForLocale(locale, "清空", "Clear")}
                    </Button>
                  </div>
                ) : null}
              </div>
            </PopoverContent>
          </Popover>

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <ToolbarButton
                aria-label={titleForLocale(locale, "排序", "Sort")}
              >
                <ArrowDownUp className="size-3.5" />
                <span className="hidden sm:inline">
                  {titleForLocale(locale, "排序", "Sort")}
                </span>
              </ToolbarButton>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start" className="w-40 p-1.5">
              {sortOptions.map((option) => (
                <DropdownMenuItem
                  key={option.value}
                  className="h-6 gap-2 px-2 py-0 text-[10px]"
                  onSelect={() => onSortChange(option.value)}
                >
                  <span className="flex-1 truncate">{option.label}</span>
                  {sortMode === option.value ? (
                    <Check className="size-3 text-muted-foreground" />
                  ) : null}
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        <div className="ml-auto flex min-h-8 shrink-0 items-center gap-1">
          <ToolbarButton
            onClick={onRefresh}
            disabled={fetching}
            aria-label={titleForLocale(locale, "刷新", "Refresh")}
            title={titleForLocale(locale, "刷新", "Refresh")}
          >
            <RefreshCw className={cn("size-3.5", fetching && "animate-spin")} />
          </ToolbarButton>
        </div>
      </section>

      <RequestsTable
        locale={locale}
        items={items}
        loading={loading}
        emptyLabel={emptyLabel}
        timeZone={timeZone}
        onOpenDetail={onOpenDetail}
      />

      <TablePagination
        locale={locale}
        total={total}
        page={displayPage}
        pageCount={totalPages}
        pageSize={pageSize}
        pageSizeOptions={PAGE_SIZE_OPTIONS}
        onPageChange={(nextPage) => onPageChange(nextPage - 1)}
        onPageSizeChange={(size) =>
          onPageSizeChange(size as (typeof PAGE_SIZE_OPTIONS)[number])
        }
        loading={loading}
      />
    </div>
  );
}
