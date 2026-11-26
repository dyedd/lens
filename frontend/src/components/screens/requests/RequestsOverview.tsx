import {
  ArrowDownUp,
  Check,
  Funnel,
  RefreshCw,
  Search,
  Trash2,
} from "lucide-react";
import { useState } from "react";
import { PageHeader } from "@/components/shell/PageHeader";
import { Button } from "@/components/ui/Button";
import { ConfirmDeleteDialog } from "@/components/ui/ConfirmDeleteDialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/DropdownMenu";
import { FilterPillGroup } from "@/components/ui/FilterPillGroup";
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
import type { ProtocolKind } from "@/lib/api/protocols";
import type {
  RequestLogFilterOption,
  RequestLogItem,
} from "@/lib/api/requests";
import { cn } from "@/lib/classNames";
import type { Locale } from "@/lib/I18nContext";
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
  onOpenDetail: (id: number, trigger: HTMLButtonElement | null) => void;
  onCancel: (id: number) => void;
  cancellingId?: number;
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
  onCancel,
  cancellingId,
}: Props) {
  const [clearDialogOpen, setClearDialogOpen] = useState(false);
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
      label: titleForLocale(locale, "成本最高", "Highest cost"),
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
        "当前筛选条件下没有匹配的请求日志。",
        "No request logs match the current filters.",
      )
    : titleForLocale(locale, "暂无请求日志。", "No request logs yet.");
  const searchPlaceholder = titleForLocale(
    locale,
    "搜索模型、渠道、网关密钥或错误信息...",
    "Search model, channel, key, or error...",
  );

  const secondaryFilterCount =
    Number(protocolFilter !== "all") +
    Number(channelFilter !== "all") +
    Number(showGatewayKeyFilter && selectedGatewayKeyId !== "all") +
    Number(effectiveModelPrefix !== "all");

  return (
    <div className="space-y-4 pb-10">
      <PageHeader
        title={titleForLocale(locale, "请求日志", "Request Logs")}
        actions={
          <>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="text-muted-foreground hover:text-foreground"
              onClick={onRefresh}
              disabled={fetching}
              aria-label={titleForLocale(locale, "刷新", "Refresh")}
            >
              <RefreshCw
                className={cn("size-3.5", fetching && "animate-spin")}
              />
              {titleForLocale(locale, "刷新", "Refresh")}
            </Button>
            <Button
              type="button"
              size="sm"
              variant="ghost"
              className="text-muted-foreground hover:text-destructive"
              disabled={clearingLogs}
              onClick={() => setClearDialogOpen(true)}
            >
              <Trash2 className="size-3.5" />
              {clearingLogs
                ? titleForLocale(locale, "清空中...", "Clearing...")
                : titleForLocale(locale, "清空日志", "Clear logs")}
            </Button>
          </>
        }
      />

      <section className="flex flex-wrap items-center justify-between gap-2.5">
        <div className="flex flex-wrap items-center gap-2">
          <FilterPillGroup
            value={statusFilter}
            ariaLabel={titleForLocale(locale, "请求状态筛选", "Request status")}
            onValueChange={(value) => onStatusChange(value as StatusFilter)}
            options={[
              { value: "all", label: titleForLocale(locale, "全部", "All") },
              {
                value: "running",
                label: titleForLocale(locale, "进行中", "Running"),
              },
              {
                value: "success",
                label: titleForLocale(locale, "成功", "Success"),
              },
              {
                value: "failed",
                label: titleForLocale(locale, "失败", "Failed"),
              },
              {
                value: "cancelled",
                label: titleForLocale(locale, "已取消", "Cancelled"),
              },
            ]}
          />

          <Popover>
            <PopoverTrigger asChild>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="h-8 px-2 text-[13px] font-medium text-muted-foreground hover:text-foreground"
                aria-label={titleForLocale(locale, "筛选", "Filter")}
              >
                <Funnel className="size-3.5" />
                <span>{titleForLocale(locale, "更多条件", "Dimensions")}</span>
                {secondaryFilterCount ? (
                  <span className="font-mono text-xs tabular-nums text-foreground">
                    {secondaryFilterCount}
                  </span>
                ) : null}
              </Button>
            </PopoverTrigger>
            <PopoverContent align="start" className="w-[260px] p-2">
              <div className="space-y-2">
                <div className="space-y-1">
                  <p className="px-1 text-xs text-muted-foreground">
                    {titleForLocale(locale, "协议", "Protocol")}
                  </p>
                  <Select
                    value={protocolFilter}
                    onValueChange={(value) =>
                      onProtocolChange(value as "all" | ProtocolKind)
                    }
                  >
                    <SelectTrigger className="h-7 px-2 text-muted-foreground">
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
                  <p className="px-1 text-xs text-muted-foreground">
                    {titleForLocale(locale, "渠道", "Channel")}
                  </p>
                  <Select value={channelFilter} onValueChange={onChannelChange}>
                    <SelectTrigger className="h-7 px-2 text-muted-foreground">
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
                    <p className="px-1 text-xs text-muted-foreground">
                      {titleForLocale(locale, "网关密钥", "Gateway key")}
                    </p>
                    <Select
                      value={selectedGatewayKeyId}
                      onValueChange={onGatewayKeyChange}
                    >
                      <SelectTrigger className="h-7 px-2 text-muted-foreground">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">
                          {titleForLocale(
                            locale,
                            "全部网关密钥",
                            "All gateway keys",
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
                    <p className="px-1 text-xs text-muted-foreground">
                      {titleForLocale(locale, "厂商", "Family")}
                    </p>
                    <Select
                      value={effectiveModelPrefix}
                      onValueChange={onModelPrefixChange}
                    >
                      <SelectTrigger className="h-7 px-2 text-muted-foreground">
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
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="h-8 rounded-xl border-border/70 px-2.5 text-[13px] font-medium"
                aria-label={titleForLocale(locale, "排序", "Sort")}
              >
                <ArrowDownUp className="size-3.5 text-muted-foreground" />
                <span>
                  {sortOptions.find((o) => o.value === sortMode)?.label ??
                    titleForLocale(locale, "排序", "Sort")}
                </span>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start" className="w-40 p-1.5">
              {sortOptions.map((option) => (
                <DropdownMenuItem
                  key={option.value}
                  className="h-7 gap-2 px-2 py-0 text-xs"
                  onSelect={() => onSortChange(option.value)}
                >
                  <span className="flex-1 truncate">{option.label}</span>
                  {sortMode === option.value ? (
                    <Check className="size-3.5 text-muted-foreground" />
                  ) : null}
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>

          {activeFilterCount > 0 ? (
            <Button
              type="button"
              size="sm"
              variant="ghost"
              className="h-8 px-2 text-xs text-muted-foreground"
              onClick={onReset}
            >
              {titleForLocale(locale, "重置", "Reset")}
            </Button>
          ) : null}
        </div>

        <div className="relative w-full sm:w-72">
          <Search className="pointer-events-none absolute top-1/2 left-3 size-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={keyword}
            placeholder={searchPlaceholder}
            aria-label={searchPlaceholder}
            onChange={(event) => onKeywordChange(event.target.value)}
            className="pl-8"
          />
        </div>
      </section>

      <RequestsTable
        locale={locale}
        items={items}
        loading={loading}
        emptyLabel={emptyLabel}
        timeZone={timeZone}
        onOpenDetail={onOpenDetail}
        onCancel={onCancel}
        cancellingId={cancellingId}
      />

      <ConfirmDeleteDialog
        open={clearDialogOpen}
        locale={locale}
        title={titleForLocale(locale, "清空请求日志", "Clear request logs")}
        description={titleForLocale(
          locale,
          "将永久删除全部请求日志。",
          "Permanently delete all request logs.",
        )}
        isBusy={clearingLogs}
        onOpenChange={setClearDialogOpen}
        onConfirm={() => {
          onClear();
          setClearDialogOpen(false);
        }}
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
