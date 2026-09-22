import {
  ArrowDownUp,
  Check,
  FileInput,
  Funnel,
  ListChecks,
  Plus,
  RefreshCw,
  Search,
  ToggleLeft,
  Trash2,
} from "lucide-react";
import { useMemo, useState } from "react";
import { Button } from "@/components/ui/Button";
import { AppDialogContent, Dialog } from "@/components/ui/Dialog";
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
import type { Site } from "@/lib/api/sites";
import { cn } from "@/lib/classNames";
import { ChannelsTable } from "./ChannelsTable";
import type {
  ChannelSort,
  ChannelStatusFilter,
  Locale,
  SiteRow,
} from "./channelTypes";

const PAGE_SIZE_OPTIONS = [25, 50, 100] as const;

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
  onSyncRemoteModels: (site: Site) => void;
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
  onSyncRemoteModels,
  onToggleSiteEnabled,
  onDelete,
  onBulkEnabled,
  onBulkDelete,
}: Props) {
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [bulkEnabled, setBulkEnabled] = useState<"enabled" | "disabled" | "">(
    "",
  );
  const [bulkDeleteOpen, setBulkDeleteOpen] = useState(false);
  const pageCount = Math.max(1, Math.ceil(visibleSites.length / pageSize));
  const safePage = Math.min(page, pageCount);
  const pagedSites = useMemo(
    () => visibleSites.slice((safePage - 1) * pageSize, safePage * pageSize),
    [pageSize, safePage, visibleSites],
  );
  const selectedSites = visibleSites.filter((site) => selected.has(site.id));
  const sortOptions: Array<{ value: ChannelSort; label: string }> = [
    {
      value: "name-asc",
      label: locale === "zh-CN" ? "名称升序" : "Name A-Z",
    },
    {
      value: "name-desc",
      label: locale === "zh-CN" ? "名称降序" : "Name Z-A",
    },
    {
      value: "models-desc",
      label: locale === "zh-CN" ? "模型优先" : "Models first",
    },
  ];

  function handleSelectAll(checked: boolean) {
    setSelected((current) => {
      const next = new Set(current);
      for (const site of pagedSites) {
        if (checked) next.add(site.id);
        else next.delete(site.id);
      }
      return next;
    });
  }

  function handleSelectOne(id: string, checked: boolean) {
    setSelected((current) => {
      const next = new Set(current);
      if (checked) next.add(id);
      else next.delete(id);
      return next;
    });
  }

  function handlePageSizeChange(size: number) {
    setPageSize(size);
    setPage(1);
  }

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
                setPage(1);
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
                      setPage(1);
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
                        setPage(1);
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
                        setPage(1);
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

          <Popover>
            <PopoverTrigger asChild>
              <ToolbarButton
                disabled={selectedSites.length === 0 || Boolean(busyId)}
                aria-label={locale === "zh-CN" ? "批量" : "Bulk"}
              >
                <ListChecks className="size-3.5" />
                <span className="hidden sm:inline">
                  {locale === "zh-CN" ? "批量" : "Bulk"}
                </span>
              </ToolbarButton>
            </PopoverTrigger>
            <PopoverContent align="start" className="w-[240px] p-2">
              <p className="flex h-7 items-center px-2 text-[11px] text-muted-foreground">
                {locale === "zh-CN"
                  ? `已选 ${selectedSites.length} 项`
                  : `${selectedSites.length} selected`}
              </p>
              <div className="flex h-7 w-full items-center gap-1.5">
                <Button
                  type="button"
                  variant="ghost"
                  className="h-7 w-16 shrink-0 justify-start gap-2 px-2 text-[11px] text-foreground/70 shadow-none hover:bg-muted"
                  disabled={!bulkEnabled || Boolean(busyId)}
                  onClick={() => {
                    void onBulkEnabled(
                      selectedSites,
                      bulkEnabled === "enabled",
                    );
                    setSelected(new Set());
                  }}
                >
                  <ToggleLeft className="size-3" />
                  {locale === "zh-CN" ? "应用" : "Apply"}
                </Button>
                <Select
                  value={bulkEnabled || undefined}
                  onValueChange={(value) =>
                    setBulkEnabled(value as "enabled" | "disabled")
                  }
                >
                  <SelectTrigger className="h-7 px-2 text-[11px] text-muted-foreground">
                    <SelectValue
                      placeholder={locale === "zh-CN" ? "状态" : "Status"}
                    />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="enabled">
                      {locale === "zh-CN" ? "启用" : "Enable"}
                    </SelectItem>
                    <SelectItem value="disabled">
                      {locale === "zh-CN" ? "停用" : "Disable"}
                    </SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <button
                type="button"
                disabled={Boolean(busyId)}
                onClick={() => setBulkDeleteOpen(true)}
                className="mt-1 flex h-7 w-full items-center gap-2 rounded-md px-2 text-left text-[11px] text-foreground/70 hover:bg-muted hover:text-foreground disabled:opacity-50"
              >
                <Trash2 className="size-3.5" />
                {locale === "zh-CN" ? "批量删除" : "Delete selected"}
              </button>
            </PopoverContent>
          </Popover>
        </div>

        <div className="ml-auto flex min-h-8 shrink-0 items-center gap-1">
          <ToolbarButton
            onClick={onRefresh}
            disabled={isLoading}
            aria-label={locale === "zh-CN" ? "刷新" : "Refresh"}
            title={locale === "zh-CN" ? "刷新" : "Refresh"}
          >
            <RefreshCw
              className={cn("size-3.5", isLoading && "animate-spin")}
            />
          </ToolbarButton>
          <ToolbarButton
            onClick={onImport}
            aria-label={locale === "zh-CN" ? "批量导入" : "Import"}
            title={locale === "zh-CN" ? "批量导入" : "Import"}
          >
            <FileInput className="size-3.5" />
          </ToolbarButton>
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
        selected={selected}
        busyId={busyId}
        onSelectAll={handleSelectAll}
        onSelectOne={handleSelectOne}
        onEdit={onOpenEdit}
        onManageModels={onManageModels}
        onSyncModels={onSyncRemoteModels}
        onToggleEnabled={onToggleSiteEnabled}
        onDelete={onDelete}
      />

      <TablePagination
        locale={locale}
        total={visibleSites.length}
        page={safePage}
        pageCount={pageCount}
        pageSize={pageSize}
        pageSizeOptions={PAGE_SIZE_OPTIONS}
        onPageChange={setPage}
        onPageSizeChange={handlePageSizeChange}
      />

      <Dialog open={bulkDeleteOpen} onOpenChange={setBulkDeleteOpen}>
        <AppDialogContent
          className="max-w-lg"
          showCloseButton={false}
          title={locale === "zh-CN" ? "确认批量删除" : "Delete channels"}
          description={
            locale === "zh-CN"
              ? `将删除选中的 ${selectedSites.length} 个渠道，其协议配置、模型和模型组成员会一起移除。`
              : `${selectedSites.length} selected channels will be removed together with their protocol configs, models, and group members.`
          }
          footer={
            <>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => setBulkDeleteOpen(false)}
              >
                {locale === "zh-CN" ? "取消" : "Cancel"}
              </Button>
              <Button
                type="button"
                variant="destructive"
                size="sm"
                disabled={Boolean(busyId)}
                onClick={() => {
                  void onBulkDelete(selectedSites);
                  setSelected(new Set());
                  setBulkDeleteOpen(false);
                }}
              >
                {locale === "zh-CN" ? "确认删除" : "Delete"}
              </Button>
            </>
          }
        />
      </Dialog>
    </div>
  );
}
