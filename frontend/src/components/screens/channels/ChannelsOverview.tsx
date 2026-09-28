import {
  ArrowDownUp,
  Check,
  FileInput,
  Funnel,
  Plus,
  RefreshCw,
  Search,
} from "lucide-react";
import { useState } from "react";
import { BulkActionsPopover } from "@/components/ui/BulkActionsPopover";
import { Button } from "@/components/ui/Button";
import { ConfirmDeleteDialog } from "@/components/ui/ConfirmDeleteDialog";
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
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/Tooltip";
import { useClientPagination } from "@/hooks/useClientPagination";
import { useRowSelection } from "@/hooks/useRowSelection";
import type { Site } from "@/lib/api/sites";
import { cn } from "@/lib/classNames";
import { ChannelsTable } from "./ChannelsTable";
import type {
  ChannelSort,
  ChannelStatusFilter,
  Locale,
  SiteRow,
} from "./channelTypes";

const siteId = (site: SiteRow) => site.id;

function channelSortOptions(
  locale: Locale,
): Array<{ value: ChannelSort; label: string }> {
  return [
    { value: "name-asc", label: locale === "zh-CN" ? "名称升序" : "Name A-Z" },
    { value: "name-desc", label: locale === "zh-CN" ? "名称降序" : "Name Z-A" },
    {
      value: "models-desc",
      label: locale === "zh-CN" ? "模型优先" : "Models first",
    },
  ];
}

type Props = {
  locale: Locale;
  visibleSites: SiteRow[];
  isLoading: boolean;
  search: string;
  statusFilter: ChannelStatusFilter;
  tags: string[];
  tagFilter: string | null;
  sortBy: ChannelSort;
  activeFilterCount: number;
  busyId: string | null;
  onSearchChange: (value: string) => void;
  onStatusChange: (value: ChannelStatusFilter) => void;
  onTagChange: (value: string | null) => void;
  onSortChange: (value: ChannelSort) => void;
  onReset: () => void;
  onRefresh: () => void;
  onCreate: () => void;
  onImport: () => void;
  onOpenEdit: (site: Site) => void;
  onManageModels: (site: Site) => void;
  onReviewPendingModels: (site: Site) => void;
  onFetchModels: (site: Site) => void;
  syncingSiteId: string | null;
  onSyncModels: (site: Site) => void;
  onToggleSiteEnabled: (site: Site, enabled: boolean) => void;
  onDelete: (site: Site) => void;
  onBulkEnabled: (sites: Site[], enabled: boolean) => void;
  onBulkDelete: (sites: Site[]) => void;
};

/** Renders the channel list as a toolbar and table. */
export function ChannelsOverview({
  locale,
  visibleSites,
  isLoading,
  search,
  statusFilter,
  tags,
  tagFilter,
  sortBy,
  activeFilterCount,
  busyId,
  onSearchChange,
  onStatusChange,
  onTagChange,
  onSortChange,
  onReset,
  onRefresh,
  onCreate,
  onImport,
  onOpenEdit,
  onManageModels,
  onReviewPendingModels,
  onFetchModels,
  syncingSiteId,
  onSyncModels,
  onToggleSiteEnabled,
  onDelete,
  onBulkEnabled,
  onBulkDelete,
}: Props) {
  const {
    pageRows: pagedSites,
    resetPage,
    paginationProps,
  } = useClientPagination(visibleSites);
  const selection = useRowSelection(visibleSites, siteId);
  const selectedSites = selection.selectedRows;
  const [bulkDeleteOpen, setBulkDeleteOpen] = useState(false);
  const sortOptions = channelSortOptions(locale);

  return (
    <div className="space-y-3 pb-10">
      <div className="flex h-10 items-center justify-between gap-3 px-1">
        <h3 className="text-sm font-semibold">
          {locale === "zh-CN" ? "渠道管理" : "Channels"}
        </h3>
      </div>

      <section className="flex min-h-10 flex-nowrap items-center gap-1.5 overflow-x-auto overscroll-x-contain py-1 [scrollbar-width:none] md:gap-3 [&::-webkit-scrollbar]:hidden">
        <div className="flex min-w-max flex-nowrap items-center gap-1.5 md:min-w-0 md:flex-1">
          <div className="relative min-w-[160px] flex-1 md:max-w-[320px]">
            <Search className="pointer-events-none absolute top-1/2 left-3 size-3.5 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={search}
              placeholder={
                locale === "zh-CN" ? "搜索名称、地址" : "Search name or URL"
              }
              onChange={(event) => {
                onSearchChange(event.target.value);
                resetPage();
              }}
              className="bg-background pl-8"
            />
          </div>

          <Popover>
            <PopoverTrigger asChild>
              <ToolbarButton
                aria-label={locale === "zh-CN" ? "筛选" : "Filter"}
              >
                <Funnel className="size-3.5" />
                <span className="hidden sm:inline">
                  {locale === "zh-CN" ? "筛选" : "Filter"}
                </span>
                {activeFilterCount ? (
                  <span className="text-[10px] tabular-nums">
                    {activeFilterCount}
                  </span>
                ) : null}
              </ToolbarButton>
            </PopoverTrigger>
            <PopoverContent align="start" className="w-[240px] p-2">
              <div className="space-y-2">
                <div className="space-y-1">
                  <p className="px-1 text-[10px] text-muted-foreground">
                    {locale === "zh-CN" ? "状态" : "Status"}
                  </p>
                  <Select
                    value={statusFilter}
                    onValueChange={(value) => {
                      onStatusChange(value as ChannelStatusFilter);
                      resetPage();
                    }}
                  >
                    <SelectTrigger className="h-7 px-2 text-[11px] text-muted-foreground">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">
                        {locale === "zh-CN" ? "全部状态" : "All statuses"}
                      </SelectItem>
                      <SelectItem value="enabled">
                        {locale === "zh-CN" ? "启用" : "Enabled"}
                      </SelectItem>
                      <SelectItem value="disabled">
                        {locale === "zh-CN" ? "停用" : "Disabled"}
                      </SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                {tags.length ? (
                  <div className="space-y-1">
                    <p className="px-1 text-[10px] text-muted-foreground">
                      {locale === "zh-CN" ? "标签" : "Tag"}
                    </p>
                    <Select
                      value={tagFilter ? `tag:${tagFilter}` : "all"}
                      onValueChange={(value) => {
                        onTagChange(value === "all" ? null : value.slice(4));
                        resetPage();
                      }}
                    >
                      <SelectTrigger className="h-7 px-2 text-[11px] text-muted-foreground">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">
                          {locale === "zh-CN" ? "全部标签" : "All tags"}
                        </SelectItem>
                        {tags.map((tag) => (
                          <SelectItem key={tag} value={`tag:${tag}`}>
                            {tag}
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
                      onClick={() => {
                        onReset();
                        resetPage();
                      }}
                    >
                      {locale === "zh-CN" ? "清空" : "Clear"}
                    </Button>
                  </div>
                ) : null}
              </div>
            </PopoverContent>
          </Popover>

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <ToolbarButton aria-label={locale === "zh-CN" ? "排序" : "Sort"}>
                <ArrowDownUp className="size-3.5" />
                <span className="hidden sm:inline">
                  {locale === "zh-CN" ? "排序" : "Sort"}
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
                  {sortBy === option.value ? (
                    <Check className="size-3 text-muted-foreground" />
                  ) : null}
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>

          <BulkActionsPopover
            locale={locale}
            count={selectedSites.length}
            isBusy={Boolean(busyId)}
            onSetEnabled={(enabled) => {
              void onBulkEnabled(selectedSites, enabled);
              selection.clear();
            }}
            onDelete={() => setBulkDeleteOpen(true)}
          />
        </div>

        <div className="ml-auto flex min-h-8 shrink-0 items-center gap-1">
          <Tooltip>
            <TooltipTrigger asChild>
              <ToolbarButton
                onClick={onRefresh}
                disabled={isLoading}
                aria-label={locale === "zh-CN" ? "刷新" : "Refresh"}
              >
                <RefreshCw
                  className={cn("size-3.5", isLoading && "animate-spin")}
                />
              </ToolbarButton>
            </TooltipTrigger>
            <TooltipContent>
              {locale === "zh-CN" ? "刷新" : "Refresh"}
            </TooltipContent>
          </Tooltip>
          <Tooltip>
            <TooltipTrigger asChild>
              <ToolbarButton
                onClick={onImport}
                aria-label={locale === "zh-CN" ? "批量导入" : "Import"}
              >
                <FileInput className="size-3.5" />
              </ToolbarButton>
            </TooltipTrigger>
            <TooltipContent>
              {locale === "zh-CN" ? "批量导入" : "Import"}
            </TooltipContent>
          </Tooltip>
          <Button
            type="button"
            size="sm"
            className="h-7 gap-1 text-xs"
            onClick={onCreate}
          >
            <Plus className="size-3.5 stroke-1" />
            {locale === "zh-CN" ? "新增" : "Add"}
          </Button>
        </div>
      </section>

      <ChannelsTable
        locale={locale}
        items={pagedSites}
        loading={isLoading}
        selected={selection.selected}
        busyId={busyId}
        onSelectAll={(checked) => selection.toggleRows(pagedSites, checked)}
        onSelectOne={selection.toggleId}
        onEdit={onOpenEdit}
        onManageModels={onManageModels}
        onReviewPendingModels={onReviewPendingModels}
        onFetchModels={onFetchModels}
        syncingSiteId={syncingSiteId}
        onSyncModels={onSyncModels}
        onToggleEnabled={onToggleSiteEnabled}
        onDelete={onDelete}
      />

      <TablePagination locale={locale} {...paginationProps} />

      <ConfirmDeleteDialog
        open={bulkDeleteOpen}
        locale={locale}
        title={locale === "zh-CN" ? "确认批量删除" : "Delete channels"}
        description={
          locale === "zh-CN"
            ? `将删除选中的 ${selectedSites.length} 个渠道，其协议配置、模型和模型组成员会一起移除。`
            : `${selectedSites.length} selected channels will be removed together with their protocol configs, models, and group members.`
        }
        isDisabled={Boolean(busyId)}
        onOpenChange={setBulkDeleteOpen}
        onConfirm={() => {
          void onBulkDelete(selectedSites);
          selection.clear();
          setBulkDeleteOpen(false);
        }}
      />
    </div>
  );
}
