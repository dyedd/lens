import {
  ArrowDownUp,
  Check,
  FileInput,
  Plus,
  RefreshCw,
  Search,
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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/Select";
import { SelectionActionBar } from "@/components/ui/SelectionActionBar";
import { useClientPagination } from "@/hooks/useClientPagination";
import { useRowSelection } from "@/hooks/useRowSelection";
import type { Site } from "@/lib/api/sites";
import { cn } from "@/lib/classNames";
import { titleForLocale } from "@/lib/I18nContext";
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
    {
      value: "name-asc",
      label: titleForLocale(locale, "渠道名称升序", "Name A-Z"),
    },
    {
      value: "name-desc",
      label: titleForLocale(locale, "渠道名称降序", "Name Z-A"),
    },
    {
      value: "models-desc",
      label: titleForLocale(locale, "模型数量", "Model count"),
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
  const searchPlaceholder =
    locale === "zh-CN"
      ? "搜索渠道名称或地址..."
      : "Search channel name or URL...";

  return (
    <div className="space-y-4 pb-10">
      <PageHeader
        title={locale === "zh-CN" ? "渠道" : "Channels"}
        actions={
          <>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="text-muted-foreground hover:text-foreground"
              onClick={onRefresh}
              disabled={isLoading}
              aria-label={locale === "zh-CN" ? "刷新" : "Refresh"}
            >
              <RefreshCw
                className={cn("size-3.5", isLoading && "animate-spin")}
              />
              {locale === "zh-CN" ? "刷新" : "Refresh"}
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={onImport}
              aria-label={locale === "zh-CN" ? "导入渠道" : "Import Channels"}
            >
              <FileInput className="size-3.5" />
              {locale === "zh-CN" ? "导入" : "Import"}
            </Button>
            <Button type="button" size="sm" onClick={onCreate}>
              <Plus className="size-3.5" />
              {locale === "zh-CN" ? "新建渠道" : "New Channel"}
            </Button>
          </>
        }
      />

      <section className="flex flex-wrap items-center justify-between gap-2.5">
        <div className="flex flex-wrap items-center gap-2">
          <FilterPillGroup
            value={statusFilter}
            ariaLabel={locale === "zh-CN" ? "渠道状态筛选" : "Channel status"}
            onValueChange={(value) => {
              onStatusChange(value);
              resetPage();
            }}
            options={[
              {
                value: "all",
                label: locale === "zh-CN" ? "全部" : "All",
              },
              {
                value: "enabled",
                label: locale === "zh-CN" ? "已启用" : "Enabled",
              },
              {
                value: "disabled",
                label: locale === "zh-CN" ? "已停用" : "Paused",
              },
            ]}
          />

          {tags.length ? (
            <Select
              value={tagFilter ? `tag:${tagFilter}` : "all"}
              onValueChange={(value) => {
                onTagChange(value === "all" ? null : value.slice(4));
                resetPage();
              }}
            >
              <SelectTrigger className="h-8 w-auto min-w-[104px] border-0 bg-transparent px-2 text-[13px] text-muted-foreground shadow-none hover:bg-muted/50 hover:text-foreground">
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
          ) : null}

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                aria-label={locale === "zh-CN" ? "排序" : "Sort"}
                className="h-8 px-2 text-[13px] font-medium text-muted-foreground hover:text-foreground"
              >
                <ArrowDownUp className="size-3.5" />
                <span>
                  {sortOptions.find((o) => o.value === sortBy)?.label ??
                    (locale === "zh-CN" ? "排序" : "Sort")}
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
                  {sortBy === option.value ? (
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
              className="h-7 px-2 text-xs text-muted-foreground"
              onClick={() => {
                onReset();
                resetPage();
              }}
            >
              {locale === "zh-CN" ? "重置" : "Reset"}
            </Button>
          ) : null}
        </div>

        <div className="relative w-full sm:w-64">
          <Search className="pointer-events-none absolute top-1/2 left-3 size-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={search}
            placeholder={searchPlaceholder}
            aria-label={searchPlaceholder}
            onChange={(event) => {
              onSearchChange(event.target.value);
              resetPage();
            }}
            className="pl-8"
          />
        </div>
      </section>

      <SelectionActionBar
        locale={locale}
        count={selectedSites.length}
        onClear={selection.clear}
      >
        <Button
          type="button"
          size="xs"
          variant="outline"
          disabled={Boolean(busyId)}
          onClick={() => {
            void onBulkEnabled(selectedSites, true);
            selection.clear();
          }}
        >
          {locale === "zh-CN" ? "启用" : "Enable"}
        </Button>
        <Button
          type="button"
          size="xs"
          variant="outline"
          disabled={Boolean(busyId)}
          onClick={() => {
            void onBulkEnabled(selectedSites, false);
            selection.clear();
          }}
        >
          {locale === "zh-CN" ? "停用" : "Disable"}
        </Button>
        <Button
          type="button"
          size="xs"
          variant="destructive"
          disabled={Boolean(busyId)}
          onClick={() => setBulkDeleteOpen(true)}
        >
          {locale === "zh-CN" ? "删除选中" : "Delete"}
        </Button>
      </SelectionActionBar>

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
        onToggleEnabled={onToggleSiteEnabled}
        onDelete={onDelete}
      />

      <TablePagination locale={locale} {...paginationProps} />

      <ConfirmDeleteDialog
        open={bulkDeleteOpen}
        locale={locale}
        title={locale === "zh-CN" ? "删除渠道" : "Delete channels"}
        description={
          locale === "zh-CN"
            ? `删除 ${selectedSites.length} 个渠道及其协议配置、模型和成员。`
            : `Delete ${selectedSites.length} channels and their configs, models, and members.`
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
